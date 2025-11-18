#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detection Service - простой видеострим как в рабочем скрипте"""

import os
import sys
import time
import threading
import json
import base64
import random
import string
from io import BytesIO
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import numpy as np

# Настройка кодировки для Windows (должно быть в самом начале)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Импорт для создания GIF
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL/Pillow не доступен, автоматическое сохранение GIF будет отключено")

# Импорты для трекинга и моделей
try:
    from tracking.sort_tracker import SortTracker
    from tracking.trackers import (
        update_tracker_cache,
        get_active_trackers,
        get_tracker_frames,
        clear_tracker_cache,
        crop_frame_for_tracker,
        get_tracker_by_id
    )
    from models.manager import ModelManager
    from detection.inference import InferenceEngine
    TRACKING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Не удалось импортировать модули трекинга: {e}")
    TRACKING_AVAILABLE = False
    SortTracker = None
    ModelManager = None
    InferenceEngine = None

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

# YOLO модель и менеджер
YOLO_AVAILABLE = False
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    print("✅ Ultralytics YOLO успешно импортирован")
except ImportError:
    print("⚠️ Ultralytics YOLO не доступен, детекция отключена")

# Глобальные переменные для детекции и трекинга
model_manager = None
tracker = None
inference_engine = None
tracker_lock = threading.Lock()
model_lock = threading.Lock()
detection_thread = None
completed_trackers = set()  # Трекеры, для которых уже создан GIF
CONFIDENCE_THRESHOLD = float(os.environ.get('CONFIDENCE_THRESHOLD', '0.5'))
INFER_FPS = float(os.environ.get('INFER_FPS', '5'))  # FPS для детекции

# Глобальные переменные для хранения последних кадров
last_annotated_frame_jpeg = None  # Последний аннотированный кадр (JPEG)
last_raw_frame = None  # Последний сырой кадр (numpy array)
last_frame_lock = threading.Lock()  # Lock для потокобезопасного доступа к кадрам


def init_camera():
    """Инициализирует камеру (picamera2 или webcam)"""
    global picam2, webcam, camera_type
    
    # Подавляем предупреждения OpenCV
    if CV2_AVAILABLE:
        import warnings
        warnings.filterwarnings('ignore')
        # Устанавливаем уровень логирования OpenCV
        cv2.setLogLevel(0)  # 0 = SILENT, 1 = ERROR, 2 = WARN, 3 = INFO, 4 = DEBUG
    
    # Сначала пробуем picamera2 (но нужен cv2 для конвертации цветов)
    if PICAMERA2_AVAILABLE and CV2_AVAILABLE:
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
            if picam2 is not None:
                try:
                    picam2.stop()
                except:
                    pass
            picam2 = None
    
    # Если picamera2 не сработал, пробуем webcam
    if CV2_AVAILABLE:
        try:
            print("🎥 Инициализация веб-камеры...")
            
            # Проверяем, указан ли индекс камеры в переменной окружения
            camera_index_env = os.environ.get('CAMERA_INDEX')
            if camera_index_env is not None:
                try:
                    camera_indices = [int(camera_index_env)]
                    print(f"   Используется индекс камеры из CAMERA_INDEX: {camera_indices[0]}")
                except ValueError:
                    print(f"   ⚠️ Неверное значение CAMERA_INDEX: {camera_index_env}, используем автопоиск")
                    camera_indices = list(range(5))  # Проверяем индексы 0-4
            else:
                camera_indices = list(range(5))  # Проверяем индексы 0-4
            
            for idx in camera_indices:
                try:
                    print(f"   Проверка камеры {idx}...")
                    test_cam = cv2.VideoCapture(idx, cv2.CAP_DSHOW)  # Используем DirectShow на Windows
                    
                    if not test_cam.isOpened():
                        test_cam.release()
                        continue
                    
                    # Устанавливаем параметры для лучшей совместимости
                    test_cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    test_cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    test_cam.set(cv2.CAP_PROP_FPS, 30)
                    
                    time.sleep(0.5)  # Даем время на инициализацию
                    
                    # Пытаемся прочитать несколько кадров для надежности
                    success = False
                    for attempt in range(3):
                        ret, frame = test_cam.read()
                        if ret and frame is not None and frame.size > 0:
                            success = True
                            break
                        time.sleep(0.2)
                    
                    if success:
                        webcam = test_cam
                        camera_type = 'webcam'
                        print(f"✅ Веб-камера {idx} инициализирована (разрешение: {frame.shape[1]}x{frame.shape[0]})")
                        return True
                    else:
                        print(f"   ⚠️ Камера {idx} открыта, но не удалось прочитать кадр")
                        test_cam.release()
                        
                except Exception as e:
                    print(f"   ⚠️ Ошибка при проверке камеры {idx}: {e}")
                    try:
                        if 'test_cam' in locals():
                            test_cam.release()
                    except:
                        pass
                    continue
                    
        except Exception as e:
            print(f"⚠️ Ошибка инициализации веб-камеры: {e}")
            import traceback
            traceback.print_exc()
    
    print("❌ Не удалось инициализировать ни одну камеру")
    if not CV2_AVAILABLE:
        print("   💡 Установите OpenCV: pip install opencv-python")
    else:
        print("   💡 Попробуйте указать индекс камеры: CAMERA_INDEX=0 python detection_server.py")
        print("   💡 Или проверьте, что камера подключена и не используется другим приложением")
    return False


