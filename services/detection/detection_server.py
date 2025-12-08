#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detection Service - HTTP server with Flask API"""

import logging
import os
import signal
import sys
import time
from pathlib import Path

# Настройка кодировки для Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

try:
    from flask import Flask, Response, jsonify, request
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None  # type: ignore[assignment, misc]
    Response = None  # type: ignore[assignment, misc]
    jsonify = None  # type: ignore[assignment, misc]
    request = None  # type: ignore[assignment, misc]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    # Ищем .env файл в корне проекта
    env_path = PROJECT_ROOT / '.env'
    if env_path.exists():
        load_dotenv(env_path, override=False)  # override=False - не перезаписываем существующие переменные
        print(f"✅ [ENV] Загружен .env файл: {env_path}", flush=True)
        # Показываем важные переменные для отладки
        servo_hw = os.environ.get("SERVO_HARDWARE", "не установлено")
        print(f"   [ENV] SERVO_HARDWARE = '{servo_hw}'", flush=True)
        if servo_hw and servo_hw.lower() not in ("none", "gpio", "pca9685"):
            print(f"⚠️  [ENV] ВНИМАНИЕ: SERVO_HARDWARE='{servo_hw}' - возможно опечатка?", flush=True)
            print(f"   [ENV] Ожидаемые значения: 'gpio', 'pca9685' или 'none'", flush=True)
    else:
        # Пробуем найти .env в текущей директории
        load_dotenv(override=False)
        print(f"ℹ️  [ENV] .env файл не найден в {env_path}, используем системные переменные окружения", flush=True)
        servo_hw = os.environ.get("SERVO_HARDWARE", "не установлено")
        print(f"   [ENV] SERVO_HARDWARE = '{servo_hw}' (из системных переменных)", flush=True)
except ImportError:
    print("⚠️  [ENV] python-dotenv не установлен. Установите: pip install python-dotenv", flush=True)
    print("   [ENV] Используются только системные переменные окружения", flush=True)
    servo_hw = os.environ.get("SERVO_HARDWARE", "не установлено")
    print(f"   [ENV] SERVO_HARDWARE = '{servo_hw}' (из системных переменных)", flush=True)

import collections
import queue

from services.detection.config.runtime import RuntimeConfig
from services.detection.service import DetectionService
from services.detection.streaming.generators import mjpeg_generator_raw

# Настройка логирования (можно отключить через переменную окружения)
enable_logging = os.environ.get("ENABLE_LOGGING", "true").lower() in ("true", "1", "yes")
log_level = logging.WARNING if not enable_logging else logging.INFO

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

if not FLASK_AVAILABLE:
    raise ImportError("Flask не установлен. Установите: pip install flask")

app = Flask(__name__)
detection_service: DetectionService | None = None


@app.after_request
def after_request(response):
    """Добавляет CORS заголовки ко всем ответам"""
    # Используем присваивание вместо add(), чтобы избежать дублирования
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,Accept,Origin,X-Requested-With'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS,PATCH'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response


@app.before_request
def handle_preflight():
    """Обработка preflight запросов OPTIONS"""
    if request.method == "OPTIONS":
        response = jsonify({})
        # Используем присваивание вместо add(), чтобы избежать дублирования
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,Accept,Origin,X-Requested-With'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS,PATCH'
        response.headers['Access-Control-Max-Age'] = '86400'
        response.status_code = 204
        return response


def create_app(config: RuntimeConfig):
    """Создает и настраивает Flask приложение"""
    global detection_service
    
    detection_service = DetectionService(config)
    detection_service.start()
    logger.info("Detection service started")
    
    return app


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    if detection_service is None:
        return jsonify({'status': 'error', 'error': 'Service not initialized'}), 503
    
    return jsonify({
        'status': 'ok',
        'camera_available': detection_service.camera_type is not None,
        'camera_type': detection_service.camera_type
    })


