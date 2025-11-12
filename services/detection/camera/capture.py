"""Camera capture module"""
import logging
import os
import shutil
import time
from io import BytesIO
from typing import Optional

import cv2

logger = logging.getLogger(__name__)

# Попытка импортировать picamera2 (доступно только на Raspberry Pi)
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None

CAMERA_BACKEND = os.getenv('CAMERA_BACKEND', 'V4L2').upper()


class Picamera2Wrapper:
    """Обертка для Picamera2, которая работает как cv2.VideoCapture"""
    
    def __init__(self, camera_index: int = 0, width: int = 1280, height: int = 720):
        if not PICAMERA2_AVAILABLE:
            raise RuntimeError('picamera2 не доступен')
        
        self.picam2 = Picamera2(camera_index)
        self.width = width
        self.height = height
        self._is_opened = False
        
    def open(self) -> bool:
        """Открывает камеру и настраивает конфигурацию"""
        try:
            # Для захвата кадров используем preview конфигурацию (быстрее, чем video)
            try:
                preview_config = self.picam2.create_preview_configuration(
                    main={"size": (self.width, self.height)},
                    buffer_count=2
                )
                self.picam2.configure(preview_config)
                logger.debug('Используется preview конфигурация для Picamera2')
            except Exception as e:
                logger.debug('Preview конфигурация не доступна, используем video: %s', e)
                video_config = self.picam2.create_video_configuration(
                    main={"size": (self.width, self.height)}
                )
                self.picam2.configure(video_config)
            
            self.picam2.start()
            self._is_opened = True
            time.sleep(0.5)
            
            # Проверяем, что камера действительно работает
            try:
                test_frame = self.picam2.capture_array()
                if test_frame is not None and test_frame.size > 0:
                    logger.debug('Тестовый кадр успешно захвачен: %s', test_frame.shape)
                    return True
                else:
                    logger.warning('Тестовый кадр пустой')
                    self.picam2.stop()
                    self._is_opened = False
                    return False
            except Exception as e:
                logger.warning('Не удалось захватить тестовый кадр: %s', e)
                self.picam2.stop()
                self._is_opened = False
                return False
                
        except Exception as e:
            logger.error('Ошибка при открытии Picamera2: %s', e)
            self._is_opened = False
            return False
    
    def isOpened(self) -> bool:
        """Проверяет, открыта ли камера"""
        return self._is_opened
    
    def read(self):
        """Читает кадр из камеры"""
        if not self._is_opened:
            return False, None
        
        try:
            frame = self.picam2.capture_array()
            if frame is None or frame.size == 0:
                return False, None
            
            # Picamera2 возвращает кадр в формате RGB, нужно конвертировать в BGR для OpenCV
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            return True, frame
        except Exception as e:
            logger.debug('Ошибка при чтении кадра из Picamera2: %s', e)
            return False, None
    
    def capture_jpeg(self) -> Optional[bytes]:
        """Захватывает кадр напрямую в JPEG (оптимизация для стриминга)"""
        if not self._is_opened:
            return None
        
        try:
            buffer = BytesIO()
            self.picam2.capture_file(buffer, format='jpeg')
            buffer.seek(0)
            return buffer.getvalue()
        except Exception as e:
            logger.debug('Ошибка при захвате JPEG из Picamera2: %s', e)
            return None
    
    def release(self):
        """Освобождает ресурсы камеры"""
        try:
            if self._is_opened:
                self.picam2.stop()
                self._is_opened = False
        except Exception as e:
            logger.debug('Ошибка при освобождении Picamera2: %s', e)
    
    def get(self, prop_id):
        """Получает свойство камеры (для совместимости с cv2.VideoCapture)"""
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return self.width
        elif prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.height
        elif prop_id == cv2.CAP_PROP_FPS:
            return 30.0
        elif prop_id == cv2.CAP_PROP_FOURCC:
            return 0
        return 0
    
    def set(self, prop_id, value):
        """Устанавливает свойство камеры (для совместимости с cv2.VideoCapture)"""
        return False
    
    def getBackendName(self) -> str:
        """Возвращает имя backend"""
        return 'PICAMERA2'


