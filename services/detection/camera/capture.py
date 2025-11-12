"""Camera capture module - рабочий скрипт"""
import time
from io import BytesIO
from typing import Optional

# Попытка импортировать picamera2 (доступно только на Raspberry Pi)
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None

# Глобальная переменная для камеры (как в рабочем скрипте)
picam2: Optional[Picamera2] = None


def init_picamera2():
    """Инициализирует Picamera2 (как в рабочем скрипте)"""
    global picam2
    if not PICAMERA2_AVAILABLE:
        return False
    
    try:
        picam2 = Picamera2()
        config = picam2.create_preview_configuration(main={"size": (1280, 720)})
        picam2.configure(config)
        picam2.start()
        print("✅ Picamera2 инициализирован (как в рабочем скрипте)")
        return True
    except Exception as e:
        print(f"❌ Ошибка при инициализации Picamera2: {e}")
        return False


def capture_frame_jpeg() -> Optional[bytes]:
    """Захватывает кадр в JPEG (точно как в рабочем скрипте)"""
    global picam2
    if picam2 is None:
        return None
    
    try:
        buffer = BytesIO()
        picam2.capture_file(buffer, format='jpeg')
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        print(f"Ошибка при захвате кадра: {e}")
        return None


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
