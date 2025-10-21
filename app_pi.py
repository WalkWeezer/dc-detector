import cv2
import base64
import time
import threading
from ultralytics import YOLO
from flask import Flask, Response, render_template, jsonify
from picamera2 import Picamera2
import numpy as np
import psutil
import os
from config_pi import config

app = Flask(__name__)

# Применяем оптимизации для Raspberry Pi
config.optimize_for_pi()

# Загружаем модель, обученную на огне
model = YOLO(config.MODEL['path'])

# Глобальные переменные для камеры
camera = None
camera_lock = threading.Lock()
last_frame = None
fire_detected = False
detection_count = 0

def initialize_camera():
    """Инициализация PiCamera"""
    global camera
    try:
        camera = Picamera2()
        
        # Конфигурация для оптимальной производительности
        camera_config = camera.create_still_configuration(
            main={"size": (config.CAMERA['width'], config.CAMERA['height']), 
                  "format": config.CAMERA['format']},
            lores={"size": (config.DETECTION['resize_for_detection'][0], 
                           config.DETECTION['resize_for_detection'][1]), 
                   "format": "YUV420"}
        )
        camera.configure(camera_config)
        camera.start()
        print(f"✅ PiCamera инициализирована: {config.CAMERA['width']}x{config.CAMERA['height']} @ {config.CAMERA['fps']}fps")
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации PiCamera: {e}")
        return False

def capture_frame():
    """Захват кадра с PiCamera"""
    global camera, last_frame
    try:
        with camera_lock:
            if camera is not None:
                # Захватываем кадр
                frame = camera.capture_array()
                # Конвертируем из RGB в BGR для OpenCV
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                last_frame = frame
                return frame
    except Exception as e:
        print(f"Ошибка захвата кадра: {e}")
    return None

