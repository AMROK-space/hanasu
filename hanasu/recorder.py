"""Audio recording functionality for Hanasu."""

from typing import Optional
import numpy as np
import sounddevice as sd


# Whisper expects 16kHz sample rate
SAMPLE_RATE = 16000


class DeviceNotFoundError(Exception):
    """Raised when specified audio device is not found."""
    pass


class Recorder:
    """Records audio from microphone."""

    def __init__(self, device: Optional[str] = None):
        """Initialize recorder with optional device name.

        Args:
            device: Name of audio input device, or None for system default.

        Raises:
            DeviceNotFoundError: If specified device is not found.
        """
        self.device = device
        self._buffer: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._recording = False

        # Validate device exists if specified
        if device is not None:
            available = list_input_devices()
            if device not in available:
                raise DeviceNotFoundError(
                    f"Audio device not found: {device}. "
                    f"Available devices: {', '.join(available)}"
                )

    def _audio_callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        """Callback for audio stream - accumulates audio chunks."""
        if self._recording:
            self._buffer.append(indata.copy().flatten())

    def start(self) -> None:
        """Start recording audio."""
        self._buffer = []
        self._recording = True
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.float32,
            device=self.device,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop recording and return audio buffer as numpy array."""
        self._recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._buffer:
            return np.array([], dtype=np.float32)

        return np.concatenate(self._buffer).astype(np.float32)


def list_input_devices() -> list[str]:
    """List available audio input devices.

    Returns:
        List of device names that have input channels.
    """
    devices = sd.query_devices()
    return [
        d["name"]
        for d in devices
        if d["max_input_channels"] > 0
    ]
