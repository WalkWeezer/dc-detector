"""Model management module"""
import glob
import logging
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ultralytics import YOLO

logger = logging.getLogger(__name__)

# Ленивая загрузка YOLO
_yolo_module = None

def _get_yolo():
    """Ленивая загрузка ultralytics.YOLO"""
    global _yolo_module
    if _yolo_module is None:
        from ultralytics import YOLO
        _yolo_module = YOLO
    return _yolo_module


class ModelManager:
    """Класс для управления моделями YOLO"""
    __slots__ = ('models_dir', 'base_dir', '_model_lock', 'model', 'model_path', 'model_name', '_available_models')
    
    def __init__(self, models_dir: Path, base_dir: Path):
        self.models_dir = models_dir
        self.base_dir = base_dir
        self._model_lock = None  # Будет установлен извне
        self.model: Optional[YOLO] = None
        self.model_path: Optional[Path] = None
        self.model_name: Optional[str] = None
        self._available_models: List[str] = []
    
    def set_lock(self, lock):
        """Устанавливает lock для потокобезопасности"""
        self._model_lock = lock
    
    def refresh_available_models(self) -> List[str]:
        """Обновляет список доступных моделей"""
        try:
            self.models_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning('Не удалось создать каталог моделей %s: %s', self.models_dir, exc)
        
        # Поддержка разных форматов: .pt, .onnx, .ptl
        patterns = ['*.pt', '*.onnx', '*.ptl']
        models = set()
        for pattern in patterns:
            models.update(Path(path).name for path in glob.glob(str(self.models_dir / pattern)))
        
        self._available_models = sorted(models)
        return self._available_models
    
    def _resolve_model_path(self, model_path: str) -> Optional[Path]:
        """Разрешает путь к модели (поддерживает .pt, .onnx, .ptl)"""
        candidate = Path(model_path)
        search_paths = []
        
        # Если расширение не указано, ищем все форматы
        if not candidate.suffix:
            extensions = ['.pt', '.onnx', '.ptl']
        else:
            extensions = [candidate.suffix]
        
        if candidate.is_absolute():
            for ext in extensions:
                search_paths.append(candidate.with_suffix(ext))
        else:
            for ext in extensions:
                search_paths.extend([
                    self.models_dir / candidate.with_suffix(ext).name,
                    self.models_dir / candidate.with_suffix(ext),
                    self.base_dir / candidate.with_suffix(ext),
                ])
        
        for path in search_paths:
            try:
                resolved = path.resolve(strict=True)
            except FileNotFoundError:
                continue
            if resolved.is_file():
                return resolved
        return None
    
    def load_model(self, model_path: str):
        """Загружает модель (поддерживает .pt, .onnx, .ptl)"""
        resolved = self._resolve_model_path(model_path)
        if resolved is None:
            raise FileNotFoundError(f'Не удалось найти модель: {model_path}')
        
        model_ext = resolved.suffix.lower()
        logger.info('🔍 Загрузка модели: %s (формат: %s)', resolved, model_ext)
        
        # Для ONNX используем ONNX Runtime, для остальных - YOLO
        if model_ext == '.onnx':
            try:
                import onnxruntime as ort
                # ONNX модели загружаются через YOLO, который поддерживает ONNX
                YOLO = _get_yolo()
                model = YOLO(str(resolved))
                logger.info('Модель загружена через ONNX Runtime')
            except ImportError:
                logger.warning('ONNX Runtime не установлен, используем стандартный YOLO')
                YOLO = _get_yolo()
                model = YOLO(str(resolved))
        else:
            # Стандартные .pt и .ptl модели
            YOLO = _get_yolo()
            model = YOLO(str(resolved))
        
        if self._model_lock:
            with self._model_lock:
                self.model = model
                self.model_path = resolved
                self.model_name = resolved.name
        else:
            self.model = model
            self.model_path = resolved
            self.model_name = resolved.name
        
        available = self.refresh_available_models()
        if self.model_name not in available:
            available.append(self.model_name)
            available.sort()
            self._available_models = available
    
    def optimize_model(self, model_path: str, output_path: Optional[str] = None, format: str = 'onnx') -> Optional[Path]:
        """Конвертирует модель в оптимизированный формат"""
        resolved = self._resolve_model_path(model_path)
        if resolved is None:
            raise FileNotFoundError(f'Не удалось найти модель: {model_path}')
        
        if format.lower() == 'onnx':
            YOLO = _get_yolo()
            model = YOLO(str(resolved))
            
            if output_path is None:
                output_path = str(resolved.with_suffix('.onnx'))
            else:
                output_path = str(Path(output_path))
            
            logger.info('Конвертация модели в ONNX: %s -> %s', resolved, output_path)
            try:
                # Экспорт в ONNX с оптимизацией для CPU
                model.export(format='onnx', imgsz=640, optimize=True)
                logger.info('✅ Модель успешно конвертирована в ONNX')
                return Path(output_path)
            except Exception as exc:
                logger.error('Ошибка конвертации в ONNX: %s', exc)
                return None
        else:
            logger.warning('Неподдерживаемый формат оптимизации: %s', format)
            return None
    
    def get_model(self) -> Optional['YOLO']:
        """Получает текущую модель"""
        if self._model_lock:
            with self._model_lock:
                return self.model
        return self.model
    
    def get_active_model(self) -> Optional[str]:
        """Получает имя активной модели"""
        return self.model_name
    
    def get_available_models(self) -> List[str]:
        """Получает список доступных моделей"""
        return list(self._available_models)
    
    def switch_model(self, model_name: str) -> str:
        """Переключает модель"""
        resolved = self._resolve_model_path(model_name)
        if resolved is None:
            raise FileNotFoundError(f'Не найдена модель "{model_name}"')
        
        if self.model_name == resolved.name:
            logger.info('Модель %s уже активна, повторная загрузка не требуется', resolved.name)
            return self.model_name
        
        self.load_model(str(resolved))
        logger.info('✅ Активная модель переключена на %s', resolved.name)
        return self.model_name

