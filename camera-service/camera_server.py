#!/usr/bin/env python3
"""
Camera Service - Универсальный сервис для работы с камерами
Поддерживает: PiCamera, Picamera2, Web Camera (OpenCV)
"""

import cv2
import threading
import time
import logging
from flask import Flask, Response
from typing import Optional, Tuple
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class CameraManager:
    """Менеджер камер с автоматическим выбором источника"""
    
    def __init__(self):
        self.camera_type = None
        self.camera = None
        self.lock = threading.Lock()
        self.running = False
        self.current_frame = None
        
    def try_picamera(self) -> bool:
        """Попытка инициализировать PiCamera (legacy)"""
        try:
            import picamera
            import picamera.array
            
            # Проверяем доступность через команду
            import subprocess
            result = subprocess.run(['vcgencmd', 'get_camera'], 
                                   capture_output=True, text=True, timeout=2)
            if 'supported=1' not in result.stdout and 'detected=1' not in result.stdout:
                logger.debug("PiCamera не обнаружена на устройстве")
                return False
            
            cam = picamera.PiCamera()
            cam.resolution = (640, 480)
            cam.framerate = 30
            cam.start_preview()
            time.sleep(2)  # Даем камере время на инициализацию
            
            self.camera = cam
            logger.info("✅ PiCamera (legacy) инициализирована")
            self.camera_type = 'picamera'
            return True
        except (ImportError, FileNotFoundError, Exception) as e:
            logger.debug(f"PiCamera не доступна: {e}")
            return False
    
    def try_picamera2(self) -> bool:
        """Попытка инициализировать Picamera2"""
        try:
            from picamera2 import Picamera2
            camera = Picamera2()
            # Настройка для preview
            camera_config = camera.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            )
            camera.configure(camera_config)
            camera.start()
            self.camera = camera
            logger.info("✅ Picamera2 инициализирована")
            self.camera_type = 'picamera2'
            return True
        except (ImportError, Exception) as e:
            logger.debug(f"Picamera2 не доступна: {e}")
            return False
    
    def try_webcam(self) -> bool:
        """Попытка инициализировать веб-камеру через OpenCV"""
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                logger.debug("Веб-камера на порту 0 не открылась")
                return False
            
            # Проверяем, что можем получить кадр
            ret, frame = cap.read()
            if not ret:
                cap.release()
                return False
            
            self.camera = cap
            logger.info("✅ Веб-камера инициализирована")
            self.camera_type = 'webcam'
            return True
        except Exception as e:
            logger.debug(f"Веб-камера не доступна: {e}")
            return False
    
    def initialize(self) -> bool:
        """Инициализация камеры с автоматическим выбором"""
        logger.info("🔍 Поиск доступной камеры...")
        
        # Порядок попыток: PiCamera -> Picamera2 -> WebCam
        strategies = [
            ("PiCamera", self.try_picamera),
            ("Picamera2", self.try_picamera2),
            ("WebCamera", self.try_webcam)
        ]
        
        for name, strategy in strategies:
            logger.info(f"Проверка {name}...")
            if strategy():
                logger.info(f"✅ Используется камера: {name}")
                self.running = True
                return True
        
        logger.error("❌ Не найдена доступная камера")
        return False
    
    def get_frame(self) -> Optional[Tuple[bool, bytes]]:
        """Получение текущего кадра"""
        with self.lock:
            if not self.running or self.camera is None:
                return None
            
            try:
                if self.camera_type == 'picamera2':
                    frame = self.camera.capture_array()
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                elif self.camera_type == 'webcam':
                    ret, frame = self.camera.read()
                    if not ret:
                        return None
                
                elif self.camera_type == 'picamera':
                    # Для PiCamera делаем захват
                    import picamera.array
                    output = picamera.array.PiRGBArray(self.camera)
                    self.camera.capture(output, format='bgr', use_video_port=True)
                    frame = output.array
                    if frame is None or frame.size == 0:
                        return None
                
                # Подготавливаем кадр для стрима
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ret:
                    return None
                
                frame_bytes = buffer.tobytes()
                self.current_frame = frame_bytes
                return (True, frame_bytes)
                
            except Exception as e:
                logger.error(f"Ошибка захвата кадра: {e}")
                return None
    
    def release(self):
        """Освобождение ресурсов камеры"""
        with self.lock:
            self.running = False
            if self.camera is not None:
                try:
                    if self.camera_type == 'webcam':
                        self.camera.release()
                    elif self.camera_type == 'picamera2':
                        self.camera.stop()
                        self.camera.close()
                    elif self.camera_type == 'picamera':
                        self.camera.stop_preview()
                        self.camera.close()
                    logger.info(f"Камера {self.camera_type} освобождена")
                except Exception as e:
                    logger.error(f"Ошибка при освобождении камеры: {e}")
                finally:
                    self.camera = None

# Глобальный менеджер камер
camera_manager = CameraManager()

def generate_frames():
    """Генератор кадров для MJPEG стрима"""
    while camera_manager.running:
        frame_data = camera_manager.get_frame()
        if frame_data is not None:
            _, frame_bytes = frame_data
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            time.sleep(0.033)  # ~30 FPS

@app.route('/')
def index():
    """Главная страница с информацией"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Camera Service</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                margin: 0; 
                padding: 20px; 
                background: #1a1a1a; 
                color: white; 
                font-family: Arial, sans-serif;
            }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            h1 {{ color: #4CAF50; text-align: center; }}
            .status {{ 
                background: rgba(255,255,255,0.1); 
                padding: 15px; 
                border-radius: 8px; 
                margin: 20px 0;
            }}
            .video-container {{ 
                text-align: center; 
                margin: 20px 0; 
            }}
            img {{ 
                max-width: 100%; 
                border: 3px solid #333; 
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            }}
            .camera-info {{ 
                background: rgba(76, 175, 80, 0.2); 
                padding: 10px; 
                border-radius: 5px; 
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📷 Camera Service</h1>
            <div class="status">
                <h3>Camera Information</h3>
                <p><strong>Type:</strong> {camera_manager.camera_type or 'Not initialized'}</p>
                <p><strong>Status:</strong> {'🟢 Active' if camera_manager.running else '🔴 Inactive'}</p>
            </div>
            <div class="video-container">
                <img src="/video_feed" alt="Live Camera Feed">
            </div>
            <div class="camera-info">
                <p><strong>API Endpoints:</strong></p>
                <ul>
                    <li><code>/video_feed</code> - MJPEG видео поток</li>
                    <li><code>/status</code> - Статус камеры (JSON)</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/video_feed')
def video_feed():
    """MJPEG видео поток"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    """Статус камеры в формате JSON"""
    from flask import jsonify
    return jsonify({
        'camera_type': camera_manager.camera_type,
        'running': camera_manager.running,
        'status': 'active' if camera_manager.running else 'inactive'
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'camera': camera_manager.camera_type}

def main():
    """Главная функция запуска сервиса"""
    logger.info("🚀 Запуск Camera Service...")
    
    if not camera_manager.initialize():
        logger.error("❌ Не удалось инициализировать камеру")
        return
    
    # Обработка завершения
    import signal
    
    def signal_handler(sig, frame):
        logger.info("\n🛑 Остановка сервиса...")
        camera_manager.release()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("🌐 Запуск Flask сервера на http://0.0.0.0:8000")
        app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"Ошибка запуска сервера: {e}")
    finally:
        camera_manager.release()
        logger.info("✅ Сервис остановлен")

if __name__ == '__main__':
    main()

