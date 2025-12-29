"""Text injection functionality for macOS.

Uses CGEvent with session-level event tap for reliable paste simulation.
Based on Maccy clipboard manager's proven implementation.
"""

import time
import Quartz
from AppKit import NSPasteboard, NSPasteboardTypeString


# Virtual key code for 'v' on US QWERTY keyboard
V_KEY_CODE = 0x09


def inject_text(text: str, clear_after: bool = False) -> None:
    """Inject text at cursor position using clipboard paste.

    Args:
        text: Text to inject.
        clear_after: If True, clear clipboard after paste.
    """
    if not text:
        return

    pasteboard = NSPasteboard.generalPasteboard()

    # Set text to clipboard
    pasteboard.clearContents()
    pasteboard.setString_forType_(text, NSPasteboardTypeString)

    # Small delay for clipboard to update
    time.sleep(0.05)

    # Wait for user's modifier keys to be released (from hotkey)
    _wait_for_modifiers_released()

    # Simulate Cmd+V
    _simulate_paste()

    # Clear clipboard after paste if requested
    if clear_after:
        pasteboard.clearContents()


def _simulate_paste() -> None:
    """Simulate Cmd+V keystroke using session-level CGEvent.

    Uses CGEventSource with combinedSessionState and posts to
    cgSessionEventTap for reliable, non-interfering paste.
    Sends both key-down and key-up events for full keystroke cycle.
    """
    # Create event source at session level
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)

    if source:
        Quartz.CGEventSourceSetLocalEventsFilterDuringSuppressionState(
            source,
            Quartz.kCGEventFilterMaskPermitLocalMouseEvents | Quartz.kCGEventFilterMaskPermitSystemDefinedEvents,
            Quartz.kCGEventSuppressionStateSuppressionInterval
        )

    # Create key down event with Command flag
    key_down = Quartz.CGEventCreateKeyboardEvent(source, V_KEY_CODE, True)
    if key_down:
        Quartz.CGEventSetFlags(key_down, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGSessionEventTap, key_down)

    # Small delay for event processing
    time.sleep(0.01)

    # Create key up event with Command flag (required for browser apps)
    key_up = Quartz.CGEventCreateKeyboardEvent(source, V_KEY_CODE, False)
    if key_up:
        Quartz.CGEventSetFlags(key_up, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGSessionEventTap, key_up)


def _wait_for_modifiers_released(timeout: float = 1.0) -> None:
    """Wait until all modifier keys are released.

    Args:
        timeout: Maximum time to wait in seconds.
    """
    start = time.time()

    while time.time() - start < timeout:
        flags = Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateCombinedSessionState)

        modifier_mask = (
            Quartz.kCGEventFlagMaskShift |
            Quartz.kCGEventFlagMaskControl |
            Quartz.kCGEventFlagMaskAlternate |
            Quartz.kCGEventFlagMaskCommand
        )

        if not (flags & modifier_mask):
            return

        time.sleep(0.01)
