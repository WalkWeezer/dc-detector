#!/usr/bin/env python3
"""Detection Service - только видеострим"""

import os
import time
from flask import Flask, Response

app = Flask(__name__)

# Импортируем функции для работы с камерой
try:
    from camera.capture import init_picamera2, capture_frame_jpeg, stop_picamera2, PICAMERA2_AVAILABLE, picam2
except ImportError:
    PICAMERA2_AVAILABLE = False
    picam2 = None
    def init_picamera2():
        return False
    def capture_frame_jpeg():
        return None
    def stop_picamera2():
        pass


@app.get('/video_feed_raw')
def video_feed_raw():
    """Сырой MJPEG поток (использует рабочий скрипт)"""
    from camera.capture import picam2
    
    if picam2 is None:
        return Response('Camera not available', status=503)
    
    def mjpeg_generator():
        """Генератор MJPEG потока (как в рабочем скрипте)"""
        boundary = b'--frame'
        
        while True:
            try:
                # Захватываем кадр через функцию (как в рабочем скрипте)
                frame = capture_frame_jpeg()
                if frame is not None:
                    # Отправляем кадр
                    yield (
                        boundary + b"\r\n"
                        + b'Content-Type: image/jpeg\r\n'
                        + b'Content-Length: ' + str(len(frame)).encode() + b"\r\n\r\n"
                        + frame + b"\r\n"
                    )
                    time.sleep(0.033)  # ~30 FPS как в рабочем скрипте
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"Stream error: {e}")
                time.sleep(0.1)
    
    response = Response(
        mjpeg_generator(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    return response


@app.get('/health')
def health():
    """Health check"""
    return {
        'status': 'ok',
        'camera_available': picam2 is not None
    }


def main():
    """Главная функция"""
    # Инициализируем Picamera2 (рабочий скрипт)
    if PICAMERA2_AVAILABLE:
        init_picamera2()
    
    debug_enabled = str(os.environ.get('DEBUG', '0')).lower() in ('1', 'true', 'yes')
    try:
        app.run(host='0.0.0.0', port=8001, debug=debug_enabled, threaded=True)
    finally:
        stop_picamera2()


if __name__ == '__main__':
    main()
