"""Simple servo controller abstraction for targeting support."""
from __future__ import annotations

import logging
import threading
from typing import Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


class ServoController:
    """Software-only servo controller stub.

    Keeps track of desired pan/tilt angles and exposes a hook for real hardware.
    """

    def __init__(self, pan: float = 90.0, tilt: float = 90.0):
        self._pan = pan
        self._tilt = tilt
        self._lock = threading.Lock()
        # Movement sensitivity (degrees per update)
        self._step = 2.5

    def track_bbox(self, bbox: Sequence[float], frame_shape: Tuple[int, int]) -> None:
        """Adjust servo angles trying to keep bbox center near frame center."""
        if not bbox or len(bbox) < 4:
            return
        height, width = frame_shape[:2]
        if width <= 0 or height <= 0:
            return

        x1, y1, x2, y2 = map(float, bbox[:4])
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        err_x = (cx - width / 2.0) / width
        err_y = (cy - height / 2.0) / height

        # Positive err_x -> object to the right, need to increase pan (turn right)
        delta_pan = err_x * self._step * 12  # amplify to be responsive
        delta_tilt = err_y * self._step * 12

        with self._lock:
            self._pan = clamp(self._pan + delta_pan, 0.0, 180.0)
            self._tilt = clamp(self._tilt - delta_tilt, 0.0, 180.0)

        # Hook point for real hardware control
        self._apply_to_hardware()

    def _apply_to_hardware(self) -> None:
        """Override in subclasses to actually move servos."""
        # For now we simply log — this keeps behaviour deterministic in dev mode.
        logger.debug("Servo target pan=%.1f tilt=%.1f", self._pan, self._tilt)

    def get_state(self) -> dict:
        with self._lock:
            return {
                "pan": round(self._pan, 2),
                "tilt": round(self._tilt, 2),
            }

    def reset(self) -> None:
        with self._lock:
            self._pan = 90.0
            self._tilt = 90.0


