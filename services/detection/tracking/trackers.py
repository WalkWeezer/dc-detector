"""Tracker management and frame cropping"""
import base64
import logging
from collections import defaultdict
from typing import Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Кэш кадров для трекеров (max 30 кадров на трекер)
_tracker_frames_cache: Dict[int, List[bytes]] = defaultdict(lambda: [])
_tracker_metadata: Dict[int, dict] = {}
MAX_FRAMES_PER_TRACKER = 30


def update_tracker_cache(track_id: int, frame: np.ndarray, bbox: List[float], metadata: dict):
    """Обновляет кэш кадров для трекера"""
    if frame is None or frame.size == 0:
        return
    
    # Кроп кадра по bbox
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    
    # Ограничиваем координаты
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(x1 + 1, min(x2, w))
    y2 = max(y1 + 1, min(y2, h))
    
    if x2 <= x1 or y2 <= y1:
        return
    
    # Кроп и ресайз
    cropped = frame[y1:y2, x1:x2]
    if cropped.size == 0:
        return
    
    # Ресайз для экономии памяти (макс 320px по ширине)
    target_width = 320
    if cropped.shape[1] > target_width:
        scale = target_width / cropped.shape[1]
        new_height = int(cropped.shape[0] * scale)
        cropped = cv2.resize(cropped, (target_width, new_height))
    
    # Кодируем в JPEG
    success, buffer = cv2.imencode('.jpg', cropped, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        return
    
    jpeg_bytes = buffer.tobytes()
    
    # Добавляем в кэш
    cache = _tracker_frames_cache[track_id]
    cache.append(jpeg_bytes)
    
    # Ограничиваем размер кэша
    if len(cache) > MAX_FRAMES_PER_TRACKER:
        cache.pop(0)
    
    # Обновляем метаданные
    _tracker_metadata[track_id] = {
        **metadata,
        'bbox': bbox,
        'last_update': metadata.get('timestamp', 0)
    }


def get_active_trackers(tracker) -> List[dict]:
    """Получает список активных трекеров"""
    active = []
    try:
        for t in getattr(tracker, 'tracks', []) or []:
            if getattr(t, 'hits', 0) >= getattr(tracker, 'min_hits', 1):
                track_dict = t.to_dict()
                track_id = track_dict.get('trackId')
                if track_id is not None:
                    # Добавляем метаданные из кэша
                    if track_id in _tracker_metadata:
                        track_dict.update(_tracker_metadata[track_id])
                    active.append(track_dict)
    except Exception as e:
        logger.debug('Ошибка при получении активных трекеров: %s', e)
    
    return active


def get_tracker_by_id(track_id: int, tracker) -> Optional[dict]:
    """Получает трекер по ID"""
    try:
        for t in getattr(tracker, 'tracks', []) or []:
            track_dict = t.to_dict()
            if track_dict.get('trackId') == track_id:
                if track_id in _tracker_metadata:
                    track_dict.update(_tracker_metadata[track_id])
                return track_dict
    except Exception:
        pass
    return None


def crop_frame_for_tracker(frame: np.ndarray, bbox: List[float]) -> Optional[bytes]:
    """Кроп кадра по bbox и возвращает JPEG"""
    if frame is None or frame.size == 0:
        return None
    
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = map(int, bbox)
    
    # Ограничиваем координаты
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(x1 + 1, min(x2, w))
    y2 = max(y1 + 1, min(y2, h))
    
    if x2 <= x1 or y2 <= y1:
        return None
    
    cropped = frame[y1:y2, x1:x2]
    if cropped.size == 0:
        return None
    
    # Ресайз для экономии памяти
    target_width = 320
    if cropped.shape[1] > target_width:
        scale = target_width / cropped.shape[1]
        new_height = int(cropped.shape[0] * scale)
        cropped = cv2.resize(cropped, (target_width, new_height))
    
    success, buffer = cv2.imencode('.jpg', cropped, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        return None
    
    return buffer.tobytes()


def get_tracker_frames(track_id: int) -> List[str]:
    """Получает последовательность кропнутых кадров для трекера (base64)"""
    if track_id not in _tracker_frames_cache:
        return []
    
    frames = _tracker_frames_cache[track_id]
    return [base64.b64encode(frame).decode('utf-8') for frame in frames]


def clear_tracker_cache(track_id: Optional[int] = None):
    """Очищает кэш трекера (или всех трекеров)"""
    if track_id is not None:
        if track_id in _tracker_frames_cache:
            del _tracker_frames_cache[track_id]
        if track_id in _tracker_metadata:
            del _tracker_metadata[track_id]
    else:
        _tracker_frames_cache.clear()
        _tracker_metadata.clear()

