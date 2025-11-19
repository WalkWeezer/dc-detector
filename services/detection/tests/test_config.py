"""Tests for runtime configuration"""
import os
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from services.detection.config.runtime import RuntimeConfig, _parse_camera_indices


def test_default_config():
    """Test default configuration values"""
    config = RuntimeConfig()
    assert config.port == 8001
    assert config.confidence_threshold == 0.5
    assert config.infer_fps == 5.0
    assert config.jpeg_quality == 85
    assert config.tracker_iou_threshold == 0.3
    assert config.tracker_max_age == 5
    assert config.tracker_min_hits == 1
    assert len(config.camera_indices) == 5


def test_config_from_env():
    """Test configuration from environment variables"""
    os.environ['PORT'] = '9000'
    os.environ['CONFIDENCE_THRESHOLD'] = '0.7'
    os.environ['INFER_FPS'] = '10.0'
    os.environ['JPEG_QUALITY'] = '90'
    os.environ['TRACKER_IOU_THRESHOLD'] = '0.4'
    os.environ['TRACKER_MAX_AGE'] = '10'
    os.environ['TRACKER_MIN_HITS'] = '2'
    
    try:
        config = RuntimeConfig.from_env()
        assert config.port == 9000
        assert config.confidence_threshold == 0.7
        assert config.infer_fps == 10.0
        assert config.jpeg_quality == 90
        assert config.tracker_iou_threshold == 0.4
        assert config.tracker_max_age == 10
        assert config.tracker_min_hits == 2
    finally:
        # Cleanup
        for key in ['PORT', 'CONFIDENCE_THRESHOLD', 'INFER_FPS', 'JPEG_QUALITY',
                   'TRACKER_IOU_THRESHOLD', 'TRACKER_MAX_AGE', 'TRACKER_MIN_HITS']:
            os.environ.pop(key, None)


def test_parse_camera_indices():
    """Test parsing camera indices"""
    assert _parse_camera_indices(None) == list(range(5))
    assert _parse_camera_indices('0') == [0]
    assert _parse_camera_indices('0,1,2') == [0, 1, 2]
    assert _parse_camera_indices('0, 1, 2') == [0, 1, 2]
    assert _parse_camera_indices('invalid') == list(range(5))
    assert _parse_camera_indices('0,invalid,2') == [0, 2]

