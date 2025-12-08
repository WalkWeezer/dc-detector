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
    jpeg_quality_stream: int = field(default=70)  # Quality for video stream
    jpeg_quality_save: int = field(default=85)  # Quality for saved images
    camera_indices: List[int] = field(default_factory=lambda: list(range(5)))
    # Tracker settings
    tracker_iou_threshold: float = field(default=0.3)
    tracker_max_age: int = field(default=5)
    tracker_min_hits: int = field(default=1)
    # Image transformation
    flip_horizontal: bool = field(default=False)
    flip_vertical: bool = field(default=False)
    rotate_angle: int = field(default=0)  # 0, 90, 180, 270
    # Queue and buffer settings
    max_infer_queue_size: int = field(default=2)
    raw_frames_buffer_size: int = field(default=30)
    # Inference settings
    input_size: int | None = field(default=None)  # None = use model default
    draw_detections: bool = field(default=True)
    # MavLink GPS settings
    mavlink_port: str | None = field(default=None)  # None = отключено. Примеры: '/dev/ttyAMA0' (GPIO UART), '/dev/ttyUSB0', 'udp:127.0.0.1:14550'
    mavlink_baudrate: int = field(default=57600)  # Скорость для последовательного порта (обычно 57600 или 115200)

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        defaults = cls()
        return cls(
            port=int(os.environ.get("PORT", defaults.port)),
            confidence_threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", defaults.confidence_threshold)),
            infer_fps=float(os.environ.get("INFER_FPS", defaults.infer_fps)),
            jpeg_quality=int(os.environ.get("JPEG_QUALITY", defaults.jpeg_quality)),
            jpeg_quality_stream=int(os.environ.get("JPEG_QUALITY_STREAM", defaults.jpeg_quality_stream)),
            jpeg_quality_save=int(os.environ.get("JPEG_QUALITY_SAVE", defaults.jpeg_quality_save)),
            camera_indices=_parse_camera_indices(os.environ.get("CAMERA_INDEX")),
            tracker_iou_threshold=float(os.environ.get("TRACKER_IOU_THRESHOLD", defaults.tracker_iou_threshold)),
            tracker_max_age=int(os.environ.get("TRACKER_MAX_AGE", defaults.tracker_max_age)),
            tracker_min_hits=int(os.environ.get("TRACKER_MIN_HITS", defaults.tracker_min_hits)),
            flip_horizontal=os.environ.get("FLIP_HORIZONTAL", "false").lower() in ("true", "1", "yes"),
            flip_vertical=os.environ.get("FLIP_VERTICAL", "false").lower() in ("true", "1", "yes"),
            rotate_angle=int(os.environ.get("ROTATE_ANGLE", defaults.rotate_angle)),
            max_infer_queue_size=int(os.environ.get("MAX_INFER_QUEUE_SIZE", defaults.max_infer_queue_size)),
            raw_frames_buffer_size=int(os.environ.get("RAW_FRAMES_BUFFER_SIZE", defaults.raw_frames_buffer_size)),
            input_size=int(os.environ.get("INPUT_SIZE", defaults.input_size)) if os.environ.get("INPUT_SIZE") else defaults.input_size,
            draw_detections=os.environ.get("DRAW_DETECTIONS", str(defaults.draw_detections)).lower() in ("true", "1", "yes"),
            mavlink_port=os.environ.get("MAVLINK_PORT") if os.environ.get("MAVLINK_PORT") else defaults.mavlink_port,
            mavlink_baudrate=int(os.environ.get("MAVLINK_BAUDRATE", defaults.mavlink_baudrate)),
        )


