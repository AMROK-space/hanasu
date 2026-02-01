# Noridoc: tests

Path: @/tests

### Overview

Pytest test suite for Hanasu. Tests cover configuration loading, hotkey parsing, recording, transcription, text injection, menu bar integration, and update checking. The tests use mocking extensively to avoid requiring macOS-specific APIs or actual audio hardware.

### How it fits into the larger codebase

Tests mirror the structure of `@/hanasu`, with one test file per module. Tests are run via `pytest` using the configuration in `pyproject.toml`. The `uv sync` command installs test dependencies including `pytest`, `pytest-cov`, `ruff`, and `mypy`.

```
tests/
  test_config.py      <-- @/hanasu/config.py
  test_hotkey.py      <-- @/hanasu/hotkey.py
  test_recorder.py    <-- @/hanasu/recorder.py
  test_transcriber.py <-- @/hanasu/transcriber.py
  test_injector.py    <-- @/hanasu/injector.py
  test_menubar.py     <-- @/hanasu/menubar.py
  test_updater.py     <-- @/hanasu/updater.py
  test_main.py        <-- @/hanasu/main.py
  test_logging_config.py <-- @/hanasu/logging_config.py
```

### Core Implementation

Tests follow a pattern of:
1. Mocking external dependencies (Quartz, sounddevice, mlx_whisper, AppKit)
2. Testing input validation and error handling
3. Verifying integration between components

Key mocking strategies:
- `mock_quartz` fixtures for CGEvent and CGEventTap APIs
- `mock_sounddevice` for audio device enumeration and recording
- `mock_mlx_whisper` for transcription results
- Temporary directories for config file tests

### Things to Know

**Mock patching scope**: PyObjC modules must be patched carefully. For example, `hanasu.menubar.NSStatusBar` patches the import in the module under test, not the original AppKit module.

**Device hotplug tests**: The `test_recorder.py` file includes tests for the `refresh_devices()` function that reinitializes PortAudio to detect newly connected microphones.

**VTT format tests**: The `test_main.py` file includes tests for the CLI transcribe command's VTT subtitle output format with timestamp generation.

Created and maintained by Nori.
