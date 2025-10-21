# Конфигурация для Raspberry Pi Fire Detection System
# Оптимизированные настройки для максимальной производительности

import os

class PiConfig:
    """Конфигурация для Raspberry Pi"""
    
    # Настройки камеры
    CAMERA = {
        'width': 640,
        'height': 480,
        'fps': 15,  # Ограничиваем FPS для экономии ресурсов
        'format': 'RGB888',
        'sensor_mode': 2,  # Режим сенсора для баланса качества/скорости
    }
    
    # Настройки детекции
    DETECTION = {
        'confidence_threshold': 0.3,  # Пониженный порог для экономии ресурсов
        'resize_for_detection': (320, 240),  # Уменьшенный размер для обработки
        'max_detections': 5,  # Максимум детекций за кадр
        'detection_interval': 3,  # Обрабатывать каждый 3-й кадр
    }
    
    # Настройки производительности
    PERFORMANCE = {
        'max_cpu_usage': 80,  # Максимальное использование CPU
        'max_memory_usage': 85,  # Максимальное использование памяти
        'max_temperature': 75,  # Максимальная температура (°C)
        'enable_gpu': False,  # Отключаем GPU для экономии ресурсов
        'thread_count': 2,  # Количество потоков
    }
    
    # Настройки веб-интерфейса
    WEB = {
        'host': '0.0.0.0',
        'port': 5000,
        'debug': False,
        'threaded': True,
        'video_quality': 70,  # Качество JPEG для видеопотока
    }
    
    # Настройки логирования
    LOGGING = {
        'level': 'INFO',
        'file': 'logs/fire_detection.log',
        'max_size': 10 * 1024 * 1024,  # 10MB
        'backup_count': 5,
    }
    
    # Настройки уведомлений
    NOTIFICATIONS = {
        'enable_sound': True,
        'enable_email': False,
        'email_smtp_server': 'smtp.gmail.com',
        'email_port': 587,
        'email_username': '',
        'email_password': '',
        'email_recipients': [],
    }
    
    # Настройки GPIO (для дополнительных датчиков)
    GPIO = {
        'enable_buzzer': True,
        'buzzer_pin': 18,
        'enable_led': True,
        'led_pin': 24,
        'enable_button': True,
        'button_pin': 16,
    }
    
    # Настройки модели
    MODEL = {
        'path': 'bestfire.pt',
        'device': 'cpu',  # Используем CPU для Raspberry Pi
        'half_precision': False,  # Отключаем для совместимости
        'verbose': False,
    }
    
    # Настройки безопасности
    SECURITY = {
        'max_failed_detections': 10,
        'cooldown_period': 30,  # секунд
        'enable_recording': False,
        'recording_duration': 60,  # секунд
        'save_path': 'recordings/',
    }
    
    @classmethod
    def get_optimal_settings(cls, pi_model='4'):
        """Получение оптимальных настроек для конкретной модели Pi"""
        if pi_model == '4':
            return {
                'camera_fps': 20,
                'detection_interval': 2,
                'thread_count': 4,
                'max_cpu_usage': 85,
            }
        elif pi_model == '3':
            return {
                'camera_fps': 15,
                'detection_interval': 3,
                'thread_count': 2,
                'max_cpu_usage': 75,
            }
        else:  # Pi Zero или старше
            return {
                'camera_fps': 10,
                'detection_interval': 5,
                'thread_count': 1,
                'max_cpu_usage': 70,
            }
    
    @classmethod
    def detect_pi_model(cls):
        """Автоматическое определение модели Raspberry Pi"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                if 'BCM2835' in cpuinfo:
                    return 'Zero'
                elif 'BCM2836' in cpuinfo:
                    return '2'
                elif 'BCM2837' in cpuinfo:
                    return '3'
                elif 'BCM2711' in cpuinfo:
                    return '4'
                else:
                    return 'Unknown'
        except:
            return 'Unknown'
    
    @classmethod
    def optimize_for_pi(cls):
        """Применение оптимизаций для Raspberry Pi"""
        pi_model = cls.detect_pi_model()
        optimal = cls.get_optimal_settings(pi_model)
        
        # Обновляем настройки
        cls.CAMERA['fps'] = optimal['camera_fps']
        cls.DETECTION['detection_interval'] = optimal['detection_interval']
        cls.PERFORMANCE['thread_count'] = optimal['thread_count']
        cls.PERFORMANCE['max_cpu_usage'] = optimal['max_cpu_usage']
        
        # Создаем необходимые директории
        os.makedirs('logs', exist_ok=True)
        os.makedirs('recordings', exist_ok=True)
        
        print(f"🔧 Оптимизация для Raspberry Pi {pi_model}")
        print(f"📊 Настройки: FPS={cls.CAMERA['fps']}, "
              f"Detection interval={cls.DETECTION['detection_interval']}, "
              f"Threads={cls.PERFORMANCE['thread_count']}")

# Экспорт конфигурации
config = PiConfig()