def try_picamera2(index: int) -> Optional[Picamera2Wrapper]:
    """Попытка использовать Picamera2 для захвата кадров"""
    if not PICAMERA2_AVAILABLE:
        logger.debug('picamera2 не доступен, пропускаем')
        return None
    
    logger.info('Попытка использовать Picamera2 для захвата кадров')
    
    try:
        wrapper = Picamera2Wrapper(camera_index=index, width=1280, height=720)
        if wrapper.open():
            logger.info('✅ Камера открыта через Picamera2')
            return wrapper
        else:
            wrapper.release()
    except Exception as e:
        logger.debug('Ошибка при открытии камеры через Picamera2: %s', e)
    
    return None


def try_rpicam_gstreamer(index: int) -> Optional[cv2.VideoCapture]:
    """Попытка использовать rpicam-vid через GStreamer pipeline для PiCamera2"""
    rpicam_cmd = shutil.which('rpicam-vid') or shutil.which('libcamera-vid')
    if not rpicam_cmd:
        logger.debug('rpicam-vid/libcamera-vid не найден, пропускаем GStreamer pipeline')
        return None
    
    if not hasattr(cv2, 'CAP_GSTREAMER'):
        logger.debug('GStreamer backend не доступен в OpenCV')
        return None
    
    logger.info('Попытка использовать rpicam-vid через GStreamer pipeline')
    
    pipeline = (
        f'libcamerasrc camera={index} ! '
        'video/x-raw,width=1280,height=720,framerate=30/1 ! '
        'videoconvert ! '
        'video/x-raw,format=BGR ! '
        'appsink drop=true max-buffers=1'
    )
    
    try:
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if cap and cap.isOpened():
            logger.info('✅ Камера открыта через GStreamer (libcamera)')
            return cap
        else:
            if cap is not None:
                cap.release()
    except Exception as e:
        logger.debug('Ошибка при открытии камеры через GStreamer: %s', e)
    
    return None


