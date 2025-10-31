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

DEFAULT_CAMERA_INDEX = int(os.getenv('CAMERA_INDEX', '0'))
CAMERA_SCAN_LIMIT = int(os.getenv('CAMERA_SCAN_LIMIT', '5'))
CAPTURE_RETRY_DELAY = float(os.getenv('CAPTURE_RETRY_DELAY', '1.0'))

MODEL_PATH = os.getenv('MODEL_PATH', 'models/bestfire.pt')
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.5'))

BACKEND_NOTIFY_URL = os.getenv('BACKEND_NOTIFY_URL')
BACKEND_NOTIFY_TIMEOUT = float(os.getenv('BACKEND_NOTIFY_TIMEOUT', '1.0'))
NOTIFY_MIN_INTERVAL = float(os.getenv('BACKEND_NOTIFY_INTERVAL', '1.0'))

_notify_lock = threading.Lock()
_last_notification_ts = 0.0

detection_results = {
    'active_camera': DEFAULT_CAMERA_INDEX,
    'available_cameras': [],
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

        self.camera_scan_limit = CAMERA_SCAN_LIMIT
        self.capture_retry_delay = CAPTURE_RETRY_DELAY
        self._camera_lock = threading.Lock()
        self._available_cameras: List[int] = []
        self.camera_index = DEFAULT_CAMERA_INDEX

        self.scan_cameras(force=True)

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

    def scan_cameras(self, *, force: bool = False) -> List[int]:
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

    def get_camera_index(self) -> int:
        with self._camera_lock:
            return self.camera_index

    def set_camera(self, index: int) -> int:
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

    def _detection_loop(self):
        current_index: Optional[int] = None
        cap: Optional[cv2.VideoCapture] = None
        while self.running:
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
                    time.sleep(0.02)
                    continue
                self.analyze_frame(frame)
            except Exception as exc:
                logger.error('Ошибка в цикле детекции: %s', exc)
                time.sleep(1.0)
        if cap is not None:
            cap.release()
        self.running = False

    def _open_capture(self, index: int) -> Optional[cv2.VideoCapture]:
        if index < 0:
            logger.error('Индекс камеры должен быть неотрицательным, получено %s', index)
            return None

        logger.info('🎥 Подключение к локальной камере %s', index)
        cap = cv2.VideoCapture(index)
        if not cap or not cap.isOpened():
            if cap is not None:
                cap.release()
            logger.error('Не удалось открыть локальную камеру: %s', index)
            self.scan_cameras(force=True)
            return None

        detection_results['active_camera'] = index
        return cap

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
                'active_camera': self.get_camera_index(),
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
            'cameraIndex': self.get_camera_index(),
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


@app.get('/cameras')
def cameras():
    cameras_list = detection_service.scan_cameras(force=True)
    return jsonify({
        'available': cameras_list,
        'active': detection_service.get_camera_index()
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
        'available': cameras_list
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
    result['cameraIndex'] = detection_service.get_camera_index()
    return jsonify(result)


@app.get('/health')
def health():
    return jsonify({
        'status': 'ok',
        'running': detection_service.running,
        'activeCamera': detection_service.get_camera_index(),
        'availableCameras': detection_results.get('available_cameras', [])
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


