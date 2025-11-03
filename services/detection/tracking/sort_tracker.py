from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


def iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
    """Compute Intersection over Union between two boxes."""
    if box_a is None or box_b is None:
        return 0.0

    x_left = max(box_a[0], box_b[0])
    y_top = max(box_a[1], box_b[1])
    x_right = min(box_a[2], box_b[2])
    y_bottom = min(box_a[3], box_b[3])

    if x_right <= x_left or y_bottom <= y_top:
        return 0.0

    intersection = (x_right - x_left) * (y_bottom - y_top)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - intersection
    if union <= 0:
        return 0.0
    return intersection / union


@dataclass
class Track:
    track_id: int
    bbox: np.ndarray
    label: Optional[str]
    class_id: Optional[int]
    confidence: float
    first_seen: float
    last_seen: float
    hits: int = 1
    misses: int = 0
    history: List[np.ndarray] = field(default_factory=list)

    def update(self, bbox: np.ndarray, label: Optional[str], class_id: Optional[int], confidence: float, timestamp: float):
        self.bbox = bbox
        if label is not None:
            self.label = label
        if class_id is not None:
            self.class_id = class_id
        if confidence is not None:
            self.confidence = confidence
        self.last_seen = timestamp
        self.hits += 1
        self.misses = 0
        self.history.append(bbox)
        # Limit history to last 10 entries to control memory
        if len(self.history) > 10:
            self.history = self.history[-10:]

    def mark_missed(self):
        self.misses += 1

    def to_dict(self):
        return {
            'trackId': self.track_id,
            'bbox': self.bbox.tolist(),
            'label': self.label,
            'classId': self.class_id,
            'confidence': float(self.confidence),
            'firstSeen': self.first_seen,
            'lastSeen': self.last_seen,
            'hits': self.hits,
            'misses': self.misses
        }


class SortTracker:
    def __init__(self, iou_threshold: float = 0.3, max_age: int = 5, min_hits: int = 1):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        self.tracks: List[Track] = []
        self._next_id = 1

    def _match_tracks(self, detections: List[dict]) -> tuple[list[tuple[int, int]], set[int], set[int]]:
        unmatched_tracks = set(range(len(self.tracks)))
        unmatched_detections = set(range(len(detections)))
        matches: list[tuple[int, int]] = []

        if not detections or not self.tracks:
            return matches, unmatched_tracks, unmatched_detections

        for det_index, det in enumerate(detections):
            bbox_det = np.asarray(det['bbox'], dtype=float)
            best_iou = 0.0
            best_track_index: Optional[int] = None

            for track_index in list(unmatched_tracks):
                current_track = self.tracks[track_index]

                # 1) IOU с текущим bbox трека
                score_current = iou(current_track.bbox, bbox_det)

                # 2) IOU с предсказанной позицией (простая линейная модель скорости)
                score_predicted = 0.0
                if len(current_track.history) >= 2:
                    prev = current_track.history[-2]
                    curr = current_track.history[-1]
                    velocity = curr - prev
                    predicted = current_track.bbox + velocity
                    score_predicted = iou(predicted, bbox_det) * 0.85  # слегка меньший вес

                # 3) IOU со средним bbox последних точек
                score_avg = 0.0
                if len(current_track.history) >= 3:
                    recent = current_track.history[-3:]
                    avg_bbox = np.mean(recent, axis=0)
                    score_avg = iou(avg_bbox, bbox_det) * 0.8

                score = max(score_current, score_predicted, score_avg)

                if score > best_iou:
                    best_iou = score
                    best_track_index = track_index

            if best_track_index is not None and best_iou >= self.iou_threshold:
                matches.append((best_track_index, det_index))
                unmatched_tracks.discard(best_track_index)
                unmatched_detections.discard(det_index)

        return matches, unmatched_tracks, unmatched_detections

    def update(self, detections: List[dict], timestamp: Optional[float] = None) -> List[dict]:
        if timestamp is None:
            timestamp = time.time()

        normalized = []
        for det in detections or []:
            bbox = det.get('bbox')
            if not bbox or len(bbox) != 4:
                continue
            normalized.append({
                'bbox': np.asarray(bbox, dtype=float),
                'label': det.get('label'),
                'class_id': det.get('class_id'),
                'confidence': float(det.get('confidence', 0.0))
            })

        matches, unmatched_tracks, unmatched_detections = self._match_tracks(normalized)

        # Update matched tracks
        for track_index, det_index in matches:
            det = normalized[det_index]
            self.tracks[track_index].update(
                det['bbox'],
                det['label'],
                det['class_id'],
                det['confidence'],
                timestamp
            )

        # Age unmatched tracks
        for track_index in unmatched_tracks:
            self.tracks[track_index].mark_missed()

        # Create new tracks for unmatched detections
        for det_index in unmatched_detections:
            det = normalized[det_index]
            track = Track(
                track_id=self._next_id,
                bbox=det['bbox'],
                label=det.get('label'),
                class_id=det.get('class_id'),
                confidence=det.get('confidence', 0.0),
                first_seen=timestamp,
                last_seen=timestamp
            )
            track.history.append(det['bbox'])
            self.tracks.append(track)
            matches.append((len(self.tracks) - 1, det_index))
            self._next_id += 1

        # Remove stale tracks
        self.tracks = [track for track in self.tracks if track.misses <= self.max_age]

        # Prepare output for active tracks with recent updates
        active_tracks: List[dict] = []
        for track in self.tracks:
            if track.hits >= self.min_hits and track.misses == 0:
                active_tracks.append(track.to_dict())

        return active_tracks


