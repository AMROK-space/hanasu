"""Tests for main orchestration and CLI."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hanasu.main import (
    Hanasu,
    ensure_homebrew_in_path,
    extract_audio_from_video,
    get_status,
    is_model_cached,
    is_video_file,
    run_setup,
    run_transcribe,
    run_update,
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
                                    clear_clipboard=True,
                                )
                                mock_dict.return_value = MagicMock(terms=[], replacements={})

                                mock_recorder = MagicMock()
                                # Need at least 8000 samples (0.5s at 16kHz) to pass minimum length check
                                mock_recorder.stop.return_value = (
                                    np.ones(16000, dtype=np.float32) * 0.1
                                )
                                mock_recorder_class.return_value = mock_recorder

                                mock_transcriber = MagicMock()
                                mock_transcriber.transcribe.return_value = "hello world"
                                mock_transcriber_class.return_value = mock_transcriber

                                app = Hanasu(config_dir=tmp_path)
                                app._on_hotkey_release()

                                mock_recorder.stop.assert_called_once()
                                mock_transcriber.transcribe.assert_called_once()
                                mock_inject.assert_called_once_with("hello world", clear_after=True)


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
            with pytest.raises(FileNotFoundError, match="(?i)source"):
                run_update()

    def test_raises_error_when_uv_not_found(self, tmp_path: Path):
        """Update raises error if uv binary is not found."""
        source_dir = tmp_path / ".hanasu" / "src"
        source_dir.mkdir(parents=True)

        with patch("hanasu.main.Path.home", return_value=tmp_path):
            with patch("hanasu.main.shutil.which", return_value=None):
                with pytest.raises(FileNotFoundError, match="(?i)uv"):
                    run_update()

    def test_uses_full_path_to_uv_binary(self, tmp_path: Path):
        """Update uses the full path to uv, not just 'uv'."""
        source_dir = tmp_path / ".hanasu" / "src"
        source_dir.mkdir(parents=True)

        # Create a fake uv binary in ~/.local/bin
        local_bin = tmp_path / ".local" / "bin"
        local_bin.mkdir(parents=True)
        uv_path = local_bin / "uv"
        uv_path.touch()
        uv_path.chmod(0o755)

        with patch("hanasu.main.subprocess.run") as mock_run:
            with patch("hanasu.main.Path.home", return_value=tmp_path):
                mock_run.return_value = MagicMock(returncode=0)

                run_update()

                # Find the uv sync call and verify it uses the full path
                uv_calls = [c for c in mock_run.call_args_list if "sync" in str(c)]
                assert len(uv_calls) > 0, "uv sync should be called"
                # The command should use full path, not just "uv"
                uv_call = uv_calls[0]
                cmd = uv_call[0][0]  # First positional arg is the command list
                assert str(uv_path) in str(cmd), f"Expected full path {uv_path}, got {cmd}"


class TestFindUvBinary:
    """Test uv binary discovery."""

    def test_finds_uv_in_local_bin(self, tmp_path: Path):
        """Finds uv in ~/.local/bin."""
        from hanasu.main import find_uv_binary

        local_bin = tmp_path / ".local" / "bin"
        local_bin.mkdir(parents=True)
        uv_path = local_bin / "uv"
        uv_path.touch()
        uv_path.chmod(0o755)

        with patch("hanasu.main.Path.home", return_value=tmp_path):
            result = find_uv_binary()

        assert result == uv_path

    def test_finds_uv_in_cargo_bin(self, tmp_path: Path):
        """Finds uv in ~/.cargo/bin (Rust install location)."""
        from hanasu.main import find_uv_binary

        cargo_bin = tmp_path / ".cargo" / "bin"
        cargo_bin.mkdir(parents=True)
        uv_path = cargo_bin / "uv"
        uv_path.touch()
        uv_path.chmod(0o755)

        with patch("hanasu.main.Path.home", return_value=tmp_path):
            with patch("hanasu.main.shutil.which", return_value=None):
                result = find_uv_binary()

        assert result == uv_path

    def test_finds_uv_via_shutil_which(self, tmp_path: Path):
        """Falls back to shutil.which if not in common locations."""
        from hanasu.main import find_uv_binary

        with patch("hanasu.main.Path.home", return_value=tmp_path):
            with patch("hanasu.main.shutil.which", return_value="/usr/local/bin/uv"):
                result = find_uv_binary()

        assert result == Path("/usr/local/bin/uv")

    def test_raises_error_when_uv_not_found(self, tmp_path: Path):
        """Raises FileNotFoundError with helpful message when uv not found."""
        from hanasu.main import find_uv_binary

        with patch("hanasu.main.Path.home", return_value=tmp_path):
            with patch("hanasu.main.shutil.which", return_value=None):
                with pytest.raises(FileNotFoundError, match="(?i)uv.*not found"):
                    find_uv_binary()


class TestChangeHotkey:
    """Test hotkey hot-reload functionality."""

    def test_change_hotkey_stops_old_listener(self, tmp_path: Path):
        """Changing hotkey stops the existing listener."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener") as mock_listener_class:
                            mock_config.return_value = MagicMock(
                                hotkey="ctrl+shift+space",
                                model="small",
                                language="en",
                                audio_device=None,
                                debug=False,
                            )
                            mock_dict.return_value = MagicMock(terms=[], replacements={})
                            mock_old_listener = MagicMock()
                            mock_listener_class.return_value = mock_old_listener

                            app = Hanasu(config_dir=tmp_path)

                            with patch("hanasu.main.save_config"):
                                app.change_hotkey("cmd+alt+v")

                            mock_old_listener.stop.assert_called_once()

    def test_change_hotkey_creates_new_listener_with_new_hotkey(self, tmp_path: Path):
        """Changing hotkey creates new listener with the new hotkey."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener") as mock_listener_class:
                            mock_config.return_value = MagicMock(
                                hotkey="ctrl+shift+space",
                                model="small",
                                language="en",
                                audio_device=None,
                                debug=False,
                            )
                            mock_dict.return_value = MagicMock(terms=[], replacements={})

                            app = Hanasu(config_dir=tmp_path)

                            with patch("hanasu.main.save_config"):
                                app.change_hotkey("cmd+alt+v")

                            # Should have been called twice: once on init, once on change
                            assert mock_listener_class.call_count == 2
                            # Second call should have new hotkey
                            second_call_kwargs = mock_listener_class.call_args_list[1]
                            assert second_call_kwargs[1]["hotkey"] == "cmd+alt+v"

    def test_change_hotkey_starts_new_listener(self, tmp_path: Path):
        """Changing hotkey starts the new listener."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener") as mock_listener_class:
                            mock_config.return_value = MagicMock(
                                hotkey="ctrl+shift+space",
                                model="small",
                                language="en",
                                audio_device=None,
                                debug=False,
                            )
                            mock_dict.return_value = MagicMock(terms=[], replacements={})
                            mock_new_listener = MagicMock()
                            # Return different mocks for first and second instantiation
                            mock_listener_class.side_effect = [MagicMock(), mock_new_listener]

                            app = Hanasu(config_dir=tmp_path)

                            with patch("hanasu.main.save_config"):
                                app.change_hotkey("cmd+alt+v")

                            mock_new_listener.start.assert_called_once()

    def test_change_hotkey_saves_config(self, tmp_path: Path):
        """Changing hotkey persists to config file."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            mock_config_obj = MagicMock(
                                hotkey="ctrl+shift+space",
                                model="small",
                                language="en",
                                audio_device=None,
                                debug=False,
                            )
                            mock_config.return_value = mock_config_obj
                            mock_dict.return_value = MagicMock(terms=[], replacements={})

                            app = Hanasu(config_dir=tmp_path)

                            with patch("hanasu.main.save_config") as mock_save:
                                app.change_hotkey("cmd+alt+v")

                                mock_save.assert_called_once()
                                # Verify config was updated before saving
                                assert mock_config_obj.hotkey == "cmd+alt+v"

    def test_change_hotkey_updates_menubar(self, tmp_path: Path):
        """Changing hotkey updates menu bar display."""
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
                            mock_menubar = MagicMock()
                            app._menubar_app = mock_menubar

                            with patch("hanasu.main.save_config"):
                                app.change_hotkey("cmd+alt+v")

                            mock_menubar.setHotkey_.assert_called_once_with("cmd+alt+v")

    def test_change_hotkey_with_invalid_hotkey_raises(self, tmp_path: Path):
        """Invalid hotkey string raises HotkeyParseError."""
        from hanasu.hotkey import HotkeyParseError

        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener") as mock_listener_class:
                            mock_config.return_value = MagicMock(
                                hotkey="ctrl+shift+space",
                                model="small",
                                language="en",
                                audio_device=None,
                                debug=False,
                            )
                            mock_dict.return_value = MagicMock(terms=[], replacements={})

                            # First call (init) succeeds, second call (change) raises
                            mock_listener_class.side_effect = [
                                MagicMock(),  # Initial listener
                                HotkeyParseError("Unknown key: invalid"),  # change_hotkey call
                            ]

                            app = Hanasu(config_dir=tmp_path)

                            with pytest.raises(HotkeyParseError):
                                app.change_hotkey("invalid+hotkey+combo")


class TestIsVideoFile:
    """Test video file detection."""

    def test_returns_true_for_mp4(self):
        """MP4 files are detected as video."""
        assert is_video_file("recording.mp4") is True

    def test_returns_true_for_mov(self):
        """MOV files are detected as video."""
        assert is_video_file("recording.mov") is True

    def test_returns_true_for_mkv(self):
        """MKV files are detected as video."""
        assert is_video_file("recording.mkv") is True

    def test_returns_true_for_other_video_formats(self):
        """Other common video formats are detected."""
        assert is_video_file("video.avi") is True
        assert is_video_file("video.webm") is True
        assert is_video_file("video.m4v") is True
        assert is_video_file("video.flv") is True
        assert is_video_file("video.wmv") is True

    def test_returns_false_for_audio_files(self):
        """Audio files are not detected as video."""
        assert is_video_file("audio.mp3") is False
        assert is_video_file("audio.wav") is False
        assert is_video_file("audio.m4a") is False
        assert is_video_file("audio.flac") is False

    def test_case_insensitive_detection(self):
        """Extension detection is case-insensitive."""
        assert is_video_file("VIDEO.MP4") is True
        assert is_video_file("video.Mp4") is True
        assert is_video_file("video.MOV") is True

    def test_handles_path_objects(self):
        """Works with Path objects, not just strings."""
        assert is_video_file(Path("/path/to/video.mp4")) is True
        assert is_video_file(Path("/path/to/audio.wav")) is False


class TestExtractAudioFromVideo:
    """Test audio extraction from video files."""

    def test_calls_ffmpeg_with_correct_arguments(self, tmp_path: Path):
        """ffmpeg is called with correct extraction arguments."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("hanasu.main.find_ffmpeg") as mock_find:
            with patch("hanasu.main.subprocess.run") as mock_run:
                mock_find.return_value = "/opt/homebrew/bin/ffmpeg"
                mock_run.return_value = MagicMock(returncode=0, stderr="")

                result = extract_audio_from_video(str(video_file))

                # Verify ffmpeg was called
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]

                # Check key arguments (now uses full path from find_ffmpeg)
                assert call_args[0] == "/opt/homebrew/bin/ffmpeg"
                assert "-i" in call_args
                assert str(video_file) in call_args
                assert "-vn" in call_args  # No video
                assert "-acodec" in call_args
                assert "pcm_s16le" in call_args  # WAV codec
                assert "-ar" in call_args
                assert "16000" in call_args  # 16kHz sample rate
                assert "-ac" in call_args
                assert "1" in call_args  # Mono
                assert "-y" in call_args  # Overwrite

                # Clean up temp file
                if Path(result).exists():
                    Path(result).unlink()

    def test_returns_temp_wav_path(self, tmp_path: Path):
        """Returns path to temporary WAV file."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("hanasu.main.find_ffmpeg") as mock_find:
            with patch("hanasu.main.subprocess.run") as mock_run:
                mock_find.return_value = "/opt/homebrew/bin/ffmpeg"
                mock_run.return_value = MagicMock(returncode=0, stderr="")

                result = extract_audio_from_video(str(video_file))

                assert result.endswith(".wav")

                # Clean up temp file
                if Path(result).exists():
                    Path(result).unlink()

    def test_raises_error_on_ffmpeg_failure(self, tmp_path: Path):
        """Raises RuntimeError when ffmpeg fails."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("hanasu.main.find_ffmpeg") as mock_find:
            with patch("hanasu.main.subprocess.run") as mock_run:
                mock_find.return_value = "/opt/homebrew/bin/ffmpeg"
                mock_run.return_value = MagicMock(
                    returncode=1, stderr="Error: No audio stream found"
                )

                with pytest.raises(RuntimeError, match="(?i)ffmpeg|audio"):
                    extract_audio_from_video(str(video_file))

    def test_raises_error_when_ffmpeg_not_installed(self, tmp_path: Path):
        """Raises helpful error when ffmpeg is not installed."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("hanasu.main.find_ffmpeg") as mock_find:
            mock_find.return_value = None

            with pytest.raises(RuntimeError, match="(?i)ffmpeg.*install"):
                extract_audio_from_video(str(video_file))


class TestFindFfmpeg:
    """Test ffmpeg binary discovery for macOS GUI apps."""

    def test_returns_homebrew_apple_silicon_path_when_exists(self):
        """Returns /opt/homebrew/bin/ffmpeg when it exists."""
        from hanasu.main import find_ffmpeg

        with patch("hanasu.main.Path.exists") as mock_exists:
            # First call is for /opt/homebrew/bin/ffmpeg, should return True
            mock_exists.side_effect = [True]

            result = find_ffmpeg()

            assert result == "/opt/homebrew/bin/ffmpeg"

    def test_returns_homebrew_intel_path_when_apple_silicon_missing(self):
        """Returns /usr/local/bin/ffmpeg when Apple Silicon path missing."""
        from hanasu.main import find_ffmpeg

        with patch("hanasu.main.Path.exists") as mock_exists:
            # First call is for /opt/homebrew/bin/ffmpeg (False)
            # Second call is for /usr/local/bin/ffmpeg (True)
            mock_exists.side_effect = [False, True]

            result = find_ffmpeg()

            assert result == "/usr/local/bin/ffmpeg"

    def test_returns_which_result_when_homebrew_paths_missing(self):
        """Falls back to shutil.which when Homebrew paths don't exist."""
        from hanasu.main import find_ffmpeg

        with patch("hanasu.main.Path.exists") as mock_exists:
            with patch("hanasu.main.shutil.which") as mock_which:
                # Both Homebrew paths don't exist
                mock_exists.side_effect = [False, False]
                mock_which.return_value = "/some/other/path/ffmpeg"

                result = find_ffmpeg()

                assert result == "/some/other/path/ffmpeg"
                mock_which.assert_called_once_with("ffmpeg")

    def test_returns_none_when_ffmpeg_not_found_anywhere(self):
        """Returns None when ffmpeg not found in any location."""
        from hanasu.main import find_ffmpeg

        with patch("hanasu.main.Path.exists") as mock_exists:
            with patch("hanasu.main.shutil.which") as mock_which:
                mock_exists.side_effect = [False, False]
                mock_which.return_value = None

                result = find_ffmpeg()

                assert result is None


