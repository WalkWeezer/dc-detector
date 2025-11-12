#!/usr/bin/env python3
"""Detection Service - перенесённый сервис детекции огня"""

import base64
import glob
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import requests
from flask import Flask, Response, jsonify, request
from ultralytics import YOLO

from tracking.sort_tracker import SortTracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

DEFAULT_CAMERA_INDEX = int(os.getenv('CAMERA_INDEX', '0'))
CAMERA_SCAN_LIMIT = int(os.getenv('CAMERA_SCAN_LIMIT', '5'))
CAPTURE_RETRY_DELAY = float(os.getenv('CAPTURE_RETRY_DELAY', '1.0'))
LOCAL_CAMERA_ENABLED = str(os.getenv('LOCAL_CAMERA_ENABLED', '1')).lower() in {'1', 'true', 'yes', 'on'}
# Performance tuning
STREAM_MAX_FPS = float(os.getenv('STREAM_MAX_FPS', '60'))  # частота обновления RAW потока (fps)
INFER_FPS = float(os.getenv('INFER_FPS', '50'))            # частота инференса (fps)
INFER_IMGSZ = int(os.getenv('INFER_IMGSZ', '416'))        # размер imgsz для YOLO (кратно 32 обычно)
# Backend для OpenCV: V4L2 лучше работает с Pi Camera, но можно использовать AUTO для автоматического выбора
CAMERA_BACKEND = os.getenv('CAMERA_BACKEND', 'V4L2').upper()  # AUTO, V4L2, GSTREAMER, etc.

MODELS_DIR = Path(os.getenv('MODELS_DIR', 'models'))
MODEL_PATH = os.getenv('MODEL_PATH', 'models/bestfire.pt')
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.5'))
JPEG_QUALITY = int(os.getenv('JPEG_QUALITY', '80'))

# Tracker parameters from environment or defaults
TRACKER_IOU_THRESHOLD = float(os.getenv('TRACKER_IOU_THRESHOLD', '0.3'))
TRACKER_MAX_AGE = int(os.getenv('TRACKER_MAX_AGE', '5'))
TRACKER_MIN_HITS = int(os.getenv('TRACKER_MIN_HITS', '1'))

BACKEND_NOTIFY_URL = os.getenv('BACKEND_NOTIFY_URL')
BACKEND_NOTIFY_TIMEOUT = float(os.getenv('BACKEND_NOTIFY_TIMEOUT', '1.0'))
NOTIFY_MIN_INTERVAL = float(os.getenv('BACKEND_NOTIFY_INTERVAL', '1.0'))

_notify_lock = threading.Lock()
_last_notification_ts = 0.0

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

# Буферы для потока с фронтенда
_frontend_frame_lock = threading.Lock()
_frontend_frame_raw: Optional[bytes] = None
_frontend_frame_queue: queue.Queue = queue.Queue(maxsize=2)  # Ограничиваем очередь для избежания задержек
_frontend_infer_running = False
_frontend_infer_thread: Optional[threading.Thread] = None


def encode_frame_to_jpeg(frame: np.ndarray) -> Optional[bytes]:
    try:
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, max(30, min(95, JPEG_QUALITY))])
        if success:
            return buffer.tobytes()
    except Exception as exc:  # pragma: no cover
        logger.error('Не удалось кодировать кадр в JPEG: %s', exc)
    return None


