#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detection Service - простой видеострим как в рабочем скрипте"""

import os
import sys
import time
import threading
from io import BytesIO
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройка кодировки для Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Попытка импортировать picamera2
picam2 = None
PICAMERA2_AVAILABLE = False
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
    print("✅ picamera2 успешно импортирован")
except ImportError:
    # Пробуем найти системный picamera2
    system_paths = [
        '/usr/lib/python3/dist-packages',
        '/usr/local/lib/python3/dist-packages',
    ]
    for path in system_paths:
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        from picamera2 import Picamera2
        PICAMERA2_AVAILABLE = True
        print("✅ picamera2 успешно импортирован из системных пакетов")
    except ImportError:
        print("⚠️ picamera2 не доступен, будет использована веб-камера")

# Попытка импортировать OpenCV для веб-камеры
webcam = None
CV2_AVAILABLE = False
try:
    import cv2
    CV2_AVAILABLE = True
    print("✅ OpenCV успешно импортирован")
except ImportError:
    print("⚠️ OpenCV не доступен")

camera_type = None  # 'picamera2' или 'webcam'


def init_camera():
    """Инициализирует камеру (picamera2 или webcam)"""
    global picam2, webcam, camera_type
    
    # Сначала пробуем picamera2
    if PICAMERA2_AVAILABLE:
        try:
            print("🎥 Инициализация Picamera2...")
            picam2 = Picamera2()
            config = picam2.create_preview_configuration(main={"size": (1280, 720)})
            picam2.configure(config)
            picam2.start()
            time.sleep(2)  # Даем время на инициализацию
            
            # Проверяем, что камера работает
            buffer = BytesIO()
            picam2.capture_file(buffer, format='jpeg')
            if buffer.getbuffer().nbytes > 0:
                camera_type = 'picamera2'
                print("✅ Picamera2 инициализирован")
                return True
        except Exception as e:
            print(f"⚠️ Ошибка инициализации Picamera2: {e}")
            picam2 = None
    
    # Если picamera2 не сработал, пробуем webcam
    if CV2_AVAILABLE:
        try:
            print("🎥 Инициализация веб-камеры...")
            for idx in [0, 1, 2]:
                test_cam = cv2.VideoCapture(idx)
                if test_cam.isOpened():
                    time.sleep(0.5)
                    ret, frame = test_cam.read()
                    if ret and frame is not None:
                        webcam = test_cam
                        camera_type = 'webcam'
                        print(f"✅ Веб-камера {idx} инициализирована")
                        return True
                    test_cam.release()
        except Exception as e:
            print(f"⚠️ Ошибка инициализации веб-камеры: {e}")
    
    print("❌ Не удалось инициализировать ни одну камеру")
    return False


def capture_frame():
    """Захватывает один кадр и возвращает JPEG bytes"""
    global picam2, webcam, camera_type
    
    if camera_type == 'picamera2' and picam2 is not None:
        buffer = BytesIO()
        picam2.capture_file(buffer, format='jpeg')
        return buffer.getvalue()
    
    elif camera_type == 'webcam' and webcam is not None:
        ret, frame = webcam.read()
        if ret and frame is not None:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return buffer.tobytes()
    
    return None


class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/video_feed_raw' or self.path == '/stream.mjpeg':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            
            try:
                while True:
                    frame_data = capture_frame()
                    if frame_data:
                        self.wfile.write(b'--frame\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', str(len(frame_data)))
                        self.end_headers()
                        self.wfile.write(frame_data)
                        self.wfile.write(b'\r\n')
                    time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                print(f"Stream closed: {e}")
        
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            status = {
                'status': 'ok',
                'camera_available': camera_type is not None,
                'camera_type': camera_type
            }
            import json
            self.wfile.write(json.dumps(status).encode())
        
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''
                <html>
                    <head>
                        <title>Video Stream</title>
                    </head>
                    <body>
                        <h1>Video Stream</h1>
                        <img src="/video_feed_raw" width="1280" height="720">
                    </body>
                </html>
            ''')


def run_server(port=8001):
    """Запускает HTTP сервер"""
    server = HTTPServer(('0.0.0.0', port), StreamingHandler)
    print(f"🌐 Сервер запущен на http://0.0.0.0:{port}")
    print(f"📹 Видео поток: http://localhost:{port}/video_feed_raw")
    print(f"🏥 Health check: http://localhost:{port}/health")
    server.serve_forever()


def main():
    """Главная функция"""
    print("🚀 Запуск Detection Service...")
    
    # Инициализируем камеру
    if not init_camera():
        print("⚠️ ВНИМАНИЕ: Камера не инициализирована!")
        print("💡 Сервер запустится, но видео поток будет недоступен")
    
    # Получаем порт из переменной окружения
    port = int(os.environ.get('PORT', 8001))
    
    # Запускаем сервер в отдельном потоке
    server_thread = threading.Thread(target=run_server, args=(port,))
    server_thread.daemon = True
    server_thread.start()
    
    try:
        print(f"✅ Камера запущена. Откройте http://localhost:{port} в браузере")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Останавливаем...")
        if picam2 is not None:
            picam2.stop()
        if webcam is not None:
            webcam.release()


if __name__ == '__main__':
    main()