def capture_frame_raw():
    """Захватывает один кадр и возвращает numpy array (BGR)"""
    global picam2, webcam, camera_type
    
    if camera_type == 'picamera2' and picam2 is not None and CV2_AVAILABLE:
        try:
            # Для picamera2 нужно конвертировать из RGB в BGR
            array = picam2.capture_array()
            # picamera2 возвращает RGB, OpenCV использует BGR
            if len(array.shape) == 3:
                frame = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                return frame
        except Exception as e:
            print(f"⚠️ Ошибка захвата кадра с Picamera2: {e}")
        return None
    
    elif camera_type == 'webcam' and webcam is not None:
        try:
            ret, frame = webcam.read()
            if ret and frame is not None:
                return frame
        except Exception as e:
            print(f"⚠️ Ошибка захвата кадра с веб-камеры: {e}")
    
    return None


def capture_frame():
    """Захватывает один кадр и возвращает JPEG bytes (без детекции)"""
    if not CV2_AVAILABLE:
        return None
    frame = capture_frame_raw()
    if frame is not None:
        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if buffer is not None:
                return buffer.tobytes()
        except Exception as e:
            print(f"⚠️ Ошибка кодирования кадра: {e}")
    return None


def capture_frame_with_detections():
    """Захватывает кадр с детекциями и возвращает JPEG bytes"""
    global last_annotated_frame_jpeg
    with last_frame_lock:
        if last_annotated_frame_jpeg is not None:
            return last_annotated_frame_jpeg
    return None


def detection_loop():
    """Основной цикл детекции в отдельном потоке"""
    global last_annotated_frame_jpeg, last_raw_frame, inference_engine, tracker
    
    if not TRACKING_AVAILABLE or inference_engine is None:
        print("⚠️ Детекция отключена: компоненты не инициализированы")
        return
    
    print("🔍 Запуск потока детекции...")
    frame_interval = 1.0 / INFER_FPS
    
    while True:
        try:
            frame = capture_frame_raw()
            if frame is None:
                time.sleep(0.1)
                continue
            
            # Сохраняем сырой кадр
            with last_frame_lock:
                last_raw_frame = frame.copy()
            
            # Выполняем детекцию
            timestamp = time.time()
            try:
                tracked, annotated, stable_tracks = inference_engine.infer(frame, timestamp)
                
                # Обновляем кэш трекеров
                if TRACKING_AVAILABLE:
                    for track in tracked:
                        track_id = track.get('trackId')
                        bbox = track.get('bbox')
                        if track_id is not None and bbox:
                            update_tracker_cache(
                                track_id,
                                frame,
                                bbox,
                                {
                                    'label': track.get('label'),
                                    'confidence': track.get('confidence'),
                                    'timestamp': timestamp
                                }
                            )
                
                # Кодируем аннотированный кадр в JPEG
                _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if buffer is not None:
                    with last_frame_lock:
                        last_annotated_frame_jpeg = buffer.tobytes()
            
            except Exception as e:
                print(f"⚠️ Ошибка детекции: {e}")
            
            time.sleep(frame_interval)
        
        except Exception as e:
            print(f"⚠️ Ошибка в цикле детекции: {e}")
            time.sleep(0.1)




