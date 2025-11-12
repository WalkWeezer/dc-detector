#!/usr/bin/env python3
"""Detection Service - только видеострим"""

import os
import time
from flask import Flask, Response

app = Flask(__name__)

# Импортируем рабочий скрипт
try:
    from camera.capture import picam2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    picam2 = None


@app.get('/video_feed_raw')
def video_feed_raw():
    """Сырой MJPEG поток (использует рабочий скрипт)"""
    if picam2 is None:
        return Response('Camera not available', status=503)
    
    def mjpeg_generator():
        """Генератор MJPEG потока (как в рабочем скрипте)"""
        from io import BytesIO
        boundary = b'--frame'
        
        while True:
            try:
                # Захватываем кадр (как в рабочем скрипте)
                buffer = BytesIO()
                picam2.capture_file(buffer, format='jpeg')
                buffer.seek(0)
                
                # Отправляем кадр
                yield (
                    boundary + b"\r\n"
                    + b'Content-Type: image/jpeg\r\n'
                    + b'Content-Length: ' + str(buffer.getbuffer().nbytes).encode() + b"\r\n\r\n"
                    + buffer.getvalue() + b"\r\n"
                )
                
                time.sleep(0.033)  # ~30 FPS как в рабочем скрипте
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
    debug_enabled = str(os.environ.get('DEBUG', '0')).lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', port=8001, debug=debug_enabled, threaded=True)


if __name__ == '__main__':
    main()
