import time
from picamera2 import Picamera2
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
import threading

class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/stream.mjpeg':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    # Захватываем кадр
                    buffer = BytesIO()
                    picam2.capture_file(buffer, format='jpeg')
                    buffer.seek(0)
                    
                    # Отправляем кадр
                    self.wfile.write(b'--frame\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(buffer.getbuffer().nbytes))
                    self.end_headers()
                    self.wfile.write(buffer.getvalue())
                    self.wfile.write(b'\r\n')
                    
                    time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                print(f"Stream closed: {e}")
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''
                <html>
                    <body>
                        <h1>Raspberry Pi Camera Stream</h1>
                        <img src="/stream.mjpeg" width="1280" height="720">
                    </body>
                </html>
            ''')

# Настройка камеры
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (1280, 720)})
picam2.configure(config)
picam2.start()

# Запуск HTTP сервера в отдельном потоке
def run_server():
    server = HTTPServer(('0.0.0.0', 8080), StreamingHandler)
    print("Сервер запущен на http://localhost:8080")
    server.serve_forever()

server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

try:
    print("Камера запущена. Откройте http://localhost:8080 в браузере")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Останавливаем...")
    picam2.stop()
