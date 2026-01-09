"""Tests for audio recording functionality."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from hanasu.recorder import (
    DeviceNotFoundError,
    Recorder,
    list_input_devices,
    refresh_devices,
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
        with patch("hanasu.recorder.sd"):
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


class TestRefreshDevices:
    """Test device refresh functionality for hotplug support."""

    def test_refresh_devices_updates_device_list(self):
        """refresh_devices() causes list_input_devices() to see newly connected devices."""
        with patch("hanasu.recorder.sd") as mock_sd:
            # Initially only built-in mic
            mock_sd.query_devices.return_value = [
                {"name": "Built-in Microphone", "max_input_channels": 2},
            ]

            devices_before = list_input_devices()
            assert "USB Microphone" not in devices_before

            # Simulate USB mic plugged in - query_devices returns new list after refresh
            def update_devices_after_reinit():
                mock_sd.query_devices.return_value = [
                    {"name": "Built-in Microphone", "max_input_channels": 2},
                    {"name": "USB Microphone", "max_input_channels": 1},
                ]

            mock_sd._initialize.side_effect = update_devices_after_reinit

            refresh_devices()

            devices_after = list_input_devices()
            assert "USB Microphone" in devices_after
            mock_sd._terminate.assert_called_once()
            mock_sd._initialize.assert_called_once()


class TestRecorderFallback:
    """Test graceful fallback when configured device is unavailable."""

    def test_recorder_falls_back_to_default_when_device_not_found(self):
        """Recorder falls back to system default when configured device is unavailable."""
        with patch("hanasu.recorder.sd") as mock_sd:
            mock_sd.query_devices.return_value = [
                {"name": "Built-in Microphone", "max_input_channels": 2},
            ]

            # Request a device that doesn't exist - should fall back to None (system default)
            recorder = Recorder(device="AirPods Pro", fallback_to_default=True)

            assert recorder.device is None  # Fell back to system default

    def test_recorder_still_raises_when_fallback_disabled(self):
        """Recorder raises DeviceNotFoundError when fallback is disabled."""
        with patch("hanasu.recorder.sd") as mock_sd:
            mock_sd.query_devices.return_value = [
                {"name": "Built-in Microphone", "max_input_channels": 2},
            ]

            # Default behavior (no fallback) should still raise
            with pytest.raises(DeviceNotFoundError, match="AirPods Pro"):
                Recorder(device="AirPods Pro")


class TestRecorderHotplug:
    """Test that recorder can use devices plugged in after app start."""

    def test_start_can_use_device_connected_after_init(self):
        """Recorder.start() refreshes devices, allowing use of newly connected mics."""
        with patch("hanasu.recorder.sd") as mock_sd:
            # Initially no USB mic
            mock_sd.query_devices.return_value = [
                {"name": "Built-in Microphone", "max_input_channels": 2},
            ]

            # Create recorder with default device
            recorder = Recorder(device=None)

            # Simulate USB mic plugged in after init
            def update_devices_after_reinit():
                mock_sd.query_devices.return_value = [
                    {"name": "Built-in Microphone", "max_input_channels": 2},
                    {"name": "USB Microphone", "max_input_channels": 1},
                ]

            mock_sd._initialize.side_effect = update_devices_after_reinit

            # Change device to the newly connected one
            recorder.device = "USB Microphone"

            # start() should refresh devices and successfully create stream
            recorder.start()

            # Verify stream was created with the USB mic
            mock_sd.InputStream.assert_called_once()
            call_kwargs = mock_sd.InputStream.call_args[1]
            assert call_kwargs["device"] == "USB Microphone"

            recorder.stop()
