"""Model management module"""
import glob
import logging
from pathlib import Path
from typing import List, Optional

from ultralytics import YOLO

logger = logging.getLogger(__name__)


class ModelManager:
    """Класс для управления моделями YOLO"""
    
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
        
        models = sorted({Path(path).name for path in glob.glob(str(self.models_dir / '*.pt'))})
        self._available_models = models
        return models
    
    def _resolve_model_path(self, model_path: str) -> Optional[Path]:
        """Разрешает путь к модели"""
        candidate = Path(model_path)
        search_paths = []
        
        if candidate.is_absolute():
            search_paths.append(candidate)
        else:
            search_paths.extend([
                self.models_dir / candidate.name,
                self.models_dir / candidate,
                self.base_dir / candidate,
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
        """Загружает модель"""
        resolved = self._resolve_model_path(model_path)
        if resolved is None:
            raise FileNotFoundError(f'Не удалось найти модель: {model_path}')
        
        logger.info('🔍 Загрузка модели YOLO: %s', resolved)
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
    
    def get_model(self) -> Optional[YOLO]:
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

