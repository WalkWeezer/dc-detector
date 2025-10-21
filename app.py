import cv2
import base64
from ultralytics import YOLO
from flask import Flask, Response, render_template

app = Flask(__name__)

# Загружаем модель, обученную на огне
model = YOLO('bestfire.pt')  # Ваша модель для детекции огня

def generate_frames():
    cap = cv2.VideoCapture(0)
    
    while True:
        success, frame = cap.read()
        if not success:
            break
        
        # Детекция с фильтрацией только огня
        results = model(frame, conf=0.4)
        
        # Создаем аннотированный кадр
        annotated_frame = frame.copy()
        fire_detected = False
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                class_name = model.names[cls]
                
                # Показываем только огонь
                if class_name.lower() in ['fire', 'flame']:
                    fire_detected = True
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    
                    # Красная рамка для огня
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    label = f"FIRE {conf:.2f}"
                    cv2.putText(annotated_frame, label, (x1, y1-10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Добавляем статус обнаружения
        status_text = "FIRE DETECTED!" if fire_detected else "Monitoring..."
        status_color = (0, 0, 255) if fire_detected else (0, 255, 0)
        cv2.putText(annotated_frame, status_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)

        # Кодируем кадр
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fire Detection System</title>
        <style>
            body { margin: 0; padding: 20px; background: #1a1a1a; color: white; font-family: Arial; }
            .container { max-width: 900px; margin: 0 auto; }
            h1 { color: #ff4444; text-align: center; }
            .video-container { text-align: center; margin: 20px 0; }
            img { max-width: 100%; border: 3px solid #333; border-radius: 10px; }
            .warning { background: #ff4444; padding: 10px; border-radius: 5px; text-align: center; display: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔥 Fire Detection System</h1>
            <div class="warning" id="warning">🚨 FIRE DETECTED! 🚨</div>
            <div class="video-container">
                <img src="/video_feed" alt="Live Fire Detection">
            </div>
        </div>
        
        <script>
            // Можно добавить JavaScript для звуковых оповещений
            function playAlert() {
                var audio = new Audio('data:audio/wav;base64,XXX'); // base64 encoded alert sound
                audio.play();
            }
        </script>
    </body>
    </html>
    """

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)