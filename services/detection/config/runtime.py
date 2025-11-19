"""Runtime configuration helpers for the detection microservice."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _parse_camera_indices(value: str | None) -> List[int]:
    if not value:
        return list(range(5))
    parts = [p.strip() for p in value.split(',') if p.strip()]
    indices: List[int] = []
    for part in parts:
        try:
            indices.append(int(part))
        except ValueError:
            # Ignore invalid entries but keep discovery going
            continue
    return indices or list(range(5))


@dataclass(slots=True)
class RuntimeConfig:
    """Container for environment-driven runtime settings."""

    port: int = field(default=8001)
    confidence_threshold: float = field(default=0.5)
    infer_fps: float = field(default=5.0)
    jpeg_quality: int = field(default=85)
    camera_indices: List[int] = field(default_factory=lambda: list(range(5)))
    # Tracker settings
    tracker_iou_threshold: float = field(default=0.3)
    tracker_max_age: int = field(default=5)
    tracker_min_hits: int = field(default=1)

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        defaults = cls()
        return cls(
            port=int(os.environ.get("PORT", defaults.port)),
            confidence_threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", defaults.confidence_threshold)),
            infer_fps=float(os.environ.get("INFER_FPS", defaults.infer_fps)),
            jpeg_quality=int(os.environ.get("JPEG_QUALITY", defaults.jpeg_quality)),
            camera_indices=_parse_camera_indices(os.environ.get("CAMERA_INDEX")),
            tracker_iou_threshold=float(os.environ.get("TRACKER_IOU_THRESHOLD", defaults.tracker_iou_threshold)),
            tracker_max_age=int(os.environ.get("TRACKER_MAX_AGE", defaults.tracker_max_age)),
            tracker_min_hits=int(os.environ.get("TRACKER_MIN_HITS", defaults.tracker_min_hits)),
        )