@app.route('/video_feed_raw', methods=['GET'])
@app.route('/stream.mjpeg', methods=['GET'])
def video_feed_raw():
    """MJPEG stream без детекции"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    return Response(
        mjpeg_generator_raw(detection_service.capture_raw_jpeg, interval=0.033),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/api/detection', methods=['GET'])
def detection_status():
    """Статус детекции"""
    if detection_service is None:
        return jsonify({'status': 'error', 'error': 'Service not initialized'}), 503
    
    return jsonify(detection_service.get_status_payload())


@app.route('/api/trackers', methods=['GET'])
def list_trackers():
    """Список активных трекеров"""
    if detection_service is None:
        return jsonify({'trackers': [], 'error': 'Service not initialized'}), 503
    
    return jsonify(detection_service.list_trackers())


@app.route('/api/trackers/target', methods=['POST'])
def update_target():
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503

    data = request.get_json()
    track_id = data.get('trackId') if isinstance(data, dict) else None
    if track_id is not None and not isinstance(track_id, int):
        try:
            track_id = int(track_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'trackId must be integer'}), 400

    try:
        result = detection_service.set_target_track(track_id)
        return jsonify(result)
    except Exception as exc:  # pragma: no cover
        logger.error("Не удалось обновить таргет: %s", exc, exc_info=True)
        return jsonify({'error': str(exc)}), 500


@app.route('/api/trackers/<int:track_id>/crop', methods=['GET'])
def tracker_crop(track_id: int):
    """Кропнутый кадр для трекера"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    crop = detection_service.get_tracker_crop(track_id)
    if crop is None:
        return jsonify({'error': 'Tracker not found or frame unavailable'}), 404
    
    return Response(crop, mimetype='image/jpeg')


