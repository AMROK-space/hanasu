"""Tests for main orchestration and CLI."""

from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest

from hanasu.main import (
    Hanasu,
    run_setup,
    run_update,
    get_status,
)


class TestHanasu:
    """Test main orchestration class."""

    def test_initializes_all_components(self, tmp_path: Path):
        """All components are initialized on creation."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            mock_config.return_value = MagicMock(
                                hotkey="ctrl+shift+space",
                                model="small",
                                language="en",
                                audio_device=None,
                                debug=False,
                            )
                            mock_dict.return_value = MagicMock(terms=[], replacements={})

                            app = Hanasu(config_dir=tmp_path)

                            assert app is not None

    def test_on_hotkey_press_starts_recording(self, tmp_path: Path):
        """Pressing hotkey starts audio recording."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder") as mock_recorder_class:
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            mock_config.return_value = MagicMock(
                                hotkey="ctrl+shift+space",
                                model="small",
                                language="en",
                                audio_device=None,
                                debug=False,
                            )
                            mock_dict.return_value = MagicMock(terms=[], replacements={})
                            mock_recorder = MagicMock()
                            mock_recorder_class.return_value = mock_recorder

                            app = Hanasu(config_dir=tmp_path)
                            app._on_hotkey_press()

                            mock_recorder.start.assert_called_once()

    def test_on_hotkey_release_transcribes_and_injects(self, tmp_path: Path):
        """Releasing hotkey transcribes audio and injects text."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder") as mock_recorder_class:
                    with patch("hanasu.main.Transcriber") as mock_transcriber_class:
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.inject_text") as mock_inject:
                                import numpy as np

                                mock_config.return_value = MagicMock(
                                    hotkey="ctrl+shift+space",
                                    model="small",
                                    language="en",
                                    audio_device=None,
                                    debug=False,
                                )
                                mock_dict.return_value = MagicMock(terms=[], replacements={})

                                mock_recorder = MagicMock()
                                # Need at least 8000 samples (0.5s at 16kHz) to pass minimum length check
                                mock_recorder.stop.return_value = np.ones(16000, dtype=np.float32) * 0.1
                                mock_recorder_class.return_value = mock_recorder

                                mock_transcriber = MagicMock()
                                mock_transcriber.transcribe.return_value = "hello world"
                                mock_transcriber_class.return_value = mock_transcriber

                                app = Hanasu(config_dir=tmp_path)
                                app._on_hotkey_release()

                                mock_recorder.stop.assert_called_once()
                                mock_transcriber.transcribe.assert_called_once()
                                mock_inject.assert_called_once_with("hello world")


class TestRunSetup:
    """Test setup command."""

    def test_creates_config_directory(self, tmp_path: Path):
        """Setup creates config directory."""
        with patch("hanasu.main.download_model"):
            with patch("hanasu.main.check_accessibility"):
                with patch("hanasu.main.list_input_devices", return_value=["Mic"]):
                    run_setup(config_dir=tmp_path)

                    assert tmp_path.exists()

    def test_creates_default_config(self, tmp_path: Path):
        """Setup creates default config file."""
        with patch("hanasu.main.download_model"):
            with patch("hanasu.main.check_accessibility"):
                with patch("hanasu.main.list_input_devices", return_value=["Mic"]):
                    run_setup(config_dir=tmp_path)

                    config_file = tmp_path / "config.json"
                    assert config_file.exists()

    def test_downloads_model(self, tmp_path: Path):
        """Setup downloads the whisper model."""
        with patch("hanasu.main.download_model") as mock_download:
            with patch("hanasu.main.check_accessibility"):
                with patch("hanasu.main.list_input_devices", return_value=["Mic"]):
                    run_setup(config_dir=tmp_path)

                    mock_download.assert_called_once()


class TestGetStatus:
    """Test status command."""

    def test_returns_status_dict(self, tmp_path: Path):
        """get_status returns status information."""
        with patch("hanasu.main.list_input_devices", return_value=["MacBook Pro Microphone"]):
            status = get_status(config_dir=tmp_path)

            assert "config_dir" in status
            assert "audio_devices" in status


class TestRunUpdate:
    """Test update command."""

    def test_runs_git_pull_in_source_directory(self, tmp_path: Path):
        """Update runs git pull in the source directory."""
        source_dir = tmp_path / ".hanasu-src"
        source_dir.mkdir()

        with patch("hanasu.main.subprocess.run") as mock_run:
            with patch("hanasu.main.Path.home", return_value=tmp_path):
                mock_run.return_value = MagicMock(returncode=0)

                run_update()

                # Check git pull was called
                calls = [str(c) for c in mock_run.call_args_list]
                assert any("git" in c and "pull" in c for c in calls)

    def test_runs_uv_sync_after_git_pull(self, tmp_path: Path):
        """Update runs uv sync after git pull."""
        source_dir = tmp_path / ".hanasu-src"
        source_dir.mkdir()

        with patch("hanasu.main.subprocess.run") as mock_run:
            with patch("hanasu.main.Path.home", return_value=tmp_path):
                mock_run.return_value = MagicMock(returncode=0)

                run_update()

                # Check uv sync was called
                calls = [str(c) for c in mock_run.call_args_list]
                assert any("uv" in c and "sync" in c for c in calls)

    def test_raises_error_when_source_dir_missing(self, tmp_path: Path):
        """Update raises error if source directory doesn't exist."""
        with patch("hanasu.main.Path.home", return_value=tmp_path):
            with pytest.raises(FileNotFoundError, match="source"):
                run_update()
