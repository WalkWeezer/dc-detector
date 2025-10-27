#!/usr/bin/env python3
"""
Detection Service - Сервис детекции огня на видеопотоке
Использует YOLO для анализа видеопотока с camera-service
"""

import cv2
import numpy as np
import logging
import threading
import time
from flask import Flask, Response, jsonify, render_template_string
from ultralytics import YOLO
import requests
from typing import Optional, Dict, List
import io

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Конфигурация
CAMERA_SERVICE_URL = "http://localhost:8000/video_feed"
MODEL_PATH = "../bestfire.pt"
CONFIDENCE_THRESHOLD = 0.5

# Глобальное состояние
detection_results = {
    'detected': False,
    'count': 0,
    'confidence': 0.0,
    'last_detection': None,
    'frame_with_detections': None
}

class DetectionService:
    """Сервис для детекции на видеопотоке"""
    
    def __init__(self, model_path: str):
        """Инициализация сервиса"""
        logger.info(f"🔍 Загрузка модели YOLO: {model_path}")
        try:
            self.model = YOLO(model_path)
            logger.info("✅ Модель загружена успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели: {e}")
            raise
        
        self.running = False
        self.thread = None
        
    def start(self):
        """Запуск сервиса детекции"""
        if self.running:
            logger.warning("Сервис уже запущен")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.thread.start()
        logger.info("🚀 Сервис детекции запущен")
    
    def stop(self):
        """Остановка сервиса"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("🛑 Сервис детекции остановлен")
    
    def _detection_loop(self):
        """Основной цикл детекции"""
        global detection_results
        
        try:
            # Подключение к видеопотоку
            response = requests.get(CAMERA_SERVICE_URL, stream=True)
            response.raise_for_status()
            
            logger.info(f"✅ Подключено к camera-service: {CAMERA_SERVICE_URL}")
            
            bytes_buffer = b''
            
            while self.running:
                try:
                    chunk = response.raw.read(1024)
                    if not chunk:
                        logger.warning("Пустой чанк от камеры")
                        time.sleep(0.1)
                        continue
                    
                    bytes_buffer += chunk
                    a = bytes_buffer.find(b'\xff\xd8')
                    b = bytes_buffer.find(b'\xff\xd9')
                    
                    if a != -1 and b != -1:
                        # Найден полный JPEG кадр
                        jpg = bytes_buffer[a:b+2]
                        bytes_buffer = bytes_buffer[b+2:]
                        
                        # Декодируем изображение
                        nparr = np.frombuffer(jpg, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            # Применяем детекцию
                            self._detect_fire(frame)
                
                except Exception as e:
                    logger.error(f"Ошибка обработки кадра: {e}")
                    time.sleep(0.1)
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Не удалось подключиться к camera-service: {e}")
            detection_results['error'] = str(e)
        except Exception as e:
            logger.error(f"Критическая ошибка в detection loop: {e}")
        finally:
            self.running = False
    
    def _detect_fire(self, frame: np.ndarray):
        """Детекция огня на кадре"""
        global detection_results
        
        try:
            # Применяем модель YOLO
            results = self.model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
            
            # Обрабатываем результаты
            detections = []
            frame_with_detections = frame.copy()
            
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    # Извлекаем координаты и уверенность
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    
                    # Рисуем bounding box
                    cv2.rectangle(frame_with_detections, 
                                (int(x1), int(y1)), 
                                (int(x2), int(y2)), 
                                (0, 0, 255), 2)
                    
                    # Добавляем метку
                    label = f"Fire: {confidence:.2f}"
                    cv2.putText(frame_with_detections, label, 
                              (int(x1), int(y1) - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
                    detections.append({
                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                        'confidence': confidence,
                        'class_id': class_id
                    })
            
            # Обновляем глобальные результаты
            detection_results['detected'] = len(detections) > 0
            detection_results['count'] = len(detections)
            detection_results['confidence'] = max([d['confidence'] for d in detections]) if detections else 0.0
            detection_results['last_detection'] = time.time()
            detection_results['detections'] = detections
            
            # Сохраняем кадр с детекциями для отображения
            if frame_with_detections is not None:
                _, buffer = cv2.imencode('.jpg', frame_with_detections, 
                                        [cv2.IMWRITE_JPEG_QUALITY, 85])
                detection_results['frame_with_detections'] = buffer.tobytes()
        
        except Exception as e:
            logger.error(f"Ошибка детекции: {e}")


# Инициализация сервиса
detection_service = DetectionService(MODEL_PATH)

@app.route('/')
def index():
    """Главная страница с результатами детекции"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Detection Service</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                margin: 0; 
                padding: 10px; 
                background: #1a1a1a; 
                color: white; 
                font-family: Arial, sans-serif;
            }}
            .container {{ 
                max-width: 600px; 
                margin: 10px auto; 
            }}
            h1 {{ 
                color: #ff4444; 
                text-align: center; 
                font-size: 18px;
                margin: 5px 0;
            }}
            .status {{ 
                background: rgba(255,255,255,0.1); 
                padding: 10px; 
                border-radius: 8px; 
                margin: 10px 0;
                font-size: 12px;
            }}
            .alert {{ 
                background: rgba(255, 68, 68, 0.3); 
                border: 2px solid #ff4444; 
                padding: 10px; 
                border-radius: 8px; 
                margin: 10px 0;
                font-size: 14px;
            }}
            .safe {{ 
                background: rgba(76, 175, 80, 0.3); 
                border: 2px solid #4CAF50; 
                padding: 10px; 
                border-radius: 8px; 
                margin: 10px 0;
                font-size: 14px;
            }}
            .detection-image {{
                width: 320px;
                height: 240px;
                object-fit: contain;
                border: 2px solid #333;
                border-radius: 8px;
                margin: 10px 0;
            }}
            .info-grid {{
                display: flex;
                flex-direction: column;
                gap: 8px;
                margin: 10px 0;
            }}
            .info-box {{
                background: rgba(255,255,255,0.05);
                padding: 8px;
                border-radius: 8px;
                font-size: 12px;
            }}
            .metric {{
                font-size: 1.5em;
                font-weight: bold;
                color: #4CAF50;
            }}
            .metric.danger {{
                color: #ff4444;
            }}
        </style>
        <script>
            setInterval(function() {{
                location.reload();
            }}, 2000);
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🔥 Detection Service</h1>
            
            <div class="status">
                <h3>Статус детекции</h3>
                <p><strong>Сервис:</strong> {'🟢 Активен' if detection_service.running else '🔴 Остановлен'}</p>
                <p><strong>Камера:</strong> {CAMERA_SERVICE_URL}</p>
            </div>
            
            {'<div class="alert"><h2>⚠️ ОГОНЬ ОБНАРУЖЕН!</h2></div>' if detection_results.get('detected') else '<div class="safe"><h2>✅ Огня не обнаружено</h2></div>'}
            
            <div class="info-grid">
                <div class="info-box">
                    <h4>Обнаружено</h4>
                    <div class="metric {'danger' if detection_results.get('count', 0) > 0 else ''}">
                        {detection_results.get('count', 0)}
                    </div>
                </div>
                <div class="info-box">
                    <h4>Уверенность</h4>
                    <div class="metric {'danger' if detection_results.get('confidence', 0) > 0.5 else ''}">
                        {detection_results.get('confidence', 0):.2f}
                    </div>
                </div>
                <div class="info-box">
                    <h4>Последнее обновление</h4>
                    <p>{time.strftime('%H:%M:%S', time.localtime(detection_results.get('last_detection'))) if detection_results.get('last_detection') else 'N/A'}</p>
                </div>
            </div>
            
            {f'<img src="/detection_frame" alt="Detection" class="detection-image">' if detection_results.get('frame_with_detections') else ''}
            
            <div class="status">
                <h3>API Endpoints</h3>
                <ul>
                    <li><code>GET /</code> - Веб-интерфейс</li>
                    <li><code>GET /api/detection</code> - JSON статус детекции</li>
                    <li><code>GET /detection_frame</code> - Последний кадр с детекциями</li>
                    <li><code>GET /health</code> - Health check</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/api/detection')
