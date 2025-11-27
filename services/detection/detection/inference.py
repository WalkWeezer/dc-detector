"""Detection inference module"""
import logging
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ..tracking.sort_tracker import SortTracker

logger = logging.getLogger(__name__)

# Дефолтный порог уверенности
DEFAULT_CONFIDENCE_THRESHOLD = 0.5


class InferenceEngine:
    """Класс для инференса детекций"""
    __slots__ = ('model_manager', 'tracker', 'tracker_lock', 'confidence_threshold', 'input_size', 'draw_detections')
    
    def __init__(self, model_manager, tracker: SortTracker, tracker_lock, confidence_threshold: Optional[float] = None, input_size: Optional[int] = None, draw_detections: bool = True):
        self.model_manager = model_manager
        self.tracker = tracker
        self.tracker_lock = tracker_lock
        self.confidence_threshold = confidence_threshold or DEFAULT_CONFIDENCE_THRESHOLD
        self.input_size = input_size  # Размер для ресайза перед инференсом (None = без ресайза)
        self.draw_detections = draw_detections  # Отключать отрисовку для оптимизации
    
    def _label_for_class(self, class_id: Optional[int], model) -> str:
        """Получает метку класса"""
        names = getattr(model, 'names', None)
        if isinstance(names, dict):
            return str(names.get(class_id, f'class_{class_id}'))
        if isinstance(names, (list, tuple)) and class_id is not None and 0 <= class_id < len(names):
            return str(names[class_id])
        return 'object'
    
    def infer(self, frame: np.ndarray, timestamp: float) -> Tuple[List[dict], np.ndarray, List[dict]]:
        """Выполняет инференс на кадре с опциональным ресайзом"""
        model = self.model_manager.get_model()
        if model is None:
            raise RuntimeError('Модель не загружена')
        
        # Ресайз кадра перед инференсом для оптимизации
        original_shape = frame.shape[:2]  # (height, width)
        infer_frame = frame
        scale_x, scale_y = 1.0, 1.0
        
        if self.input_size and self.input_size > 0:
            h, w = original_shape
            # Ресайз с сохранением пропорций
            if w > h:
                new_w = self.input_size
                new_h = int(h * (self.input_size / w))
            else:
                new_h = self.input_size
                new_w = int(w * (self.input_size / h))
            
            infer_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            scale_x = w / new_w
            scale_y = h / new_h
        
        # Инференс на ресайзнутом кадре
        results = model(infer_frame, conf=self.confidence_threshold, verbose=False)
        
        # Копируем оригинальный кадр только если нужна отрисовка
        annotated = frame.copy() if self.draw_detections else None
        raw_detections: List[dict] = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                
                # Масштабируем bbox обратно к оригинальному размеру
                if self.input_size and self.input_size > 0:
                    x1 = x1 * scale_x
                    y1 = y1 * scale_y
                    x2 = x2 * scale_x
                    y2 = y2 * scale_y
                
                confidence = float(box.conf[0].cpu().numpy())
                class_id = None
                if hasattr(box, 'cls') and box.cls is not None:
                    class_values = box.cls.cpu().numpy()
                    if class_values.size:
                        class_id = int(class_values[0])
                label = self._label_for_class(class_id, model)
                raw_detections.append({
                    'bbox': [float(x1), float(y1), float(x2), float(y2)],
                    'confidence': confidence,
                    'class_id': class_id,
                    'label': label
                })
        
        with self.tracker_lock:
            tracked = self.tracker.update(raw_detections, timestamp=timestamp)
            stable_tracks = self._collect_stable_tracks_locked()
        
        # Draw detections только если включено
        if self.draw_detections and annotated is not None:
            for track in tracked:
                x1, y1, x2, y2 = map(int, track['bbox'])
                track_label = track.get('label') or 'object'
                caption = f"{track_label}#{track['trackId']} {track.get('confidence', 0.0):.2f}"
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 70), 2)
                cv2.putText(annotated, caption, (x1, max(y1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 70), 2)
        
        return tracked, annotated, stable_tracks

    def _collect_stable_tracks_locked(self) -> List[dict]:
        stable_tracks: List[dict] = []
        try:
            for t in getattr(self.tracker, 'tracks', []) or []:
                if getattr(t, 'hits', 0) >= getattr(self.tracker, 'min_hits', 1) and getattr(t, 'misses', 0) <= getattr(self.tracker, 'max_age', 5):
                    stable_tracks.append(t.to_dict())
        except Exception:
            return []
        return stable_tracks

