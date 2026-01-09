"""Audio recording functionality for Hanasu."""

import numpy as np
import sounddevice as sd

# Whisper expects 16kHz sample rate
SAMPLE_RATE = 16000


class DeviceNotFoundError(Exception):
    """Raised when specified audio device is not found."""

    pass


def refresh_devices() -> None:
    """Refresh the audio device list by reinitializing PortAudio.

    This is necessary to detect devices plugged in after the app started,
    as PortAudio caches the device list on first initialization.

    Note: Uses private sounddevice APIs (_terminate, _initialize).
    If refresh fails, continues with the existing device list.
    """
    try:
        sd._terminate()
        sd._initialize()
    except Exception:
        # If refresh fails, continue with existing device list rather than crash
        pass


class Recorder:
    """Records audio from microphone."""

    def __init__(self, device: str | None = None, fallback_to_default: bool = False):
        """Initialize recorder with optional device name.

        Args:
            device: Name of audio input device, or None for system default.
            fallback_to_default: If True, fall back to system default when
                specified device is not found. If False, raise DeviceNotFoundError.

        Raises:
            DeviceNotFoundError: If specified device is not found and fallback_to_default is False.
        """
        self.device = device
        self._buffer: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._recording = False

        # Validate device exists if specified
        if device is not None:
            available = list_input_devices()
            if device not in available:
                if fallback_to_default:
                    self.device = None  # Fall back to system default
                else:
                    raise DeviceNotFoundError(
                        f"Audio device not found: {device}. Available devices: {', '.join(available)}"
                    )

    def _audio_callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        """Callback for audio stream - accumulates audio chunks."""
        if self._recording:
            self._buffer.append(indata.copy().flatten())

    def start(self) -> None:
        """Start recording audio.

        Refreshes the device list before recording to detect any
        microphones plugged in since the app started.
        """
        refresh_devices()
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
    return [d["name"] for d in devices if d["max_input_channels"] > 0]
