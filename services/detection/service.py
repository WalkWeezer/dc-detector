"""Core detection microservice orchestration."""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import numpy as np

from .camera.manager import CameraInitializationError, CameraManager
from .camera.servo_controller import ServoController
from .config.runtime import RuntimeConfig
from .detection.inference import InferenceEngine
from .models.manager import ModelManager
from .tracking.sort_tracker import SortTracker
from .tracking.trackers import (
    crop_frame_for_tracker,
    get_active_trackers,
    get_tracker_by_id,
    get_tracker_frames,
    update_tracker_cache,
)

logger = logging.getLogger(__name__)


class DetectionService:
    """Coordinates camera capture, inference and tracker state."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.camera = CameraManager(config)
        self.model_lock = threading.RLock()
        self.tracker_lock = threading.RLock()
        self.frame_lock = threading.Lock()
        self.stop_event = threading.Event()

        self.model_manager: Optional[ModelManager] = None
        self.tracker: Optional[SortTracker] = None
        self.inference_engine: Optional[InferenceEngine] = None
        self.detection_thread: Optional[threading.Thread] = None

        self.last_raw_frame: Optional[np.ndarray] = None
        self.last_annotated_frame: Optional[bytes] = None
        self.servo = ServoController()
        self.target_track_id: Optional[int] = None

    # Lifecycle -----------------------------------------------------------------------

    def start(self) -> None:
        """Start camera and detection thread."""
        try:
            self.camera.start()
            logger.info("Камера инициализирована: %s", self.camera.camera_type)
        except CameraInitializationError:
            logger.warning("Камера не инициализирована. Видео поток будет недоступен.")

        self._init_models()
        if self.inference_engine:
            self.detection_thread = threading.Thread(target=self._detection_loop, name="detection-loop", daemon=True)
            self.detection_thread.start()

    def stop(self) -> None:
        """Stop threads and release resources."""
        self.stop_event.set()
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=3)
        self.camera.shutdown()

    # Properties ----------------------------------------------------------------------

    @property
    def camera_type(self) -> Optional[str]:
        return self.camera.camera_type

    # Public API ----------------------------------------------------------------------

    def capture_raw_jpeg(self) -> Optional[bytes]:
        return self.camera.capture_jpeg()

    def capture_annotated_jpeg(self) -> Optional[bytes]:
        with self.frame_lock:
            return self.last_annotated_frame

    def get_status_payload(self) -> dict:
        detection_enabled = self.inference_engine is not None
        model_loaded = self.model_manager is not None and self.model_manager.get_model() is not None
        tracker_active = self.tracker is not None
        detection_thread_running = self.detection_thread is not None and self.detection_thread.is_alive()

        payload = {
            "status": "ok",
            "detection_enabled": detection_enabled,
            "camera_available": self.camera_type is not None,
            "camera_type": self.camera_type,
            "model_loaded": model_loaded,
            "active_model": self.model_manager.get_active_model() if self.model_manager else None,
            "tracker_active": tracker_active,
            "detection_thread_running": detection_thread_running,
            "confidence_threshold": self.config.confidence_threshold,
            "infer_fps": self.config.infer_fps,
            "target_track_id": self.target_track_id,
            "servo": self.servo.get_state(),
        }

        if tracker_active:
            try:
                with self.tracker_lock:
                    payload["active_trackers_count"] = len(get_active_trackers(self.tracker))
            except Exception as exc:  # pragma: no cover - defensive
                payload["active_trackers_count"] = 0
                payload["tracker_error"] = str(exc)
        else:
            payload["active_trackers_count"] = 0

        return payload

    def list_trackers(self) -> dict:
        if not self.tracker:
            return {"trackers": [], "error": "Tracker not initialized"}
        with self.tracker_lock:
            trackers = get_active_trackers(self.tracker)
        for tracker in trackers:
            if tracker.get("trackId") == self.target_track_id:
                tracker["isTarget"] = True
            else:
                tracker["isTarget"] = False
        return {"trackers": trackers, "target_track_id": self.target_track_id}

    def get_tracker_crop(self, track_id: int) -> Optional[bytes]:
        if not self.tracker:
            return None
        with self.frame_lock:
            frame = self.last_raw_frame.copy() if self.last_raw_frame is not None else None
        if frame is None:
            return None
        with self.tracker_lock:
            track = get_tracker_by_id(track_id, self.tracker)
        if track is None or "bbox" not in track:
            return None
        return crop_frame_for_tracker(frame, track["bbox"])

    def get_tracker_frames_payload(self, track_id: int) -> dict:
        frames = get_tracker_frames(track_id)
        return {"track_id": track_id, "frames": frames}

    def list_models_payload(self) -> dict:
        if not self.model_manager:
            return {
                "available_models": [],
                "active_model": None,
                "error": "Model manager not initialized",
            }
        try:
            available = self.model_manager.get_available_models()
            active = self.model_manager.get_active_model()
            return {"available_models": available, "active_model": active}
        except Exception as exc:  # pragma: no cover - defensive
            return {"available_models": [], "active_model": None, "error": str(exc)}

    def switch_model(self, model_name: str) -> dict:
        if not self.model_manager:
            raise RuntimeError("Model manager not initialized")

        with self.model_lock:
            previous = self.model_manager.get_active_model()
            new_model = self.model_manager.switch_model(model_name)
            if new_model != previous and self.tracker:
                self.inference_engine = InferenceEngine(
                    self.model_manager,
                    self.tracker,
                    self.tracker_lock,
                    confidence_threshold=self.config.confidence_threshold,
                )
        return {"success": True, "active_model": new_model, "previous_model": previous}

    def set_target_track(self, track_id: Optional[int]) -> dict:
        if track_id is None:
            self.target_track_id = None
            self.servo.reset()
            return {"target_track_id": None, "servo": self.servo.get_state()}
        if not isinstance(track_id, int):
            raise ValueError("track_id must be int")
        self.target_track_id = track_id
        return {"target_track_id": track_id, "servo": self.servo.get_state()}

    # Internal logic ------------------------------------------------------------------

    def _init_models(self) -> None:
        try:
            base_dir = self._base_dir()
            models_dir = base_dir / "models"
            self.model_manager = ModelManager(models_dir, base_dir)
            self.model_manager.set_lock(self.model_lock)

            candidate_paths = [
                models_dir / "yolov8n.pt",
                models_dir / "bestfire.pt",
                base_dir.parent / "models" / "yolov8n.pt",
            ]

            for path in candidate_paths:
                if path.exists():
                    self.model_manager.load_model(str(path))
                    break

            if self.model_manager.get_model() is None:
                logger.warning("Модель не найдена, детекция отключена")
                return

            self.tracker = SortTracker(
                iou_threshold=self.config.tracker_iou_threshold,
                max_age=self.config.tracker_max_age,
                min_hits=self.config.tracker_min_hits,
            )
            logger.info(
                "Tracker инициализирован: iou=%.2f, max_age=%d, min_hits=%d",
                self.config.tracker_iou_threshold,
                self.config.tracker_max_age,
                self.config.tracker_min_hits,
            )
            self.inference_engine = InferenceEngine(
                self.model_manager,
                self.tracker,
                self.tracker_lock,
                confidence_threshold=self.config.confidence_threshold,
            )
            logger.info("Inference engine инициализирован")
        except Exception as exc:
            logger.error("Ошибка инициализации детекции: %s", exc, exc_info=True)

    def _detection_loop(self) -> None:
        if not self.inference_engine or not self.tracker:
            return

        frame_interval = 1.0 / max(self.config.infer_fps, 0.1)
        while not self.stop_event.is_set():
            frame = self.camera.capture_raw()
            if frame is None:
                time.sleep(0.1)
                continue

            with self.frame_lock:
                self.last_raw_frame = frame.copy()

            timestamp = time.time()
            try:
                tracked, annotated, _ = self.inference_engine.infer(frame, timestamp)
                for track in tracked:
                    track_id = track.get("trackId")
                    bbox = track.get("bbox")
                    if track_id is not None and bbox:
                        update_tracker_cache(
                            track_id,
                            frame,
                            bbox,
                            {
                                "label": track.get("label"),
                                "confidence": track.get("confidence"),
                                "timestamp": timestamp,
                            },
                        )

                self._update_servo_target(tracked, frame.shape)

                if annotated is not None:
                    success, buffer = self._encode_jpeg(annotated)
                else:
                    success, buffer = self._encode_jpeg(frame)
                if success and buffer is not None:
                    with self.frame_lock:
                        self.last_annotated_frame = buffer
            except Exception as exc:
                logger.error("Ошибка детекции: %s", exc, exc_info=True)

            time.sleep(frame_interval)

    def _encode_jpeg(self, frame: np.ndarray) -> tuple[bool, Optional[bytes]]:
        try:
            import cv2

            success, buffer = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, self.config.jpeg_quality],
            )
        except Exception:
            return False, None
        if not success:
            return False, None
        return True, buffer.tobytes()

    def _base_dir(self):
        from pathlib import Path

        return Path(__file__).resolve().parent

    def _update_servo_target(self, tracked: list[dict], frame_shape: tuple[int, ...]) -> None:
        if not self.target_track_id or not tracked:
            return
        try:
            target = next((track for track in tracked if track.get("trackId") == self.target_track_id), None)
        except StopIteration:
            target = None
        if target and target.get("bbox"):
            self.servo.track_bbox(target["bbox"], frame_shape)