def api_detection():
    """API для получения статуса детекции"""
    return jsonify({
        'detected': detection_results.get('detected', False),
        'count': detection_results.get('count', 0),
        'confidence': detection_results.get('confidence', 0.0),
        'last_detection': detection_results.get('last_detection'),
        'detections': detection_results.get('detections', [])
    })

@app.route('/detection_frame')
def detection_frame():
    """Получение последнего кадра с детекциями"""
    frame = detection_results.get('frame_with_detections')
    
    if frame is None:
        return Response("No frame available", status=404, mimetype='text/plain')
    
    return Response(frame, mimetype='image/jpeg')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'running': detection_service.running,
        'camera_service': CAMERA_SERVICE_URL
    })

def main():
    """Главная функция запуска сервиса"""
    logger.info("🚀 Запуск Detection Service...")
    
    try:
        # Запускаем сервис детекции
        detection_service.start()
        
        # Обработка сигналов завершения
        import signal
        
        def signal_handler(sig, frame):
            logger.info("\n🛑 Остановка сервиса...")
            detection_service.stop()
            exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Запускаем Flask сервер
        logger.info("🌐 Запуск Flask сервера на http://0.0.0.0:8001")
        app.run(host='0.0.0.0', port=8001, debug=False, threaded=True)
    
    except Exception as e:
        logger.error(f"Ошибка запуска сервиса: {e}")
    finally:
        detection_service.stop()
        logger.info("✅ Сервис остановлен")

if __name__ == '__main__':
    main()