class TestExtractAudioUsesFoundFfmpeg:
    """Test that extract_audio_from_video uses find_ffmpeg result."""

    def test_uses_found_ffmpeg_path(self, tmp_path: Path):
        """Calls subprocess with the path returned by find_ffmpeg."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("hanasu.main.find_ffmpeg") as mock_find:
            with patch("hanasu.main.subprocess.run") as mock_run:
                mock_find.return_value = "/opt/homebrew/bin/ffmpeg"
                mock_run.return_value = MagicMock(returncode=0, stderr="")

                result = extract_audio_from_video(str(video_file))

                # Verify ffmpeg path is used
                call_args = mock_run.call_args[0][0]
                assert call_args[0] == "/opt/homebrew/bin/ffmpeg"

                # Clean up
                if Path(result).exists():
                    Path(result).unlink()


class TestRunTranscribeVideo:
    """Test video transcription integration."""

    def test_transcribes_video_file(self, tmp_path: Path, capsys):
        """Video file is extracted and transcribed."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("hanasu.main.is_video_file", return_value=True):
            with patch("hanasu.main.extract_audio_from_video") as mock_extract:
                with patch("mlx_whisper.transcribe") as mock_transcribe:
                    temp_audio = tmp_path / "temp.wav"
                    temp_audio.touch()
                    mock_extract.return_value = str(temp_audio)
                    mock_transcribe.return_value = {
                        "text": "Hello from video",
                        "segments": [],
                    }

                    run_transcribe(str(video_file))

                    # Verify extraction was called
                    mock_extract.assert_called_once_with(str(video_file))

                    # Verify transcription was called with extracted audio
                    mock_transcribe.assert_called_once()
                    call_args = mock_transcribe.call_args[0]
                    assert str(temp_audio) in call_args

                    # Verify output
                    captured = capsys.readouterr()
                    assert "Hello from video" in captured.out

    def test_cleans_up_temp_file_after_transcription(self, tmp_path: Path):
        """Temporary audio file is deleted after successful transcription."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()
        temp_audio = tmp_path / "temp.wav"
        temp_audio.touch()

        with patch("hanasu.main.is_video_file", return_value=True):
            with patch("hanasu.main.extract_audio_from_video") as mock_extract:
                with patch("mlx_whisper.transcribe") as mock_transcribe:
                    mock_extract.return_value = str(temp_audio)
                    mock_transcribe.return_value = {
                        "text": "Hello",
                        "segments": [],
                    }

                    run_transcribe(str(video_file))

                    # Temp file should be cleaned up
                    assert not temp_audio.exists()

    def test_cleans_up_temp_file_on_error(self, tmp_path: Path):
        """Temporary audio file is deleted even when transcription fails."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()
        temp_audio = tmp_path / "temp.wav"
        temp_audio.touch()

        with patch("hanasu.main.is_video_file", return_value=True):
            with patch("hanasu.main.extract_audio_from_video") as mock_extract:
                with patch("mlx_whisper.transcribe") as mock_transcribe:
                    mock_extract.return_value = str(temp_audio)
                    mock_transcribe.side_effect = Exception("Transcription failed")

                    with pytest.raises(Exception, match="Transcription failed"):
                        run_transcribe(str(video_file))

                    # Temp file should still be cleaned up
                    assert not temp_audio.exists()

    def test_audio_files_transcribed_directly(self, tmp_path: Path, capsys):
        """Audio files bypass extraction and are transcribed directly."""
        audio_file = tmp_path / "audio.wav"
        audio_file.touch()

        with patch("hanasu.main.is_video_file", return_value=False):
            with patch("hanasu.main.extract_audio_from_video") as mock_extract:
                with patch("mlx_whisper.transcribe") as mock_transcribe:
                    mock_transcribe.return_value = {
                        "text": "Hello from audio",
                        "segments": [],
                    }

                    run_transcribe(str(audio_file))

                    # Extraction should NOT be called for audio files
                    mock_extract.assert_not_called()

                    # Transcription should be called with original file
                    mock_transcribe.assert_called_once()
                    call_args = mock_transcribe.call_args[0]
                    assert str(audio_file) in call_args


