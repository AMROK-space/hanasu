"""Tests for audio recording functionality."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from hanasu.recorder import (
    Recorder,
    DeviceNotFoundError,
    list_input_devices,
)


class TestRecorderStartStop:
    """Test recorder start/stop behavior."""

    def test_stop_returns_numpy_array(self):
        """Stopping recording returns audio as numpy array."""
        with patch("hanasu.recorder.sd") as mock_sd:
            # Mock the stream to provide audio data
            mock_stream = MagicMock()
            mock_sd.InputStream.return_value.__enter__ = MagicMock(return_value=mock_stream)
            mock_sd.InputStream.return_value.__exit__ = MagicMock(return_value=False)

            recorder = Recorder()
            recorder.start()
            # Simulate some audio being recorded
            recorder._buffer = [np.array([0.1, 0.2, 0.3], dtype=np.float32)]
            audio = recorder.stop()

            assert isinstance(audio, np.ndarray)
            assert audio.dtype == np.float32

    def test_stop_without_start_returns_empty_array(self):
        """Stopping without starting returns empty array."""
        recorder = Recorder()
        audio = recorder.stop()

        assert isinstance(audio, np.ndarray)
        assert len(audio) == 0

    def test_recording_accumulates_audio_chunks(self):
        """Multiple audio chunks are accumulated during recording."""
        with patch("hanasu.recorder.sd") as mock_sd:
            mock_stream = MagicMock()
            mock_sd.InputStream.return_value.__enter__ = MagicMock(return_value=mock_stream)
            mock_sd.InputStream.return_value.__exit__ = MagicMock(return_value=False)

            recorder = Recorder()
            recorder.start()
            # Simulate multiple chunks
            recorder._buffer = [
                np.array([0.1, 0.2], dtype=np.float32),
                np.array([0.3, 0.4], dtype=np.float32),
            ]
            audio = recorder.stop()

            assert len(audio) == 4


class TestRecorderDevice:
    """Test device selection."""

    def test_raises_error_when_device_not_found(self):
        """DeviceNotFoundError raised when specified device doesn't exist."""
        with patch("hanasu.recorder.sd") as mock_sd:
            mock_sd.query_devices.return_value = [
                {"name": "Built-in Microphone", "max_input_channels": 2},
            ]

            with pytest.raises(DeviceNotFoundError, match="AirPods Pro"):
                Recorder(device="AirPods Pro")

    def test_uses_specified_device_when_found(self):
        """Recorder uses specified device when it exists."""
        with patch("hanasu.recorder.sd") as mock_sd:
            mock_sd.query_devices.return_value = [
                {"name": "Built-in Microphone", "max_input_channels": 2},
                {"name": "AirPods Pro", "max_input_channels": 1},
            ]

            recorder = Recorder(device="AirPods Pro")

            assert recorder.device == "AirPods Pro"

    def test_uses_default_device_when_none_specified(self):
        """Recorder uses system default when no device specified."""
        with patch("hanasu.recorder.sd") as mock_sd:
            recorder = Recorder(device=None)

            assert recorder.device is None


class TestListInputDevices:
    """Test device enumeration."""

    def test_returns_only_input_devices(self):
        """list_input_devices returns only devices with input channels."""
        with patch("hanasu.recorder.sd") as mock_sd:
            mock_sd.query_devices.return_value = [
                {"name": "Built-in Microphone", "max_input_channels": 2},
                {"name": "Built-in Speakers", "max_input_channels": 0},
                {"name": "AirPods Pro", "max_input_channels": 1},
            ]

            devices = list_input_devices()

            assert "Built-in Microphone" in devices
            assert "AirPods Pro" in devices
            assert "Built-in Speakers" not in devices

    def test_returns_empty_list_when_no_input_devices(self):
        """Returns empty list when no input devices found."""
        with patch("hanasu.recorder.sd") as mock_sd:
            mock_sd.query_devices.return_value = [
                {"name": "Built-in Speakers", "max_input_channels": 0},
            ]

            devices = list_input_devices()

            assert devices == []
