"""Tests for text injection functionality."""

from unittest.mock import patch, MagicMock, call
import pytest

from hanasu.injector import (
    inject_text,
    _simulate_paste,
    _wait_for_modifiers_released,
)


class TestInjectText:
    """Test main text injection function."""

    def test_empty_string_does_nothing(self):
        """Empty string should not access clipboard or simulate paste."""
        with patch("hanasu.injector.NSPasteboard") as mock_pb:
            with patch("hanasu.injector._simulate_paste") as mock_paste:
                inject_text("")

                mock_pb.generalPasteboard.assert_not_called()
                mock_paste.assert_not_called()

    def test_sets_clipboard_and_pastes(self):
        """Non-empty text is copied to clipboard and pasted."""
        with patch("hanasu.injector.NSPasteboard") as mock_pb_class:
            with patch("hanasu.injector._wait_for_modifiers_released"):
                with patch("hanasu.injector._simulate_paste") as mock_paste:
                    with patch("hanasu.injector.time.sleep"):
                        mock_pasteboard = MagicMock()
                        mock_pb_class.generalPasteboard.return_value = mock_pasteboard

                        inject_text("hello world")

                        # Clipboard should be cleared and text set
                        mock_pasteboard.clearContents.assert_called_once()
                        mock_pasteboard.setString_forType_.assert_called_once()

                        # Paste should be simulated
                        mock_paste.assert_called_once()

    def test_waits_for_modifiers_before_paste(self):
        """Waits for modifier keys to be released before pasting."""
        with patch("hanasu.injector.NSPasteboard") as mock_pb_class:
            with patch("hanasu.injector._wait_for_modifiers_released") as mock_wait:
                with patch("hanasu.injector._simulate_paste"):
                    with patch("hanasu.injector.time.sleep"):
                        mock_pasteboard = MagicMock()
                        mock_pb_class.generalPasteboard.return_value = mock_pasteboard

                        inject_text("test")

                        mock_wait.assert_called_once()


class TestSimulatePaste:
    """Test Cmd+V keystroke simulation."""

    def test_creates_event_source(self):
        """Creates CGEvent source with session state."""
        with patch("hanasu.injector.Quartz") as mock_quartz:
            with patch("hanasu.injector.time.sleep"):
                mock_quartz.CGEventSourceCreate.return_value = MagicMock()
                mock_quartz.CGEventCreateKeyboardEvent.return_value = MagicMock()

                _simulate_paste()

                mock_quartz.CGEventSourceCreate.assert_called_once_with(
                    mock_quartz.kCGEventSourceStateCombinedSessionState
                )

    def test_posts_key_down_event(self):
        """Posts key-down event with Command flag."""
        with patch("hanasu.injector.Quartz") as mock_quartz:
            with patch("hanasu.injector.time.sleep"):
                mock_source = MagicMock()
                mock_key_down = MagicMock()
                mock_key_up = MagicMock()

                mock_quartz.CGEventSourceCreate.return_value = mock_source
                mock_quartz.CGEventCreateKeyboardEvent.side_effect = [mock_key_down, mock_key_up]

                _simulate_paste()

                # Key down should be created with True (key pressed)
                calls = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
                assert calls[0] == call(mock_source, 0x09, True)

                # Command flag should be set on key down
                mock_quartz.CGEventSetFlags.assert_any_call(
                    mock_key_down, mock_quartz.kCGEventFlagMaskCommand
                )

                # Key down should be posted
                mock_quartz.CGEventPost.assert_any_call(
                    mock_quartz.kCGSessionEventTap, mock_key_down
                )

    def test_posts_key_up_event(self):
        """Posts key-up event with Command flag (required for browser apps)."""
        with patch("hanasu.injector.Quartz") as mock_quartz:
            with patch("hanasu.injector.time.sleep"):
                mock_source = MagicMock()
                mock_key_down = MagicMock()
                mock_key_up = MagicMock()

                mock_quartz.CGEventSourceCreate.return_value = mock_source
                mock_quartz.CGEventCreateKeyboardEvent.side_effect = [mock_key_down, mock_key_up]

                _simulate_paste()

                # Key up should be created with False (key released)
                calls = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
                assert calls[1] == call(mock_source, 0x09, False)

                # Command flag should be set on key up
                mock_quartz.CGEventSetFlags.assert_any_call(
                    mock_key_up, mock_quartz.kCGEventFlagMaskCommand
                )

                # Key up should be posted
                mock_quartz.CGEventPost.assert_any_call(
                    mock_quartz.kCGSessionEventTap, mock_key_up
                )

    def test_delay_between_key_down_and_up(self):
        """Small delay between key-down and key-up for event processing."""
        with patch("hanasu.injector.Quartz") as mock_quartz:
            with patch("hanasu.injector.time.sleep") as mock_sleep:
                mock_quartz.CGEventSourceCreate.return_value = MagicMock()
                mock_quartz.CGEventCreateKeyboardEvent.return_value = MagicMock()

                _simulate_paste()

                # Should sleep between key down and key up
                mock_sleep.assert_called_with(0.01)


