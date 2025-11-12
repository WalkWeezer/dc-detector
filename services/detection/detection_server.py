#!/usr/bin/env python3
"""Detection Service - рефакторированный сервис детекции огня"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
import requests
from flask import Flask, Response, jsonify, request

from tracking.sort_tracker import SortTracker

# Импорты модулей
from camera.capture import open_capture, Picamera2Wrapper, PICAMERA2_AVAILABLE
from camera.servos import ServoController
from detection.inference import InferenceEngine
from models.manager import ModelManager
from streaming.generators import mjpeg_generator_raw, mjpeg_generator_detections
from tracking.trackers import (
    get_active_trackers, get_tracker_by_id, crop_frame_for_tracker,
    get_tracker_frames, update_tracker_cache
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Конфигурация из переменных окружения
DEFAULT_CAMERA_INDEX = int(os.getenv('CAMERA_INDEX', '0'))
CAMERA_SCAN_LIMIT = int(os.getenv('CAMERA_SCAN_LIMIT', '5'))
CAPTURE_RETRY_DELAY = float(os.getenv('CAPTURE_RETRY_DELAY', '1.0'))
LOCAL_CAMERA_ENABLED = str(os.getenv('LOCAL_CAMERA_ENABLED', '1')).lower() in {'1', 'true', 'yes', 'on'}

STREAM_MAX_FPS = float(os.getenv('STREAM_MAX_FPS', '60'))
INFER_FPS = float(os.getenv('INFER_FPS', '50'))
INFER_IMGSZ = int(os.getenv('INFER_IMGSZ', '416'))

MODELS_DIR = Path(os.getenv('MODELS_DIR', 'models'))
MODEL_PATH = os.getenv('MODEL_PATH', 'models/bestfire.pt')
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.5'))
JPEG_QUALITY = int(os.getenv('JPEG_QUALITY', '80'))

TRACKER_IOU_THRESHOLD = float(os.getenv('TRACKER_IOU_THRESHOLD', '0.3'))
TRACKER_MAX_AGE = int(os.getenv('TRACKER_MAX_AGE', '5'))
TRACKER_MIN_HITS = int(os.getenv('TRACKER_MIN_HITS', '1'))

BACKEND_NOTIFY_URL = os.getenv('BACKEND_NOTIFY_URL')
BACKEND_NOTIFY_TIMEOUT = float(os.getenv('BACKEND_NOTIFY_TIMEOUT', '1.0'))
NOTIFY_MIN_INTERVAL = float(os.getenv('BACKEND_NOTIFY_INTERVAL', '1.0'))

_notify_lock = threading.Lock()
_last_notification_ts = 0.0

# Глобальное состояние
detection_results = {
    'local_camera_enabled': LOCAL_CAMERA_ENABLED,
    'active_camera': DEFAULT_CAMERA_INDEX if LOCAL_CAMERA_ENABLED else None,
    'available_cameras': [],
    'active_model': None,
    'available_models': [],
    'detected': False,
    'count': 0,
    'confidence': 0.0,
    'last_detection': None,
    'detections': [],
    'trackIds': [],
    'frame_with_detections': None,
    'frame_raw': None,
    'stable_detections': []
}


def encode_frame_to_jpeg(frame: np.ndarray) -> Optional[bytes]:
    """Кодирует кадр в JPEG"""
    try:
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, max(30, min(95, JPEG_QUALITY))])
        if success:
            return buffer.tobytes()
    except Exception as exc:
        logger.error('Не удалось кодировать кадр в JPEG: %s', exc)
    return None


class DetectionService:
    """Основной сервис детекции"""
    
    def __init__(self, model_path: str):
        self.base_dir = Path(__file__).resolve().parent
        
        self.running = False
        self.capture_running = False
        self.capture_thread: Optional[threading.Thread] = None
        self.infer_running = False
        self.infer_thread: Optional[threading.Thread] = None
        self.latest_frame_lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self._last_raw_push_ts: float = 0.0
        self._last_infer_ts: float = 0.0
        
        self.camera_scan_limit = CAMERA_SCAN_LIMIT
        self.capture_retry_delay = CAPTURE_RETRY_DELAY
        self._camera_lock = threading.Lock()
        self._available_cameras: List[int] = []
        self.camera_index = DEFAULT_CAMERA_INDEX
        
        # Модели
        models_dir = MODELS_DIR
        if not models_dir.is_absolute():
            models_dir = (self.base_dir / models_dir).resolve()
        
        self._model_lock = threading.Lock()
        self.model_manager = ModelManager(models_dir, self.base_dir)
        self.model_manager.set_lock(self._model_lock)
        self.model_manager.load_model(model_path)
        
        # Трекер
        self._tracker_lock = threading.Lock()
        self.tracker = SortTracker(
            iou_threshold=TRACKER_IOU_THRESHOLD,
            max_age=TRACKER_MAX_AGE,
            min_hits=TRACKER_MIN_HITS
        )
        
        # Инференс
        self.inference_engine = InferenceEngine(self.model_manager, self.tracker, self._tracker_lock)
        
        # Сервы (задел)
        self.servo_controller = ServoController()
        
        # Обновляем состояние
        detection_results['active_model'] = self.model_manager.get_active_model()
        detection_results['available_models'] = self.model_manager.get_available_models()
        
        if not LOCAL_CAMERA_ENABLED:
            logger.info('🛑 Локальная камера отключена (LOCAL_CAMERA_ENABLED=0)')
            detection_results.update({
                'local_camera_enabled': False,
                'active_camera': None,
                'available_cameras': []
            })
            return
        
        self.scan_cameras(force=True)
    
    def start(self):
        """Запускает потоки захвата и инференса"""
        if not LOCAL_CAMERA_ENABLED:
            logger.debug('Local camera disabled; start() вызван, но захват не инициирован')
            return
        
        if self.capture_running and self.infer_running:
            return
        
        if not self.capture_running:
            self.capture_running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
        
        if not self.infer_running:
            self.infer_running = True
            self.infer_thread = threading.Thread(target=self._inference_loop, daemon=True)
            self.infer_thread.start()
    
    def stop(self):
        """Останавливает потоки"""
        self.running = False
        self.capture_running = False
        self.infer_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.infer_thread:
            self.infer_thread.join(timeout=2)
    
    def scan_cameras(self, *, force: bool = False) -> List[int]:
        """Сканирует доступные камеры"""
        if not LOCAL_CAMERA_ENABLED:
            detection_results.update({
                'local_camera_enabled': False,
                'available_cameras': [],
                'active_camera': None
            })
            return []
        
        with self._camera_lock:
            if self._available_cameras and not force:
                return list(self._available_cameras)
            
            cameras: List[int] = []
            for index in range(self.camera_scan_limit + 1):
                cap = cv2.VideoCapture(index)
                if cap is not None and cap.isOpened():
                    if index not in cameras:
                        cameras.append(index)
                    cap.release()
                else:
                    if cap is not None:
                        cap.release()
                    if index == self.camera_index and index not in cameras:
                        cameras.append(index)
            
            if cameras:
                if self.camera_index not in cameras:
                    self.camera_index = cameras[0]
            detection_results['active_camera'] = self.camera_index
            detection_results['available_cameras'] = cameras
            
            self._available_cameras = cameras
            return list(cameras)
    
    def get_camera_index(self) -> Optional[int]:
        """Получает индекс активной камеры"""
        if not LOCAL_CAMERA_ENABLED:
            return None
        with self._camera_lock:
            return self.camera_index
    
    def set_camera(self, index: int) -> int:
        """Устанавливает активную камеру"""
        if not LOCAL_CAMERA_ENABLED:
            raise ValueError('Локальный захват камеры отключен')
        index = int(index)
        if index < 0:
            raise ValueError('Camera index must be non-negative')
        
        with self._camera_lock:
            self.camera_index = index
            detection_results['active_camera'] = index
            if index not in self._available_cameras:
                self._available_cameras.append(index)
                self._available_cameras.sort()
            detection_results['available_cameras'] = list(self._available_cameras)
        return index
    
    def _capture_loop(self):
        """Цикл захвата кадров"""
        current_index: Optional[int] = None
        cap = None
        min_interval = 1.0 / max(1.0, STREAM_MAX_FPS)
        is_picamera2 = False
        
        while self.capture_running:
            try:
                desired_index = self.get_camera_index()
                if desired_index != current_index or cap is None or not cap.isOpened():
                    if cap is not None:
                        cap.release()
                    cap = open_capture(desired_index, scan_cameras_callback=self.scan_cameras)
                    if cap is None:
                        current_index = None
                        is_picamera2 = False
                        time.sleep(self.capture_retry_delay)
                        continue
                    current_index = desired_index
                    is_picamera2 = isinstance(cap, Picamera2Wrapper)
                
                now = time.time()
                
                # Оптимизация для Picamera2: используем capture_jpeg() для стриминга
                if is_picamera2 and now - self._last_raw_push_ts >= min_interval:
                    raw_jpeg = cap.capture_jpeg()
                    if raw_jpeg is not None:
                        detection_results['frame_raw'] = raw_jpeg
                        self._last_raw_push_ts = now
                        # Также сохраняем кадр для инференса (декодируем)
                        frame = cv2.imdecode(np.frombuffer(raw_jpeg, np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            with self.latest_frame_lock:
                                self.latest_frame = frame
                    else:
                        time.sleep(0.01)
                    continue
                
                # Для других камер используем стандартный метод
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.01)
                    continue
                
                with self.latest_frame_lock:
                    self.latest_frame = frame.copy()
                
                if now - self._last_raw_push_ts >= min_interval:
                    raw_jpeg = encode_frame_to_jpeg(frame)
                    if raw_jpeg is not None:
                        detection_results['frame_raw'] = raw_jpeg
                        self._last_raw_push_ts = now
            except Exception as exc:
                logger.error('Ошибка в цикле захвата: %s', exc)
                time.sleep(0.2)
        
        if cap is not None:
            cap.release()
    
    def _inference_loop(self):
        """Цикл инференса"""
        min_interval = 1.0 / max(0.1, INFER_FPS)
        
        while self.infer_running:
            try:
                now = time.time()
                if (now - self._last_infer_ts) < min_interval:
                    time.sleep(0.005)
                    continue
                
                with self.latest_frame_lock:
                    frame = None if self.latest_frame is None else self.latest_frame.copy()
                
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                self._last_infer_ts = now
                self.analyze_frame(frame)
            except Exception as exc:
                logger.error('Ошибка в цикле инференса: %s', exc)
                time.sleep(0.2)
    
    def analyze_frame(self, frame: np.ndarray, *, update_state: bool = True, notify: bool = True):
        """Анализирует кадр"""
        timestamp = time.time()
        detections, annotated, stable_tracks = self.inference_engine.infer(frame, timestamp)
        confidence = max((d['confidence'] for d in detections), default=0.0)
        jpeg_bytes = encode_frame_to_jpeg(annotated)
        raw_jpeg = encode_frame_to_jpeg(frame)
        
        # Обновляем кэш трекеров
        for det in detections:
            track_id = det.get('trackId')
            if track_id is not None:
                bbox = det.get('bbox', [])
                if bbox:
                    update_tracker_cache(track_id, frame, bbox, {
                        'trackId': track_id,
                        'confidence': det.get('confidence', 0.0),
                        'label': det.get('label', 'object'),
                        'timestamp': timestamp
                    })
        
        if update_state:
            detection_results.update({
                'active_camera': self.get_camera_index(),
                'active_model': self.model_manager.get_active_model(),
                'detected': bool(detections),
                'count': len(detections),
                'confidence': confidence,
                'last_detection': timestamp,
                'detections': detections,
                'trackIds': [d['trackId'] for d in detections],
                'frame_with_detections': jpeg_bytes,
                'frame_raw': raw_jpeg,
                'stable_detections': stable_tracks
            })
        
        if notify and detections:
            self._schedule_notification(detections, confidence, timestamp)
        
        return {
            'cameraIndex': self.get_camera_index(),
            'detected': bool(detections),
            'confidence': confidence,
            'detections': detections,
            'capturedAt': timestamp,
            'model': self.model_manager.get_active_model()
        }
    
    def _schedule_notification(self, detections: List[dict], confidence: float, captured_at: float):
        """Планирует уведомление бэкенда"""
        if not detections or not BACKEND_NOTIFY_URL:
            return
        
        now = time.time()
        global _last_notification_ts
        with _notify_lock:
            if now - _last_notification_ts < NOTIFY_MIN_INTERVAL:
                return
            _last_notification_ts = now
        
        payload = {
            'detected': True,
            'confidence': confidence,
            'detections': detections,
            'capturedAt': captured_at,
            'model': self.model_manager.get_active_model(),
            'cameraIndex': self.get_camera_index()
        }
        
        threading.Thread(target=self._post_detection, args=(payload,), daemon=True).start()
    
    def _post_detection(self, payload):
        """Отправляет уведомление бэкенду"""
        try:
            response = requests.post(
                BACKEND_NOTIFY_URL,
                json=payload,
                timeout=BACKEND_NOTIFY_TIMEOUT
            )
            if response.status_code >= 400:
                logger.warning('Backend notify failed: %s %s', response.status_code, response.text)
        except Exception as exc:
            logger.debug('Unable to notify backend: %s', exc)


# Инициализация сервиса
detection_service = DetectionService(MODEL_PATH)


# Эндпоинты Flask

@app.get('/video_feed_raw')
def video_feed_raw():
    """Сырой MJPEG поток (использует рабочий скрипт)"""
    from camera.capture import capture_frame_jpeg, picam2
    
    def mjpeg_generator():
        """Генератор MJPEG потока (как в рабочем скрипте)"""
        boundary = b'--frame'
        while True:
            if picam2 is not None:
                frame = capture_frame_jpeg()
                if frame is not None:
                    yield (
                        boundary + b"\r\n"
                        + b'Content-Type: image/jpeg\r\n'
                        + b'Content-Length: ' + str(len(frame)).encode() + b"\r\n\r\n"
                        + frame + b"\r\n"
                    )
                    time.sleep(0.033)  # ~30 FPS как в рабочем скрипте
                else:
                    time.sleep(0.1)
            else:
                # Fallback на старый метод
                frame = detection_results.get('frame_raw')
                if frame is not None:
                    yield (
                        boundary + b"\r\n"
                        + b'Content-Type: image/jpeg\r\n'
                        + b'Content-Length: ' + str(len(frame)).encode() + b"\r\n\r\n"
                        + frame + b"\r\n"
                    )
                time.sleep(0.01)
    
    response = Response(
        mjpeg_generator(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    return response


@app.get('/video_feed')
def video_feed():
    """MJPEG поток с детекциями"""
    def get_frame():
        return detection_results.get('frame_with_detections')
    
    response = Response(
        mjpeg_generator_detections(get_frame, interval=0.1),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    return response


@app.get('/api/trackers')
def get_trackers():
    """Получает список активных трекеров"""
    try:
        with detection_service._tracker_lock:
            trackers = get_active_trackers(detection_service.tracker)
        return jsonify({'trackers': trackers})
    except Exception as exc:
        logger.error('Ошибка при получении трекеров: %s', exc)
        return jsonify({'error': 'Unable to get trackers', 'details': str(exc)}), 500


@app.get('/api/trackers/<int:track_id>/crop')
def get_tracker_crop(track_id: int):
    """Получает кропнутый кадр для трекера"""
    try:
        with detection_service._tracker_lock:
            tracker = get_tracker_by_id(track_id, detection_service.tracker)
        
        if tracker is None:
            return Response('Tracker not found', status=404)
        
        bbox = tracker.get('bbox')
        if not bbox:
            return Response('No bbox for tracker', status=404)
        
        with detection_service.latest_frame_lock:
            frame = detection_service.latest_frame
        
        if frame is None:
            return Response('No frame available', status=404)
        
        cropped = crop_frame_for_tracker(frame, bbox)
        if cropped is None:
            return Response('Unable to crop frame', status=500)
        
        return Response(cropped, mimetype='image/jpeg')
    except Exception as exc:
        logger.error('Ошибка при получении кропа трекера: %s', exc)
        return Response('Error', status=500)


@app.get('/api/trackers/<int:track_id>/frames')
def get_tracker_frames_endpoint(track_id: int):
    """Получает последовательность кропнутых кадров для трекера"""
    try:
        frames = get_tracker_frames(track_id)
        return jsonify({
            'trackId': track_id,
            'frames': frames,
            'count': len(frames)
        })
    except Exception as exc:
        logger.error('Ошибка при получении кадров трекера: %s', exc)
        return jsonify({'error': 'Unable to get tracker frames', 'details': str(exc)}), 500


@app.get('/models')
def models():
    """Получает список моделей"""
    models_list = detection_service.model_manager.refresh_available_models()
    return jsonify({
        'models': models_list,
        'active': detection_service.model_manager.get_active_model()
    })


@app.post('/models')
def set_model():
    """Переключает модель"""
    payload = request.get_json(silent=True) or {}
    model_name = payload.get('name') or payload.get('model')
    if not model_name:
        return jsonify({'error': 'name is required'}), 400
    
    try:
        active = detection_service.model_manager.switch_model(model_name)
        detection_results['active_model'] = active
        detection_results['available_models'] = detection_service.model_manager.get_available_models()
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:
        logger.error('Не удалось переключить модель: %s', exc)
        return jsonify({'error': 'Unable to switch model', 'details': str(exc)}), 500
    
    return jsonify({
        'active': active,
        'models': detection_service.model_manager.get_available_models()
    })


@app.get('/cameras')
def cameras():
    """Получает список камер"""
    cameras_list = detection_service.scan_cameras(force=True)
    return jsonify({
        'available': cameras_list,
        'active': detection_service.get_camera_index(),
        'localCameraEnabled': LOCAL_CAMERA_ENABLED
    })


@app.patch('/cameras/<int:index>')
def set_camera(index: int):
    """Переключает камеру"""
    try:
        active = detection_service.set_camera(index)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    cameras_list = detection_service.scan_cameras(force=True)
    return jsonify({
        'active': active,
        'available': cameras_list,
        'localCameraEnabled': LOCAL_CAMERA_ENABLED
    })


@app.get('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'running': detection_service.running,
        'activeCamera': detection_service.get_camera_index(),
        'availableCameras': detection_results.get('available_cameras', []),
        'localCameraEnabled': detection_results.get('local_camera_enabled', True),
        'activeModel': detection_results.get('active_model'),
        'availableModels': detection_results.get('available_models', [])
    })


def main():
    """Главная функция"""
    from camera.capture import init_picamera2, stop_picamera2
    
    debug_enabled = str(os.environ.get('DEBUG', '0')).lower() in ('1', 'true', 'yes')
    try:
        # Инициализируем Picamera2 (рабочий скрипт)
        if PICAMERA2_AVAILABLE and LOCAL_CAMERA_ENABLED:
            init_picamera2()
        
        if LOCAL_CAMERA_ENABLED:
            if debug_enabled:
                if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
                    detection_service.start()
            else:
                detection_service.start()
        else:
            logger.info('Фоновый цикл локальной камеры не запускается (LOCAL_CAMERA_ENABLED=0)')
        app.run(host='0.0.0.0', port=8001, debug=debug_enabled, threaded=True)
    finally:
        detection_service.stop()
        stop_picamera2()


if __name__ == '__main__':
    main()
