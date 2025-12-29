"""Main entry point for Hanasu."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from hanasu import __version__
from hanasu.config import (
    Config,
    Dictionary,
    load_config,
    load_dictionary,
    save_config,
    DEFAULT_CONFIG,
)
from hanasu.recorder import Recorder, list_input_devices
from hanasu.transcriber import Transcriber
from hanasu.hotkey import HotkeyListener
from hanasu.injector import inject_text
from hanasu.menubar import run_menubar_app, start_app_loop, stop_app_loop


DEFAULT_CONFIG_DIR = Path.home() / ".hanasu"


class Hanasu:
    """Main application class that orchestrates all components."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        """Initialize Hanasu with all components.

        Args:
            config_dir: Path to configuration directory.
        """
        self.config_dir = config_dir
        self.config = load_config(config_dir)
        self.dictionary = load_dictionary(config_dir)

        # Initialize components
        self.recorder = Recorder(device=self.config.audio_device)
        self.transcriber = Transcriber(
            model=self.config.model,
            language=self.config.language,
        )
        self.hotkey_listener = HotkeyListener(
            hotkey=self.config.hotkey,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )

        self._recording = False
        self._menubar_app = None

        if self.config.debug:
            print(f"[hanasu] Initialized with hotkey: {self.config.hotkey}")
            print(f"[hanasu] Model: {self.config.model}")
            print(f"[hanasu] Audio device: {self.config.audio_device or 'system default'}")

    def run(self) -> None:
        """Start the daemon and listen for hotkey."""
        print(f"Hanasu v{__version__} running...")
        print(f"Hotkey: {self.config.hotkey}")
        print("Running in menu bar (click icon to quit)")

        # Set up menu bar app
        self._menubar_app = run_menubar_app(
            hotkey=self.config.hotkey,
            on_quit=self._on_quit,
            on_hotkey_change=self._on_hotkey_change,
        )

        # Start hotkey listener
        self.hotkey_listener.start()

        try:
            # Run the macOS event loop (blocking)
            start_app_loop()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.hotkey_listener.stop()

    def _on_quit(self) -> None:
        """Handle quit from menu bar."""
        print("\nShutting down...")
        self.hotkey_listener.stop()

    def _on_hotkey_change(self, new_hotkey: str) -> None:
        """Handle hotkey change from menu bar.

        Args:
            new_hotkey: New hotkey string.
        """
        # Validate hotkey is not empty
        if not new_hotkey or not new_hotkey.strip():
            print("Error: Hotkey cannot be empty")
            return

        if self.config.debug:
            print(f"[hanasu] Changing hotkey to: {new_hotkey}")

        # Stop any in-progress recording before changing hotkey
        if self._recording:
            self._recording = False
            self.recorder.stop()
            if self._menubar_app:
                self._menubar_app.setRecording_(False)
            if self.config.debug:
                print("[hanasu] Stopped recording due to hotkey change")

        # Stop old listener before creating new one
        self.hotkey_listener.stop()

        # Try to create new listener before saving config
        try:
            new_listener = HotkeyListener(
                hotkey=new_hotkey,
                on_press=self._on_hotkey_press,
                on_release=self._on_hotkey_release,
            )
        except Exception as e:
            # Restore old listener if new hotkey is invalid
            print(f"Error: Invalid hotkey '{new_hotkey}': {e}")
            self.hotkey_listener.start()
            return

        # New listener is valid, now update config
        self.config = Config(
            hotkey=new_hotkey,
            model=self.config.model,
            language=self.config.language,
            audio_device=self.config.audio_device,
            debug=self.config.debug,
            clear_clipboard=self.config.clear_clipboard,
        )

        # Save to file
        save_config(self.config, self.config_dir)

        # Switch to new listener
        self.hotkey_listener = new_listener
        self.hotkey_listener.start()

        # Update menu bar display
        if self._menubar_app:
            self._menubar_app.setHotkey_(new_hotkey)

        print(f"Hotkey changed to: {new_hotkey}")

    def _on_hotkey_press(self) -> None:
        """Called when hotkey is pressed - start recording."""
        if self._recording:
            return

        self._recording = True
        self.recorder.start()

        # Update menu bar to show recording state
        if self._menubar_app:
            self._menubar_app.setRecording_(True)

        if self.config.debug:
            print("[hanasu] Recording started...")

    def _on_hotkey_release(self) -> None:
        """Called when hotkey is released - transcribe and inject."""
        if not self._recording:
            # May have been released without starting
            pass

        self._recording = False
        audio = self.recorder.stop()

        # Update menu bar to show idle state
        if self._menubar_app:
            self._menubar_app.setRecording_(False)

        if self.config.debug:
            print(f"[hanasu] Recording stopped. Audio length: {len(audio)} samples")

        if len(audio) == 0:
            if self.config.debug:
                print("[hanasu] No audio recorded")
            return

        # Check minimum recording length (0.5 seconds at 16kHz)
        if len(audio) < 8000:
            if self.config.debug:
                print("[hanasu] Recording too short, ignoring")
            return

        if self.config.debug:
            print("[hanasu] Transcribing...")

        text = self.transcriber.transcribe(audio, dictionary=self.dictionary)

        if self.config.debug:
            print(f"[hanasu] Transcribed: {text}")

        if text:
            inject_text(text, clear_after=self.config.clear_clipboard)


def download_model(model: str = "small") -> None:
    """Download the whisper model.

    Args:
        model: Model size to download.
    """
    import mlx_whisper
    from hanasu.transcriber import MODEL_PATHS

    model_path = MODEL_PATHS.get(model, MODEL_PATHS["small"])
    print(f"Downloading {model} model from {model_path}...")

    # Trigger download by doing a dummy transcription
    import numpy as np
    dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence

    try:
        mlx_whisper.transcribe(
            dummy_audio,
            path_or_hf_repo=model_path,
            language="en",
        )
        print("Model downloaded successfully!")
    except Exception as e:
        print(f"Warning: Could not fully verify model download: {e}")
        print("Model files should be cached for future use.")


def run_update() -> None:
    """Update Hanasu to the latest version.

    Pulls latest code from git and syncs dependencies.

    Raises:
        FileNotFoundError: If source directory doesn't exist.
        RuntimeError: If git or uv commands fail.
    """
    source_dir = Path.home() / ".hanasu-src"

    if not source_dir.exists():
        raise FileNotFoundError(
            f"Source directory not found: {source_dir}\n"
            "Please reinstall using the install script."
        )

    print("Updating Hanasu...")

    # Pull latest code
    print("Pulling latest changes...")
    result = subprocess.run(
        ["git", "pull"],
        cwd=source_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git pull failed: {result.stderr}")
    print(result.stdout.strip() or "Already up to date.")

    # Sync dependencies
    print("Syncing dependencies...")
    result = subprocess.run(
        ["uv", "sync"],
        cwd=source_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"uv sync failed: {result.stderr}")

    print("Update complete! Restart Hanasu to use the new version.")


def check_accessibility() -> bool:
    """Check if Accessibility permission is granted.

    Returns:
        True if permission is granted, False otherwise.
    """
    try:
        import Quartz
        # Try to create an event source - will fail without permission
        source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        return source is not None
    except Exception:
        return False


def run_setup(config_dir: Path = DEFAULT_CONFIG_DIR) -> None:
    """Run first-time setup.

    Args:
        config_dir: Path to configuration directory.
    """
    print("Hanasu Setup")
    print("=" * 40)
    print()

    # Create config directory
    config_dir.mkdir(parents=True, exist_ok=True)
    print(f"Config directory: {config_dir}")

    # Create default config
    config_file = config_dir / "config.json"
    if not config_file.exists():
        with open(config_file, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print("Created default config.json")
    else:
        print("Config file already exists")

    # Create empty dictionary
    dict_file = config_dir / "dictionary.json"
    if not dict_file.exists():
        with open(dict_file, "w") as f:
            json.dump({"terms": [], "replacements": {}}, f, indent=2)
        print("Created empty dictionary.json")

    print()

    # Download model
    print("Downloading whisper model...")
    download_model("small")
    print()

    # Check accessibility
    print("Checking Accessibility permission...")
    if check_accessibility():
        print("Accessibility permission: GRANTED")
    else:
        print("Accessibility permission: NOT GRANTED")
        print()
        print("Please grant access:")
        print("  System Settings -> Privacy & Security -> Accessibility")
        print("  Enable access for Terminal or your Python executable")
    print()

    # List audio devices
    print("Available microphones:")
    devices = list_input_devices()
    if devices:
        for device in devices:
            print(f"  - {device}")
    else:
        print("  No input devices found!")
    print()

    print("Setup complete!")
    print()
    print("To start Hanasu, run:")
    print("  hanasu")
    print()
    print("To check status:")
    print("  hanasu --status")


def get_status(config_dir: Path = DEFAULT_CONFIG_DIR) -> dict:
    """Get current status information.

    Args:
        config_dir: Path to configuration directory.

    Returns:
        Dict with status information.
    """
    status = {
        "version": __version__,
        "config_dir": str(config_dir),
        "config_exists": (config_dir / "config.json").exists(),
        "dictionary_exists": (config_dir / "dictionary.json").exists(),
        "audio_devices": list_input_devices(),
        "accessibility": check_accessibility(),
    }

    if status["config_exists"]:
        config = load_config(config_dir)
        status["hotkey"] = config.hotkey
        status["model"] = config.model
        status["audio_device"] = config.audio_device
        status["debug"] = config.debug
        status["clear_clipboard"] = config.clear_clipboard

    return status


def print_status(config_dir: Path = DEFAULT_CONFIG_DIR) -> None:
    """Print status to console.

    Args:
        config_dir: Path to configuration directory.
    """
    status = get_status(config_dir)

    print(f"Hanasu v{status['version']}")
    print("=" * 40)
    print(f"Config directory: {status['config_dir']}")
    print(f"Config file: {'exists' if status['config_exists'] else 'MISSING'}")
    print(f"Dictionary file: {'exists' if status['dictionary_exists'] else 'MISSING'}")
    print()

    if status["config_exists"]:
        print("Configuration:")
        print(f"  Hotkey: {status['hotkey']}")
        print(f"  Model: {status['model']}")
        print(f"  Audio device: {status.get('audio_device') or 'system default'}")
        print(f"  Debug mode: {status['debug']}")
        print(f"  Clear clipboard: {status['clear_clipboard']}")
        print()

    print("Accessibility permission:", "GRANTED" if status["accessibility"] else "NOT GRANTED")
    print()

    print("Audio devices:")
    if status["audio_devices"]:
        for device in status["audio_devices"]:
            print(f"  - {device}")
    else:
        print("  No input devices found")


def main() -> None:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="hanasu",
        description="Local voice-to-text dictation for macOS. By AMROK.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"hanasu {__version__}",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current status and exit",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help=f"Config directory (default: {DEFAULT_CONFIG_DIR})",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["setup", "update"],
        help="Command to run (setup for first-time setup, update to update)",
    )

    args = parser.parse_args()

    if args.command == "setup":
        run_setup(args.config_dir)
    elif args.command == "update":
        try:
            run_update()
        except (FileNotFoundError, RuntimeError) as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.status:
        print_status(args.config_dir)
    else:
        # Run the daemon
        try:
            app = Hanasu(config_dir=args.config_dir)
            app.run()
        except FileNotFoundError:
            print("Error: Config not found. Run 'hanasu setup' first.")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