class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Нормализуем путь (убираем query параметры и завершающий слэш)
        parsed_path = urlparse(self.path)
        path = parsed_path.path.rstrip('/')
        
        if path == '/video_feed_raw' or path == '/stream.mjpeg' or self.path == '/video_feed_raw' or self.path == '/stream.mjpeg':
            # Поток без детекции
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            
            try:
                while True:
                    frame_data = capture_frame()
                    if frame_data:
                        try:
                            self.wfile.write(b'--frame\r\n')
                            self.send_header('Content-Type', 'image/jpeg')
                            self.send_header('Content-Length', str(len(frame_data)))
                            self.end_headers()
                            self.wfile.write(frame_data)
                            self.wfile.write(b'\r\n')
                        except (BrokenPipeError, OSError):
                            # Клиент отключился - это нормально
                            break
                    time.sleep(0.033)  # ~30 FPS
            except (BrokenPipeError, OSError):
                pass  # Клиент отключился
            except Exception as e:
                print(f"Stream closed: {e}")
        
        elif path == '/health' or self.path == '/health':
            try:
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
            except (BrokenPipeError, OSError):
                pass  # Клиент отключился до получения ответа
        
        elif path == '/api/detection' or self.path == '/api/detection':
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                # Собираем информацию о статусе детекции
                status = {
                    'status': 'ok',
                    'detection_enabled': inference_engine is not None and TRACKING_AVAILABLE,
                    'camera_available': camera_type is not None,
                    'camera_type': camera_type,
                    'model_loaded': model_manager is not None and model_manager.get_model() is not None,
                    'active_model': model_manager.get_active_model() if model_manager else None,
                    'tracker_active': tracker is not None,
                    'detection_thread_running': detection_thread is not None and detection_thread.is_alive(),
                    'confidence_threshold': CONFIDENCE_THRESHOLD,
                    'infer_fps': INFER_FPS
                }
                
                # Добавляем информацию об активных трекерах, если доступно
                if TRACKING_AVAILABLE and tracker is not None:
                    try:
                        with tracker_lock:
                            active_trackers = get_active_trackers(tracker)
                            status['active_trackers_count'] = len(active_trackers)
                    except Exception as e:
                        status['active_trackers_count'] = 0
                        status['tracker_error'] = str(e)
                else:
                    status['active_trackers_count'] = 0
                
                import json
                self.wfile.write(json.dumps(status, ensure_ascii=False).encode('utf-8'))
            except (BrokenPipeError, OSError):
                pass  # Клиент отключился до получения ответа
            except Exception as e:
                try:
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'status': 'error', 'error': str(e)}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                except:
                    pass
        
        elif path == '/api/trackers' or self.path.startswith('/api/trackers'):
            try:
                # Обработка /api/trackers - список трекеров
                if path == '/api/trackers':
                    try:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        
                        if not TRACKING_AVAILABLE:
                            result = {'trackers': [], 'error': 'Tracking module not available'}
                        elif tracker is None:
                            result = {'trackers': [], 'error': 'Tracker not initialized'}
                        else:
                            try:
                                with tracker_lock:
                                    active_trackers = get_active_trackers(tracker)
                                result = {'trackers': active_trackers}
                            except Exception as e:
                                print(f"⚠️ Ошибка получения трекеров: {e}")
                                import traceback
                                traceback.print_exc()
                                result = {'trackers': [], 'error': str(e)}
                        
                        import json
                        response_data = json.dumps(result, ensure_ascii=False).encode('utf-8')
                        self.wfile.write(response_data)
                    except Exception as e:
                        print(f"⚠️ Ошибка обработки /api/trackers: {e}")
                        import traceback
                        traceback.print_exc()
                        try:
                            self.send_response(500)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            error_response = {'error': str(e), 'trackers': []}
                            import json
                            self.wfile.write(json.dumps(error_response).encode())
                        except:
                            pass
                
                # Обработка /api/trackers/<track_id>/crop - кропнутый кадр
                elif path.endswith('/crop') or self.path.endswith('/crop'):
                    # Парсим путь: /api/trackers/<track_id>/crop
                    parts = path.split('/') if '/' in path else self.path.split('/')
                    # parts: ['', 'api', 'trackers', '<track_id>', 'crop']
                    if len(parts) >= 5 and parts[1] == 'api' and parts[2] == 'trackers' and parts[4] == 'crop':
                        try:
                            track_id = int(parts[3])
                            
                            if not TRACKING_AVAILABLE or tracker is None:
                                self.send_response(404)
                                self.end_headers()
                                return
                            
                            # Получаем трекер
                            with tracker_lock:
                                track = get_tracker_by_id(track_id, tracker)
                            
                            if track is None:
                                self.send_response(404)
                                self.end_headers()
                                return
                            
                            # Получаем последний кадр и кропаем
                            with last_frame_lock:
                                frame = last_raw_frame
                            
                            if frame is None:
                                self.send_response(503)
                                self.end_headers()
                                return
                            
                            bbox = track.get('bbox')
                            if not bbox:
                                self.send_response(404)
                                self.end_headers()
                                return
                            
                            cropped_jpeg = crop_frame_for_tracker(frame, bbox)
                            if cropped_jpeg is None:
                                self.send_response(503)
                                self.end_headers()
                                return
                            
                            self.send_response(200)
                            self.send_header('Content-Type', 'image/jpeg')
                            self.send_header('Content-Length', str(len(cropped_jpeg)))
                            self.end_headers()
                            self.wfile.write(cropped_jpeg)
                        except ValueError:
                            self.send_response(400)
                            self.end_headers()
                        except Exception as e:
                            self.send_response(500)
                            self.end_headers()
                    else:
                        self.send_response(400)
                        self.end_headers()
                
                # Обработка /api/trackers/<track_id>/frames - последовательность кадров
                elif path.endswith('/frames') or self.path.endswith('/frames'):
                    # Парсим путь: /api/trackers/<track_id>/frames
                    parts = path.split('/') if '/' in path else self.path.split('/')
                    # parts: ['', 'api', 'trackers', '<track_id>', 'frames']
                    if len(parts) >= 5 and parts[1] == 'api' and parts[2] == 'trackers' and parts[4] == 'frames':
                        try:
                            track_id = int(parts[3])
                            
                            if not TRACKING_AVAILABLE:
                                self.send_response(404)
                                self.end_headers()
                                return
                            
                            frames_base64 = get_tracker_frames(track_id)
                            
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            
                            result = {'track_id': track_id, 'frames': frames_base64}
                            import json
                            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
                        except ValueError:
                            self.send_response(400)
                            self.end_headers()
                        except Exception as e:
                            self.send_response(500)
                            self.end_headers()
                    else:
                        self.send_response(400)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()
                    
            except (BrokenPipeError, OSError):
                pass  # Клиент отключился до получения ответа
            except Exception as e:
                try:
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'error': str(e)}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                except:
                    pass
        
        elif path == '/models' or self.path == '/models':
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                if model_manager is None:
                    result = {
                        'available_models': [],
                        'active_model': None,
                        'error': 'Model manager not initialized'
                    }
                else:
                    try:
                        available = model_manager.get_available_models()
                        active = model_manager.get_active_model()
                        result = {
                            'available_models': available,
                            'active_model': active
                        }
                    except Exception as e:
                        result = {
                            'available_models': [],
                            'active_model': None,
                            'error': str(e)
                        }
                
                import json
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
            except (BrokenPipeError, OSError):
                pass  # Клиент отключился до получения ответа
            except Exception as e:
                try:
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'error': str(e)}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                except:
                    pass
        
        else:
            try:
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
                            <p><a href="/video_feed_raw">Raw stream</a></p>
                            <img src="/video_feed_raw" width="1280" height="720">
                        </body>
                    </html>
                ''')
            except (BrokenPipeError, OSError):
                pass  # Клиент отключился до получения ответа
    
    def do_POST(self):
        """Обработка POST запросов"""
        # Нормализуем путь
        parsed_path = urlparse(self.path)
        path = parsed_path.path.rstrip('/')
        
        if path == '/models' or self.path == '/models':
            try:
                # Читаем тело запроса
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'error': 'Request body is required'}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                    return
                
                body = self.rfile.read(content_length)
                try:
                    request_data = json.loads(body.decode('utf-8'))
                except json.JSONDecodeError:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'error': 'Invalid JSON in request body'}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                    return
                
                model_name = request_data.get('name')
                if not model_name:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'error': 'Model name is required in "name" field'}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                    return
                
                if model_manager is None:
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'error': 'Model manager not initialized'}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                    return
                
                try:
                    # Переключаем модель
                    with model_lock:
                        old_model = model_manager.get_active_model()
                        new_model = model_manager.switch_model(model_name)
                    
                    # Если модель изменилась, нужно переинициализировать inference_engine
                    global inference_engine, tracker
                    if old_model != new_model and TRACKING_AVAILABLE and tracker is not None:
                        try:
                            inference_engine = InferenceEngine(model_manager, tracker, tracker_lock)
                            print(f"✅ Inference engine переинициализирован для модели {new_model}")
                        except Exception as e:
                            print(f"⚠️ Ошибка переинициализации inference engine: {e}")
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    result = {
                        'success': True,
                        'active_model': new_model,
                        'previous_model': old_model
                    }
                    import json
                    self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
                    
                except FileNotFoundError as e:
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'error': str(e)}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                except Exception as e:
                    print(f"⚠️ Ошибка переключения модели: {e}")
                    import traceback
                    traceback.print_exc()
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'error': str(e)}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                    
            except (BrokenPipeError, OSError):
                pass  # Клиент отключился до получения ответа
            except Exception as e:
                try:
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    error_response = {'error': str(e)}
                    import json
                    self.wfile.write(json.dumps(error_response).encode())
                except:
                    pass
        else:
            self.send_response(404)
            self.end_headers()


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
    global model_manager, tracker, inference_engine, detection_thread
    
    print("🚀 Запуск Detection Service...")
    
    # Инициализируем камеру
    if not init_camera():
        print("⚠️ ВНИМАНИЕ: Камера не инициализирована!")
        print("💡 Сервер запустится, но видео поток будет недоступен")
    
    # Инициализируем компоненты детекции
    if TRACKING_AVAILABLE and YOLO_AVAILABLE:
        try:
            base_dir = Path(__file__).parent
            models_dir = base_dir / 'models'
            
            # Инициализируем model_manager
            model_manager = ModelManager(models_dir, base_dir)
            model_manager.set_lock(model_lock)
            
            # Ищем модель для загрузки
            model_paths = [
                models_dir / 'yolov8n.pt',
                models_dir / 'bestfire.pt',
                base_dir.parent / 'models' / 'yolov8n.pt',
            ]
            
            model_path = None
            for path in model_paths:
                if path.exists():
                    model_path = path
                    break
            
            if model_path:
                try:
                    model_manager.load_model(str(model_path))
                    print(f"✅ Модель загружена: {model_manager.get_active_model()}")
                except Exception as e:
                    print(f"⚠️ Ошибка загрузки модели: {e}")
            else:
                print("⚠️ Модель не найдена, детекция будет отключена")
            
            # Инициализируем tracker
            tracker = SortTracker(iou_threshold=0.3, max_age=5, min_hits=1)
            print("✅ Tracker инициализирован")
            
            # Инициализируем inference_engine
            if model_manager.get_model() is not None:
                inference_engine = InferenceEngine(model_manager, tracker, tracker_lock)
                print("✅ Inference engine инициализирован")
                
                # Запускаем поток детекции
                detection_thread = threading.Thread(target=detection_loop, daemon=True)
                detection_thread.start()
                print("✅ Поток детекции запущен")
            else:
                print("⚠️ Inference engine не инициализирован: модель не загружена")
                
        except Exception as e:
            print(f"⚠️ Ошибка инициализации компонентов детекции: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⚠️ Компоненты трекинга недоступны, детекция отключена")
    
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