class TestIsModelCached:
    """Test model cache detection."""

    def test_returns_true_when_cache_directory_exists(self, tmp_path: Path):
        """Returns True when model cache directory exists."""
        # Create mock cache structure
        cache_dir = tmp_path / ".cache" / "huggingface" / "hub"
        model_cache = cache_dir / "models--mlx-community--whisper-small-mlx"
        model_cache.mkdir(parents=True)

        with patch("hanasu.main.Path.home", return_value=tmp_path):
            result = is_model_cached("small")

        assert result is True

    def test_returns_false_when_cache_directory_missing(self, tmp_path: Path):
        """Returns False when model cache directory does not exist."""
        # Create cache base but not the model directory
        cache_dir = tmp_path / ".cache" / "huggingface" / "hub"
        cache_dir.mkdir(parents=True)

        with patch("hanasu.main.Path.home", return_value=tmp_path):
            result = is_model_cached("medium")

        assert result is False

    def test_constructs_correct_cache_path_for_each_model(self, tmp_path: Path):
        """Constructs the correct HuggingFace cache path for each model size."""
        cache_dir = tmp_path / ".cache" / "huggingface" / "hub"
        cache_dir.mkdir(parents=True)

        # Test that large model uses v3 suffix
        large_cache = cache_dir / "models--mlx-community--whisper-large-v3-mlx"
        large_cache.mkdir()

        with patch("hanasu.main.Path.home", return_value=tmp_path):
            result = is_model_cached("large")

        assert result is True

    def test_defaults_to_small_for_unknown_model(self, tmp_path: Path):
        """Falls back to small model path for unknown model names."""
        cache_dir = tmp_path / ".cache" / "huggingface" / "hub"
        small_cache = cache_dir / "models--mlx-community--whisper-small-mlx"
        small_cache.mkdir(parents=True)

        with patch("hanasu.main.Path.home", return_value=tmp_path):
            result = is_model_cached("nonexistent-model")

        assert result is True


