#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detection Service - простой видеострим как в рабочем скрипте"""

import os
import sys
import time
import threading
from io import BytesIO
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import numpy as np

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

# YOLO модель
yolo_model = None
YOLO_AVAILABLE = False
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    print("✅ Ultralytics YOLO успешно импортирован")
except ImportError:
    print("⚠️ Ultralytics YOLO не доступен, детекция отключена")


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


def capture_frame_raw():
    """Захватывает один кадр и возвращает numpy array (BGR)"""
    global picam2, webcam, camera_type
    
    if camera_type == 'picamera2' and picam2 is not None:
        # Для picamera2 нужно конвертировать из RGB в BGR
        array = picam2.capture_array()
        # picamera2 возвращает RGB, OpenCV использует BGR
        if len(array.shape) == 3:
            frame = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
            return frame
        return None
    
    elif camera_type == 'webcam' and webcam is not None:
        ret, frame = webcam.read()
        if ret and frame is not None:
            return frame
    
    return None


def capture_frame():
    """Захватывает один кадр и возвращает JPEG bytes (без детекции)"""
    frame = capture_frame_raw()
    if frame is not None:
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buffer.tobytes()
    return None


def capture_frame_with_detection():
    """Захватывает кадр, выполняет детекцию YOLO и возвращает JPEG bytes с bbox"""
    global yolo_model
    
    frame = capture_frame_raw()
    if frame is None:
        return None
    
    # Если модель загружена, выполняем детекцию
    if yolo_model is not None:
        try:
            # Выполняем инференс
            results = yolo_model(frame, conf=0.5, verbose=False)
            
            # Рисуем детекции на кадре
            annotated_frame = frame.copy()
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Получаем координаты bbox
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    confidence = float(box.conf[0].cpu().numpy())
                    
                    # Получаем класс
                    class_id = None
                    label = 'object'
                    if hasattr(box, 'cls') and box.cls is not None:
                        class_values = box.cls.cpu().numpy()
                        if class_values.size:
                            class_id = int(class_values[0])
                            # Получаем имя класса из модели
                            if hasattr(yolo_model, 'names') and class_id in yolo_model.names:
                                label = yolo_model.names[class_id]
                    
                    # Рисуем прямоугольник
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Рисуем метку с уверенностью
                    caption = f"{label} {confidence:.2f}"
                    cv2.putText(annotated_frame, caption, (x1, max(y1 - 10, 20)), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            frame = annotated_frame
        except Exception as e:
            print(f"⚠️ Ошибка детекции: {e}")
    
    # Конвертируем в JPEG
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buffer.tobytes()


class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/video_feed_raw' or self.path == '/stream.mjpeg':
            # Поток без детекции
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
        
        elif self.path == '/video_feed':
            # Поток с детекцией YOLO
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            
            try:
                while True:
                    frame_data = capture_frame_with_detection()
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
                        <p><a href="/video_feed_raw">Raw stream (no detection)</a> | 
                           <a href="/video_feed">Stream with YOLO detection</a></p>
                        <img src="/video_feed" width="1280" height="720">
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


def load_yolo_model():
    """Загружает модель YOLO"""
    global yolo_model
    
    if not YOLO_AVAILABLE:
        print("⚠️ YOLO не доступен, детекция отключена")
        return False
    
    # Ищем модель yolov8n.pt
    model_paths = [
        Path(__file__).parent / 'models' / 'yolov8n.pt',
        Path(__file__).parent.parent / 'models' / 'yolov8n.pt',
        Path('models/yolov8n.pt'),
    ]
    
    model_path = None
    for path in model_paths:
        if path.exists():
            model_path = path
            break
    
    if model_path is None:
        print("⚠️ Модель yolov8n.pt не найдена, детекция отключена")
        print("💡 Скачайте модель: wget https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt")
        return False
    
    try:
        print(f"🔍 Загрузка модели YOLO: {model_path}")
        yolo_model = YOLO(str(model_path))
        print("✅ Модель YOLO загружена")
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки модели: {e}")
        yolo_model = None
        return False


def main():
    """Главная функция"""
    print("🚀 Запуск Detection Service...")
    
    # Инициализируем камеру
    if not init_camera():
        print("⚠️ ВНИМАНИЕ: Камера не инициализирована!")
        print("💡 Сервер запустится, но видео поток будет недоступен")
    
    # Загружаем модель YOLO
    load_yolo_model()
    
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
