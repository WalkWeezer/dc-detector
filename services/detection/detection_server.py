#!/usr/bin/env python3
"""Detection Service - только видеострим"""

import os
import time
from io import BytesIO
from typing import Optional
from flask import Flask, Response

app = Flask(__name__)

# Попытка импортировать picamera2 (доступно только на Raspberry Pi)
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None

# Глобальная переменная для камеры (как в рабочем скрипте)
picam2: Optional[Picamera2] = None


def init_picamera2():
    """Инициализирует Picamera2 (как в рабочем скрипте)"""
    global picam2
    if not PICAMERA2_AVAILABLE:
        print("picamera2 не доступен")
        return False
    
    try:
        picam2 = Picamera2()
        config = picam2.create_preview_configuration(main={"size": (1280, 720)})
        picam2.configure(config)
        picam2.start()
        print("✅ Picamera2 инициализирован (как в рабочем скрипте)")
        return True
    except Exception as e:
        print(f"❌ Ошибка при инициализации Picamera2: {e}")
        return False


def capture_frame_jpeg() -> Optional[bytes]:
    """Захватывает кадр в JPEG (точно как в рабочем скрипте)"""
    global picam2
    if picam2 is None:
        return None
    
    try:
        buffer = BytesIO()
        picam2.capture_file(buffer, format='jpeg')
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        print(f"Ошибка при захвате кадра: {e}")
        return None


def stop_picamera2():
    """Останавливает Picamera2"""
    global picam2
    if picam2 is not None:
        try:
            picam2.stop()
            picam2 = None
            print("Picamera2 остановлен")
        except Exception as e:
            print(f"Ошибка при остановке Picamera2: {e}")


@app.get('/video_feed_raw')
def video_feed_raw():
    """Сырой MJPEG поток (использует рабочий скрипт)"""
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
