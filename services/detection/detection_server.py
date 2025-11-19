#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detection Service - HTTP server with Flask API"""

import logging
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

from services.detection.config.runtime import RuntimeConfig
from services.detection.service import DetectionService
from services.detection.streaming.generators import mjpeg_generator_raw

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
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
