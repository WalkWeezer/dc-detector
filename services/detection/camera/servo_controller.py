"""Simple servo controller abstraction for targeting support."""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional, Sequence, Tuple

from .servo_hardware import create_servo_controller, HardwareServoController

logger = logging.getLogger(__name__)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


class ServoController:
    """Servo controller with optional hardware support.

    Keeps track of desired pan/tilt angles and can control real hardware servos.
    """

    def __init__(
        self,
        pan: float = 90.0,
        tilt: float = 90.0,
        hardware_controller: Optional[HardwareServoController] = None,
    ):
        self._pan = pan
        self._tilt = tilt
        self._lock = threading.Lock()
        # Movement sensitivity (degrees per update)
        self._step = 2.5
        self._hardware = hardware_controller
        self._last_pan = None
        self._last_tilt = None
        # Минимальное изменение угла для отправки на серво (чтобы не перегружать)
        self._min_change = 0.5

        # Инициализируем железо, если оно предоставлено
        if self._hardware:
            if self._hardware.initialize():
                logger.info("Hardware servos initialized successfully")
                # Устанавливаем начальную позицию
                self._hardware.set_angle("pan", self._pan)
                self._hardware.set_angle("tilt", self._tilt)
            else:
                logger.warning("Hardware servos initialization failed, using software mode")
                self._hardware = None

    @classmethod
    def from_config(cls, config=None) -> "ServoController":
        """Create ServoController from configuration."""
        # Читаем настройки из переменных окружения
        hardware_type = os.environ.get("SERVO_HARDWARE", "none").lower()
        
        if hardware_type == "none":
            return cls()
        
        # Параметры для GPIO
        pan_pin = os.environ.get("SERVO_PAN_PIN")
        tilt_pin = os.environ.get("SERVO_TILT_PIN")
        
        # Параметры для PCA9685
        pan_channel = os.environ.get("SERVO_PAN_CHANNEL")
        tilt_channel = os.environ.get("SERVO_TILT_CHANNEL")
        address = os.environ.get("SERVO_PCA9685_ADDRESS", "0x40")
        frequency = int(os.environ.get("SERVO_FREQUENCY", "50"))
        
        kwargs = {"frequency": frequency}
        if hardware_type == "pca9685":
            kwargs["address"] = int(address, 16) if isinstance(address, str) and address.startswith("0x") else int(address)
            if pan_channel:
                kwargs["pan_channel"] = int(pan_channel)
            if tilt_channel:
                kwargs["tilt_channel"] = int(tilt_channel)
        
        hardware = create_servo_controller(
            hardware_type=hardware_type,
            pan_pin=int(pan_pin) if pan_pin else None,
            tilt_pin=int(tilt_pin) if tilt_pin else None,
            **kwargs
        )
        
        return cls(hardware_controller=hardware)

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
            new_pan = clamp(self._pan + delta_pan, 0.0, 180.0)
            new_tilt = clamp(self._tilt - delta_tilt, 0.0, 180.0)
            
            # Обновляем только если изменение значительное
            if abs(new_pan - self._pan) >= self._min_change:
                self._pan = new_pan
            if abs(new_tilt - self._tilt) >= self._min_change:
                self._tilt = new_tilt

        # Отправляем на железо
        self._apply_to_hardware()

    def _apply_to_hardware(self) -> None:
        """Send angles to hardware servos if available."""
        with self._lock:
            pan = self._pan
            tilt = self._tilt
        
        # Отправляем только если угол изменился достаточно
        if self._hardware and self._hardware.is_available():
            if self._last_pan is None or abs(pan - self._last_pan) >= self._min_change:
                self._hardware.set_angle("pan", pan)
                self._last_pan = pan
            if self._last_tilt is None or abs(tilt - self._last_tilt) >= self._min_change:
                self._hardware.set_angle("tilt", tilt)
                self._last_tilt = tilt
        else:
            # Software-only mode - просто логируем
            logger.debug("Servo target pan=%.1f tilt=%.1f", pan, tilt)

    def get_state(self) -> dict:
        with self._lock:
            state = {
                "pan": round(self._pan, 2),
                "tilt": round(self._tilt, 2),
                "hardware_enabled": self._hardware is not None and self._hardware.is_available(),
            }
        return state

    def reset(self) -> None:
        """Reset servos to center position (90 degrees)."""
        with self._lock:
            self._pan = 90.0
            self._tilt = 90.0
        
        if self._hardware and self._hardware.is_available():
            self._hardware.set_angle("pan", 90.0)
            self._hardware.set_angle("tilt", 90.0)
            self._last_pan = 90.0
            self._last_tilt = 90.0

    def cleanup(self) -> None:
        """Cleanup hardware resources."""
        if self._hardware:
            self._hardware.cleanup()
            self._hardware = None