class TestChangeModel:
    """Test model hot-swap functionality."""

    def test_change_model_creates_new_transcriber(self, tmp_path: Path):
        """Changing model creates a new Transcriber instance with new model."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber") as mock_transcriber_class:
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.is_model_cached", return_value=True):
                                with patch("hanasu.main.save_config"):
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=False,
                                        clear_clipboard=False,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})

                                    app = Hanasu(config_dir=tmp_path)

                                    # Change to medium model
                                    app.change_model("medium")

                                    # Wait for background thread to complete
                                    import time

                                    time.sleep(0.1)

                                    # Verify Transcriber was created with new model
                                    assert mock_transcriber_class.call_count == 2
                                    second_call = mock_transcriber_class.call_args_list[1]
                                    assert second_call[1]["model"] == "medium"

    def test_change_model_saves_config(self, tmp_path: Path):
        """Changing model persists the new model to config file."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.is_model_cached", return_value=True):
                                with patch("hanasu.main.save_config") as mock_save:
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=False,
                                        clear_clipboard=False,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})

                                    app = Hanasu(config_dir=tmp_path)
                                    mock_save.reset_mock()

                                    app.change_model("medium")

                                    # Wait for background thread
                                    import time

                                    time.sleep(0.1)

                                    mock_save.assert_called_once()
                                    saved_config = mock_save.call_args[0][0]
                                    assert saved_config.model == "medium"

    def test_change_model_blocked_while_recording(self, tmp_path: Path):
        """Model change is blocked while recording is in progress."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber") as mock_transcriber_class:
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.is_model_cached", return_value=True):
                                with patch("hanasu.main.save_config") as mock_save:
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=True,
                                        clear_clipboard=False,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})

                                    app = Hanasu(config_dir=tmp_path)
                                    app._recording = True

                                    initial_call_count = mock_transcriber_class.call_count
                                    mock_save.reset_mock()

                                    app.change_model("medium")

                                    # Wait a bit to ensure nothing happened
                                    import time

                                    time.sleep(0.1)

                                    # Transcriber should NOT have been recreated
                                    assert mock_transcriber_class.call_count == initial_call_count
                                    # Config should NOT have been saved
                                    mock_save.assert_not_called()

    def test_change_model_downloads_uncached_model(self, tmp_path: Path):
        """Model change downloads uncached model before switching."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.is_model_cached", return_value=False):
                                with patch("hanasu.main.save_config"):
                                    with patch("hanasu.main.download_model") as mock_download:
                                        mock_config.return_value = MagicMock(
                                            hotkey="ctrl+shift+space",
                                            model="small",
                                            language="en",
                                            audio_device=None,
                                            debug=False,
                                            clear_clipboard=False,
                                        )
                                        mock_dict.return_value = MagicMock(
                                            terms=[], replacements={}
                                        )

                                        app = Hanasu(config_dir=tmp_path)

                                        app.change_model("large")

                                        # Wait for background thread
                                        import time

                                        time.sleep(0.1)

                                        mock_download.assert_called_once_with("large")

    def test_change_model_same_model_does_nothing(self, tmp_path: Path):
        """Changing to the same model is a no-op."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber") as mock_transcriber_class:
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.save_config") as mock_save:
                                mock_config.return_value = MagicMock(
                                    hotkey="ctrl+shift+space",
                                    model="small",
                                    language="en",
                                    audio_device=None,
                                    debug=False,
                                    clear_clipboard=False,
                                )
                                mock_dict.return_value = MagicMock(terms=[], replacements={})

                                app = Hanasu(config_dir=tmp_path)
                                initial_call_count = mock_transcriber_class.call_count
                                mock_save.reset_mock()

                                # Try to change to same model
                                app.change_model("small")

                                import time

                                time.sleep(0.1)

                                # Should not create new transcriber or save
                                assert mock_transcriber_class.call_count == initial_call_count
                                mock_save.assert_not_called()

    def test_change_model_invalid_model_does_nothing(self, tmp_path: Path):
        """Changing to an invalid model is a no-op."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber") as mock_transcriber_class:
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.save_config") as mock_save:
                                mock_config.return_value = MagicMock(
                                    hotkey="ctrl+shift+space",
                                    model="small",
                                    language="en",
                                    audio_device=None,
                                    debug=False,
                                    clear_clipboard=False,
                                )
                                mock_dict.return_value = MagicMock(terms=[], replacements={})

                                app = Hanasu(config_dir=tmp_path)
                                initial_call_count = mock_transcriber_class.call_count
                                mock_save.reset_mock()

                                # Try to change to invalid model
                                app.change_model("nonexistent")

                                import time

                                time.sleep(0.1)

                                # Should not create new transcriber or save
                                assert mock_transcriber_class.call_count == initial_call_count
                                mock_save.assert_not_called()

    def test_change_model_blocked_while_change_in_progress(self, tmp_path: Path):
        """Model change is blocked while another change is in progress."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber") as mock_transcriber_class:
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.is_model_cached", return_value=True):
                                with patch("hanasu.main.save_config") as mock_save:
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=True,
                                        clear_clipboard=False,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})

                                    app = Hanasu(config_dir=tmp_path)
                                    # Simulate a model change already in progress
                                    app._model_change_in_progress = True

                                    initial_call_count = mock_transcriber_class.call_count
                                    mock_save.reset_mock()

                                    app.change_model("medium")

                                    # Should not start new change
                                    assert mock_transcriber_class.call_count == initial_call_count
                                    mock_save.assert_not_called()

    def test_change_model_updates_menubar(self, tmp_path: Path):
        """Changing model updates the menu bar state."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.is_model_cached", return_value=True):
                                with patch("hanasu.main.save_config"):
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=False,
                                        clear_clipboard=False,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})

                                    app = Hanasu(config_dir=tmp_path)
                                    mock_menubar = MagicMock()
                                    app._menubar_app = mock_menubar

                                    app.change_model("medium")

                                    # Wait for background thread
                                    import time

                                    time.sleep(0.1)

                                    mock_menubar.setCurrentModel_.assert_called_with("medium")
                                    mock_menubar.refreshModelStates.assert_called()


