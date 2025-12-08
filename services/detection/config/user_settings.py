"""Helpers for persisting user-facing detection settings."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_FILENAME = "detection-settings.json"
SETTINGS_PATH_ENV = "DC_DETECTOR_SETTINGS_PATH"
STATE_DIR_ENV = "DC_DETECTOR_STATE_DIR"


def _detect_settings_path() -> Path:
    """Resolve path to the JSON file that stores persisted settings."""
    custom_path = os.environ.get(SETTINGS_PATH_ENV)
    if custom_path:
        return Path(custom_path).expanduser().resolve()

    base_dir = os.environ.get(STATE_DIR_ENV)
    if base_dir:
        base_path = Path(base_dir).expanduser()
    else:
        base_path = Path(__file__).resolve().parent.parent / "data"
    return (base_path / DEFAULT_FILENAME).resolve()


SETTINGS_PATH = _detect_settings_path()

PERFORMANCE_FIELDS = (
    "infer_fps",
    "confidence_threshold",
    "max_infer_queue_size",
    "jpeg_quality_stream",
    "jpeg_quality_save",
    "input_size",
    "draw_detections",
    "raw_frames_buffer_size",
)

FLOAT_FIELDS = {"infer_fps", "confidence_threshold"}
INT_FIELDS = {"max_infer_queue_size", "jpeg_quality_stream", "jpeg_quality_save", "raw_frames_buffer_size"}
OPTIONAL_INT_FIELDS = {"input_size"}
BOOL_FIELDS = {"draw_detections"}


def get_settings_file_path() -> Path:
    """Public accessor for the resolved settings path (useful for logging)."""
    return SETTINGS_PATH


def load_user_settings() -> Dict[str, Any]:
    """Load persisted settings from disk."""
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return data
            logger.warning("Settings file %s does not contain an object, resetting", SETTINGS_PATH)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        logger.warning("Settings file %s is corrupted: %s", SETTINGS_PATH, exc)
    except OSError as exc:
        logger.warning("Failed to read settings file %s: %s", SETTINGS_PATH, exc)
    return {}


def _save_user_settings(state: Dict[str, Any]) -> Dict[str, Any]:
    """Persist settings to disk."""
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SETTINGS_PATH.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
    except OSError as exc:
        logger.warning("Failed to write settings file %s: %s", SETTINGS_PATH, exc)
    return state


def apply_performance_overrides(config, overrides: Optional[Dict[str, Any]]) -> bool:
    """Apply persisted performance overrides to a RuntimeConfig instance."""
    if not isinstance(overrides, dict):
        return False

    changed = False

    for field in PERFORMANCE_FIELDS:
        if field not in overrides:
            continue

        value = overrides[field]

        if field in FLOAT_FIELDS:
            try:
                casted = float(value)
            except (TypeError, ValueError):
                continue
        elif field in INT_FIELDS:
            try:
                casted = int(value)
            except (TypeError, ValueError):
                continue
        elif field in OPTIONAL_INT_FIELDS:
            if value is None:
                casted = None
            else:
                try:
                    casted = int(value)
                except (TypeError, ValueError):
                    continue
        elif field in BOOL_FIELDS:
            casted = bool(value)
        else:
            casted = value

        if getattr(config, field) != casted:
            setattr(config, field, casted)
            changed = True

    return changed


def snapshot_performance(config) -> Dict[str, Any]:
    """Create a serializable snapshot of the runtime performance settings."""
    return {
        "infer_fps": float(config.infer_fps),
        "confidence_threshold": float(config.confidence_threshold),
        "max_infer_queue_size": int(config.max_infer_queue_size),
        "jpeg_quality_stream": int(config.jpeg_quality_stream),
        "jpeg_quality_save": int(config.jpeg_quality_save),
        "input_size": None if config.input_size is None else int(config.input_size),
        "draw_detections": bool(config.draw_detections),
        "raw_frames_buffer_size": int(config.raw_frames_buffer_size),
    }


def persist_performance_config(config, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Persist the current performance-related config values."""
    data = dict(state or load_user_settings())
    data["performance"] = snapshot_performance(config)
    return _save_user_settings(data)


def get_saved_active_model(state: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Return the preferred model name if it was persisted earlier."""
    data = state if isinstance(state, dict) else load_user_settings()
    model_name = data.get("active_model")
    if isinstance(model_name, str) and model_name.strip():
        return model_name
    return None


def persist_active_model(model_name: Optional[str], state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Remember the most recently used model."""
    data = dict(state or load_user_settings())
    if model_name:
        data["active_model"] = model_name
    else:
        data.pop("active_model", None)
    return _save_user_settings(data)





