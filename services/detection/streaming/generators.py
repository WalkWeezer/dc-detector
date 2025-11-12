"""MJPEG stream generators"""
import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def mjpeg_generator_raw(frame_getter: Callable[[], Optional[bytes]], interval: float = 0.01):
    """Генератор сырого MJPEG потока"""
    boundary = b'--frame'
    while True:
        frame = frame_getter()
        if frame is not None:
            yield (
                boundary + b"\r\n"
                + b'Content-Type: image/jpeg\r\n'
                + b'Content-Length: ' + str(len(frame)).encode() + b"\r\n\r\n"
                + frame + b"\r\n"
            )
            time.sleep(interval)
        else:
            time.sleep(0.2)


def mjpeg_generator_detections(frame_getter: Callable[[], Optional[bytes]], interval: float = 0.1):
    """Генератор MJPEG потока с детекциями"""
    boundary = b'--frame'
    while True:
        frame = frame_getter()
        if frame is not None:
            yield (
                boundary + b"\r\n"
                + b'Content-Type: image/jpeg\r\n'
                + b'Content-Length: ' + str(len(frame)).encode() + b"\r\n\r\n"
                + frame + b"\r\n"
            )
            time.sleep(interval)
        else:
            time.sleep(0.2)

