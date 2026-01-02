"""Tests for hotkey handling functionality."""

from unittest.mock import MagicMock, patch

import pytest

from hanasu.hotkey import (
    KEYCODE_MAP,
    MODIFIER_FLAGS,
    HotkeyListener,
    HotkeyParseError,
    parse_hotkey,
)


class TestParseHotkey:
    """Test hotkey string parsing."""

    def test_parses_simple_hotkey_with_modifiers(self):
        """Hotkey with modifiers returns correct mask and keycode."""
        result = parse_hotkey("ctrl+shift+space")

        # Should have both ctrl and shift flags
        assert result["modifier_mask"] != 0
        assert result["keycode"] == KEYCODE_MAP["space"]

    def test_parses_single_modifier(self):
        """Single modifier hotkey is parsed correctly."""
        result = parse_hotkey("cmd+d")

        assert result["modifier_mask"] == MODIFIER_FLAGS["cmd"]
        assert result["keycode"] == KEYCODE_MAP["d"]

    def test_parses_function_key_without_modifiers(self):
        """Function keys without modifiers have zero modifier mask."""
        result = parse_hotkey("f19")

        assert result["modifier_mask"] == 0
        assert result["keycode"] == KEYCODE_MAP["f19"]

    def test_handles_alternate_modifier_names(self):
        """Alternate modifier names (command/cmd, option/alt) work."""
        result1 = parse_hotkey("command+a")
        result2 = parse_hotkey("cmd+a")

        assert result1["modifier_mask"] == result2["modifier_mask"]

        result3 = parse_hotkey("option+b")
        result4 = parse_hotkey("alt+b")

        assert result3["modifier_mask"] == result4["modifier_mask"]

    def test_case_insensitive(self):
        """Parsing is case-insensitive."""
        result1 = parse_hotkey("CTRL+SHIFT+SPACE")
        result2 = parse_hotkey("ctrl+shift+space")

        assert result1["modifier_mask"] == result2["modifier_mask"]
        assert result1["keycode"] == result2["keycode"]

    def test_raises_error_for_empty_hotkey(self):
        """Empty hotkey raises HotkeyParseError."""
        with pytest.raises(HotkeyParseError):
            parse_hotkey("")

    def test_raises_error_for_whitespace_only(self):
        """Whitespace-only hotkey raises HotkeyParseError."""
        with pytest.raises(HotkeyParseError):
            parse_hotkey("   ")

    def test_raises_error_for_invalid_key(self):
        """Invalid key name raises HotkeyParseError."""
        with pytest.raises(HotkeyParseError, match="Unknown key"):
            parse_hotkey("ctrl+invalidkey")

    def test_raises_error_for_multiple_keys(self):
        """Multiple non-modifier keys raises HotkeyParseError."""
        with pytest.raises(HotkeyParseError, match="Multiple keys"):
            parse_hotkey("a+b")

    def test_raises_error_for_modifiers_only(self):
        """Modifiers without a key raises HotkeyParseError."""
        with pytest.raises(HotkeyParseError, match="No key specified"):
            parse_hotkey("ctrl+shift")


class TestHotkeyListener:
    """Test hotkey listener functionality."""

    def test_initializes_with_parsed_hotkey(self):
        """HotkeyListener parses hotkey on initialization."""
        on_press = MagicMock()
        on_release = MagicMock()

        listener = HotkeyListener(
            hotkey="cmd+alt+v",
            on_press=on_press,
            on_release=on_release,
        )

        # Should have stored parsed config
        assert listener._hotkey_config["keycode"] == KEYCODE_MAP["v"]
        assert listener._hotkey_config["modifier_mask"] != 0

    def test_raises_error_for_invalid_hotkey(self):
        """Invalid hotkey raises HotkeyParseError during init."""
        with pytest.raises(HotkeyParseError):
            HotkeyListener(
                hotkey="invalid+key",
                on_press=lambda: None,
                on_release=lambda: None,
            )

    def test_start_sets_running_flag(self):
        """start() sets internal running flag."""
        with patch("hanasu.hotkey.Quartz"):
            listener = HotkeyListener(
                hotkey="cmd+v",
                on_press=lambda: None,
                on_release=lambda: None,
            )

            # Patch thread to avoid actually starting
            with patch.object(listener, "_thread"):
                listener._running = False
                listener.start()

                assert listener._running is True

    def test_stop_clears_running_flag(self):
        """stop() clears internal running flag."""
        with patch("hanasu.hotkey.Quartz"):
            listener = HotkeyListener(
                hotkey="cmd+v",
                on_press=lambda: None,
                on_release=lambda: None,
            )
            listener._running = True
            listener._tap = None
            listener._thread = None

            listener.stop()

            assert listener._running is False