class TestMenubarWiring:
    """Test wiring between Hanasu and MenuBar for model selection."""

    def test_run_passes_model_callbacks_to_menubar(self, tmp_path: Path):
        """Hanasu.run() passes model callbacks to run_menubar_app."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener") as mock_listener:
                            with patch("hanasu.main.run_menubar_app") as mock_menubar_app:
                                with patch("hanasu.main.start_app_loop"):
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=False,
                                        clear_clipboard=False,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})
                                    mock_listener_instance = MagicMock()
                                    mock_listener.return_value = mock_listener_instance

                                    app = Hanasu(config_dir=tmp_path)
                                    app.run()

                                    # Verify run_menubar_app was called with model params
                                    mock_menubar_app.assert_called_once()
                                    call_kwargs = mock_menubar_app.call_args[1]

                                    assert "on_model_change" in call_kwargs
                                    assert "current_model" in call_kwargs
                                    assert "is_model_cached" in call_kwargs
                                    assert call_kwargs["current_model"] == "small"

    def test_on_model_change_callback_calls_change_model(self, tmp_path: Path):
        """Model change callback from menubar triggers change_model."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.run_menubar_app") as mock_menubar_app:
                                with patch("hanasu.main.start_app_loop"):
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=False,
                                        clear_clipboard=False,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})

                                    app = Hanasu(config_dir=tmp_path)
                                    app.change_model = MagicMock()
                                    app.run()

                                    # Get the callback that was passed
                                    call_kwargs = mock_menubar_app.call_args[1]
                                    on_model_change = call_kwargs["on_model_change"]

                                    # Simulate menubar calling back
                                    on_model_change("medium")

                                    # Verify change_model was called
                                    app.change_model.assert_called_once_with("medium")


class TestRunTranscribeFileOutput:
    """Test file output option for transcribe command."""

    def test_outputs_to_stdout_by_default(self, tmp_path: Path, capsys):
        """When no output file specified, result goes to stdout."""
        audio_file = tmp_path / "audio.wav"
        audio_file.touch()

        with patch("hanasu.main.is_video_file", return_value=False):
            with patch("mlx_whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "text": "Hello world",
                    "segments": [],
                }

                run_transcribe(str(audio_file))

                captured = capsys.readouterr()
                assert "Hello world" in captured.out

    def test_writes_plain_text_to_file(self, tmp_path: Path, capsys):
        """When output file specified, plain text written to file not stdout."""
        audio_file = tmp_path / "audio.wav"
        audio_file.touch()
        output_file = tmp_path / "output.txt"

        with patch("hanasu.main.is_video_file", return_value=False):
            with patch("mlx_whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "text": "Hello from file",
                    "segments": [],
                }

                run_transcribe(str(audio_file), output_file=str(output_file))

                # Output should be in file
                assert output_file.exists()
                assert "Hello from file" in output_file.read_text()

                # Stdout should be empty
                captured = capsys.readouterr()
                assert captured.out == ""

    def test_writes_vtt_format_to_file(self, tmp_path: Path, capsys):
        """When output file and VTT flag specified, VTT written to file."""
        audio_file = tmp_path / "audio.wav"
        audio_file.touch()
        output_file = tmp_path / "output.vtt"

        with patch("hanasu.main.is_video_file", return_value=False):
            with patch("mlx_whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "text": "Full text",
                    "segments": [
                        {"start": 0.0, "end": 2.5, "text": " Hello world"},
                        {"start": 2.5, "end": 5.0, "text": " Goodbye"},
                    ],
                }

                run_transcribe(str(audio_file), use_vtt=True, output_file=str(output_file))

                # Output should be in file with VTT format
                content = output_file.read_text()
                assert "WEBVTT" in content
                assert "00:00:00.000 --> 00:00:02.500" in content
                assert "Hello world" in content

                # Stdout should be empty
                captured = capsys.readouterr()
                assert captured.out == ""

    def test_raises_error_when_parent_dir_missing(self, tmp_path: Path):
        """When output file's parent directory doesn't exist, raises error."""
        audio_file = tmp_path / "audio.wav"
        audio_file.touch()
        output_file = tmp_path / "nonexistent" / "subdir" / "output.txt"

        with patch("hanasu.main.is_video_file", return_value=False):
            with patch("mlx_whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "text": "Hello",
                    "segments": [],
                }

                with pytest.raises(FileNotFoundError):
                    run_transcribe(str(audio_file), output_file=str(output_file))


