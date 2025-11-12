"""Detection inference module"""
import logging
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ..tracking.sort_tracker import SortTracker

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = float(__import__('os').getenv('CONFIDENCE_THRESHOLD', '0.5'))


class InferenceEngine:
    """Класс для инференса детекций"""
    
    def __init__(self, model_manager, tracker: SortTracker, tracker_lock):
        self.model_manager = model_manager
        self.tracker = tracker
        self.tracker_lock = tracker_lock
    
    def _label_for_class(self, class_id: Optional[int], model) -> str:
        """Получает метку класса"""
        names = getattr(model, 'names', None)
        if isinstance(names, dict):
            return str(names.get(class_id, f'class_{class_id}'))
        if isinstance(names, (list, tuple)) and class_id is not None and 0 <= class_id < len(names):
            return str(names[class_id])
        return 'object'
    
    def infer(self, frame: np.ndarray, timestamp: float) -> Tuple[List[dict], np.ndarray, List[dict]]:
        """Выполняет инференс на кадре"""
        model = self.model_manager.get_model()
        if model is None:
            raise RuntimeError('Модель не загружена')
        
        results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
        annotated = frame.copy()
        raw_detections: List[dict] = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
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
        
        tracked = self.tracker.update(raw_detections, timestamp=timestamp)
        
        # Build stable tracks list
        stable_tracks: List[dict] = []
        try:
            with self.tracker_lock:
                for t in getattr(self.tracker, 'tracks', []) or []:
                    if getattr(t, 'hits', 0) >= getattr(self.tracker, 'min_hits', 1) and getattr(t, 'misses', 0) <= getattr(self.tracker, 'max_age', 5):
                        stable_tracks.append(t.to_dict())
        except Exception:
            stable_tracks = []
        
        # Draw detections
        for track in tracked:
            x1, y1, x2, y2 = map(int, track['bbox'])
            track_label = track.get('label') or 'object'
            caption = f"{track_label}#{track['trackId']} {track.get('confidence', 0.0):.2f}"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 70), 2)
            cv2.putText(annotated, caption, (x1, max(y1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 70), 2)
        
        return tracked, annotated, stable_tracks

