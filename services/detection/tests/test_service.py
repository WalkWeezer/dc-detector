"""Tests for DetectionService"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from services.detection.config.runtime import RuntimeConfig
from services.detection.service import DetectionService
from services.detection.camera.manager import CameraInitializationError


@pytest.fixture
def config():
    """Test configuration"""
    return RuntimeConfig(
        port=8001,
        confidence_threshold=0.5,
        infer_fps=5.0,
        jpeg_quality=85
    )


@pytest.fixture
def mock_camera_manager():
    """Mock camera manager"""
    with patch('services.detection.service.CameraManager') as mock:
        manager = MagicMock()
        manager.camera_type = 'webcam'
        manager.start = MagicMock()
        manager.shutdown = MagicMock()
        manager.capture_raw = MagicMock(return_value=None)
        manager.capture_jpeg = MagicMock(return_value=None)
        mock.return_value = manager
        yield manager


@pytest.fixture(autouse=True)
def stub_init_models(monkeypatch):
    """Prevent heavy model initialization in tests"""

    def _noop(self):
        self.model_manager = None
        self.tracker = None
        self.inference_engine = None

    monkeypatch.setattr(DetectionService, '_init_models', _noop)


def test_service_initialization(config, mock_camera_manager):
    """Test service initialization"""
    service = DetectionService(config)
    assert service.config == config
    assert service.camera is not None
    assert service.model_manager is None
    assert service.tracker is None
    assert service.inference_engine is None


def test_service_start_without_camera(config, mock_camera_manager):
    """Test service start when camera initialization fails"""
    mock_camera_manager.camera_type = None
    mock_camera_manager.start.side_effect = CameraInitializationError("No camera")
    
    service = DetectionService(config)
    service.start()  # Should not raise
    
    assert service.camera_type is None


def test_service_stop(config, mock_camera_manager):
    """Test service stop"""
    service = DetectionService(config)
    service.start()
    service.stop()
    
    assert service.stop_event.is_set()
    mock_camera_manager.shutdown.assert_called_once()


def test_service_status_payload(config, mock_camera_manager):
    """Test status payload generation"""
    service = DetectionService(config)
    service.start()
    
    status = service.get_status_payload()
    assert status['status'] == 'ok'
    assert status['camera_available'] is True
    assert status['camera_type'] == 'webcam'
    assert status['detection_enabled'] is False  # No model loaded
    assert status['active_trackers_count'] == 0


def test_list_trackers_without_tracker(config, mock_camera_manager):
    """Test listing trackers when tracker is not initialized"""
    service = DetectionService(config)
    service.start()
    
    result = service.list_trackers()
    assert result['trackers'] == []
    assert 'error' in result


def test_get_tracker_crop_without_tracker(config, mock_camera_manager):
    """Test getting tracker crop when tracker is not initialized"""
    service = DetectionService(config)
    service.start()
    
    crop = service.get_tracker_crop(1)
    assert crop is None


def test_list_models_without_manager(config, mock_camera_manager):
    """Test listing models when model manager is not initialized"""
    service = DetectionService(config)
    service.start()
    
    result = service.list_models_payload()
    assert result['available_models'] == []
    assert result['active_model'] is None
    assert 'error' in result

