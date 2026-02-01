# Noridoc: hanasu

Path: @/hanasu

### Overview

The main Python package containing all application logic for Hanasu. This package implements a push-to-talk voice transcription system using macOS-specific APIs for hotkey detection, audio recording, Whisper transcription, and text injection.

### How it fits into the larger codebase

This is the core application package, installed via `pyproject.toml` and invoked either as a module (`python -m hanasu`) or via the console script entry point (`hanasu`). The package is designed for macOS only, relying on PyObjC bindings to Quartz and AppKit frameworks.

External dependencies:
- `mlx-whisper`: Whisper models optimized for Apple Silicon
- `sounddevice`: Cross-platform audio I/O built on PortAudio
- `pyobjc-framework-Quartz`: macOS event handling and keyboard simulation
- `pyobjc-framework-ApplicationServices`: macOS accessibility APIs

### Core Implementation

| Module | Responsibility |
|--------|---------------|
| `main.py` | CLI parsing, `Hanasu` orchestrator class, setup/doctor/transcribe commands |
| `config.py` | Configuration loading/saving, validation, default values |
| `hotkey.py` | Global hotkey detection via Quartz CGEventTap |
| `recorder.py` | Audio capture via sounddevice InputStream |
| `transcriber.py` | Whisper transcription via mlx-whisper, dictionary processing |
| `injector.py` | Text injection via clipboard + Cmd+V simulation |
| `menubar.py` | macOS menu bar UI via NSStatusBar and NSMenu |
| `updater.py` | GitHub release version checking with caching |
| `logging_config.py` | Logging setup to console and `~/Library/Logs/Hanasu/` |

The application lifecycle:
1. `main()` parses CLI arguments and either runs a subcommand or starts the daemon
2. `Hanasu.__init__()` loads config, creates Recorder, Transcriber, and HotkeyListener
3. `Hanasu.run()` sets up the menu bar, starts the hotkey listener, and enters the NSApplication event loop
4. On hotkey press: `Recorder.start()` begins audio capture
5. On hotkey release: `Recorder.stop()` returns audio buffer, `Transcriber.transcribe()` runs Whisper, `inject_text()` pastes result

### Things to Know

**Configuration hot-reload**: Hotkey and model can be changed at runtime without restart. The `change_hotkey()` and `change_model()` methods stop the old components and create new ones.

**Dictionary prompting**: The user's custom dictionary terms are passed to Whisper as an `initial_prompt` to bias transcription toward expected vocabulary. Replacements are applied post-transcription via case-insensitive regex.

**Model caching**: Whisper models are downloaded to `~/.cache/huggingface/hub/` on first use. The `is_model_cached()` function checks this location to show download indicators in the UI.

**Event tap thread safety**: The HotkeyListener runs in a background thread with its own CFRunLoop. UI updates from hotkey callbacks use `performSelectorOnMainThread_withObject_waitUntilDone_` to safely update the menu bar.

**Minimum recording length**: Recordings shorter than 0.5 seconds (8000 samples at 16kHz) are silently ignored to avoid noisy transcription from accidental key presses.

Created and maintained by Nori.
