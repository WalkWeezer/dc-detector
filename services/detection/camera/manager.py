"""Camera management for the detection service."""
from __future__ import annotations

import logging
import sys
import time
import warnings
from io import BytesIO
from typing import Optional

from ..config.runtime import RuntimeConfig

logger = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    Picamera2 = None  # type: ignore[assignment]
    PICAMERA2_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:  # pragma: no cover - OpenCV might be unavailable on CI
    cv2 = None  # type: ignore[assignment]
    CV2_AVAILABLE = False


class CameraInitializationError(RuntimeError):
    """Raised when no camera backend can be initialized."""


class CameraManager:
    """Encapsulates camera discovery, capture and resource management."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.camera_type: Optional[str] = None  # 'picamera2' or 'webcam'
        self.picam2: Optional[Picamera2] = None
        self.webcam = None

    def start(self) -> None:
        """Initialize available camera backend."""
        if self._try_init_picamera():
            self.camera_type = "picamera2"
            return

        if self._try_init_webcam():
            self.camera_type = "webcam"
            return

        raise CameraInitializationError("Не удалось инициализировать ни один источник камеры")

    def capture_raw(self):
        """Capture raw frame as numpy array in BGR format."""
        if self.camera_type == "picamera2" and self.picam2 is not None and CV2_AVAILABLE:
            array = self.picam2.capture_array()
            if array is None:
                return None
            if len(array.shape) == 3:
                return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
            return array

        if self.camera_type == "webcam" and self.webcam is not None and CV2_AVAILABLE:
            ret, frame = self.webcam.read()
            if ret and frame is not None:
                return frame
        return None

    def capture_jpeg(self) -> Optional[bytes]:
        """Capture frame as JPEG bytes."""
        # Для PiCamera2 используем capture_file() напрямую (как в рабочем скрипте)
        if self.camera_type == "picamera2" and self.picam2 is not None:
            try:
                buffer = BytesIO()
                self.picam2.capture_file(buffer, format="jpeg")
                if buffer.getbuffer().nbytes > 0:
                    return buffer.getvalue()
            except Exception as exc:
                logger.debug("Ошибка захвата JPEG с PiCamera2: %s", exc)
            return None
        
        # Для веб-камеры используем OpenCV
        if not CV2_AVAILABLE:
            return None
        frame = self.capture_raw()
        if frame is None:
            return None
        success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.config.jpeg_quality])
        if not success:
            return None
        return buffer.tobytes()

    def shutdown(self) -> None:
        """Release camera resources."""
        if self.picam2 is not None:
            try:
                self.picam2.stop()
            finally:
                self.picam2 = None
        if self.webcam is not None:
            try:
                self.webcam.release()
            finally:
                self.webcam = None

    # Internal helpers -----------------------------------------------------------------

    def _try_init_picamera(self) -> bool:
        if not PICAMERA2_AVAILABLE:
            # На Linux (Raspberry Pi) это может быть проблемой, на Windows - нормально
            if sys.platform != 'win32':
                logger.info("Picamera2 недоступен (модуль не установлен). Попытка подключения веб-камеры...")
            else:
                logger.debug("Picamera2 недоступен (ожидаемо на Windows)")
            return False

        try:
            logger.info("Инициализация Picamera2...")
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(main={"size": (1280, 720)})
            self.picam2.configure(config)
            self.picam2.start()
            # Небольшая задержка для стабилизации камеры (как в рабочем скрипте обычно не требуется, но для надежности оставляем минимальную)
            time.sleep(0.5)
            # Тестовый снимок для проверки работоспособности (как в рабочем скрипте)
            buffer = BytesIO()
            self.picam2.capture_file(buffer, format="jpeg")
            if buffer.getbuffer().nbytes > 0:
                logger.info("Picamera2 успешно инициализирован")
                return True
        except Exception as exc:
            logger.warning("Ошибка инициализации Picamera2: %s", exc)
            if self.picam2 is not None:
                try:
                    self.picam2.stop()
                finally:
                    self.picam2 = None
        return False

    def _try_init_webcam(self) -> bool:
        if not CV2_AVAILABLE:
            return False

        warnings.filterwarnings("ignore")
        cv2.setLogLevel(0)

        indices = self.config.camera_indices or list(range(5))
        logger.info("Инициализация веб-камеры, проверка индексов: %s", indices)
        
        # Список backend'ов для попытки инициализации (Windows)
        backends = []
        try:
            # На Windows пробуем разные backend'ы
            import sys
            if sys.platform == 'win32':
                backends = [
                    cv2.CAP_DSHOW,  # DirectShow (Windows)
                    cv2.CAP_MSMF,  # Microsoft Media Foundation
                    cv2.CAP_ANY,   # Любой доступный
                ]
            else:
                backends = [cv2.CAP_ANY]
        except:
            backends = [cv2.CAP_ANY]
        
        for idx in indices:
            for backend in backends:
                capture = None
                try:
                    logger.debug("Проверка камеры %d с backend %s...", idx, backend)
                    capture = cv2.VideoCapture(idx, backend)
                    if not capture.isOpened():
                        if capture is not None:
                            capture.release()
                        continue
                    
                    # Пробуем установить параметры, но не критично если не получится
                    try:
                        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    except:
                        pass
                    
                    try:
                        capture.set(cv2.CAP_PROP_FPS, 30)
                    except:
                        pass
                    
                    # Даем камере время на инициализацию
                    time.sleep(0.5)
                    
                    # Пробуем прочитать несколько кадров
                    success_count = 0
                    for attempt in range(5):
                        ret, frame = capture.read()
                        if ret and frame is not None and frame.size > 0:
                            # Проверяем, что кадр валидный
                            if len(frame.shape) >= 2 and frame.shape[0] > 0 and frame.shape[1] > 0:
                                success_count += 1
                                if success_count >= 2:  # Нужно минимум 2 успешных кадра
                                    self.webcam = capture
                                    logger.info("Веб-камера %d успешно инициализирована с backend %s (разрешение: %dx%d)", 
                                               idx, backend, frame.shape[1], frame.shape[0])
                                    return True
                        time.sleep(0.2)
                    
                    # Если не получилось, освобождаем ресурсы
                    if capture is not None:
                        capture.release()
                        capture = None
                        
                except Exception as exc:
                    logger.debug("Ошибка при проверке камеры %d с backend %s: %s", idx, backend, exc)
                    if capture is not None:
                        try:
                            capture.release()
                        except:
                            pass
                    continue
                    
        logger.warning("Не удалось инициализировать ни одну веб-камеру из индексов: %s", indices)
        return False