class TestWaitForModifiersReleased:
    """Test modifier key release detection."""

    def test_returns_immediately_when_no_modifiers(self):
        """Returns immediately if no modifier keys are held."""
        with patch("hanasu.injector.Quartz") as mock_quartz:
            with patch("hanasu.injector.time.time") as mock_time_time:
                with patch("hanasu.injector.time.sleep") as mock_sleep:
                    # Set up all modifier mask constants as integers
                    mock_quartz.kCGEventFlagMaskShift = 0x20000
                    mock_quartz.kCGEventFlagMaskControl = 0x40000
                    mock_quartz.kCGEventFlagMaskAlternate = 0x80000
                    mock_quartz.kCGEventFlagMaskCommand = 0x100000
                    mock_quartz.kCGEventSourceStateCombinedSessionState = 0

                    # No modifiers pressed (flags = 0)
                    mock_quartz.CGEventSourceFlagsState.return_value = 0
                    mock_time_time.return_value = 0

                    _wait_for_modifiers_released(timeout=1.0)

                    # Should not sleep (returned immediately)
                    mock_sleep.assert_not_called()

    def test_waits_until_modifiers_released(self):
        """Waits in loop until modifier keys are released."""
        with patch("hanasu.injector.Quartz") as mock_quartz:
            with patch("hanasu.injector.time.time") as mock_time_time:
                with patch("hanasu.injector.time.sleep") as mock_sleep:
                    # Set up all modifier mask constants as integers
                    mock_quartz.kCGEventFlagMaskShift = 0x20000
                    mock_quartz.kCGEventFlagMaskControl = 0x40000
                    mock_quartz.kCGEventFlagMaskAlternate = 0x80000
                    mock_quartz.kCGEventFlagMaskCommand = 0x100000
                    mock_quartz.kCGEventSourceStateCombinedSessionState = 0

                    # First call: Command held, second call: released
                    mock_quartz.CGEventSourceFlagsState.side_effect = [
                        0x100000,  # Command pressed
                        0,  # Released
                    ]
                    mock_time_time.side_effect = [0, 0.1, 0.2]

                    _wait_for_modifiers_released(timeout=1.0)

                    # Should have slept while waiting
                    mock_sleep.assert_called()

    def test_times_out_after_specified_duration(self):
        """Stops waiting after timeout even if modifiers still held."""
        with patch("hanasu.injector.Quartz") as mock_quartz:
            with patch("hanasu.injector.time.time") as mock_time_time:
                with patch("hanasu.injector.time.sleep"):
                    # Set up all modifier mask constants as integers
                    mock_quartz.kCGEventFlagMaskShift = 0x20000
                    mock_quartz.kCGEventFlagMaskControl = 0x40000
                    mock_quartz.kCGEventFlagMaskAlternate = 0x80000
                    mock_quartz.kCGEventFlagMaskCommand = 0x100000
                    mock_quartz.kCGEventSourceStateCombinedSessionState = 0

                    # Always return Command pressed
                    mock_quartz.CGEventSourceFlagsState.return_value = 0x100000

                    # Simulate time passing beyond timeout
                    mock_time_time.side_effect = [0, 1.1]  # Exceeds 1.0 timeout

                    _wait_for_modifiers_released(timeout=1.0)

                    # Should have exited due to timeout (function returns, doesn't hang)
                    assert True  # If we get here, timeout worked
