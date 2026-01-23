"""Main entry point for Hanasu."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import typing
from pathlib import Path

import logging

from hanasu import __version__
from hanasu.config import (
    DEFAULT_CONFIG,
    VALID_MODELS,
    Config,
    load_config,
    load_dictionary,
    save_config,
)
from hanasu.logging_config import setup_logging
from hanasu.hotkey import HotkeyListener
from hanasu.injector import inject_text
from hanasu.menubar import (
    open_file_picker,
    run_menubar_app,
    save_file_picker,
    show_format_picker,
    start_app_loop,
)
from hanasu.recorder import Recorder, list_input_devices
from hanasu.transcriber import Transcriber
from hanasu.updater import check_for_update

DEFAULT_CONFIG_DIR = Path.home() / ".hanasu"

# Homebrew paths for macOS - GUI apps don't inherit shell PATH
HOMEBREW_PATHS = [
    "/opt/homebrew/bin",  # Apple Silicon
    "/usr/local/bin",  # Intel Mac
]


def ensure_homebrew_in_path() -> None:
    """Add Homebrew paths to PATH for macOS GUI apps.

    macOS GUI apps launched from Finder/Spotlight don't inherit the shell's PATH,
    so tools like ffmpeg installed via Homebrew won't be found. This function
    adds common Homebrew paths to PATH so subprocess calls can find them.
    """
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(":") if current_path else []

    # Prepend Homebrew paths that aren't already present
    paths_to_add = [p for p in HOMEBREW_PATHS if p not in path_parts]

    if paths_to_add:
        new_path = ":".join(paths_to_add + path_parts)
        os.environ["PATH"] = new_path


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

        # Set up logging based on config
        setup_logging(debug=self.config.debug, log_to_file=True)
        self._logger = logging.getLogger("hanasu.main")

        # Initialize components - fallback to default if configured device unavailable
        self.recorder = Recorder(device=self.config.audio_device, fallback_to_default=True)
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
        self._model_change_in_progress = False

        self._logger.info(f"Initialized with hotkey: {self.config.hotkey}")
        self._logger.info(f"Model: {self.config.model}")
        self._logger.info(f"Audio device: {self.config.audio_device or 'system default'}")

    def change_hotkey(self, new_hotkey: str) -> None:
        """Change the hotkey while running (hot-reload).

        Args:
            new_hotkey: New hotkey string (e.g., "cmd+shift+space").

        Raises:
            HotkeyParseError: If the hotkey string is invalid.
        """
        # Stop old listener
        self.hotkey_listener.stop()

        # Create new listener (will raise HotkeyParseError if invalid)
        self.hotkey_listener = HotkeyListener(
            hotkey=new_hotkey,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )

        # Update config
        self.config.hotkey = new_hotkey
        save_config(self.config, self.config_dir)

        # Start new listener
        self.hotkey_listener.start()

        # Update menu bar display
        if self._menubar_app:
            self._menubar_app.setHotkey_(new_hotkey)

        self._logger.info(f"Hotkey changed to: {new_hotkey}")

    def change_model(self, new_model: str) -> None:
        """Change the whisper model (hot-swap).

        Downloads the model if not cached, then creates a new Transcriber.
        Runs in a background thread to avoid blocking the UI.

        Args:
            new_model: Model size (tiny, base, small, medium, large).
        """
        # Validate model
        if new_model not in VALID_MODELS:
            self._logger.warning(f"Invalid model: {new_model}")
            return

        # No-op if same model
        if new_model == self.config.model:
            return

        # Block while recording
        if self._recording:
            self._logger.debug("Cannot change model while recording")
            return

        # Prevent concurrent model changes
        if self._model_change_in_progress:
            self._logger.debug("Model change already in progress")
            return

        self._model_change_in_progress = True

        def do_change():
            try:
                # Download if not cached
                if not is_model_cached(new_model):
                    if self._menubar_app:
                        self._menubar_app.setModelDownloading_(new_model, True)
                    try:
                        download_model(new_model)
                    finally:
                        if self._menubar_app:
                            self._menubar_app.setModelDownloading_(new_model, False)

                # Create new transcriber
                self.transcriber = Transcriber(
                    model=new_model,
                    language=self.config.language,
                )

                # Update config
                self.config = Config(
                    hotkey=self.config.hotkey,
                    model=new_model,
                    language=self.config.language,
                    audio_device=self.config.audio_device,
                    debug=self.config.debug,
                    clear_clipboard=self.config.clear_clipboard,
                    last_output_dir=self.config.last_output_dir,
                )
                save_config(self.config, self.config_dir)

                # Update menu bar
                if self._menubar_app:
                    self._menubar_app.setCurrentModel_(new_model)
                    self._menubar_app.refreshModelStates()

                self._logger.info(f"Model changed to: {new_model}")
            finally:
                self._model_change_in_progress = False

        threading.Thread(target=do_change, daemon=True).start()

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
            on_update=self._on_update,
            on_transcribe_file=self._on_transcribe_file,
            on_model_change=self._on_model_change,
            version=__version__,
            current_model=self.config.model,
            is_model_cached=is_model_cached,
        )

        # Check for updates in background
        update_thread = threading.Thread(target=self._check_for_updates, daemon=True)
        update_thread.start()

        # Start hotkey listener
        self.hotkey_listener.start()

        try:
            # Run the macOS event loop (blocking)
            start_app_loop()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.hotkey_listener.stop()

    def _check_for_updates(self) -> None:
        """Check for updates in background thread."""
        try:
            status = check_for_update(__version__, cache_dir=self.config_dir)
            if self._menubar_app:
                self._menubar_app.setUpdateStatus_(status)

            if status.update_available:
                self._logger.info(f"Update available: v{status.latest_version}")
            elif status.checked:
                self._logger.debug("Up to date")
            else:
                self._logger.debug("Could not check for updates")
        except Exception as e:
            self._logger.error(f"Error checking for updates: {e}")

    def _on_update(self) -> None:
        """Handle update request from menu bar."""
        # Prevent multiple concurrent updates
        if getattr(self, "_update_in_progress", False):
            return
        self._update_in_progress = True

        if self._menubar_app:
            self._menubar_app.setUpdateInProgress()

        # Run update in background thread
        def do_update():
            try:
                run_update()
                if self._menubar_app:
                    self._menubar_app.setUpdateComplete()
            except Exception as e:
                self._logger.error(f"Update failed: {e}")
                if self._menubar_app:
                    self._menubar_app.setUpdateFailed()
            finally:
                self._update_in_progress = False

        update_thread = threading.Thread(target=do_update, daemon=True)
        update_thread.start()

    def _on_model_change(self, new_model: str) -> None:
        """Handle model change from menu bar.

        Args:
            new_model: New model size to switch to.
        """
        self.change_model(new_model)

    def _on_quit(self) -> None:
        """Handle quit from menu bar."""
        self._logger.info("Shutting down...")
        self.hotkey_listener.stop()

    def _on_hotkey_change(self, new_hotkey: str) -> None:
        """Handle hotkey change from menu bar.

        Args:
            new_hotkey: New hotkey string.
        """
        # Validate hotkey is not empty
        if not new_hotkey or not new_hotkey.strip():
            self._logger.error("Hotkey cannot be empty")
            return

        self._logger.debug(f"Changing hotkey to: {new_hotkey}")

        # Stop any in-progress recording before changing hotkey
        if self._recording:
            self._recording = False
            self.recorder.stop()
            if self._menubar_app:
                self._menubar_app.setRecording_(False)
            self._logger.debug("Stopped recording due to hotkey change")

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
            last_output_dir=self.config.last_output_dir,
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

        self._logger.debug("Recording started...")

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

        self._logger.debug(f"Recording stopped. Audio length: {len(audio)} samples")

        if len(audio) == 0:
            self._logger.debug("No audio recorded")
            return

        # Check minimum recording length (0.5 seconds at 16kHz)
        if len(audio) < 8000:
            self._logger.debug("Recording too short, ignoring")
            return

        self._logger.debug("Transcribing...")

        text = self.transcriber.transcribe(audio, dictionary=self.dictionary)

        self._logger.debug(f"Transcribed: {text}")

        if text:
            inject_text(text, clear_after=self.config.clear_clipboard)

    def _on_transcribe_file(self) -> None:
        """Handle file transcription request from menu."""
        # Audio/video extensions
        extensions = ["mp3", "wav", "m4a", "mp4", "mov", "mkv", "avi", "webm"]

        # Step 1: Select input file
        input_path = open_file_picker(allowed_extensions=extensions)
        if not input_path:
            return

        # Step 2: Select output format
        fmt = show_format_picker()
        if not fmt:
            return

        # Step 3: Select output location
        input_name = Path(input_path).stem
        suggested_name = f"{input_name}.{fmt}"
        output_path = save_file_picker(
            suggested_name=suggested_name,
            initial_dir=self.config.last_output_dir,
            file_types=[fmt],
        )
        if not output_path:
            return

        # Step 4: Update last output dir
        self.config.last_output_dir = str(Path(output_path).parent)
        save_config(self.config, self.config_dir)

        # Step 5: Run transcription in background
        threading.Thread(
            target=self._run_file_transcription,
            args=(input_path, output_path, fmt == "vtt"),
            daemon=True,
        ).start()

    def _run_file_transcription(self, input_path: str, output_path: str, use_vtt: bool) -> None:
        """Run file transcription via subprocess to isolate Metal GPU context.

        Using subprocess instead of calling mlx_whisper directly avoids Metal/MLX
        thread-safety issues that cause crashes with large files when transcription
        runs in a background thread while the macOS event loop runs on main thread.

        Args:
            input_path: Path to audio/video file.
            output_path: Path for output file.
            use_vtt: True to output VTT format, False for plain text.
        """
        # Build command using current Python interpreter
        cmd = [sys.executable, "-m", "hanasu", "transcribe", input_path, "-o", output_path]

        # Add model flag with configured model
        cmd.extend(["--model", self.config.model])

        # Add VTT flag if requested
        if use_vtt:
            cmd.append("--vtt")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for large files
            )
            if result.returncode != 0:
                self._show_transcription_error(result.stderr or "Transcription failed")
        except subprocess.TimeoutExpired:
            self._show_transcription_error("Transcription timed out (exceeded 10 minutes)")
        except Exception as e:
            self._show_transcription_error(str(e))

    def _show_transcription_error(self, message: str) -> None:
        """Show error dialog on main thread.

        Args:
            message: Error message to display.
        """
        from AppKit import NSAlert
        from PyObjCTools import AppHelper

        def show_alert():
            alert = NSAlert.alloc().init()
            alert.setMessageText_("Transcription Failed")
            alert.setInformativeText_(message)
            alert.addButtonWithTitle_("OK")
            alert.runModal()

        # Schedule on main thread
        AppHelper.callAfter(show_alert)


def download_model(model: str = "small") -> None:
    """Download the whisper model if not already cached.

    Args:
        model: Model size to download.
    """
    import mlx_whisper

    from hanasu.transcriber import MODEL_PATHS

    model_path = MODEL_PATHS.get(model, MODEL_PATHS["small"])

    # Check if model is already cached
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_cache_name = f"models--{model_path.replace('/', '--')}"
    model_cached = (cache_dir / model_cache_name).exists()

    if model_cached:
        print(f"Model {model} already cached, verifying...")
    else:
        print(f"Downloading {model} model from {model_path}...")

    # Trigger download/verification by doing a dummy transcription
    import numpy as np

    dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence

    try:
        mlx_whisper.transcribe(
            dummy_audio,
            path_or_hf_repo=model_path,
            language="en",
        )
        if model_cached:
            print("Model verified!")
        else:
            print("Model downloaded successfully!")
    except Exception as e:
        print(f"Warning: Could not fully verify model: {e}")
        print("Model files should be cached for future use.")


def is_model_cached(model: str) -> bool:
    """Check if a whisper model is cached locally.

    Args:
        model: Model size (tiny, base, small, medium, large).

    Returns:
        True if model is cached, False otherwise.
    """
    from hanasu.transcriber import MODEL_PATHS

    model_path = MODEL_PATHS.get(model, MODEL_PATHS["small"])
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_cache_name = f"models--{model_path.replace('/', '--')}"
    return (cache_dir / model_cache_name).exists()


def find_uv_binary() -> Path:
    """Find the uv binary in common installation locations.

    macOS menu bar apps don't inherit the shell's PATH, so we need to
    look in common locations where uv might be installed.

    Returns:
        Path to the uv binary.

    Raises:
        FileNotFoundError: If uv is not found in any location.
    """
    home = Path.home()

    # Common installation locations for uv
    candidates = [
        home / ".local" / "bin" / "uv",  # pipx, uv installer
        home / ".cargo" / "bin" / "uv",  # Rust/cargo install
        Path("/opt/homebrew/bin/uv"),  # Homebrew Apple Silicon
        Path("/usr/local/bin/uv"),  # Homebrew Intel, system install
    ]

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    # Fall back to shutil.which for PATH lookup (already verifies exists + executable)
    which_result = shutil.which("uv")
    if which_result:
        return Path(which_result)

    raise FileNotFoundError(
        "uv not found. Please ensure uv is installed.\n"
        "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    )


def run_update() -> None:
    """Update Hanasu to the latest version.

    Pulls latest code from git and syncs dependencies.

    Raises:
        FileNotFoundError: If source directory or uv binary doesn't exist.
        RuntimeError: If git or uv commands fail.
    """
    # New canonical location
    source_dir = Path.home() / ".hanasu" / "src"

    # Fall back to legacy location if new doesn't exist
    if not source_dir.exists():
        legacy_dir = Path.home() / ".hanasu-src"
        if legacy_dir.exists():
            source_dir = legacy_dir
        else:
            raise FileNotFoundError(
                "Source directory not found.\n"
                "Please reinstall: curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash"
            )

    # Find uv binary - menu bar apps don't inherit shell PATH
    uv_path = find_uv_binary()

    print("Updating Hanasu...")

    # Reset auto-generated files that might block pull
    subprocess.run(
        ["git", "checkout", "--", "uv.lock"],
        cwd=source_dir,
        capture_output=True,
    )

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

    # Sync dependencies using explicit path to uv
    print("Syncing dependencies...")
    result = subprocess.run(
        [str(uv_path), "sync"],
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


def run_doctor() -> None:
    """Check installation health and report issues.

    Verifies:
    - Install manifest exists and is valid
    - All artifacts exist and are correct
    - No conflicting installations
    """
    install_dir = Path.home() / ".hanasu"
    src_dir = install_dir / "src"
    manifest_file = install_dir / ".install-manifest"
    legacy_dir = Path.home() / ".hanasu-src"
    app_path = Path("/Applications/Hanasu.app")
    cli_link = Path.home() / ".local" / "bin" / "hanasu"
    venv_bin = src_dir / ".venv" / "bin" / "hanasu"

    issues = []
    warnings = []

    print(f"Hanasu Doctor v{__version__}")
    print("=" * 40)
    print()

    # Check install manifest
    print("Checking installation...")
    if manifest_file.exists():
        print(f"  ✓ Install manifest: {manifest_file}")
        try:
            import json

            with open(manifest_file) as f:
                manifest = json.load(f)
            print(f"    Installed: {manifest.get('installed_at', 'unknown')}")
        except Exception as e:
            issues.append(f"Manifest is corrupt: {e}")
    else:
        warnings.append("No install manifest found (may be legacy install)")

    # Check source directory
    if src_dir.exists():
        print(f"  ✓ Source: {src_dir}")
        if (src_dir / ".git").exists():
            print("    Git repository: OK")
        else:
            issues.append("Source directory is not a git repository")
    else:
        issues.append(f"Source directory missing: {src_dir}")

    # Check virtual environment
    if venv_bin.exists():
        print(f"  ✓ Virtual environment: {install_dir / '.venv'}")
    else:
        issues.append(f"Virtual environment missing or incomplete: {install_dir / '.venv'}")

    # Check application bundle
    print()
    print("Checking application bundle...")
    if app_path.exists():
        print(f"  ✓ App: {app_path}")
        launcher = app_path / "Contents" / "MacOS" / "hanasu"
        if launcher.exists():
            try:
                content = launcher.read_text()
                if str(install_dir) in content:
                    print("    Launcher: OK")
                else:
                    warnings.append("App launcher may point to wrong location")
            except Exception:
                pass
    else:
        issues.append(f"Application bundle missing: {app_path}")

    # Check CLI symlink
    print()
    print("Checking CLI...")
    if cli_link.exists():
        if cli_link.is_symlink():
            target = cli_link.resolve()
            print(f"  ✓ Symlink: {cli_link} -> {target}")
            if not target.exists():
                issues.append(f"CLI symlink points to missing target: {target}")
        else:
            warnings.append(f"CLI is a file, not symlink: {cli_link}")
    else:
        issues.append(f"CLI symlink missing: {cli_link}")

    # Check for legacy installation
    print()
    print("Checking for conflicts...")
    if legacy_dir.exists():
        warnings.append(f"Legacy installation found: {legacy_dir}")
        print(f"  ! Legacy install: {legacy_dir}")
    else:
        print("  ✓ No legacy installation")

    # Check accessibility
    print()
    print("Checking permissions...")
    if check_accessibility():
        print("  ✓ Accessibility permission: Granted")
    else:
        issues.append("Accessibility permission not granted")

    # Summary
    print()
    print("=" * 40)

    if issues:
        print(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  ✗ {issue}")

    if warnings:
        print(f"Found {len(warnings)} warning(s):")
        for warning in warnings:
            print(f"  ! {warning}")

    if not issues and not warnings:
        print("✓ Installation is healthy")
    elif issues:
        print()
        print("To fix, try reinstalling:")
        print(
            "  curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash"
        )


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".wmv"}


def is_video_file(file_path: str | Path) -> bool:
    """Check if a file is a video file based on extension.

    Args:
        file_path: Path to the file.

    Returns:
        True if file is a video file, False otherwise.
    """
    return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS


def find_ffmpeg() -> str | None:
    """Find ffmpeg binary, checking common macOS locations.

    macOS GUI apps don't inherit shell PATH, so we check Homebrew paths first.

    Returns:
        Path to ffmpeg binary, or None if not found.
    """
    # Check Homebrew paths first (GUI apps don't have shell PATH)
    homebrew_paths = [
        "/opt/homebrew/bin/ffmpeg",  # Apple Silicon
        "/usr/local/bin/ffmpeg",  # Intel Mac
    ]

    for path in homebrew_paths:
        if Path(path).exists():
            return path

    # Fall back to shutil.which for other installations
    return shutil.which("ffmpeg")


def extract_audio_from_video(video_path: str) -> str:
    """Extract audio from a video file to a temporary WAV file.

    Args:
        video_path: Path to video file.

    Returns:
        Path to temporary WAV file.

    Raises:
        RuntimeError: If ffmpeg fails or is not installed.
    """
    import tempfile

    # Find ffmpeg binary (macOS GUI apps don't have shell PATH)
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path is None:
        raise RuntimeError(
            "ffmpeg not found. Please install ffmpeg to transcribe video files.\n"
            "Install with: brew install ffmpeg"
        )

    # Create temp file for extracted audio
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_path = temp_file.name
    temp_file.close()

    try:
        result = subprocess.run(
            [
                ffmpeg_path,
                "-i",
                video_path,
                "-vn",  # No video
                "-acodec",
                "pcm_s16le",  # WAV codec
                "-ar",
                "16000",  # 16kHz sample rate (whisper input)
                "-ac",
                "1",  # Mono
                "-y",  # Overwrite
                temp_path,
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as err:
        # Clean up temp file before raising
        Path(temp_path).unlink()
        raise RuntimeError(
            "ffmpeg not found. Please install ffmpeg to transcribe video files.\n"
            "Install with: brew install ffmpeg"
        ) from err

    if result.returncode != 0:
        # Clean up temp file before raising
        Path(temp_path).unlink()
        raise RuntimeError(f"ffmpeg failed to extract audio: {result.stderr}")

    return temp_path


def run_transcribe(
    audio_file: str,
    use_vtt: bool = False,
    use_large: bool = False,
    model: str = "small",
    output_file: str | None = None,
) -> None:
    """Transcribe an audio or video file to text or VTT format.

    Args:
        audio_file: Path to audio or video file to transcribe.
        use_vtt: Output in VTT subtitle format with timestamps.
        use_large: Use large model for better accuracy (overrides --model).
        model: Model size to use (tiny, base, small, medium, large).
        output_file: Path to write output to. If None, writes to stdout.
    """
    import mlx_whisper

    from hanasu.transcriber import MODEL_PATHS

    # --large flag overrides --model for backward compatibility
    model_key = "large" if use_large else model
    model_path = MODEL_PATHS.get(model_key, MODEL_PATHS["small"])

    # Check if input is a video file
    temp_audio_path = None
    if is_video_file(audio_file):
        temp_audio_path = extract_audio_from_video(audio_file)
        transcribe_path = temp_audio_path
    else:
        transcribe_path = audio_file

    try:
        result = mlx_whisper.transcribe(transcribe_path, path_or_hf_repo=model_path)

        def write_output(out: typing.TextIO) -> None:
            if use_vtt:
                out.write("WEBVTT\n\n")
                for seg in result["segments"]:
                    start = seg["start"]
                    end = seg["end"]
                    sh, sm, ss = int(start // 3600), int((start % 3600) // 60), start % 60
                    eh, em, es = int(end // 3600), int((end % 3600) // 60), end % 60
                    out.write(f"{sh:02d}:{sm:02d}:{ss:06.3f} --> {eh:02d}:{em:02d}:{es:06.3f}\n")
                    out.write(seg["text"].strip() + "\n")
                    out.write("\n")
            else:
                out.write(result["text"] + "\n")

        if output_file:
            with open(output_file, "w") as f:
                write_output(f)
        else:
            write_output(sys.stdout)
    finally:
        # Clean up temp file if we created one
        if temp_audio_path and Path(temp_audio_path).exists():
            Path(temp_audio_path).unlink()


def main() -> None:
    """Main entry point for CLI."""
    # Ensure Homebrew paths are in PATH for GUI app context
    ensure_homebrew_in_path()

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

    subparsers = parser.add_subparsers(dest="command")

    # setup command
    subparsers.add_parser("setup", help="Run first-time setup")

    # update command
    subparsers.add_parser("update", help="Update to latest version")

    # doctor command
    subparsers.add_parser("doctor", help="Check installation health")

    # transcribe command
    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe an audio file to text")
    transcribe_parser.add_argument("audio_file", help="Path to audio file")
    transcribe_parser.add_argument(
        "--vtt", action="store_true", help="Output in VTT subtitle format"
    )
    transcribe_parser.add_argument(
        "--large", action="store_true", help="Use large model for better accuracy"
    )
    transcribe_parser.add_argument(
        "--model",
        type=str,
        choices=sorted(VALID_MODELS),
        default="small",
        help="Model size to use (default: small)",
    )
    transcribe_parser.add_argument(
        "-o",
        "--output",
        type=str,
        metavar="FILE",
        help="Write output to FILE instead of stdout",
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
    elif args.command == "doctor":
        run_doctor()
    elif args.command == "transcribe":
        run_transcribe(
            args.audio_file,
            use_vtt=args.vtt,
            use_large=args.large,
            model=args.model,
            output_file=args.output,
        )
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
