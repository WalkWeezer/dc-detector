import cv2
import base64
import eventlet
import socketio
from ultralytics import YOLO
from flask import Flask, render_template

# Создаем сервер
sio = socketio.Server(async_mode='eventlet')
app = Flask(__name__)
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

# Загружаем модель YOLO
model = YOLO('yolov8n.pt')

def video_stream():
    """Потоковая передача видео"""
    cap = cv2.VideoCapture(0)
    
    while True:
        success, frame = cap.read()
        if not success:
            break
        
        # Обработка кадра YOLO
        results = model(frame)
        annotated_frame = results[0].plot()
        
        # Кодируем кадр в JPEG и base64
        ret, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Отправляем кадр всем подключенным клиентам
        sio.emit('video_frame', {'image': f'data:image/jpeg;base64,{frame_base64}'})
        
        eventlet.sleep(0.03)  # ~30 FPS

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>YOLO Fire Detection - WebSocket</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container {
                max-width: 900px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }
            h1 {
                text-align: center;
                color: #333;
                margin-bottom: 30px;
            }
            .video-container {
                text-align: center;
                margin: 20px 0;
            }
            #videoFeed {
                max-width: 100%;
                border: 3px solid #333;
                border-radius: 10px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
            .stats {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                text-align: center;
            }
            .connection-status {
                padding: 10px;
                border-radius: 5px;
                margin: 10px 0;
                text-align: center;
                font-weight: bold;
            }
            .connected {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .disconnected {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔥 YOLO Fire Detection - Live Web Stream</h1>
            
            <div class="connection-status" id="status">Подключение...</div>
            
            <div class="stats">
                <p>Детекция объектов в реальном времени через браузер</p>
            </div>
            
            <div class="video-container">
                <img id="videoFeed" src="" alt="Live Video Feed">
            </div>
            
            <div class="stats" id="detectionInfo">
                Ожидание данных...
            </div>
        </div>

        <script>
            const socket = io();
            const videoFeed = document.getElementById('videoFeed');
            const statusDiv = document.getElementById('status');
            const detectionInfo = document.getElementById('detectionInfo');

            socket.on('connect', function() {
                statusDiv.textContent = '✅ Подключено к серверу';
                statusDiv.className = 'connection-status connected';
            });

            socket.on('disconnect', function() {
                statusDiv.textContent = '❌ Отключено от сервера';
                statusDiv.className = 'connection-status disconnected';
            });

            socket.on('video_frame', function(data) {
                videoFeed.src = data.image;
                
                // Можно добавить дополнительную информацию о детекции
                if (data.detections) {
                    detectionInfo.textContent = `Обнаружено объектов: ${data.detections.length}`;
                }
            });

            // Обработка ошибок
            socket.on('connect_error', function(error) {
                statusDiv.textContent = '❌ Ошибка подключения: ' + error;
                statusDiv.className = 'connection-status disconnected';
            });
        </script>
    </body>
    </html>
    """

@sio.event
def connect(sid, environ):
    print('Клиент подключен:', sid)

@sio.event
def disconnect(sid):
    print('Клиент отключен:', sid)

if __name__ == '__main__':
    # Запускаем поток обработки видео в фоне
    eventlet.spawn(video_stream)
    # Запускаем сервер
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), app)