class TestRunTranscribeModelFlag:
    """Test --model flag for transcribe command."""

    def test_uses_small_model_by_default(self, tmp_path: Path):
        """Default model is small when no flag provided."""
        audio_file = tmp_path / "audio.wav"
        audio_file.touch()

        with patch("hanasu.main.is_video_file", return_value=False):
            with patch("mlx_whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {"text": "Hello", "segments": []}

                run_transcribe(str(audio_file))

                # Should use small model path
                call_args = mock_transcribe.call_args
                model_path = call_args[1]["path_or_hf_repo"]
                assert "small" in model_path.lower()

    def test_uses_specified_model(self, tmp_path: Path):
        """Uses model specified by --model flag."""
        audio_file = tmp_path / "audio.wav"
        audio_file.touch()

        with patch("hanasu.main.is_video_file", return_value=False):
            with patch("mlx_whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {"text": "Hello", "segments": []}

                run_transcribe(str(audio_file), model="medium")

                # Should use medium model path
                call_args = mock_transcribe.call_args
                model_path = call_args[1]["path_or_hf_repo"]
                assert "medium" in model_path.lower()

    def test_large_flag_overrides_model(self, tmp_path: Path):
        """--large flag takes precedence over --model."""
        audio_file = tmp_path / "audio.wav"
        audio_file.touch()

        with patch("hanasu.main.is_video_file", return_value=False):
            with patch("mlx_whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {"text": "Hello", "segments": []}

                # When both --large and --model are specified, --large wins
                run_transcribe(str(audio_file), use_large=True, model="tiny")

                # Should use large model path
                call_args = mock_transcribe.call_args
                model_path = call_args[1]["path_or_hf_repo"]
                assert "large" in model_path.lower()

    def test_supports_all_valid_models(self, tmp_path: Path):
        """All valid model sizes are supported."""
        from hanasu.config import VALID_MODELS

        audio_file = tmp_path / "audio.wav"
        audio_file.touch()

        for model in VALID_MODELS:
            with patch("hanasu.main.is_video_file", return_value=False):
                with patch("mlx_whisper.transcribe") as mock_transcribe:
                    mock_transcribe.return_value = {"text": "Hello", "segments": []}

                    # Should not raise for any valid model
                    run_transcribe(str(audio_file), model=model)

                    call_args = mock_transcribe.call_args
                    model_path = call_args[1]["path_or_hf_repo"]
                    # Model path should contain the model name
                    assert model in model_path.lower()


class TestOnTranscribeFile:
    """Test file transcription menu handler."""

    def test_on_transcribe_file_method_exists(self, tmp_path: Path):
        """Hanasu class has _on_transcribe_file method."""
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
                                clear_clipboard=False,
                                last_output_dir=None,
                            )
                            mock_dict.return_value = MagicMock(terms=[], replacements={})

                            app = Hanasu(config_dir=tmp_path)

                            assert hasattr(app, "_on_transcribe_file")
                            assert callable(app._on_transcribe_file)

    def test_calls_file_picker_with_audio_video_extensions(self, tmp_path: Path):
        """Opens file picker with correct audio/video extensions."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.open_file_picker") as mock_picker:
                                mock_config.return_value = MagicMock(
                                    hotkey="ctrl+shift+space",
                                    model="small",
                                    language="en",
                                    audio_device=None,
                                    debug=False,
                                    clear_clipboard=False,
                                    last_output_dir=None,
                                )
                                mock_dict.return_value = MagicMock(terms=[], replacements={})
                                mock_picker.return_value = None  # User cancelled

                                app = Hanasu(config_dir=tmp_path)
                                app._on_transcribe_file()

                                mock_picker.assert_called_once()
                                call_kwargs = mock_picker.call_args
                                extensions = (
                                    call_kwargs[1].get("allowed_extensions") or call_kwargs[0][0]
                                )

                                # Should include common audio/video formats
                                assert "mp3" in extensions
                                assert "wav" in extensions
                                assert "mp4" in extensions
                                assert "mov" in extensions

    def test_returns_early_if_file_picker_cancelled(self, tmp_path: Path):
        """Does nothing if user cancels file picker."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.open_file_picker") as mock_file_picker:
                                with patch("hanasu.main.show_format_picker") as mock_format:
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=False,
                                        clear_clipboard=False,
                                        last_output_dir=None,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})
                                    mock_file_picker.return_value = None  # User cancelled

                                    app = Hanasu(config_dir=tmp_path)
                                    app._on_transcribe_file()

                                    # Format picker should not be called
                                    mock_format.assert_not_called()

    def test_calls_format_picker_after_file_selection(self, tmp_path: Path):
        """Shows format picker after file is selected."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.open_file_picker") as mock_file_picker:
                                with patch("hanasu.main.show_format_picker") as mock_format:
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=False,
                                        clear_clipboard=False,
                                        last_output_dir=None,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})
                                    mock_file_picker.return_value = "/path/to/audio.mp3"
                                    mock_format.return_value = None  # User cancelled

                                    app = Hanasu(config_dir=tmp_path)
                                    app._on_transcribe_file()

                                    mock_format.assert_called_once()


class TestRunFileTranscription:
    """Test background file transcription via subprocess."""

    def test_run_file_transcription_method_exists(self, tmp_path: Path):
        """Hanasu class has _run_file_transcription method."""
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
                                clear_clipboard=False,
                                last_output_dir=None,
                            )
                            mock_dict.return_value = MagicMock(terms=[], replacements={})

                            app = Hanasu(config_dir=tmp_path)

                            assert hasattr(app, "_run_file_transcription")
                            assert callable(app._run_file_transcription)

    def test_uses_subprocess_to_run_transcription(self, tmp_path: Path):
        """Transcription runs via subprocess to isolate Metal GPU context."""
        with (
            patch("hanasu.main.load_config") as mock_config,
            patch("hanasu.main.load_dictionary") as mock_dict,
            patch("hanasu.main.Recorder"),
            patch("hanasu.main.Transcriber"),
            patch("hanasu.main.HotkeyListener"),
            patch("subprocess.run") as mock_run,
        ):
            mock_config.return_value = MagicMock(
                hotkey="ctrl+shift+space",
                model="small",
                language="en",
                audio_device=None,
                debug=False,
                clear_clipboard=False,
                last_output_dir=None,
            )
            mock_dict.return_value = MagicMock(terms=[], replacements={})
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            app = Hanasu(config_dir=tmp_path)
            output_file = tmp_path / "output.txt"

            app._run_file_transcription("/path/to/audio.mp3", str(output_file), False)

            # Verify subprocess.run was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            # Command should include hanasu transcribe
            assert "hanasu" in cmd[1] or cmd[0].endswith(("python", "python3"))
            assert "transcribe" in cmd
            assert "/path/to/audio.mp3" in cmd
            assert "-o" in cmd
            assert str(output_file) in cmd

    def test_subprocess_includes_model_flag(self, tmp_path: Path):
        """Subprocess command includes --model flag with configured model."""
        with (
            patch("hanasu.main.load_config") as mock_config,
            patch("hanasu.main.load_dictionary") as mock_dict,
            patch("hanasu.main.Recorder"),
            patch("hanasu.main.Transcriber"),
            patch("hanasu.main.HotkeyListener"),
            patch("subprocess.run") as mock_run,
        ):
            mock_config.return_value = MagicMock(
                hotkey="ctrl+shift+space",
                model="medium",
                language="en",
                audio_device=None,
                debug=False,
                clear_clipboard=False,
                last_output_dir=None,
            )
            mock_dict.return_value = MagicMock(terms=[], replacements={})
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            app = Hanasu(config_dir=tmp_path)
            output_file = tmp_path / "output.txt"

            app._run_file_transcription("/path/to/audio.mp3", str(output_file), False)

            call_args = mock_run.call_args
            cmd = call_args[0][0]

            # Command should include --model medium
            assert "--model" in cmd
            model_idx = cmd.index("--model")
            assert cmd[model_idx + 1] == "medium"

    def test_subprocess_includes_vtt_flag_when_requested(self, tmp_path: Path):
        """Subprocess command includes --vtt flag when VTT format requested."""
        with (
            patch("hanasu.main.load_config") as mock_config,
            patch("hanasu.main.load_dictionary") as mock_dict,
            patch("hanasu.main.Recorder"),
            patch("hanasu.main.Transcriber"),
            patch("hanasu.main.HotkeyListener"),
            patch("subprocess.run") as mock_run,
        ):
            mock_config.return_value = MagicMock(
                hotkey="ctrl+shift+space",
                model="small",
                language="en",
                audio_device=None,
                debug=False,
                clear_clipboard=False,
                last_output_dir=None,
            )
            mock_dict.return_value = MagicMock(terms=[], replacements={})
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            app = Hanasu(config_dir=tmp_path)
            output_file = tmp_path / "output.vtt"

            app._run_file_transcription("/path/to/audio.mp3", str(output_file), True)

            call_args = mock_run.call_args
            cmd = call_args[0][0]

            # Command should include --vtt flag
            assert "--vtt" in cmd

    def test_shows_error_on_subprocess_failure(self, tmp_path: Path):
        """Shows error dialog when subprocess returns non-zero exit code."""
        with (
            patch("hanasu.main.load_config") as mock_config,
            patch("hanasu.main.load_dictionary") as mock_dict,
            patch("hanasu.main.Recorder"),
            patch("hanasu.main.Transcriber"),
            patch("hanasu.main.HotkeyListener"),
            patch("subprocess.run") as mock_run,
        ):
            mock_config.return_value = MagicMock(
                hotkey="ctrl+shift+space",
                model="small",
                language="en",
                audio_device=None,
                debug=False,
                clear_clipboard=False,
                last_output_dir=None,
            )
            mock_dict.return_value = MagicMock(terms=[], replacements={})
            mock_run.return_value = MagicMock(returncode=1, stderr="ffmpeg not found")

            app = Hanasu(config_dir=tmp_path)
            app._show_transcription_error = MagicMock()
            output_file = tmp_path / "output.txt"

            app._run_file_transcription("/path/to/video.mp4", str(output_file), False)

            # Error dialog should be shown
            app._show_transcription_error.assert_called_once()
            error_msg = app._show_transcription_error.call_args[0][0]
            assert "ffmpeg" in error_msg.lower() or "failed" in error_msg.lower()

    def test_shows_error_on_subprocess_timeout(self, tmp_path: Path):
        """Shows error dialog when subprocess times out."""
        import subprocess

        with (
            patch("hanasu.main.load_config") as mock_config,
            patch("hanasu.main.load_dictionary") as mock_dict,
            patch("hanasu.main.Recorder"),
            patch("hanasu.main.Transcriber"),
            patch("hanasu.main.HotkeyListener"),
            patch("subprocess.run") as mock_run,
        ):
            mock_config.return_value = MagicMock(
                hotkey="ctrl+shift+space",
                model="small",
                language="en",
                audio_device=None,
                debug=False,
                clear_clipboard=False,
                last_output_dir=None,
            )
            mock_dict.return_value = MagicMock(terms=[], replacements={})
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["hanasu"], timeout=600)

            app = Hanasu(config_dir=tmp_path)
            app._show_transcription_error = MagicMock()
            output_file = tmp_path / "output.txt"

            app._run_file_transcription("/path/to/large_video.mp4", str(output_file), False)

            # Error dialog should be shown with timeout message
            app._show_transcription_error.assert_called_once()
            error_msg = app._show_transcription_error.call_args[0][0]
            assert "timed out" in error_msg.lower() or "timeout" in error_msg.lower()

    def test_no_error_shown_on_successful_completion(self, tmp_path: Path):
        """No error dialog shown when subprocess succeeds."""
        with (
            patch("hanasu.main.load_config") as mock_config,
            patch("hanasu.main.load_dictionary") as mock_dict,
            patch("hanasu.main.Recorder"),
            patch("hanasu.main.Transcriber"),
            patch("hanasu.main.HotkeyListener"),
            patch("subprocess.run") as mock_run,
        ):
            mock_config.return_value = MagicMock(
                hotkey="ctrl+shift+space",
                model="small",
                language="en",
                audio_device=None,
                debug=False,
                clear_clipboard=False,
                last_output_dir=None,
            )
            mock_dict.return_value = MagicMock(terms=[], replacements={})
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            app = Hanasu(config_dir=tmp_path)
            app._show_transcription_error = MagicMock()
            output_file = tmp_path / "output.txt"

            app._run_file_transcription("/path/to/audio.mp3", str(output_file), False)

            # No error should be shown on success
            app._show_transcription_error.assert_not_called()

    def test_handles_paths_with_spaces(self, tmp_path: Path):
        """Subprocess command handles file paths with spaces correctly."""
        with (
            patch("hanasu.main.load_config") as mock_config,
            patch("hanasu.main.load_dictionary") as mock_dict,
            patch("hanasu.main.Recorder"),
            patch("hanasu.main.Transcriber"),
            patch("hanasu.main.HotkeyListener"),
            patch("subprocess.run") as mock_run,
        ):
            mock_config.return_value = MagicMock(
                hotkey="ctrl+shift+space",
                model="small",
                language="en",
                audio_device=None,
                debug=False,
                clear_clipboard=False,
                last_output_dir=None,
            )
            mock_dict.return_value = MagicMock(terms=[], replacements={})
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            app = Hanasu(config_dir=tmp_path)
            output_file = tmp_path / "my output file.txt"

            app._run_file_transcription("/path/to/my audio file.mp3", str(output_file), False)

            call_args = mock_run.call_args
            cmd = call_args[0][0]

            # Paths with spaces should be passed as separate list elements (not shell-quoted)
            assert "/path/to/my audio file.mp3" in cmd
            assert str(output_file) in cmd


class TestShowTranscriptionError:
    """Test error dialog for file transcription."""

    def test_show_transcription_error_method_exists(self, tmp_path: Path):
        """Hanasu class has _show_transcription_error method."""
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
                                clear_clipboard=False,
                                last_output_dir=None,
                            )
                            mock_dict.return_value = MagicMock(terms=[], replacements={})

                            app = Hanasu(config_dir=tmp_path)

                            assert hasattr(app, "_show_transcription_error")
                            assert callable(app._show_transcription_error)


class TestEnsureHomebrewInPath:
    """Test PATH configuration for macOS GUI apps."""

    def test_adds_homebrew_apple_silicon_to_path(self, monkeypatch):
        """Adds /opt/homebrew/bin to PATH if not present."""
        monkeypatch.setenv("PATH", "/usr/bin:/bin")

        ensure_homebrew_in_path()

        assert "/opt/homebrew/bin" in os.environ["PATH"]

    def test_adds_homebrew_intel_to_path(self, monkeypatch):
        """Adds /usr/local/bin to PATH if not present."""
        monkeypatch.setenv("PATH", "/usr/bin:/bin")

        ensure_homebrew_in_path()

        assert "/usr/local/bin" in os.environ["PATH"]

    def test_does_not_duplicate_if_already_present(self, monkeypatch):
        """Does not add paths that are already in PATH."""
        original_path = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
        monkeypatch.setenv("PATH", original_path)

        ensure_homebrew_in_path()

        # Should not have duplicates
        path_parts = os.environ["PATH"].split(":")
        assert path_parts.count("/opt/homebrew/bin") == 1
        assert path_parts.count("/usr/local/bin") == 1

    def test_prepends_to_path(self, monkeypatch):
        """Homebrew paths are prepended so they take precedence."""
        monkeypatch.setenv("PATH", "/usr/bin:/bin")

        ensure_homebrew_in_path()

        path_parts = os.environ["PATH"].split(":")
        # Homebrew paths should come before /usr/bin
        homebrew_idx = min(
            path_parts.index("/opt/homebrew/bin") if "/opt/homebrew/bin" in path_parts else 999,
            path_parts.index("/usr/local/bin") if "/usr/local/bin" in path_parts else 999,
        )
        usr_bin_idx = path_parts.index("/usr/bin")
        assert homebrew_idx < usr_bin_idx

    def test_handles_empty_path(self, monkeypatch):
        """Works when PATH is empty (fresh GUI app context)."""
        monkeypatch.delenv("PATH", raising=False)

        ensure_homebrew_in_path()

        assert "/opt/homebrew/bin" in os.environ["PATH"]
        assert "/usr/local/bin" in os.environ["PATH"]


class TestRunMethodLogging:
    """Test that run() method logs progress at key stages for debugging Spotlight launch issues."""

    def test_run_logs_entering_method(self, tmp_path: Path):
        """run() logs a debug message when entering the method."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener") as mock_listener_class:
                            with patch("hanasu.main.run_menubar_app"):
                                with patch("hanasu.main.start_app_loop"):
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=True,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})
                                    mock_listener = MagicMock()
                                    mock_listener_class.return_value = mock_listener

                                    app = Hanasu(config_dir=tmp_path)

                                    with patch.object(app._logger, "debug") as mock_debug:
                                        app.run()

                                        # Should have logged at least one debug message about setting up
                                        debug_messages = [
                                            str(call) for call in mock_debug.call_args_list
                                        ]
                                        assert any(
                                            "menu" in msg.lower() or "setting" in msg.lower()
                                            for msg in debug_messages
                                        ), f"Expected menu bar setup log, got: {debug_messages}"

    def test_run_logs_hotkey_listener_start(self, tmp_path: Path):
        """run() logs when starting the hotkey listener."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener") as mock_listener_class:
                            with patch("hanasu.main.run_menubar_app"):
                                with patch("hanasu.main.start_app_loop"):
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=True,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})
                                    mock_listener = MagicMock()
                                    mock_listener_class.return_value = mock_listener

                                    app = Hanasu(config_dir=tmp_path)

                                    with patch.object(app._logger, "debug") as mock_debug:
                                        app.run()

                                        debug_messages = [
                                            str(call) for call in mock_debug.call_args_list
                                        ]
                                        assert any(
                                            "hotkey" in msg.lower() or "listener" in msg.lower()
                                            for msg in debug_messages
                                        ), f"Expected hotkey listener log, got: {debug_messages}"

    def test_run_logs_event_loop_start(self, tmp_path: Path):
        """run() logs when starting the event loop."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener") as mock_listener_class:
                            with patch("hanasu.main.run_menubar_app"):
                                with patch("hanasu.main.start_app_loop"):
                                    mock_config.return_value = MagicMock(
                                        hotkey="ctrl+shift+space",
                                        model="small",
                                        language="en",
                                        audio_device=None,
                                        debug=True,
                                    )
                                    mock_dict.return_value = MagicMock(terms=[], replacements={})
                                    mock_listener = MagicMock()
                                    mock_listener_class.return_value = mock_listener

                                    app = Hanasu(config_dir=tmp_path)

                                    with patch.object(app._logger, "debug") as mock_debug:
                                        app.run()

                                        debug_messages = [
                                            str(call) for call in mock_debug.call_args_list
                                        ]
                                        assert any(
                                            "event" in msg.lower() or "loop" in msg.lower()
                                            for msg in debug_messages
                                        ), f"Expected event loop log, got: {debug_messages}"


class TestMainExceptionLogging:
    """Test that main() logs exceptions to file instead of just printing."""

    def test_main_logs_exceptions_via_logger(self, tmp_path: Path, monkeypatch):
        """main() logs fatal exceptions via logger, not just print."""
        from hanasu.main import main

        # Simulate args to run daemon
        monkeypatch.setattr("sys.argv", ["hanasu", "--config-dir", str(tmp_path)])

        with patch("hanasu.main.Hanasu") as mock_hanasu_class:
            with patch("hanasu.main.setup_logging"):
                # Make Hanasu.run() raise an exception
                mock_app = MagicMock()
                mock_app.run.side_effect = RuntimeError("Test error")
                mock_hanasu_class.return_value = mock_app

                with patch("hanasu.main.logging.getLogger") as mock_get_logger:
                    mock_logger = MagicMock()
                    mock_get_logger.return_value = mock_logger

                    with pytest.raises(SystemExit):
                        main()

                    # Should have logged the exception via logger
                    assert mock_logger.exception.called or mock_logger.error.called, (
                        "Expected exception to be logged via logger"
                    )
