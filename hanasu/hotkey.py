"""Hotkey handling using macOS Quartz event taps.

Uses CGEventTap to intercept and suppress hotkey events so they don't
pass through to other applications.
"""

import threading
from collections.abc import Callable

import Quartz


class HotkeyParseError(Exception):
    """Raised when hotkey string cannot be parsed."""

    pass


# Map key names to macOS virtual key codes
# Reference: https://stackoverflow.com/questions/3202629/where-can-i-find-a-list-of-mac-virtual-key-codes
KEYCODE_MAP = {
    # Letters
    "a": 0,
    "b": 11,
    "c": 8,
    "d": 2,
    "e": 14,
    "f": 3,
    "g": 5,
    "h": 4,
    "i": 34,
    "j": 38,
    "k": 40,
    "l": 37,
    "m": 46,
    "n": 45,
    "o": 31,
    "p": 35,
    "q": 12,
    "r": 15,
    "s": 1,
    "t": 17,
    "u": 32,
    "v": 9,
    "w": 13,
    "x": 7,
    "y": 16,
    "z": 6,
    # Numbers
    "0": 29,
    "1": 18,
    "2": 19,
    "3": 20,
    "4": 21,
    "5": 23,
    "6": 22,
    "7": 26,
    "8": 28,
    "9": 25,
    # Special keys
    "space": 49,
    "enter": 36,
    "return": 36,
    "tab": 48,
    "escape": 53,
    "esc": 53,
    "backspace": 51,
    "delete": 51,
    "forwarddelete": 117,
    "up": 126,
    "down": 125,
    "left": 123,
    "right": 124,
    "home": 115,
    "end": 119,
    "pageup": 116,
    "pagedown": 121,
    # Function keys
    "f1": 122,
    "f2": 120,
    "f3": 99,
    "f4": 118,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f8": 100,
    "f9": 101,
    "f10": 109,
    "f11": 103,
    "f12": 111,
    "f13": 105,
    "f14": 107,
    "f15": 113,
    "f16": 106,
    "f17": 64,
    "f18": 79,
    "f19": 80,
    "f20": 90,
}

# Modifier key names to Quartz flags
MODIFIER_FLAGS = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "command": Quartz.kCGEventFlagMaskCommand,
    "meta": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "option": Quartz.kCGEventFlagMaskAlternate,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "control": Quartz.kCGEventFlagMaskControl,
}


def parse_hotkey(hotkey_str: str) -> dict:
    """Parse hotkey string into components.

    Args:
        hotkey_str: Hotkey string like "ctrl+shift+space".

    Returns:
        Dict with 'modifiers' (combined flag mask) and 'keycode'.

    Raises:
        HotkeyParseError: If hotkey string is invalid.
    """
    if not hotkey_str or not hotkey_str.strip():
        raise HotkeyParseError("Hotkey string cannot be empty")

    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    modifier_mask = 0
    keycode = None

    for part in parts:
        if part in MODIFIER_FLAGS:
            modifier_mask |= MODIFIER_FLAGS[part]
        elif part in KEYCODE_MAP:
            if keycode is not None:
                raise HotkeyParseError("Multiple keys specified")
            keycode = KEYCODE_MAP[part]
        else:
            raise HotkeyParseError(f"Unknown key: {part}")

    if keycode is None:
        raise HotkeyParseError("No key specified in hotkey")

    return {
        "modifier_mask": modifier_mask,
        "keycode": keycode,
    }


class HotkeyListener:
    """Listens for global hotkey press/release events using Quartz."""

    def __init__(
        self,
        hotkey: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ):
        """Initialize hotkey listener.

        Args:
            hotkey: Hotkey string like "ctrl+shift+space".
            on_press: Callback when hotkey is pressed.
            on_release: Callback when hotkey is released.
        """
        self._hotkey_config = parse_hotkey(hotkey)
        self._on_press = on_press
        self._on_release = on_release
        self._hotkey_active = False
        self._tap = None
        self._run_loop_source = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """Start listening for hotkey."""
        self._running = True
        self._thread = threading.Thread(target=self._run_event_tap, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop listening for hotkey."""
        self._running = False
        if self._tap:
            Quartz.CGEventTapEnable(self._tap, False)
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run_event_tap(self) -> None:
        """Run the event tap in a background thread."""
        # Create event tap
        mask = (1 << Quartz.kCGEventKeyDown) | (1 << Quartz.kCGEventKeyUp)
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask,
            self._event_callback,
            None,
        )

        if self._tap is None:
            print("Error: Could not create event tap. Check Accessibility permissions.")
            return

        # Create run loop source
        self._run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            self._run_loop_source,
            Quartz.kCFRunLoopCommonModes,
        )

        # Enable the tap
        Quartz.CGEventTapEnable(self._tap, True)

        # Run the loop
        while self._running:
            Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.1, False)

    def _event_callback(self, proxy, event_type, event, refcon):
        """Handle keyboard events from the event tap."""
        # Check if tap was disabled (e.g., due to timeout)
        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            Quartz.CGEventTapEnable(self._tap, True)
            return event

        # Get key code and flags
        keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        flags = Quartz.CGEventGetFlags(event)

        # Check if this is our hotkey
        target_keycode = self._hotkey_config["keycode"]
        target_modifiers = self._hotkey_config["modifier_mask"]

        # Mask out non-modifier flags (like caps lock state)
        modifier_only_flags = flags & (
            Quartz.kCGEventFlagMaskCommand
            | Quartz.kCGEventFlagMaskShift
            | Quartz.kCGEventFlagMaskAlternate
            | Quartz.kCGEventFlagMaskControl
        )

        if keycode == target_keycode and modifier_only_flags == target_modifiers:
            # This is our hotkey
            if event_type == Quartz.kCGEventKeyDown:
                if not self._hotkey_active:
                    self._hotkey_active = True
                    self._on_press()
                # Suppress the event by returning None
                return None
            elif event_type == Quartz.kCGEventKeyUp:
                if self._hotkey_active:
                    self._hotkey_active = False
                    self._on_release()
                # Suppress the event
                return None

        # Not our hotkey - pass through
        return event