@app.route('/api/trackers/<int:track_id>/frames', methods=['GET'])
def tracker_frames(track_id: int):
    """Последовательность кадров для трекера"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    return jsonify(detection_service.get_tracker_frames_payload(track_id))


@app.route('/models', methods=['GET'])
def list_models():
    """Список доступных моделей"""
    if detection_service is None:
        return jsonify({
            'available_models': [],
            'active_model': None,
            'error': 'Service not initialized'
        }), 503
    
    return jsonify(detection_service.list_models_payload())


@app.route('/models', methods=['POST'])
def switch_model():
    """Переключение модели"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Model name is required in "name" field'}), 400
    
    try:
        result = detection_service.switch_model(data['name'])
        return jsonify(result)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error("Ошибка переключения модели: %s", e, exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/gps', methods=['GET'])
def get_gps():
    """Получить текущие GPS координаты"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    gps = detection_service.get_gps()
    if gps is None:
        return jsonify({
            'available': False,
            'error': 'GPS not configured or unavailable'
        })
    
    return jsonify(gps)


@app.route('/api/gps/status', methods=['GET'])
def get_gps_status():
    """Получить детальный статус подключения MavLink"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    status = detection_service.get_gps_connection_status()
    if status is None:
        return jsonify({
            'available': False,
            'configured': False,
            'error': 'MavLink не настроен (MAVLINK_PORT не указан в переменных окружения)'
        })
    
    return jsonify(status)


@app.route('/api/servo', methods=['GET'])
def get_servo():
    """Получить текущее состояние сервоприводов"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    return jsonify(detection_service.servo.get_state())


@app.route('/api/servo/status', methods=['GET'])
def get_servo_status():
    """Получить детальный статус подключения сервоприводов"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    status = detection_service.servo.get_connection_status()
    return jsonify(status)


@app.route('/api/servo', methods=['POST'])
def set_servo():
    """Установить углы сервоприводов"""
    print("=" * 60, flush=True)
    print("📡 [API] POST /api/servo получен", flush=True)
    
    if detection_service is None:
        print("❌ [API] Detection service не инициализирован", flush=True)
        return jsonify({'error': 'Service not initialized'}), 503
    
    data = request.get_json()
    print(f"   [API] Данные запроса: {data}", flush=True)
    
    if not data:
        print("❌ [API] JSON body отсутствует", flush=True)
        return jsonify({'error': 'JSON body required'}), 400
    
    pan = data.get('pan')
    tilt = data.get('tilt')
    print(f"   [API] Извлеченные значения: pan={pan}, tilt={tilt}", flush=True)
    
    # Валидация
    if pan is not None:
        try:
            pan = float(pan)
            if not (0.0 <= pan <= 180.0):
                print(f"❌ [API] Pan вне диапазона: {pan}", flush=True)
                return jsonify({'error': 'pan must be between 0.0 and 180.0'}), 400
        except (TypeError, ValueError) as exc:
            print(f"❌ [API] Ошибка валидации Pan: {exc}", flush=True)
            return jsonify({'error': 'pan must be a number'}), 400
    
    if tilt is not None:
        try:
            tilt = float(tilt)
            if not (0.0 <= tilt <= 180.0):
                print(f"❌ [API] Tilt вне диапазона: {tilt}", flush=True)
                return jsonify({'error': 'tilt must be between 0.0 and 180.0'}), 400
        except (TypeError, ValueError) as exc:
            print(f"❌ [API] Ошибка валидации Tilt: {exc}", flush=True)
            return jsonify({'error': 'tilt must be a number'}), 400
    
    try:
        print(f"⏳ [API] Вызов detection_service.set_servo_angles(pan={pan}, tilt={tilt})...", flush=True)
        result = detection_service.set_servo_angles(pan, tilt)
        print(f"✅ [API] Углы установлены успешно: {result}", flush=True)
        print("=" * 60, flush=True)
        return jsonify(result)
    except Exception as exc:
        print(f"❌ [API] Ошибка установки углов: {exc}", flush=True)
        logger.error("Не удалось установить углы сервоприводов: %s", exc, exc_info=True)
        print("=" * 60, flush=True)
        return jsonify({'error': str(exc)}), 500


@app.route('/api/config/performance', methods=['GET'])
def get_performance_config():
    """Получить текущие настройки производительности и метрики"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    config = detection_service.config
    
    # Получаем реальные метрики из статуса
    status = detection_service.get_status_payload()
    
    return jsonify({
        'infer_fps': config.infer_fps,
        'confidence_threshold': config.confidence_threshold,
        'max_infer_queue_size': config.max_infer_queue_size,
        'jpeg_quality_stream': config.jpeg_quality_stream,
        'jpeg_quality_save': config.jpeg_quality_save,
        'input_size': config.input_size,
        'draw_detections': config.draw_detections,
        'raw_frames_buffer_size': config.raw_frames_buffer_size,
        # Реальные метрики
        'queue_size': status.get('queue_size', 0),
        'frame_process_time_ms': status.get('frame_process_time_ms'),
    })


@app.route('/api/config/performance', methods=['POST'])
def update_performance_config():
    """Обновить настройки производительности в runtime"""
    if detection_service is None:
        return jsonify({'error': 'Service not initialized'}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    config = detection_service.config
    updated = {}
    
    # Обновляем параметры если они переданы
    if 'infer_fps' in data:
        new_fps = float(data['infer_fps'])
        if 0.1 <= new_fps <= 30.0:
            config.infer_fps = new_fps
            updated['infer_fps'] = new_fps
        else:
            return jsonify({'error': 'infer_fps must be between 0.1 and 30.0'}), 400
    
    if 'confidence_threshold' in data:
        new_conf = float(data['confidence_threshold'])
        if 0.0 <= new_conf <= 1.0:
            config.confidence_threshold = new_conf
            if detection_service.inference_engine:
                detection_service.inference_engine.confidence_threshold = new_conf
            updated['confidence_threshold'] = new_conf
        else:
            return jsonify({'error': 'confidence_threshold must be between 0.0 and 1.0'}), 400
    
    if 'max_infer_queue_size' in data:
        new_size = int(data['max_infer_queue_size'])
        if 1 <= new_size <= 10:
            config.max_infer_queue_size = new_size
            # Пересоздаем очередь с новым размером
            old_queue = detection_service.infer_queue
            detection_service.infer_queue = queue.Queue(maxsize=new_size)
            # Переносим кадры из старой очереди
            while not old_queue.empty():
                try:
                    item = old_queue.get_nowait()
                    try:
                        detection_service.infer_queue.put_nowait(item)
                    except queue.Full:
                        break
                except queue.Empty:
                    break
            updated['max_infer_queue_size'] = new_size
        else:
            return jsonify({'error': 'max_infer_queue_size must be between 1 and 10'}), 400
    
    if 'jpeg_quality_stream' in data:
        new_quality = int(data['jpeg_quality_stream'])
        if 10 <= new_quality <= 100:
            config.jpeg_quality_stream = new_quality
            updated['jpeg_quality_stream'] = new_quality
        else:
            return jsonify({'error': 'jpeg_quality_stream must be between 10 and 100'}), 400
    
    if 'jpeg_quality_save' in data:
        new_quality = int(data['jpeg_quality_save'])
        if 10 <= new_quality <= 100:
            config.jpeg_quality_save = new_quality
            updated['jpeg_quality_save'] = new_quality
        else:
            return jsonify({'error': 'jpeg_quality_save must be between 10 and 100'}), 400
    
    if 'input_size' in data:
        new_size = data['input_size']
        if new_size is None:
            config.input_size = None
            updated['input_size'] = None
        else:
            new_size = int(new_size)
            if new_size > 0:
                config.input_size = new_size
                if detection_service.inference_engine:
                    detection_service.inference_engine.input_size = new_size
                updated['input_size'] = new_size
            else:
                return jsonify({'error': 'input_size must be positive integer or null'}), 400
    
    if 'draw_detections' in data:
        new_draw = bool(data['draw_detections'])
        config.draw_detections = new_draw
        if detection_service.inference_engine:
            detection_service.inference_engine.draw_detections = new_draw
        updated['draw_detections'] = new_draw
    
    if 'raw_frames_buffer_size' in data:
        new_size = int(data['raw_frames_buffer_size'])
        if 10 <= new_size <= 100:
            config.raw_frames_buffer_size = new_size
            # Пересоздаем буфер с новым размером
            old_buffer = detection_service.raw_frames_buffer
            detection_service.raw_frames_buffer = collections.deque(maxlen=new_size)
            # Переносим кадры из старого буфера
            for frame in old_buffer:
                detection_service.raw_frames_buffer.append(frame)
            updated['raw_frames_buffer_size'] = new_size
        else:
            return jsonify({'error': 'raw_frames_buffer_size must be between 10 and 100'}), 400
    
    if updated and detection_service:
        detection_service.persist_performance_snapshot()

    return jsonify({'success': True, 'updated': updated})


@app.route('/', methods=['GET'])
def index():
    """Главная страница с видео потоком"""
    return '''
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
    '''


def setup_signal_handlers():
    """Настройка обработчиков сигналов для graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info("Получен сигнал %d, останавливаем сервис...", signum)
        if detection_service:
            detection_service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main():
    """Главная функция"""
    global detection_service
    
    logger.info("🚀 Запуск Detection Service...")
    
    # Загружаем конфигурацию из переменных окружения
    config = RuntimeConfig.from_env()
    logger.info("Конфигурация: port=%d, confidence=%.2f, infer_fps=%.1f", 
                config.port, config.confidence_threshold, config.infer_fps)
    
    # Создаем приложение
    create_app(config)
    
    # Настраиваем обработчики сигналов
    setup_signal_handlers()
    
    # Запускаем Flask сервер
    try:
        logger.info("🌐 Сервер запущен на http://0.0.0.0:%d", config.port)
        logger.info("📹 Видео поток: http://localhost:%d/video_feed_raw", config.port)
        logger.info("🏥 Health check: http://localhost:%d/health", config.port)
        
        app.run(
            host='0.0.0.0',
            port=config.port,
            threaded=True,
            debug=False
        )
    except KeyboardInterrupt:
        logger.info("Получен KeyboardInterrupt, останавливаем...")
    finally:
        if detection_service:
            detection_service.stop()
        logger.info("Сервис остановлен")


if __name__ == '__main__':
    main()
