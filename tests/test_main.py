"""Tests for main orchestration and CLI."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hanasu.main import (
    Hanasu,
    extract_audio_from_video,
    get_status,
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

        with patch("hanasu.main.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            result = extract_audio_from_video(str(video_file))

            # Verify ffmpeg was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]

            # Check key arguments
            assert call_args[0] == "ffmpeg"
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

        with patch("hanasu.main.subprocess.run") as mock_run:
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

        with patch("hanasu.main.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Error: No audio stream found")

            with pytest.raises(RuntimeError, match="(?i)ffmpeg|audio"):
                extract_audio_from_video(str(video_file))

    def test_raises_error_when_ffmpeg_not_installed(self, tmp_path: Path):
        """Raises helpful error when ffmpeg is not installed."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("hanasu.main.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")

            with pytest.raises(RuntimeError, match="(?i)ffmpeg.*install"):
                extract_audio_from_video(str(video_file))


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


class TestOnTranscribeFile:
    """Test file transcription menu handler."""

    def _create_hanasu_with_mocks(self, tmp_path: Path):
        """Helper to create Hanasu instance with mocked dependencies."""
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

                            return Hanasu(config_dir=tmp_path)

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

    def test_returns_early_if_format_picker_cancelled(self, tmp_path: Path):
        """Does nothing if user cancels format picker."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.open_file_picker") as mock_file_picker:
                                with patch("hanasu.main.show_format_picker") as mock_format:
                                    with patch("hanasu.main.save_file_picker") as mock_save:
                                        mock_config.return_value = MagicMock(
                                            hotkey="ctrl+shift+space",
                                            model="small",
                                            language="en",
                                            audio_device=None,
                                            debug=False,
                                            clear_clipboard=False,
                                            last_output_dir=None,
                                        )
                                        mock_dict.return_value = MagicMock(
                                            terms=[], replacements={}
                                        )
                                        mock_file_picker.return_value = "/path/to/audio.mp3"
                                        mock_format.return_value = None  # User cancelled

                                        app = Hanasu(config_dir=tmp_path)
                                        app._on_transcribe_file()

                                        # Save picker should not be called
                                        mock_save.assert_not_called()

    def test_calls_save_picker_with_suggested_name(self, tmp_path: Path):
        """Save picker uses input filename as suggested name."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.open_file_picker") as mock_file_picker:
                                with patch("hanasu.main.show_format_picker") as mock_format:
                                    with patch("hanasu.main.save_file_picker") as mock_save:
                                        mock_config.return_value = MagicMock(
                                            hotkey="ctrl+shift+space",
                                            model="small",
                                            language="en",
                                            audio_device=None,
                                            debug=False,
                                            clear_clipboard=False,
                                            last_output_dir=None,
                                        )
                                        mock_dict.return_value = MagicMock(
                                            terms=[], replacements={}
                                        )
                                        mock_file_picker.return_value = "/path/to/interview.mp3"
                                        mock_format.return_value = "txt"
                                        mock_save.return_value = None

                                        app = Hanasu(config_dir=tmp_path)
                                        app._on_transcribe_file()

                                        mock_save.assert_called_once()
                                        call_kwargs = mock_save.call_args[1]
                                        assert call_kwargs["suggested_name"] == "interview.txt"

    def test_save_picker_uses_last_output_dir(self, tmp_path: Path):
        """Save picker opens in last used directory."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.open_file_picker") as mock_file_picker:
                                with patch("hanasu.main.show_format_picker") as mock_format:
                                    with patch("hanasu.main.save_file_picker") as mock_save:
                                        mock_config.return_value = MagicMock(
                                            hotkey="ctrl+shift+space",
                                            model="small",
                                            language="en",
                                            audio_device=None,
                                            debug=False,
                                            clear_clipboard=False,
                                            last_output_dir="/Users/test/transcripts",
                                        )
                                        mock_dict.return_value = MagicMock(
                                            terms=[], replacements={}
                                        )
                                        mock_file_picker.return_value = "/path/to/audio.mp3"
                                        mock_format.return_value = "txt"
                                        mock_save.return_value = None

                                        app = Hanasu(config_dir=tmp_path)
                                        app._on_transcribe_file()

                                        call_kwargs = mock_save.call_args[1]
                                        assert (
                                            call_kwargs["initial_dir"] == "/Users/test/transcripts"
                                        )

    def test_updates_last_output_dir_after_save(self, tmp_path: Path):
        """Saves new output directory to config."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.open_file_picker") as mock_file_picker:
                                with patch("hanasu.main.show_format_picker") as mock_format:
                                    with patch("hanasu.main.save_file_picker") as mock_save:
                                        with patch("hanasu.main.save_config") as mock_save_cfg:
                                            with patch("threading.Thread"):
                                                mock_cfg_obj = MagicMock(
                                                    hotkey="ctrl+shift+space",
                                                    model="small",
                                                    language="en",
                                                    audio_device=None,
                                                    debug=False,
                                                    clear_clipboard=False,
                                                    last_output_dir=None,
                                                )
                                                mock_config.return_value = mock_cfg_obj
                                                mock_dict.return_value = MagicMock(
                                                    terms=[], replacements={}
                                                )
                                                mock_file_picker.return_value = "/path/to/audio.mp3"
                                                mock_format.return_value = "txt"
                                                mock_save.return_value = (
                                                    "/Users/test/new_dir/output.txt"
                                                )

                                                app = Hanasu(config_dir=tmp_path)
                                                app._on_transcribe_file()

                                                # Config should be updated
                                                assert (
                                                    mock_cfg_obj.last_output_dir
                                                    == "/Users/test/new_dir"
                                                )
                                                mock_save_cfg.assert_called()

    def test_starts_transcription_in_background_thread(self, tmp_path: Path):
        """Transcription runs in background thread."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("hanasu.main.open_file_picker") as mock_file_picker:
                                with patch("hanasu.main.show_format_picker") as mock_format:
                                    with patch("hanasu.main.save_file_picker") as mock_save:
                                        with patch("hanasu.main.save_config"):
                                            with patch("threading.Thread") as mock_thread_class:
                                                mock_config.return_value = MagicMock(
                                                    hotkey="ctrl+shift+space",
                                                    model="small",
                                                    language="en",
                                                    audio_device=None,
                                                    debug=False,
                                                    clear_clipboard=False,
                                                    last_output_dir=None,
                                                )
                                                mock_dict.return_value = MagicMock(
                                                    terms=[], replacements={}
                                                )
                                                mock_file_picker.return_value = "/path/to/audio.mp3"
                                                mock_format.return_value = "txt"
                                                mock_save.return_value = "/output/file.txt"
                                                mock_thread = MagicMock()
                                                mock_thread_class.return_value = mock_thread

                                                app = Hanasu(config_dir=tmp_path)
                                                app._on_transcribe_file()

                                                # Thread should be created and started
                                                mock_thread_class.assert_called_once()
                                                mock_thread.start.assert_called_once()


class TestRunFileTranscription:
    """Test background file transcription."""

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

    def test_writes_plain_text_output(self, tmp_path: Path):
        """Writes transcription as plain text when use_vtt is False."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("mlx_whisper.transcribe") as mock_transcribe:
                                with patch("hanasu.main.is_video_file", return_value=False):
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
                                    mock_transcribe.return_value = {
                                        "text": "Hello world",
                                        "segments": [],
                                    }

                                    app = Hanasu(config_dir=tmp_path)
                                    output_file = tmp_path / "output.txt"

                                    app._run_file_transcription(
                                        "/path/to/audio.mp3", str(output_file), False
                                    )

                                    assert output_file.exists()
                                    assert output_file.read_text() == "Hello world"

    def test_writes_vtt_output(self, tmp_path: Path):
        """Writes transcription as VTT when use_vtt is True."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("mlx_whisper.transcribe") as mock_transcribe:
                                with patch("hanasu.main.is_video_file", return_value=False):
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
                                    mock_transcribe.return_value = {
                                        "text": "Hello world",
                                        "segments": [
                                            {"start": 0.0, "end": 1.5, "text": " Hello"},
                                            {"start": 1.5, "end": 3.0, "text": " world"},
                                        ],
                                    }

                                    app = Hanasu(config_dir=tmp_path)
                                    output_file = tmp_path / "output.vtt"

                                    app._run_file_transcription(
                                        "/path/to/audio.mp3", str(output_file), True
                                    )

                                    assert output_file.exists()
                                    content = output_file.read_text()
                                    assert content.startswith("WEBVTT")
                                    assert "00:00:00.000 --> 00:00:01.500" in content
                                    assert "Hello" in content

    def test_extracts_audio_from_video_files(self, tmp_path: Path):
        """Extracts audio from video before transcribing."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("mlx_whisper.transcribe") as mock_transcribe:
                                with patch("hanasu.main.is_video_file", return_value=True):
                                    with patch(
                                        "hanasu.main.extract_audio_from_video"
                                    ) as mock_extract:
                                        mock_config.return_value = MagicMock(
                                            hotkey="ctrl+shift+space",
                                            model="small",
                                            language="en",
                                            audio_device=None,
                                            debug=False,
                                            clear_clipboard=False,
                                            last_output_dir=None,
                                        )
                                        mock_dict.return_value = MagicMock(
                                            terms=[], replacements={}
                                        )
                                        temp_audio = tmp_path / "temp.wav"
                                        temp_audio.touch()
                                        mock_extract.return_value = str(temp_audio)
                                        mock_transcribe.return_value = {
                                            "text": "Video text",
                                            "segments": [],
                                        }

                                        app = Hanasu(config_dir=tmp_path)
                                        output_file = tmp_path / "output.txt"

                                        app._run_file_transcription(
                                            "/path/to/video.mp4", str(output_file), False
                                        )

                                        mock_extract.assert_called_once_with("/path/to/video.mp4")

    def test_calls_error_handler_on_failure(self, tmp_path: Path):
        """Calls _show_transcription_error on failure."""
        with patch("hanasu.main.load_config") as mock_config:
            with patch("hanasu.main.load_dictionary") as mock_dict:
                with patch("hanasu.main.Recorder"):
                    with patch("hanasu.main.Transcriber"):
                        with patch("hanasu.main.HotkeyListener"):
                            with patch("mlx_whisper.transcribe") as mock_transcribe:
                                with patch("hanasu.main.is_video_file", return_value=False):
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
                                    mock_transcribe.side_effect = Exception("Transcription failed")

                                    app = Hanasu(config_dir=tmp_path)
                                    app._show_transcription_error = MagicMock()

                                    app._run_file_transcription(
                                        "/path/to/audio.mp3",
                                        str(tmp_path / "output.txt"),
                                        False,
                                    )

                                    app._show_transcription_error.assert_called_once()


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