class DetectionService:
    def __init__(self, model_path: str):
        self.base_dir = Path(__file__).resolve().parent

        self.running = False
        self.thread: Optional[threading.Thread] = None  # legacy

        # Разделение захвата и инференса
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

        self.models_dir = MODELS_DIR
        if not self.models_dir.is_absolute():
            self.models_dir = (self.base_dir / self.models_dir).resolve()

        self._model_lock = threading.Lock()
        self.model: Optional[YOLO] = None
        self.model_path: Optional[Path] = None
        self.model_name: Optional[str] = None
        self._available_models: List[str] = []

        self.refresh_available_models()
        self._load_model(model_path)
        self._tracker_lock = threading.Lock()
        self.tracker = SortTracker(
            iou_threshold=TRACKER_IOU_THRESHOLD,
            max_age=TRACKER_MAX_AGE,
            min_hits=TRACKER_MIN_HITS
        )

        if not LOCAL_CAMERA_ENABLED:
            logger.info('🛑 Локальная камера отключена (LOCAL_CAMERA_ENABLED=0). Фоновый захват запускаться не будет.')
            detection_results.update({
                'local_camera_enabled': False,
                'active_camera': None,
                'available_cameras': []
            })
            return

        self.scan_cameras(force=True)

    def refresh_available_models(self) -> List[str]:
        try:
            self.models_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover
            logger.warning('Не удалось создать каталог моделей %s: %s', self.models_dir, exc)

        models = sorted({Path(path).name for path in glob.glob(str(self.models_dir / '*.pt'))})
        self._available_models = models
        detection_results['available_models'] = list(models)
        return models

    def _resolve_model_path(self, model_path: str) -> Optional[Path]:
        candidate = Path(model_path)
        search_paths = []

        if candidate.is_absolute():
            search_paths.append(candidate)
        else:
            search_paths.extend([
                self.models_dir / candidate.name,
                self.models_dir / candidate,
                self.base_dir / candidate,
            ])

        for path in search_paths:
            try:
                resolved = path.resolve(strict=True)
            except FileNotFoundError:
                continue
            if resolved.is_file():
                return resolved
        return None

    def _load_model(self, model_path: str):
        resolved = self._resolve_model_path(model_path)
        if resolved is None:
            raise FileNotFoundError(f'Не удалось найти модель: {model_path}')

        logger.info('🔍 Загрузка модели YOLO: %s', resolved)
        model = YOLO(str(resolved))
        with self._model_lock:
            self.model = model
            self.model_path = resolved
            self.model_name = resolved.name

        available = self.refresh_available_models()
        if self.model_name not in available:
            available.append(self.model_name)
            available.sort()
            self._available_models = available
            detection_results['available_models'] = list(available)

        detection_results['active_model'] = self.model_name

    def get_available_models(self) -> List[str]:
        return list(self._available_models)

    def get_active_model(self) -> Optional[str]:
        return self.model_name

    def get_models_info(self) -> dict:
        return {
            'active': self.get_active_model(),
            'models': self.get_available_models()
        }

    def set_model(self, model_name: str) -> str:
        resolved = self._resolve_model_path(model_name)
        if resolved is None:
            raise FileNotFoundError(f'Не найдена модель "{model_name}"')

        if self.model_name == resolved.name:
            logger.info('Модель %s уже активна, повторная загрузка не требуется', resolved.name)
            detection_results['active_model'] = self.model_name
            return self.model_name

        self._load_model(str(resolved))
        logger.info('✅ Активная модель переключена на %s', resolved.name)
        return self.model_name

    def update_tracker_config(self, iou_threshold: Optional[float] = None, 
                              max_age: Optional[int] = None, 
                              min_hits: Optional[int] = None):
        """Обновить параметры трекера на лету"""
        with self._tracker_lock:
            iou = iou_threshold if iou_threshold is not None else self.tracker.iou_threshold
            max_a = max_age if max_age is not None else self.tracker.max_age
            min_h = min_hits if min_hits is not None else self.tracker.min_hits
            
            self.tracker = SortTracker(iou_threshold=iou, max_age=max_a, min_hits=min_h)
            logger.info('✅ Параметры трекера обновлены: iou=%.2f, max_age=%d, min_hits=%d', iou, max_a, min_h)

    def get_tracker_config(self) -> dict:
        """Получить текущие параметры трекера"""
        with self._tracker_lock:
            return {
                'iou_threshold': self.tracker.iou_threshold,
                'max_age': self.tracker.max_age,
                'min_hits': self.tracker.min_hits
            }

    def start(self):
        if not LOCAL_CAMERA_ENABLED:
            logger.debug('Local camera disabled; start() вызван, но захват не инициирован')
            return

        if self.capture_running and self.infer_running:
            return

        # Стартуем поток захвата
        if not self.capture_running:
            self.capture_running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()

        # Стартуем поток инференса
        if not self.infer_running:
            self.infer_running = True
            self.infer_thread = threading.Thread(target=self._inference_loop, daemon=True)
            self.infer_thread.start()

    def stop(self):
        self.running = False
        self.capture_running = False
        self.infer_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.infer_thread:
            self.infer_thread.join(timeout=2)

    def scan_cameras(self, *, force: bool = False) -> List[int]:
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
        if not LOCAL_CAMERA_ENABLED:
            return None
        with self._camera_lock:
            return self.camera_index

    def set_camera(self, index: int) -> int:
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
        current_index: Optional[int] = None
        cap: Optional[cv2.VideoCapture] = None
        min_interval = 1.0 / max(1.0, STREAM_MAX_FPS)
        while self.capture_running:
            try:
                desired_index = self.get_camera_index()
                if desired_index != current_index or cap is None or not cap.isOpened():
                    if cap is not None:
                        cap.release()
                    cap = self._open_capture(desired_index)
                    if cap is None:
                        current_index = None
                        time.sleep(self.capture_retry_delay)
                        continue
                    current_index = desired_index

                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.01)
                    continue

                now = time.time()
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

                # При необходимости изменить размер для инференса, но сохраняем исходный кадр для отображения
                self._last_infer_ts = now
                self.analyze_frame(frame)
            except Exception as exc:
                logger.error('Ошибка в цикле инференса: %s', exc)
                time.sleep(0.2)

    def _open_capture(self, index: int) -> Optional[cv2.VideoCapture]:
        if index < 0:
            logger.error('Индекс камеры должен быть неотрицательным, получено %s', index)
            return None

        logger.info('🎥 Подключение к локальной камере %s (backend: %s)', index, CAMERA_BACKEND)
        
        # Определяем backend для OpenCV
        backend = None
        if CAMERA_BACKEND == 'V4L2':
            backend = cv2.CAP_V4L2
        elif CAMERA_BACKEND == 'GSTREAMER':
            backend = cv2.CAP_GSTREAMER
        elif CAMERA_BACKEND == 'AUTO':
            backend = None  # OpenCV выберет автоматически
        else:
            # Попытка использовать числовой код backend
            try:
                backend = int(CAMERA_BACKEND) if CAMERA_BACKEND.isdigit() else None
            except (ValueError, AttributeError):
                backend = None
        
        # Попытка открыть камеру с указанным backend
        if backend is not None:
            cap = cv2.VideoCapture(index, backend)
        else:
            cap = cv2.VideoCapture(index)
        
        if not cap or not cap.isOpened():
            if cap is not None:
                cap.release()
            logger.error('Не удалось открыть локальную камеру: %s (backend: %s)', index, CAMERA_BACKEND)
            
            # Если использовался не AUTO backend, попробуем AUTO
            if CAMERA_BACKEND != 'AUTO':
                logger.info('Попытка открыть камеру с AUTO backend')
                cap = cv2.VideoCapture(index)
                if cap and cap.isOpened():
                    logger.info('✅ Камера открыта с AUTO backend')
                else:
                    if cap is not None:
                        cap.release()
                    self.scan_cameras(force=True)
                    return None
            else:
                self.scan_cameras(force=True)
                return None
        
        # ВАЖНО: Даем время на инициализацию камеры перед настройкой параметров
        # PiCamera2 может требовать больше времени для инициализации
        time.sleep(0.5)
        
        # Настройка параметров камеры для лучшей производительности
        # Для PiCamera2 важно установить параметры ПОСЛЕ небольшой задержки
        try:
            # Буферизация: 1 кадр (для минимальной задержки) - устанавливаем первым
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Для V4L2 (PiCamera2) пробуем разные форматы пикселей
            if backend == cv2.CAP_V4L2:
                # Список форматов для попытки (в порядке приоритета)
                formats_to_try = [
                    ('YUYV', cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V')),
                    ('RGB3', cv2.VideoWriter_fourcc('R', 'G', 'B', '3')),
                    ('BGR3', cv2.VideoWriter_fourcc('B', 'G', 'R', '3')),
                ]
                
                format_set = False
                for fmt_name, fmt_code in formats_to_try:
                    try:
                        if cap.set(cv2.CAP_PROP_FOURCC, fmt_code):
                            logger.debug('Попытка установить формат %s для V4L2', fmt_name)
                            # Проверяем, что формат действительно установлен
                            actual_fourcc = cap.get(cv2.CAP_PROP_FOURCC)
                            if actual_fourcc == fmt_code:
                                logger.info('✅ Установлен формат %s для V4L2', fmt_name)
                                format_set = True
                                break
                    except Exception as e:
                        logger.debug('Не удалось установить формат %s: %s', fmt_name, e)
                        continue
                
                if not format_set:
                    logger.debug('Не удалось установить явный формат, используем формат по умолчанию')
            
            # Устанавливаем разрешение (если поддерживается)
            # Для PiCamera2 лучше устанавливать после формата
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
        except Exception as e:
            logger.debug('Не удалось установить некоторые параметры камеры: %s', e)
        
        # Дополнительная задержка после настройки параметров
        time.sleep(0.5)
        
        # Проверяем, что камера действительно работает
        # Пробуем несколько раз, так как первое чтение может не сработать
        # Для PiCamera2 может потребоваться больше попыток
        ret = False
        frame = None
        max_attempts = 10  # Увеличиваем количество попыток
        for attempt in range(max_attempts):
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                logger.info('✅ Кадр успешно прочитан с попытки %d/%d (размер: %dx%d)', 
                           attempt + 1, max_attempts, frame.shape[1], frame.shape[0])
                break
            
            if attempt < max_attempts - 1:  # Не ждем после последней попытки
                wait_time = 0.2 * (attempt + 1)  # Увеличиваем время ожидания с каждой попыткой
                logger.debug('Попытка %d/%d: кадр не получен (ret=%s, frame=%s), ожидание %.1f сек...', 
                           attempt + 1, max_attempts, ret, 'None' if frame is None else f'{frame.shape if hasattr(frame, "shape") else "invalid"}', wait_time)
                time.sleep(wait_time)
        
        if not ret or frame is None or (hasattr(frame, 'size') and frame.size == 0):
            logger.warning('Камера открыта, но не может получать кадры после %d попыток', max_attempts)
            # Пробуем получить информацию о камере для диагностики
            try:
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                fourcc = cap.get(cv2.CAP_PROP_FOURCC)
                fps = cap.get(cv2.CAP_PROP_FPS)
                backend_name = cap.getBackendName()
                logger.warning('Параметры камеры: %dx%d, FOURCC=%s, FPS=%.2f, backend=%s', 
                             width, height, fourcc, fps, backend_name)
            except Exception as e:
                logger.debug('Не удалось получить параметры камеры: %s', e)
            cap.release()
            self.scan_cameras(force=True)
            return None
        
        logger.info('✅ Камера успешно подключена (разрешение: %dx%d)', 
                   int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
                   int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
        
        detection_results['active_camera'] = index
        return cap

    def _label_for_class(self, class_id: Optional[int]) -> str:
        names = getattr(self.model, 'names', None)
        if isinstance(names, dict):
            return str(names.get(class_id, f'class_{class_id}'))
        if isinstance(names, (list, tuple)) and class_id is not None and 0 <= class_id < len(names):
            return str(names[class_id])
        return 'object'

    def _infer(self, frame: np.ndarray, timestamp: float) -> Tuple[List[dict], np.ndarray]:
        with self._model_lock:
            model = self.model
        if model is None:
            raise RuntimeError('Модель не загружена')

        results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
        annotated = frame.copy()
        raw_detections: List[dict] = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())
                class_id = None
                if hasattr(box, 'cls') and box.cls is not None:
                    class_values = box.cls.cpu().numpy()
                    if class_values.size:
                        class_id = int(class_values[0])
                label = self._label_for_class(class_id)
                raw_detections.append({
                    'bbox': [float(x1), float(y1), float(x2), float(y2)],
                    'confidence': confidence,
                    'class_id': class_id,
                    'label': label
                })

        tracked = self.tracker.update(raw_detections, timestamp=timestamp)

        # Build stable tracks list (confirmed + tolerant to short misses)
        stable_tracks: List[dict] = []
        try:
            with self._tracker_lock:
                for t in getattr(self.tracker, 'tracks', []) or []:
                    # Consider tracks that reached confirmation and not expired by max_age
                    if getattr(t, 'hits', 0) >= getattr(self.tracker, 'min_hits', 1) and getattr(t, 'misses', 0) <= getattr(self.tracker, 'max_age', 5):
                        stable_tracks.append(t.to_dict())
        except Exception:
            stable_tracks = []

        for track in tracked:
            x1, y1, x2, y2 = map(int, track['bbox'])
            track_label = track.get('label') or 'object'
            caption = f"{track_label}#{track['trackId']} {track.get('confidence', 0.0):.2f}"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 70), 2)
            cv2.putText(annotated, caption, (x1, max(y1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 70), 2)

        return tracked, annotated, stable_tracks

    def analyze_frame(self, frame: np.ndarray, *, update_state: bool = True, notify: bool = True):
        timestamp = time.time()
        detections, annotated, stable_tracks = self._infer(frame, timestamp)
        confidence = max((d['confidence'] for d in detections), default=0.0)
        jpeg_bytes = encode_frame_to_jpeg(annotated)
        raw_jpeg = encode_frame_to_jpeg(frame)

        if update_state:
            detection_results.update({
                'active_camera': self.get_camera_index(),
                'active_model': self.get_active_model(),
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
            'model': self.get_active_model()
        }

    def _schedule_notification(self, detections: List[dict], confidence: float, captured_at: float):
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
            'model': self.get_active_model(),
            'cameraIndex': self.get_camera_index()
        }

        threading.Thread(target=self._post_detection, args=(payload,), daemon=True).start()

    def _post_detection(self, payload):
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


detection_service = DetectionService(MODEL_PATH)


def _mjpeg_generator():
    boundary = b'--frame'
    while True:
        frame = detection_results.get('frame_with_detections')
        if frame is not None:
            yield (
                boundary + b"\r\n"
                + b'Content-Type: image/jpeg\r\n'
                + b'Content-Length: ' + str(len(frame)).encode() + b"\r\n\r\n"
                + frame + b"\r\n"
            )
            time.sleep(0.1)
        else:
            time.sleep(0.2)


def _mjpeg_generator_raw():
    boundary = b'--frame'
    while True:
        frame = detection_results.get('frame_raw')
        if frame is not None:
            yield (
                boundary + b"\r\n"
                + b'Content-Type: image/jpeg\r\n'
                + b'Content-Length: ' + str(len(frame)).encode() + b"\r\n\r\n"
                + frame + b"\r\n"
            )
            time.sleep(0.01)
        else:
            time.sleep(0.2)


def _mjpeg_generator_frontend():
    """Генератор MJPEG потока для кадров с фронтенда - максимальная скорость"""
    boundary = b'--frame'
    while True:
        with _frontend_frame_lock:
            frame = _frontend_frame_raw
        if frame is not None:
            yield (
                boundary + b"\r\n"
                + b'Content-Type: image/jpeg\r\n'
                + b'Content-Length: ' + str(len(frame)).encode() + b"\r\n\r\n"
                + frame + b"\r\n"
            )
            time.sleep(0.001)  # Минимальная задержка для максимального FPS
        else:
            time.sleep(0.01)


def _frontend_inference_worker():
    """Асинхронный обработчик кадров с фронтенда - не блокирует поток"""
    global _frontend_infer_running
    min_interval = 1.0 / max(0.1, INFER_FPS)
    _last_infer_ts = 0.0
    
    while _frontend_infer_running:
        try:
            now = time.time()
            if (now - _last_infer_ts) < min_interval:
                time.sleep(0.005)
                continue
            
            # Пытаемся получить кадр из очереди (не блокируемся надолго)
            try:
                frame = _frontend_frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            # Очищаем очередь от старых кадров, оставляем только последний
            while not _frontend_frame_queue.empty():
                try:
                    _frontend_frame_queue.get_nowait()
                except queue.Empty:
                    break
            
            if frame is not None:
                _last_infer_ts = now
                # Асинхронная обработка - не блокирует поток
                detection_service.analyze_frame(frame, update_state=True, notify=True)
        except Exception as exc:
            logger.error('Ошибка в обработчике фронтенд кадров: %s', exc)
            time.sleep(0.1)


@app.get('/')
def index():
    state = detection_results.copy()
    state['running'] = detection_service.running
    return jsonify(state)


@app.get('/detection_frame')
def detection_frame():
    frame = detection_results.get('frame_with_detections')
    if frame is None:
        return Response('No frame', status=404)
    return Response(frame, mimetype='image/jpeg')


@app.get('/video_feed')
def video_feed():
    response = Response(_mjpeg_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    return response


@app.get('/video_feed_raw')
def video_feed_raw():
    response = Response(_mjpeg_generator_raw(), mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    return response


@app.get('/video_feed_frontend')
def video_feed_frontend():
    """MJPEG поток для кадров с фронтенда - максимальная скорость без задержек"""
    response = Response(_mjpeg_generator_frontend(), mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    return response


@app.post('/stream_frame')
def stream_frame():
    """
    Принимает кадр с фронтенда, немедленно сохраняет для ретрансляции,
    и ставит в очередь для асинхронной обработки
    """
    global _frontend_frame_raw, _frontend_infer_running, _frontend_infer_thread
    
    payload = request.get_json(silent=True) or {}
    image_b64 = payload.get('image')
    
    if not image_b64:
        return jsonify({'error': 'image is required'}), 400
    
    try:
        # Декодируем кадр
        frame_bytes = base64.b64decode(image_b64)
        frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Unable to decode image'}), 400
        
        # НЕМЕДЛЕННО сохраняем RAW кадр для ретрансляции (без задержек)
        raw_jpeg = encode_frame_to_jpeg(frame)
        if raw_jpeg:
            with _frontend_frame_lock:
                _frontend_frame_raw = raw_jpeg
        
        # Ставим в очередь для асинхронной обработки (не блокируем ответ)
        # Очищаем очередь от старых кадров, оставляем только последний
        while not _frontend_frame_queue.empty():
            try:
                _frontend_frame_queue.get_nowait()
            except queue.Empty:
                break
        
        try:
            _frontend_frame_queue.put_nowait(frame.copy())
        except queue.Full:
            # Если очередь полная, просто пропускаем - это нормально для высокой частоты
            pass
        
        # Запускаем поток обработки если еще не запущен
        if not _frontend_infer_running:
            _frontend_infer_running = True
            _frontend_infer_thread = threading.Thread(target=_frontend_inference_worker, daemon=True)
            _frontend_infer_thread.start()
        
        # Немедленно возвращаем ответ - не ждем инференса
        return jsonify({
            'status': 'ok',
            'queued': True
        })
        
    except Exception as exc:
        logger.error('Ошибка при приеме кадра с фронтенда: %s', exc)
        return jsonify({'error': 'Unable to process frame', 'details': str(exc)}), 500


@app.get('/models')
def models():
    models_list = detection_service.refresh_available_models()
    return jsonify({
        'models': models_list,
        'active': detection_service.get_active_model()
    })


@app.post('/models')
def set_model():
    payload = request.get_json(silent=True) or {}
    model_name = payload.get('name') or payload.get('model')
    if not model_name:
        return jsonify({'error': 'name is required'}), 400

    try:
        active = detection_service.set_model(model_name)
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:  # pragma: no cover
        logger.error('Не удалось переключить модель: %s', exc)
        return jsonify({'error': 'Unable to switch model', 'details': str(exc)}), 500

    return jsonify({
        'active': active,
        'models': detection_service.get_available_models()
    })


@app.get('/cameras')
def cameras():
    cameras_list = detection_service.scan_cameras(force=True)
    return jsonify({
        'available': cameras_list,
        'active': detection_service.get_camera_index(),
        'localCameraEnabled': LOCAL_CAMERA_ENABLED
    })


@app.patch('/cameras/<int:index>')
def set_camera(index: int):
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


@app.get('/api/detection')
def api_detection():
    return jsonify({
        'activeCamera': detection_results.get('active_camera'),
        'availableCameras': detection_results.get('available_cameras', []),
        'detected': detection_results.get('detected', False),
        'count': detection_results.get('count', 0),
        'confidence': detection_results.get('confidence', 0.0),
        'last_detection': detection_results.get('last_detection'),
        'detections': detection_results.get('detections', []),
        'stableDetections': detection_results.get('stable_detections', []),
        'localCameraEnabled': detection_results.get('local_camera_enabled', True),
        'activeModel': detection_results.get('active_model'),
        'availableModels': detection_results.get('available_models', [])
    })


@app.post('/detect')
def detect_once():
    payload = request.get_json(silent=True) or {}
    image_b64 = payload.get('image')
    image_url = payload.get('imageUrl')

    if not image_b64 and not image_url:
        return jsonify({'error': 'image or imageUrl is required'}), 400

    frame_bytes = None
    try:
        if image_url:
            response = requests.get(image_url, timeout=3)
            response.raise_for_status()
            frame_bytes = response.content
        else:
            frame_bytes = base64.b64decode(image_b64)
    except Exception as exc:
        return jsonify({'error': 'Unable to load image', 'details': str(exc)}), 400

    frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({'error': 'Unable to decode image'}), 400

    result = detection_service.analyze_frame(frame, update_state=True, notify=False)
    # Also include stable tracks snapshot for consumers that want non-flickering lists
    try:
        with detection_service._tracker_lock:
            stable_tracks = []
            for t in getattr(detection_service.tracker, 'tracks', []) or []:
                if getattr(t, 'hits', 0) >= getattr(detection_service.tracker, 'min_hits', 1) and getattr(t, 'misses', 0) <= getattr(detection_service.tracker, 'max_age', 5):
                    stable_tracks.append(t.to_dict())
    except Exception:
        stable_tracks = []
    result['stableDetections'] = stable_tracks
    result['cameraIndex'] = detection_service.get_camera_index()
    return jsonify(result)


@app.get('/api/tracker/config')
def get_tracker_config():
    return jsonify(detection_service.get_tracker_config())


@app.patch('/api/tracker/config')
def update_tracker_config():
    payload = request.get_json(silent=True) or {}
    try:
        detection_service.update_tracker_config(
            iou_threshold=payload.get('iou_threshold'),
            max_age=payload.get('max_age'),
            min_hits=payload.get('min_hits')
        )
        return jsonify(detection_service.get_tracker_config())
    except Exception as exc:
        logger.error('Не удалось обновить параметры трекера: %s', exc)
        return jsonify({'error': 'Unable to update tracker config', 'details': str(exc)}), 500


@app.get('/health')
def health():
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
    debug_enabled = str(os.environ.get('DEBUG', '0')).lower() in ('1', 'true', 'yes')
    try:
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


if __name__ == '__main__':
    main()