def open_capture(index: int, scan_cameras_callback=None):
    """Открывает камеру с приоритетным порядком подключения"""
    if index < 0:
        logger.error('Индекс камеры должен быть неотрицательным, получено %s', index)
        return None

    logger.info('🎥 Подключение к локальной камере %s (backend: %s)', index, CAMERA_BACKEND)
    
    # ПРИОРИТЕТ 1: Пробуем Picamera2
    if PICAMERA2_AVAILABLE:
        logger.info('Пробуем использовать Picamera2 (нативный API для PiCamera2)')
        cap = try_picamera2(index)
        if cap and cap.isOpened():
            time.sleep(0.5)
            ret, frame = cap.read()
            if ret and frame is not None and (hasattr(frame, 'size') and frame.size > 0):
                logger.info('✅ Камера успешно подключена через Picamera2 (разрешение: %dx%d)', 
                           frame.shape[1], frame.shape[0])
                return cap
            else:
                if cap is not None:
                    cap.release()
                cap = None
    
    # ПРИОРИТЕТ 2: Пробуем указанный backend
    backend = None
    if CAMERA_BACKEND == 'V4L2':
        backend = cv2.CAP_V4L2
    elif CAMERA_BACKEND == 'GSTREAMER':
        backend = cv2.CAP_GSTREAMER
    elif CAMERA_BACKEND == 'AUTO':
        backend = None
    else:
        try:
            backend = int(CAMERA_BACKEND) if CAMERA_BACKEND.isdigit() else None
        except (ValueError, AttributeError):
            backend = None
    
    cap = None
    if backend is not None:
        cap = cv2.VideoCapture(index, backend)
    else:
        cap = cv2.VideoCapture(index)
    
    if not cap or not cap.isOpened():
        if cap is not None:
            cap.release()
        logger.warning('Не удалось открыть локальную камеру: %s (backend: %s)', index, CAMERA_BACKEND)
        
        # ПРИОРИТЕТ 3: GStreamer с libcamera
        if CAMERA_BACKEND == 'V4L2':
            logger.info('V4L2 не работает, пробуем GStreamer с libcamera (rpicam-vid)')
            cap = try_rpicam_gstreamer(index)
            if cap and cap.isOpened():
                time.sleep(0.5)
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    logger.info('✅ Камера успешно подключена через GStreamer (разрешение: %dx%d)', 
                               frame.shape[1], frame.shape[0])
                    return cap
                else:
                    if cap is not None:
                        cap.release()
                    cap = None
        
        # ПРИОРИТЕТ 4: AUTO backend
        if cap is None and CAMERA_BACKEND != 'AUTO':
            logger.info('Попытка открыть камеру с AUTO backend')
            cap = cv2.VideoCapture(index)
            if cap and cap.isOpened():
                logger.info('✅ Камера открыта с AUTO backend')
            else:
                if cap is not None:
                    cap.release()
                if scan_cameras_callback:
                    scan_cameras_callback(force=True)
                return None
        elif cap is None:
            if scan_cameras_callback:
                scan_cameras_callback(force=True)
            return None
    
    # Настройка параметров
    time.sleep(0.5)
    
    actual_backend = None
    try:
        actual_backend = cap.getBackendName()
    except Exception:
        pass
    
    if actual_backend and ('GSTREAMER' in actual_backend.upper() or 'PICAMERA2' in actual_backend.upper()):
        logger.debug('Пропускаем настройку параметров для %s (параметры уже заданы)', actual_backend)
    else:
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if backend == cv2.CAP_V4L2:
                formats_to_try = [
                    ('YUYV', cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V')),
                    ('RGB3', cv2.VideoWriter_fourcc('R', 'G', 'B', '3')),
                    ('BGR3', cv2.VideoWriter_fourcc('B', 'G', 'R', '3')),
                ]
                
                format_set = False
                for fmt_name, fmt_code in formats_to_try:
                    try:
                        if cap.set(cv2.CAP_PROP_FOURCC, fmt_code):
                            actual_fourcc = cap.get(cv2.CAP_PROP_FOURCC)
                            if actual_fourcc == fmt_code:
                                logger.info('✅ Установлен формат %s для V4L2', fmt_name)
                                format_set = True
                                break
                    except Exception:
                        continue
                
                if not format_set:
                    logger.debug('Не удалось установить явный формат, используем формат по умолчанию')
            
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
        except Exception as e:
            logger.debug('Не удалось установить некоторые параметры камеры: %s', e)
    
    time.sleep(0.5)
    
    # Проверка работоспособности
    ret = False
    frame = None
    max_attempts = 10
    for attempt in range(max_attempts):
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            logger.info('✅ Кадр успешно прочитан с попытки %d/%d (размер: %dx%d)', 
                       attempt + 1, max_attempts, frame.shape[1], frame.shape[0])
            break
        
        if attempt < max_attempts - 1:
            wait_time = 0.2 * (attempt + 1)
            logger.debug('Попытка %d/%d: кадр не получен, ожидание %.1f сек...', 
                       attempt + 1, max_attempts, wait_time)
            time.sleep(wait_time)
    
    if not ret or frame is None or (hasattr(frame, 'size') and frame.size == 0):
        logger.warning('Камера открыта, но не может получать кадры после %d попыток', max_attempts)
        try:
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            fourcc = cap.get(cv2.CAP_PROP_FOURCC)
            fps = cap.get(cv2.CAP_PROP_FPS)
            backend_name = cap.getBackendName()
            logger.warning('Параметры камеры: %dx%d, FOURCC=%s, FPS=%.2f, backend=%s', 
                         width, height, fourcc, fps, backend_name)
        except Exception:
            pass
        cap.release()
        if scan_cameras_callback:
            scan_cameras_callback(force=True)
        return None
    
    logger.info('✅ Камера успешно подключена (разрешение: %dx%d)', 
               int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
               int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
    
    return cap

