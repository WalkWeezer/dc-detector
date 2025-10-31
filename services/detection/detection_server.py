#!/usr/bin/env python3
"""Detection Service - перенесённый сервис детекции огня"""

import base64
import logging
import os
import threading
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np
import requests
from flask import Flask, Response, jsonify, request
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

CAMERA_ID_ENV = os.getenv('CAMERA_ID', 'camera-default')
DEFAULT_CAMERA_MODE = os.getenv('CAMERA_MODE', 'http')
DEFAULT_CAMERA_SOURCE = os.getenv('CAMERA_SOURCE', '0')
DEFAULT_CAMERA_STREAM = os.getenv('CAMERA_SERVICE_URL') or DEFAULT_CAMERA_SOURCE
CAMERA_CONFIG_URL = os.getenv('CAMERA_CONFIG_URL')
CONFIG_REFRESH_INTERVAL = float(os.getenv('CAMERA_CONFIG_REFRESH', '15.0'))

MODEL_PATH = os.getenv('MODEL_PATH', 'models/bestfire.pt')
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.5'))

BACKEND_NOTIFY_URL = os.getenv('BACKEND_NOTIFY_URL')
BACKEND_NOTIFY_TIMEOUT = float(os.getenv('BACKEND_NOTIFY_TIMEOUT', '1.0'))
NOTIFY_MIN_INTERVAL = float(os.getenv('BACKEND_NOTIFY_INTERVAL', '1.0'))

_notify_lock = threading.Lock()
_last_notification_ts = 0.0

detection_results = {
    'camera_id': CAMERA_ID_ENV,
    'detected': False,
    'count': 0,
    'confidence': 0.0,
    'last_detection': None,
    'detections': [],
    'frame_with_detections': None
}


def encode_frame_to_jpeg(frame: np.ndarray) -> Optional[bytes]:
    try:
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if success:
            return buffer.tobytes()
    except Exception as exc:  # pragma: no cover
        logger.error('Не удалось кодировать кадр в JPEG: %s', exc)
    return None


