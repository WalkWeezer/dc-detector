#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detection Service - только видеострим"""

import os
import sys
import time
import threading
from io import BytesIO
from typing import Optional
from flask import Flask, Response

# Настройка кодировки для Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Для старых версий Python
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

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
    print("💡 Будет использована веб-камера через OpenCV")

# Попытка импортировать OpenCV для веб-камеры
try:
    import cv2
    CV2_AVAILABLE = True
    print("✅ OpenCV успешно импортирован")
except ImportError as e:
    CV2_AVAILABLE = False
    cv2 = None
    print(f"⚠️ Не удалось импортировать OpenCV: {e}")
    print("💡 Установите opencv-python: pip install opencv-python")

# Глобальные переменные для камеры и буферизации кадров
picam2: Optional[Picamera2] = None
webcam: Optional[cv2.VideoCapture] = None
camera_type: Optional[str] = None  # 'picamera2' или 'webcam'
current_frame: Optional[bytes] = None
frame_lock = threading.Lock()
capture_thread: Optional[threading.Thread] = None


def capture_frames_loop():
    """Поток для захвата кадров (улучшенная версия с буферизацией)"""
    global picam2, webcam, camera_type, current_frame
    
    if camera_type == 'picamera2' and picam2 is None:
        return
    if camera_type == 'webcam' and webcam is None:
        return
    
    print("🎬 Запуск потока захвата кадров...")
    
    try:
        while True:
            try:
                jpeg_data = None
                
                if camera_type == 'picamera2' and picam2 is not None:
                    # Захватываем кадр с Picamera2
                    buffer = BytesIO()
                    picam2.capture_file(buffer, format='jpeg')
                    jpeg_data = buffer.getvalue()
                    
                elif camera_type == 'webcam' and webcam is not None:
                    # Захватываем кадр с веб-камеры
                    ret, frame = webcam.read()
                    if ret:
                        # Конвертируем в JPEG
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        jpeg_data = buffer.tobytes()
                
                if jpeg_data:
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
    global picam2, capture_thread, camera_type
    
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
                
                # Устанавливаем тип камеры
                camera_type = 'picamera2'
                
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


def init_webcam():
    """Инициализирует веб-камеру через OpenCV"""
    global webcam, capture_thread, camera_type
    
    if not CV2_AVAILABLE:
        print("⚠️ OpenCV не доступен")
        return False
    
    try:
        print("🎥 Инициализация веб-камеры...")
        # Пытаемся открыть камеру (обычно индекс 0)
        webcam = cv2.VideoCapture(0)
        
        if not webcam.isOpened():
            print("⚠️ Не удалось открыть веб-камеру")
            webcam = None
            return False
        
        # Устанавливаем разрешение
        webcam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        print("✅ Веб-камера открыта")
        
        # Даем время на инициализацию
        time.sleep(1.0)
        
        # Проверяем, что камера работает
        ret, frame = webcam.read()
        if ret and frame is not None:
            print(f"✅ Тестовый кадр захвачен: {frame.shape}")
            
            # Устанавливаем тип камеры
            camera_type = 'webcam'
            
            # Запускаем поток захвата кадров
            capture_thread = threading.Thread(target=capture_frames_loop, daemon=True)
            capture_thread.start()
            print("✅ Поток захвата кадров запущен")
            
            print("✅ Веб-камера полностью инициализирована")
            return True
        else:
            print("⚠️ Не удалось захватить тестовый кадр с веб-камеры")
            webcam.release()
            webcam = None
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при инициализации веб-камеры: {e}")
        import traceback
        traceback.print_exc()
        if webcam is not None:
            webcam.release()
            webcam = None
        return False


def capture_frame_jpeg() -> Optional[bytes]:
    """Получает последний захваченный кадр из буфера"""
    global current_frame
    with frame_lock:
        return current_frame


def stop_picamera2():
    """Останавливает Picamera2"""
    global picam2, camera_type
    if picam2 is not None:
        try:
            picam2.stop()
            picam2 = None
            camera_type = None
            print("✅ Picamera2 остановлен")
        except Exception as e:
            print(f"⚠️ Ошибка при остановке Picamera2: {e}")


def stop_webcam():
    """Останавливает веб-камеру"""
    global webcam, camera_type
    if webcam is not None:
        try:
            webcam.release()
            webcam = None
            camera_type = None
            print("✅ Веб-камера остановлена")
        except Exception as e:
            print(f"⚠️ Ошибка при остановке веб-камеры: {e}")


def stop_camera():
    """Останавливает любую активную камеру"""
    stop_picamera2()
    stop_webcam()


@app.get('/video_feed_raw')
def video_feed_raw():
    """Сырой MJPEG поток с буферизацией кадров"""
    if camera_type is None or (picam2 is None and webcam is None):
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
    camera_available = camera_type is not None and (picam2 is not None or webcam is not None)
    return {
        'status': 'ok',
        'camera_available': camera_available,
        'camera_type': camera_type
    }


def main():
    """Главная функция"""
    print("🚀 Запуск Detection Service...")
    print(f"PICAMERA2_AVAILABLE: {PICAMERA2_AVAILABLE}")
    print(f"CV2_AVAILABLE: {CV2_AVAILABLE}")
    
    # Сначала пытаемся инициализировать Picamera2
    camera_initialized = False
    if PICAMERA2_AVAILABLE:
        print("📷 Попытка инициализации Picamera2...")
        if init_picamera2():
            print("✅ Picamera2 успешно инициализирован")
            camera_initialized = True
        else:
            print("⚠️ Не удалось инициализировать Picamera2")
    
    # Если Picamera2 не удалось, пытаемся веб-камеру
    if not camera_initialized and CV2_AVAILABLE:
        print("📷 Попытка инициализации веб-камеры...")
        if init_webcam():
            print("✅ Веб-камера успешно инициализирована")
            camera_initialized = True
        else:
            print("⚠️ Не удалось инициализировать веб-камеру")
    
    if not camera_initialized:
        print("⚠️ ВНИМАНИЕ: Ни одна камера не инициализирована!")
        print("💡 Убедитесь, что:")
        print("   - На Raspberry Pi установлен picamera2, или")
        print("   - Установлен opencv-python и подключена веб-камера")
    
    # Получаем порт из переменной окружения или используем 8001 по умолчанию
    port = int(os.environ.get('PORT', 8001))
    debug_enabled = str(os.environ.get('DEBUG', '0')).lower() in ('1', 'true', 'yes')
    
    print(f"🌐 Запуск Flask сервера на http://localhost:{port}")
    print(f"📹 Видео поток доступен по адресу: http://localhost:{port}/video_feed_raw")
    print(f"🏥 Health check: http://localhost:{port}/health")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=debug_enabled, threaded=True)
    finally:
        print("🛑 Остановка сервиса...")
        stop_camera()


if __name__ == '__main__':
    main()