def detect_fire_optimized(frame):
    """Оптимизированная детекция огня для Raspberry Pi"""
    global fire_detected, detection_count
    
    if frame is None:
        return frame, False
    
    try:
        # Уменьшаем размер кадра для ускорения обработки
        small_frame = cv2.resize(frame, config.DETECTION['resize_for_detection'])
        
        # Детекция с настраиваемым порогом уверенности
        results = model(small_frame, 
                       conf=config.DETECTION['confidence_threshold'], 
                       verbose=config.MODEL['verbose'])
        
        fire_found = False
        annotated_frame = frame.copy()
        
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    cls = int(box.cls[0])
                    class_name = model.names[cls]
                    
                    # Показываем только огонь
                    if class_name.lower() in ['fire', 'flame']:
                        fire_found = True
                        # Масштабируем координаты обратно к исходному размеру
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        x1, y1, x2, y2 = x1*2, y1*2, x2*2, y2*2  # Масштабируем обратно
                        conf = float(box.conf[0])
                        
                        # Красная рамка для огня
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                        label = f"FIRE {conf:.2f}"
                        cv2.putText(annotated_frame, label, (x1, y1-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Обновляем статус
        if fire_found:
            detection_count += 1
            fire_detected = True
        else:
            fire_detected = False
        
        return annotated_frame, fire_found
        
    except Exception as e:
        print(f"Ошибка в детекции: {e}")
        return frame, False

def generate_frames():
    """Генератор кадров для видеопотока"""
    global last_frame, fire_detected
    
    while True:
        try:
            # Захватываем кадр
            frame = capture_frame()
            
            if frame is not None:
                # Детекция огня
                annotated_frame, fire_found = detect_fire_optimized(frame)
                
                # Добавляем информацию о системе
                cpu_percent = psutil.cpu_percent()
                memory_percent = psutil.virtual_memory().percent
                temp = get_cpu_temperature()
                
                # Статус обнаружения
                status_text = "🔥 FIRE DETECTED!" if fire_found else "🟢 Monitoring..."
                status_color = (0, 0, 255) if fire_found else (0, 255, 0)
                cv2.putText(annotated_frame, status_text, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)
                
                # Системная информация
                info_text = f"CPU: {cpu_percent:.1f}% | RAM: {memory_percent:.1f}% | Temp: {temp:.1f}°C"
                cv2.putText(annotated_frame, info_text, (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Кодируем кадр с оптимизацией для Raspberry Pi
                ret, buffer = cv2.imencode('.jpg', annotated_frame, 
                                         [cv2.IMWRITE_JPEG_QUALITY, config.WEB['video_quality']])
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                # Если кадр не получен, ждем немного
                time.sleep(0.1)
                
        except Exception as e:
            print(f"Ошибка в генераторе кадров: {e}")
            time.sleep(0.1)

def get_cpu_temperature():
    """Получение температуры CPU Raspberry Pi"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read()) / 1000.0
        return temp
    except:
        return 0.0

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Raspberry Pi Fire Detection System</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); 
                color: white; 
                font-family: 'Segoe UI', Arial, sans-serif;
                min-height: 100vh;
            }
            .container { 
                max-width: 1000px; 
                margin: 0 auto; 
            }
            h1 { 
                color: #ff4444; 
                text-align: center; 
                margin-bottom: 20px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
            }
            .video-container { 
                text-align: center; 
                margin: 20px 0; 
                position: relative;
            }
            img { 
                max-width: 100%; 
                border: 3px solid #333; 
                border-radius: 15px; 
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            }
            .warning { 
                background: linear-gradient(45deg, #ff4444, #ff6666); 
                padding: 15px; 
                border-radius: 10px; 
                text-align: center; 
                display: none;
                animation: pulse 1s infinite;
                box-shadow: 0 4px 15px rgba(255, 68, 68, 0.3);
            }
            .status-panel {
                background: rgba(255, 255, 255, 0.1);
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                backdrop-filter: blur(10px);
            }
            .status-item {
                display: flex;
                justify-content: space-between;
                margin: 10px 0;
                padding: 10px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 5px;
            }
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.05); }
                100% { transform: scale(1); }
            }
            .controls {
                text-align: center;
                margin: 20px 0;
            }
            .btn {
                background: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                margin: 5px;
                font-size: 16px;
            }
            .btn:hover {
                background: #45a049;
            }
            .btn.danger {
                background: #f44336;
            }
            .btn.danger:hover {
                background: #da190b;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔥 Raspberry Pi Fire Detection System</h1>
            
            <div class="warning" id="warning">
                🚨 FIRE DETECTED! 🚨<br>
                <strong>IMMEDIATE ACTION REQUIRED!</strong>
            </div>
            
            <div class="status-panel">
                <h3>System Status</h3>
                <div class="status-item">
                    <span>Camera Status:</span>
                    <span id="camera-status">Initializing...</span>
                </div>
                <div class="status-item">
                    <span>Detection Status:</span>
                    <span id="detection-status">Monitoring...</span>
                </div>
                <div class="status-item">
                    <span>System Temperature:</span>
                    <span id="temperature">Loading...</span>
                </div>
            </div>
            
            <div class="video-container">
                <img src="/video_feed" alt="Live Fire Detection" id="video-feed">
            </div>
            
            <div class="controls">
                <button class="btn" onclick="toggleDetection()">Toggle Detection</button>
                <button class="btn danger" onclick="emergencyStop()">Emergency Stop</button>
            </div>
        </div>
        
        <script>
            let detectionActive = true;
            let fireDetected = false;
            
            // Обновление статуса каждые 2 секунды
            setInterval(updateStatus, 2000);
            
            function updateStatus() {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('camera-status').textContent = data.camera_status;
                        document.getElementById('detection-status').textContent = data.detection_status;
                        document.getElementById('temperature').textContent = data.temperature + '°C';
                        
                        // Обновляем предупреждение
                        const warning = document.getElementById('warning');
                        if (data.fire_detected && detectionActive) {
                            warning.style.display = 'block';
                            fireDetected = true;
                            playAlert();
                        } else {
                            warning.style.display = 'none';
                            fireDetected = false;
                        }
                    })
                    .catch(error => {
                        console.error('Ошибка получения статуса:', error);
                    });
            }
            
            function toggleDetection() {
                detectionActive = !detectionActive;
                const btn = event.target;
                btn.textContent = detectionActive ? 'Pause Detection' : 'Resume Detection';
                btn.style.background = detectionActive ? '#4CAF50' : '#ff9800';
            }
            
            function emergencyStop() {
                if (confirm('Are you sure you want to stop the fire detection system?')) {
                    detectionActive = false;
                    alert('Fire detection system stopped!');
                }
            }
            
            function playAlert() {
                if (fireDetected) {
                    // Создаем звуковой сигнал
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const oscillator = audioContext.createOscillator();
                    const gainNode = audioContext.createGain();
                    
                    oscillator.connect(gainNode);
                    gainNode.connect(audioContext.destination);
                    
                    oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
                    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                    
                    oscillator.start();
                    oscillator.stop(audioContext.currentTime + 0.5);
                }
            }
            
            // Обработка ошибок загрузки изображения
            document.getElementById('video-feed').onerror = function() {
                console.log('Ошибка загрузки видеопотока');
            };
        </script>
    </body>
    </html>
    """

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    """API для получения статуса системы"""
    global fire_detected, camera
    
    try:
        temp = get_cpu_temperature()
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        
        return jsonify({
            'camera_status': 'Active' if camera is not None else 'Error',
            'detection_status': 'FIRE DETECTED!' if fire_detected else 'Monitoring...',
            'fire_detected': fire_detected,
            'temperature': round(temp, 1),
            'cpu_percent': round(cpu_percent, 1),
            'memory_percent': round(memory_percent, 1),
            'detection_count': detection_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/detection_count')
def get_detection_count():
    """API для получения количества обнаружений"""
    return jsonify({'count': detection_count})

if __name__ == '__main__':
    print("🔥 Запуск Raspberry Pi Fire Detection System...")
    
    # Инициализируем камеру
    if initialize_camera():
        print("✅ Система готова к работе")
        print("🌐 Веб-интерфейс доступен по адресу: http://0.0.0.0:5000")
        print("📱 Для доступа с других устройств используйте IP адрес Raspberry Pi")
        
        try:
            app.run(host=config.WEB['host'], 
                   port=config.WEB['port'], 
                   debug=config.WEB['debug'], 
                   threaded=config.WEB['threaded'])
        except KeyboardInterrupt:
            print("\n🛑 Остановка системы...")
        finally:
            if camera:
                camera.stop()
                camera.close()
                print("✅ Камера отключена")
    else:
        print("❌ Не удалось инициализировать камеру. Проверьте подключение PiCamera.")