class DetectionService:
    def __init__(self, model_path: str):
        logger.info('🔍 Загрузка модели YOLO: %s', model_path)
        self.model = YOLO(model_path)
        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.camera_id = CAMERA_ID_ENV
        self.camera_mode = DEFAULT_CAMERA_MODE.lower()
        self.camera_source = DEFAULT_CAMERA_SOURCE
        self.camera_stream = DEFAULT_CAMERA_STREAM
        self.camera_config_url = CAMERA_CONFIG_URL
        self.config_refresh_interval = CONFIG_REFRESH_INTERVAL
        self.last_config_fetch = 0.0

        self._refresh_camera_config(force=True)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def _refresh_camera_config(self, force: bool = False) -> bool:
        if not self.camera_config_url:
            return False
        now = time.time()
        if not force and (now - self.last_config_fetch) < self.config_refresh_interval:
            return False
        try:
            response = requests.get(self.camera_config_url, timeout=2)
            response.raise_for_status()
            data = response.json()
            self.camera_id = data.get('id', self.camera_id)
            if data.get('mode'):
                self.camera_mode = str(data['mode']).lower()
            if data.get('source'):
                self.camera_source = str(data['source'])
                if self.camera_mode != 'local':
                    self.camera_stream = self.camera_source
            if data.get('rtsp_url'):
                self.camera_stream = data['rtsp_url']
            self.last_config_fetch = now
            logger.info('📡 Конфигурация камеры обновлена: id=%s mode=%s source=%s', self.camera_id, self.camera_mode, self.camera_stream)
            return True
        except Exception as exc:
            logger.warning('⚠️ Не удалось обновить конфигурацию камеры: %s', exc)
            return False

    def _open_local_capture(self):
        src = self.camera_source
        if str(src).isdigit():
            cap = cv2.VideoCapture(int(src))
        else:
            cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        if not cap or not cap.isOpened():
            raise RuntimeError(f'Не удалось открыть локальный источник: {src}')
        return cap

    def _detection_loop(self):
        while self.running:
            try:
                self._refresh_camera_config()
                mode = self.camera_mode
                if mode == 'local':
                    self._consume_local()
                else:
                    self._consume_stream()
            except Exception as exc:
                logger.error('Ошибка в цикле детекции: %s', exc)
                time.sleep(1.0)
        self.running = False

    def _consume_local(self):
        try:
            cap = self._open_local_capture()
        except Exception as exc:
            logger.error('Не удалось открыть локальную камеру: %s', exc)
            time.sleep(1.0)
            return

        current_source = self.camera_source
        current_mode = self.camera_mode
        try:
            while self.running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.02)
                    continue
                self.analyze_frame(frame)
                if self._refresh_camera_config():
                    if self.camera_mode != current_mode or self.camera_source != current_source:
                        logger.info('🎛️ Конфигурация камеры изменена, перезапуск потока')
                        break
        finally:
            cap.release()

    def _consume_stream(self):
        url = self.camera_stream or self.camera_source
        if not url:
            logger.warning('HTTP поток камеры не задан')
            time.sleep(1.0)
            return
        logger.info('🎥 Подключение к потоку %s', url)
        try:
            response = requests.get(url, stream=True, timeout=5)
            response.raise_for_status()
        except Exception as exc:
            logger.error('Не удалось подключиться к потоку %s: %s', url, exc)
            time.sleep(1.0)
            return

        bytes_buffer = b''
        current_url = url
        try:
            for chunk in response.iter_content(chunk_size=4096):
                if not self.running:
                    break
                if not chunk:
                    continue
                bytes_buffer += chunk
                start = bytes_buffer.find(b'\xff\xd8')
                end = bytes_buffer.find(b'\xff\xd9')
                if start != -1 and end != -1 and end > start:
                    jpg = bytes_buffer[start:end + 2]
                    bytes_buffer = bytes_buffer[end + 2:]
                    frame = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        self.analyze_frame(frame)
                if self._refresh_camera_config():
                    new_url = self.camera_stream or self.camera_source
                    if self.camera_mode == 'local' or new_url != current_url:
                        logger.info('🔁 URL потока изменился, переподключаемся')
                        break
        finally:
            response.close()

    def _infer(self, frame: np.ndarray) -> Tuple[List[dict], np.ndarray]:
        results = self.model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
        detections: List[dict] = []
        annotated = frame.copy()
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())
                cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                label = f'Fire: {confidence:.2f}'
                cv2.putText(annotated, label, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                detections.append({
                    'bbox': [float(x1), float(y1), float(x2), float(y2)],
                    'confidence': confidence
                })
        return detections, annotated

    def analyze_frame(self, frame: np.ndarray, *, update_state: bool = True, notify: bool = True):
        detections, annotated = self._infer(frame)
        timestamp = time.time()
        confidence = max((d['confidence'] for d in detections), default=0.0)
        jpeg_bytes = encode_frame_to_jpeg(annotated)

        if update_state:
            detection_results.update({
                'camera_id': self.camera_id,
                'detected': bool(detections),
                'count': len(detections),
                'confidence': confidence,
                'last_detection': timestamp,
                'detections': detections,
                'frame_with_detections': jpeg_bytes
            })

        if notify and detections:
            self._schedule_notification(detections, confidence, timestamp)

        return {
            'cameraId': self.camera_id,
            'detected': bool(detections),
            'confidence': confidence,
            'detections': detections,
            'capturedAt': timestamp
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
            'cameraId': self.camera_id,
            'detected': True,
            'confidence': confidence,
            'detections': detections,
            'capturedAt': captured_at
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


@app.get('/api/detection')
def api_detection():
    return jsonify({
        'cameraId': detection_results.get('camera_id'),
        'detected': detection_results.get('detected', False),
        'count': detection_results.get('count', 0),
        'confidence': detection_results.get('confidence', 0.0),
        'last_detection': detection_results.get('last_detection'),
        'detections': detection_results.get('detections', [])
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

    result = detection_service.analyze_frame(frame, update_state=False, notify=False)
    result['cameraId'] = payload.get('cameraId', detection_service.camera_id)
    return jsonify(result)


@app.post('/refresh-config')
def refresh_config():
    updated = detection_service._refresh_camera_config(force=True)
    return jsonify({
        'updated': updated,
        'cameraId': detection_service.camera_id,
        'mode': detection_service.camera_mode,
        'source': detection_service.camera_source
    })


@app.get('/health')
def health():
    return jsonify({
        'status': 'ok',
        'running': detection_service.running,
        'cameraId': detection_service.camera_id,
        'mode': detection_service.camera_mode
    })


def main():
    debug_enabled = str(os.environ.get('DEBUG', '0')).lower() in ('1', 'true', 'yes')
    try:
        if debug_enabled:
            if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
                detection_service.start()
        else:
            detection_service.start()
        app.run(host='0.0.0.0', port=8001, debug=debug_enabled, threaded=True)
    finally:
        detection_service.stop()


if __name__ == '__main__':
    main()


