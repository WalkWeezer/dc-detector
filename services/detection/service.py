"""Core detection microservice orchestration."""
from __future__ import annotations

import collections
import logging
import queue
import threading
import time
from typing import Optional

import numpy as np

from .camera.manager import CameraInitializationError, CameraManager
from .camera.servo_controller import ServoController
from .config.runtime import RuntimeConfig
from .mavlink.gps_reader import MavLinkGPSReader
from .config.user_settings import (
    apply_performance_overrides,
    get_saved_active_model,
    get_settings_file_path,
    load_user_settings,
    persist_active_model,
    persist_performance_config,
)
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
        self._settings_state = load_user_settings()
        overrides = self._settings_state.get("performance") if isinstance(self._settings_state, dict) else None
        if apply_performance_overrides(self.config, overrides):
            logger.info("Применены сохранённые настройки производительности (%s)", get_settings_file_path())

        self.camera = CameraManager(self.config)
        self.model_lock = threading.RLock()
        self.tracker_lock = threading.RLock()
        self.frame_lock = threading.Lock()
        self.stop_event = threading.Event()

        self.model_manager: Optional[ModelManager] = None
        self.tracker: Optional[SortTracker] = None
        self.inference_engine: Optional[InferenceEngine] = None
        self.detection_thread: Optional[threading.Thread] = None

        # Очередь кадров для инференса (пропуск старых кадров)
        self.infer_queue: queue.Queue = queue.Queue(maxsize=self.config.max_infer_queue_size)
        
        # Буфер сырых кадров для GIF (collections.deque с maxlen)
        self.raw_frames_buffer: collections.deque = collections.deque(
            maxlen=self.config.raw_frames_buffer_size
        )
        
        # Метрики производительности
        self.last_frame_process_time: float = 0.0  # Время обработки последнего кадра в секундах
        self.frame_process_times: collections.deque = collections.deque(maxlen=10)  # История времени обработки
        
        self.last_raw_frame: Optional[np.ndarray] = None
        self.last_annotated_frame: Optional[bytes] = None
        
        # Инициализация сервоприводов
        print("🔧 [SERVICE] Инициализация сервоприводов...")
        logger.info("🔧 Инициализация сервоприводов...")
        self.servo = ServoController.from_config(config)
        print("✅ [SERVICE] Сервоприводы инициализированы")
        logger.info("✅ Сервоприводы инициализированы")
        
        self.target_track_id: Optional[int] = None
        
        # Флаг автоследования сервоприводов (можно отключить через переменную окружения)
        import os
        self.servo_auto_tracking_enabled = os.environ.get("SERVO_AUTO_TRACKING", "true").lower() in ("true", "1", "yes")
        if not self.servo_auto_tracking_enabled:
            print("ℹ️  [SERVICE] Автоследование сервоприводов ОТКЛЮЧЕНО", flush=True)
            logger.info("ℹ️  Автоследование сервоприводов отключено (SERVO_AUTO_TRACKING=false)")
            # ПОЛНОСТЬЮ блокируем автоследование в ServoController
            self.servo._auto_tracking_disabled = True
            print("   [SERVICE] Автоследование заблокировано в ServoController", flush=True)
        
        # MavLink GPS reader
        self.mavlink_gps: Optional[MavLinkGPSReader] = None
        if config.mavlink_port:
            try:
                self.mavlink_gps = MavLinkGPSReader(config.mavlink_port, config.mavlink_baudrate)
            except Exception as exc:
                logger.warning("Не удалось инициализировать MavLink GPS reader: %s", exc)

    # Lifecycle -----------------------------------------------------------------------

    def start(self) -> None:
        """Start camera and detection thread."""
        try:
            self.camera.start()
            logger.info("Камера инициализирована: %s", self.camera.camera_type)
        except CameraInitializationError:
            logger.warning("Камера не инициализирована. Видео поток будет недоступен.")

        # Запускаем MavLink GPS reader если настроен
        if self.mavlink_gps:
            if self.mavlink_gps.start():
                logger.info("MavLink GPS reader запущен")
            else:
                logger.warning("Не удалось запустить MavLink GPS reader")

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
        # Cleanup servo hardware
        if self.servo:
            self.servo.cleanup()
        # Останавливаем MavLink GPS reader
        if self.mavlink_gps:
            self.mavlink_gps.stop()

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

        # Вычисляем среднее время обработки кадра
        avg_frame_time = 0.0
        if self.frame_process_times:
            avg_frame_time = sum(self.frame_process_times) / len(self.frame_process_times)

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
            # Метрики производительности
            "queue_size": self.infer_queue.qsize(),
            "frame_process_time_ms": round(avg_frame_time, 1) if avg_frame_time > 0 else None,
        }
        
        # Добавляем GPS координаты если доступны
        if self.mavlink_gps:
            gps_status = self.mavlink_gps.get_gps_with_status()
            payload["gps"] = gps_status

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
        # Используем последний кадр из буфера вместо копирования last_raw_frame
        if not self.raw_frames_buffer:
            with self.frame_lock:
                frame = self.last_raw_frame.copy() if self.last_raw_frame is not None else None
        else:
            # Используем последний кадр из буфера (уже скопирован)
            frame = self.raw_frames_buffer[-1]
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
            # Обновляем список моделей перед возвратом (чтобы подхватить новые ONNX модели)
            self.model_manager.refresh_available_models()
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
            self._remember_active_model(new_model)
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
    
    def get_gps(self) -> Optional[dict]:
        """
        Возвращает текущие GPS координаты.
        
        Returns:
            Dict с полями: latitude, longitude, altitude, fix_type, last_update, available
            или None если GPS не настроен
        """
        if not self.mavlink_gps:
            return None
        return self.mavlink_gps.get_gps_with_status()
    
    def get_gps_connection_status(self) -> Optional[dict]:
        """
        Возвращает детальный статус подключения MavLink.
        
        Returns:
            Dict с детальной информацией о состоянии подключения
            или None если GPS не настроен
        """
        if not self.mavlink_gps:
            return None
        return self.mavlink_gps.get_connection_status()
    
    def set_servo_angles(self, pan: Optional[float] = None, tilt: Optional[float] = None) -> dict:
        """
        Устанавливает углы сервоприводов вручную.
        
        Args:
            pan: Угол pan (0-180 градусов), None чтобы не изменять
            tilt: Угол tilt (0-180 градусов), None чтобы не изменять
        
        Returns:
            Dict с текущим состоянием сервоприводов
        """
        self.servo.set_angles(pan, tilt)
        return self.servo.get_state()

    # Internal logic ------------------------------------------------------------------

    def _init_models(self) -> None:
        try:
            base_dir = self._base_dir()
            models_dir = base_dir / "models"
            self.model_manager = ModelManager(models_dir, base_dir)
            self.model_manager.set_lock(self.model_lock)

            preferred_model = get_saved_active_model(self._settings_state)
            if preferred_model:
                try:
                    self.model_manager.load_model(preferred_model)
                    logger.info("Загружена ранее выбранная модель: %s", preferred_model)
                except FileNotFoundError:
                    logger.warning("Сохранённая модель %s не найдена, пробуем дефолтные", preferred_model)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.error("Не удалось загрузить сохранённую модель %s: %s", preferred_model, exc)

            candidate_paths = [
                models_dir / "yolov8n.pt",
                models_dir / "bestfire.pt",
                base_dir.parent / "models" / "yolov8n.pt",
            ]

            if self.model_manager.get_model() is None:
                for path in candidate_paths:
                    if path.exists():
                        try:
                            self.model_manager.load_model(str(path))
                            break
                        except Exception as exc:
                            logger.warning("Не удалось загрузить модель %s: %s", path, exc)

            if self.model_manager.get_model() is None:
                logger.warning("Модель не найдена, детекция отключена")
                return
            else:
                self._remember_active_model(self.model_manager.get_active_model())

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
        last_infer_time = 0.0
        
        while not self.stop_event.is_set():
            frame = self.camera.capture_raw()
            if frame is None:
                time.sleep(0.1)
                continue

            timestamp = time.time()
            
            # Добавляем сырой кадр в буфер для GIF (без копирования, используем view)
            # Копируем только если нужно сохранить в last_raw_frame
            with self.frame_lock:
                # Копируем только если действительно нужно (для get_tracker_crop)
                self.last_raw_frame = frame.copy()
            
            # Добавляем в буфер сырых кадров (копируем только при необходимости)
            # Используем view для экономии памяти, копируем только при добавлении в deque
            self.raw_frames_buffer.append(frame.copy())
            
            # Добавляем кадр в очередь для инференса (пропускаем старые)
            try:
                self.infer_queue.put_nowait((frame, timestamp))
            except queue.Full:
                # Удаляем самый старый кадр
                try:
                    self.infer_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.infer_queue.put_nowait((frame, timestamp))
                except queue.Full:
                    # Если очередь все еще полна, пропускаем этот кадр
                    continue
            
            # Обрабатываем инференс только если прошло достаточно времени
            if timestamp - last_infer_time >= frame_interval:
                try:
                    # Берем последний кадр из очереди
                    infer_frame, infer_timestamp = None, timestamp
                    while not self.infer_queue.empty():
                        try:
                            infer_frame, infer_timestamp = self.infer_queue.get_nowait()
                        except queue.Empty:
                            break
                    
                    if infer_frame is not None:
                        # Засекаем время обработки кадра
                        infer_start_time = time.time()
                        tracked, annotated, _ = self.inference_engine.infer(infer_frame, infer_timestamp)
                        infer_end_time = time.time()
                        
                        # Сохраняем время обработки
                        process_time = (infer_end_time - infer_start_time) * 1000  # в миллисекундах
                        self.last_frame_process_time = process_time
                        self.frame_process_times.append(process_time)
                        
                        # Обновляем кэш трекеров используя оригинальный кадр из буфера
                        # Используем последний кадр из буфера для трекинга
                        tracker_frame = self.raw_frames_buffer[-1] if self.raw_frames_buffer else infer_frame
                        
                        for track in tracked:
                            track_id = track.get("trackId")
                            bbox = track.get("bbox")
                            if track_id is not None and bbox:
                                update_tracker_cache(
                                    track_id,
                                    tracker_frame,  # Используем кадр из буфера
                                    bbox,
                                    {
                                        "label": track.get("label"),
                                        "confidence": track.get("confidence"),
                                        "timestamp": infer_timestamp,
                                    },
                                )

                        self._update_servo_target(tracked, infer_frame.shape)

                        # Кодируем кадр для потока
                        if annotated is not None:
                            success, buffer = self._encode_jpeg(annotated, stream=True)
                        else:
                            success, buffer = self._encode_jpeg(infer_frame, stream=True)
                        if success and buffer is not None:
                            with self.frame_lock:
                                self.last_annotated_frame = buffer
                        
                        last_infer_time = timestamp
                except Exception as exc:
                    if getattr(self.config, 'enable_logging', True):
                        logger.error("Ошибка детекции: %s", exc, exc_info=True)

            time.sleep(0.01)  # Небольшая задержка для снижения нагрузки

    def _encode_jpeg(self, frame: np.ndarray, stream: bool = False) -> tuple[bool, Optional[bytes]]:
        """Кодирует кадр в JPEG с выбором качества для потока или сохранения"""
        try:
            import cv2

            # Используем разное качество для потока и сохранения
            quality = self.config.jpeg_quality_stream if stream else self.config.jpeg_quality_save
            
            success, buffer = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, quality],
            )
        except Exception:
            return False, None
        if not success:
            return False, None
        return True, buffer.tobytes()

    def _base_dir(self):
        from pathlib import Path

        return Path(__file__).resolve().parent

    def _remember_active_model(self, model_name: Optional[str]) -> None:
        if not model_name:
            return
        self._settings_state = persist_active_model(model_name, self._settings_state)

    def persist_performance_snapshot(self) -> None:
        self._settings_state = persist_performance_config(self.config, self._settings_state)

    def _update_servo_target(self, tracked: list[dict], frame_shape: tuple[int, ...]) -> None:
        """Обновляет позицию сервоприводов для отслеживания цели."""
        # Полностью отключаем автоследование, если оно отключено в настройках
        if not self.servo_auto_tracking_enabled:
            return  # Автоследование отключено
        
        if not self.target_track_id or not tracked:
            return
        try:
            target = next((track for track in tracked if track.get("trackId") == self.target_track_id), None)
        except StopIteration:
            target = None
        if target and target.get("bbox"):
            self.servo.track_bbox(target["bbox"], frame_shape)



