"""Tests for logging configuration."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest


class TestSetupLogging:
    """Test logging setup functionality."""

    def test_setup_logging_returns_logger(self):
        """setup_logging returns a logger instance."""
        from hanasu.logging_config import setup_logging

        with patch("hanasu.logging_config.Path.mkdir"):
            logger = setup_logging(debug=False, log_to_file=False)

        assert isinstance(logger, logging.Logger)
        assert logger.name == "hanasu"

    def test_setup_logging_sets_debug_level_when_debug_true(self):
        """setup_logging sets DEBUG level when debug=True."""
        from hanasu.logging_config import setup_logging

        with patch("hanasu.logging_config.Path.mkdir"):
            logger = setup_logging(debug=True, log_to_file=False)

        assert logger.level == logging.DEBUG

    def test_setup_logging_sets_info_level_when_debug_false(self):
        """setup_logging sets INFO level when debug=False."""
        from hanasu.logging_config import setup_logging

        with patch("hanasu.logging_config.Path.mkdir"):
            logger = setup_logging(debug=False, log_to_file=False)

        assert logger.level == logging.INFO

    def test_setup_logging_creates_console_handler(self):
        """setup_logging adds a StreamHandler for console output."""
        from hanasu.logging_config import setup_logging

        with patch("hanasu.logging_config.Path.mkdir"):
            logger = setup_logging(debug=False, log_to_file=False)

        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_setup_logging_creates_file_handler_when_log_to_file_true(self, tmp_path: Path):
        """setup_logging adds a FileHandler when log_to_file=True."""
        from hanasu.logging_config import setup_logging

        with patch("hanasu.logging_config.Path.home", return_value=tmp_path):
            logger = setup_logging(debug=False, log_to_file=True)

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) >= 1

    def test_setup_logging_creates_log_directory(self, tmp_path: Path):
        """setup_logging creates ~/Library/Logs/Hanasu directory."""
        from hanasu.logging_config import setup_logging

        with patch("hanasu.logging_config.Path.home", return_value=tmp_path):
            setup_logging(debug=False, log_to_file=True)

        log_dir = tmp_path / "Library" / "Logs" / "Hanasu"
        assert log_dir.exists()

    def test_setup_logging_writes_to_hanasu_log_file(self, tmp_path: Path):
        """setup_logging writes to hanasu.log file."""
        from hanasu.logging_config import setup_logging

        with patch("hanasu.logging_config.Path.home", return_value=tmp_path):
            logger = setup_logging(debug=True, log_to_file=True)
            logger.debug("test message")

        log_file = tmp_path / "Library" / "Logs" / "Hanasu" / "hanasu.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "test message" in content

    def test_setup_logging_no_file_handler_when_log_to_file_false(self):
        """setup_logging does not create FileHandler when log_to_file=False."""
        from hanasu.logging_config import setup_logging

        logger = setup_logging(debug=False, log_to_file=False)

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 0

    def test_console_handler_level_matches_debug_setting(self):
        """Console handler level is DEBUG when debug=True, WARNING otherwise."""
        from hanasu.logging_config import setup_logging

        # Test debug mode
        with patch("hanasu.logging_config.Path.mkdir"):
            logger_debug = setup_logging(debug=True, log_to_file=False)
        stream_handlers = [
            h for h in logger_debug.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert stream_handlers[0].level == logging.DEBUG

        # Clear handlers for next test
        logger_debug.handlers.clear()

        # Test non-debug mode
        with patch("hanasu.logging_config.Path.mkdir"):
            logger_normal = setup_logging(debug=False, log_to_file=False)
        stream_handlers = [
            h for h in logger_normal.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert stream_handlers[0].level == logging.WARNING


class TestLoggingIntegration:
    """Test logging integration with main app."""

    def test_hanasu_configures_logging_at_startup(self, tmp_path: Path):
        """Hanasu.__init__ configures logging from config."""
        from unittest.mock import MagicMock

        with (
            patch("hanasu.main.setup_logging") as mock_setup,
            patch("hanasu.main.load_config") as mock_config,
            patch("hanasu.main.load_dictionary") as mock_dict,
            patch("hanasu.main.Recorder"),
            patch("hanasu.main.Transcriber"),
            patch("hanasu.main.HotkeyListener"),
        ):
            mock_setup.return_value = MagicMock()
            mock_config.return_value = MagicMock(
                hotkey="cmd+v",
                model="small",
                language="en",
                audio_device=None,
                debug=True,
            )
            mock_dict.return_value = MagicMock(terms=[], replacements={})

            from hanasu.main import Hanasu

            # Create Hanasu instance - should configure logging
            Hanasu(config_dir=tmp_path)

            # setup_logging should have been called with debug=True
            mock_setup.assert_called_once_with(debug=True, log_to_file=True)
