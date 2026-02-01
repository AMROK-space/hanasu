# Noridoc: Hanasu

Path: @/

### Overview

Hanasu is a local voice-to-text dictation application for macOS that uses Apple Silicon's MLX framework to run OpenAI Whisper models on-device. It runs as a menu bar application, activated by a configurable hotkey, and pastes transcribed text directly into the active application.

### How it fits into the larger codebase

This is the root of the Hanasu repository. The application follows a component-based architecture where `main.py` orchestrates initialization and wiring of distinct subsystems:

```
User Input (hotkey press)
        |
        v
+-------------------+     +-------------------+
| HotkeyListener    | --> | Recorder          |
| (Quartz events)   |     | (sounddevice)     |
+-------------------+     +-------------------+
                                   |
                                   v
                          +-------------------+
                          | Transcriber       |
                          | (mlx-whisper)     |
                          +-------------------+
                                   |
                                   v
                          +-------------------+
                          | Injector          |
                          | (CGEvent paste)   |
                          +-------------------+
                                   |
                                   v
                          Active Application
```

The `menubar.py` module provides the user interface and drives application lifecycle through NSApplication's event loop. The `updater.py` module handles version checking against GitHub releases.

### Core Implementation

| Entry Point | Purpose |
|------------|---------|
| `hanasu.main:main` | CLI entry point, handles subcommands and starts daemon |
| `hanasu/__main__.py` | Enables `python -m hanasu` invocation |
| `install.sh` | Bootstrap installer for system-wide installation |

The `Hanasu` class in `main.py` is the central orchestrator that:
1. Loads configuration from `~/.hanasu/config.json`
2. Initializes Recorder, Transcriber, and HotkeyListener components
3. Sets up the menu bar UI and starts the macOS event loop
4. Coordinates hotkey press/release events with recording and transcription

Configuration is stored in `~/.hanasu/` with JSON files for user settings and custom dictionary terms.

### Things to Know

**macOS GUI app limitations**: GUI apps launched from Finder/Spotlight do not inherit shell PATH. The codebase explicitly checks Homebrew paths (`/opt/homebrew/bin`, `/usr/local/bin`) when locating external tools like `ffmpeg` and `uv`.

**Metal GPU thread safety**: File transcription through the UI runs via subprocess to isolate the Metal GPU context. Running mlx-whisper in a background thread while the macOS event loop runs on the main thread causes crashes with large files.

**Hotkey suppression**: The hotkey listener uses Quartz CGEventTap to intercept and suppress hotkey events (returning `None` from the callback), preventing them from passing to other applications.

**Accessibility permissions**: The application requires macOS Accessibility permissions to create event taps for hotkey detection and to inject paste keystrokes.

Created and maintained by Nori.
