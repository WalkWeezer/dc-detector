#!/usr/bin/env python3
"""Detection Service - только видеострим"""

import os
import time
import threading
from io import BytesIO
from typing import Optional
from flask import Flask, Response

app = Flask(__name__)

# Попытка импортировать picamera2 (доступно только на Raspberry Pi)
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
    print("✅ picamera2 успешно импортирован")
except ImportError as e:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None
    print(f"⚠️ Не удалось импортировать picamera2: {e}")
    print("💡 Убедитесь, что python3-picamera2 установлен в контейнере")

# Глобальные переменные для камеры и буферизации кадров
picam2: Optional[Picamera2] = None
current_frame: Optional[bytes] = None
frame_lock = threading.Lock()
capture_thread: Optional[threading.Thread] = None


def capture_frames_loop():
    """Поток для захвата кадров (улучшенная версия с буферизацией)"""
    global picam2, current_frame
    
    if picam2 is None:
        return
    
    print("🎬 Запуск потока захвата кадров...")
    
    try:
        while True:
            try:
                # Захватываем кадр
                buffer = BytesIO()
                picam2.capture_file(buffer, format='jpeg')
                jpeg_data = buffer.getvalue()
                
                # Обновляем буфер кадра
                with frame_lock:
                    current_frame = jpeg_data
                
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                print(f"⚠️ Ошибка при захвате кадра: {e}")
                time.sleep(0.1)
                
    except Exception as e:
        print(f"❌ Критическая ошибка в потоке захвата: {e}")


def init_picamera2():
    """Инициализирует Picamera2 с буферизацией кадров"""
    global picam2, capture_thread
    
    if not PICAMERA2_AVAILABLE:
        print("⚠️ picamera2 не доступен")
        return False
    
    try:
        print("🎥 Инициализация Picamera2...")
        picam2 = Picamera2()
        print("✅ Picamera2 объект создан")
        
        config = picam2.create_preview_configuration(
            main={"size": (1280, 720)},
            encode="main"
        )
        print("✅ Конфигурация создана")
        
        picam2.configure(config)
        print("✅ Конфигурация применена")
        
        picam2.start()
        print("✅ Picamera2 запущен")
        
        # Даем время на инициализацию
        time.sleep(2.0)
        
        # Проверяем, что камера работает
        try:
            buffer = BytesIO()
            picam2.capture_file(buffer, format='jpeg')
            buffer.seek(0)
            if buffer.getbuffer().nbytes > 0:
                print(f"✅ Тестовый кадр захвачен: {buffer.getbuffer().nbytes} байт")
                
                # Запускаем поток захвата кадров
                capture_thread = threading.Thread(target=capture_frames_loop, daemon=True)
                capture_thread.start()
                print("✅ Поток захвата кадров запущен")
                
                print("✅ Picamera2 полностью инициализирован")
                return True
            else:
                print("⚠️ Тестовый кадр пустой")
                return False
        except Exception as e:
            print(f"⚠️ Не удалось захватить тестовый кадр: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при инициализации Picamera2: {e}")
        import traceback
        traceback.print_exc()
        return False


def capture_frame_jpeg() -> Optional[bytes]:
    """Получает последний захваченный кадр из буфера"""
    global current_frame
    with frame_lock:
        return current_frame


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
    """Сырой MJPEG поток с буферизацией кадров"""
    if picam2 is None:
        return Response('Camera not available', status=503)
    
    def mjpeg_generator():
        """Генератор MJPEG потока с использованием буферизованных кадров"""
        boundary = b'--frame'
        
        while True:
            try:
                # Получаем кадр из буфера
                frame = capture_frame_jpeg()
                if frame is not None:
                    # Отправляем кадр
                    yield (
                        boundary + b"\r\n"
                        + b'Content-Type: image/jpeg\r\n'
                        + b'Content-Length: ' + str(len(frame)).encode() + b"\r\n\r\n"
                        + frame + b"\r\n"
                    )
                    time.sleep(0.033)  # ~30 FPS
                else:
                    # Если кадр еще не готов, ждем немного
                    time.sleep(0.01)
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
    print("🚀 Запуск Detection Service...")
    print(f"PICAMERA2_AVAILABLE: {PICAMERA2_AVAILABLE}")
    
    # Инициализируем Picamera2 (рабочий скрипт)
    if PICAMERA2_AVAILABLE:
        print("Попытка инициализации Picamera2...")
        success = init_picamera2()
        if success:
            print("✅ Камера успешно инициализирована")
        else:
            print("⚠️ Не удалось инициализировать камеру")
    else:
        print("⚠️ Picamera2 не доступен (не на Raspberry Pi или не установлен)")
    
    debug_enabled = str(os.environ.get('DEBUG', '0')).lower() in ('1', 'true', 'yes')
    print(f"🌐 Запуск Flask сервера на 0.0.0.0:8001 (debug={debug_enabled})")
    try:
        app.run(host='0.0.0.0', port=8001, debug=debug_enabled, threaded=True)
    finally:
        print("🛑 Остановка сервиса...")
        stop_picamera2()


if __name__ == '__main__':
    main()
