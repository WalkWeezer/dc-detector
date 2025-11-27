"""Runtime configuration helpers for the detection microservice."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


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
    jpeg_quality: int = field(default=85)  # Для обратной совместимости
    jpeg_quality_stream: int = field(default=60)  # Для MJPEG потока (ниже качество)
    jpeg_quality_save: int = field(default=85)  # Для сохранения детекций
    camera_indices: List[int] = field(default_factory=lambda: list(range(5)))
    # Tracker settings
    tracker_iou_threshold: float = field(default=0.3)
    tracker_max_age: int = field(default=5)
    tracker_min_hits: int = field(default=1)
    # Image transformation
    flip_horizontal: bool = field(default=False)
    flip_vertical: bool = field(default=False)
    rotate_angle: int = field(default=0)  # 0, 90, 180, 270
    # Performance optimization
    max_infer_queue_size: int = field(default=2)  # Максимальный размер очереди для инференса
    raw_frames_buffer_size: int = field(default=30)  # Размер буфера сырых кадров для GIF
    input_size: Optional[int] = field(default=640)  # Размер входного изображения для инференса (None = без ресайза)
    draw_detections: bool = field(default=True)  # Отрисовка детекций на сервере
    enable_logging: bool = field(default=True)  # Логирование в production

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        defaults = cls()
        # Для обратной совместимости: если задан JPEG_QUALITY, используем его для обоих
        jpeg_quality_env = os.environ.get("JPEG_QUALITY")
        if jpeg_quality_env:
            jpeg_q = int(jpeg_quality_env)
            jpeg_quality_stream = jpeg_q
            jpeg_quality_save = jpeg_q
        else:
            jpeg_quality_stream = int(os.environ.get("JPEG_QUALITY_STREAM", defaults.jpeg_quality_stream))
            jpeg_quality_save = int(os.environ.get("JPEG_QUALITY_SAVE", defaults.jpeg_quality_save))
        
        input_size_env = os.environ.get("INPUT_SIZE")
        input_size = int(input_size_env) if input_size_env else defaults.input_size
        
        return cls(
            port=int(os.environ.get("PORT", defaults.port)),
            confidence_threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", defaults.confidence_threshold)),
            infer_fps=float(os.environ.get("INFER_FPS", defaults.infer_fps)),
            jpeg_quality=jpeg_quality_save,  # Для обратной совместимости
            jpeg_quality_stream=jpeg_quality_stream,
            jpeg_quality_save=jpeg_quality_save,
            camera_indices=_parse_camera_indices(os.environ.get("CAMERA_INDEX")),
            tracker_iou_threshold=float(os.environ.get("TRACKER_IOU_THRESHOLD", defaults.tracker_iou_threshold)),
            tracker_max_age=int(os.environ.get("TRACKER_MAX_AGE", defaults.tracker_max_age)),
            tracker_min_hits=int(os.environ.get("TRACKER_MIN_HITS", defaults.tracker_min_hits)),
            flip_horizontal=os.environ.get("FLIP_HORIZONTAL", "false").lower() in ("true", "1", "yes"),
            flip_vertical=os.environ.get("FLIP_VERTICAL", "false").lower() in ("true", "1", "yes"),
            rotate_angle=int(os.environ.get("ROTATE_ANGLE", defaults.rotate_angle)),
            max_infer_queue_size=int(os.environ.get("MAX_INFER_QUEUE_SIZE", defaults.max_infer_queue_size)),
            raw_frames_buffer_size=int(os.environ.get("RAW_FRAMES_BUFFER_SIZE", defaults.raw_frames_buffer_size)),
            input_size=input_size,
            draw_detections=os.environ.get("DRAW_DETECTIONS", "true").lower() in ("true", "1", "yes"),
            enable_logging=os.environ.get("ENABLE_LOGGING", "true").lower() in ("true", "1", "yes"),
        )


