"""macOS menu bar integration using PyObjC."""

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import objc
import Quartz
from AppKit import (
    NSAlert,
    NSApplication,
    NSMenu,
    NSMenuItem,
    NSModalPanelRunLoopMode,
    NSOpenPanel,
    NSSavePanel,
    NSStatusBar,
    NSTextField,
    NSVariableStatusItemLength,
)
from Foundation import NSURL, NSArray, NSDefaultRunLoopMode, NSObject
from PyObjCTools import AppHelper

from hanasu.hotkey import parse_hotkey

if TYPE_CHECKING:
    from hanasu.updater import UpdateStatus


class MenuBarApp(NSObject):
    """macOS menu bar application."""

    def initWithCallbacks_(self, callbacks: dict):
        """Initialize with callback functions.

        Args:
            callbacks: Dict with 'on_quit', 'on_hotkey_change', and 'on_update' callbacks.
        """
        self = objc.super(MenuBarApp, self).init()
        if self is None:
            return None

        self._callbacks = callbacks
        self._status_item = None
        self._status_menu_item = None
        self._version_menu_item = None
        self._update_menu_item = None
        self._update_status = None
        self._is_recording = False
        self._hotkey_display = "?"

        return self

    def setupStatusBar(self, version: str = ""):
        """Set up the status bar item and menu.

        Args:
            version: Current app version to display.
        """
        status_bar = NSStatusBar.systemStatusBar()
        self._status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)

        # Set initial title (microphone emoji)
        self._updateTitle()

        # Create menu
        menu = NSMenu.alloc().init()

        # Status item (disabled, just for display)
        self._status_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Hotkey: {self._hotkey_display}", None, ""
        )
        self._status_menu_item.setEnabled_(False)
        menu.addItem_(self._status_menu_item)

        # Change Hotkey item
        change_hotkey_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Change Hotkey...", "changeHotkey:", ""
        )
        change_hotkey_item.setTarget_(self)
        menu.addItem_(change_hotkey_item)

        # Transcribe File item
        transcribe_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Transcribe File...", "transcribeFile:", ""
        )
        transcribe_item.setTarget_(self)
        menu.addItem_(transcribe_item)

        # Separator
        menu.addItem_(NSMenuItem.separatorItem())

        # Version display (disabled, just for display)
        version_text = f"Version {version}" if version else "Version unknown"
        self._version_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            version_text, None, ""
        )
        self._version_menu_item.setEnabled_(False)
        menu.addItem_(self._version_menu_item)

        # Update status item (clickable when update available)
        self._update_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Checking for updates...", "triggerUpdate:", ""
        )
        self._update_menu_item.setTarget_(self)
        self._update_menu_item.setEnabled_(False)
        menu.addItem_(self._update_menu_item)

        # Separator
        menu.addItem_(NSMenuItem.separatorItem())

        # Quit item
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "quit:", "q")
        quit_item.setTarget_(self)
        menu.addItem_(quit_item)

        self._status_item.setMenu_(menu)

    def _updateTitle(self):
        """Update the status bar title based on recording state."""
        if self._is_recording:
            # Red circle when recording
            title = "\U0001f534"  # Red circle emoji
        else:
            # Microphone when idle
            title = "\U0001f3a4"  # Microphone emoji

        self._status_item.setTitle_(title)

    def setRecording_(self, recording: bool):
        """Update recording state.

        Args:
            recording: True if currently recording.
        """
        self._is_recording = recording
        # Schedule UI update on main thread
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "updateRecordingState", None, False
        )

    def updateRecordingState(self):
        """Update UI for recording state (must be called on main thread)."""
        self._updateTitle()

    def setHotkey_(self, hotkey: str):
        """Update hotkey display.

        Args:
            hotkey: Hotkey string to display.
        """
        self._hotkey_display = hotkey
        if self._status_menu_item:
            self._status_menu_item.setTitle_(f"Hotkey: {hotkey}")

    def changeHotkey_(self, sender):
        """Handle change hotkey menu item."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Change Hotkey")
        alert.setInformativeText_("Enter the new hotkey (e.g., cmd+alt+v, f19):")
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        # Add text field with proper configuration for editing
        text_field = NSTextField.alloc().initWithFrame_(((0, 0), (200, 24)))
        text_field.setStringValue_(self._hotkey_display)
        text_field.setEditable_(True)
        text_field.setSelectable_(True)
        text_field.setBezeled_(True)
        text_field.setDrawsBackground_(True)
        alert.setAccessoryView_(text_field)

        # Force layout so the window is created before setting first responder
        alert.layout()

        # Use delayed selector with modal run loop mode to set first responder
        # This ensures the text field receives keyboard focus when the modal opens
        modes = NSArray.arrayWithObjects_(NSDefaultRunLoopMode, NSModalPanelRunLoopMode, None)
        text_field.performSelector_withObject_afterDelay_inModes_(
            "selectText:",
            None,
            0.0,
            modes,
        )

        # Run modal
        response = alert.runModal()

        # Check if OK was clicked (first button = 1000)
        if response == 1000:
            new_hotkey = text_field.stringValue().strip()
            if new_hotkey and new_hotkey != self._hotkey_display:
                # Validate by having user press the new hotkey
                if validate_hotkey(new_hotkey):
                    if self._callbacks.get("on_hotkey_change"):
                        self._callbacks["on_hotkey_change"](new_hotkey)

    def setUpdateStatus_(self, status: "UpdateStatus"):
        """Update the update status display (thread-safe).

        Args:
            status: UpdateStatus with check results.
        """
        self._update_status = status
        # Schedule UI update on main thread
        self.performSelectorOnMainThread_withObject_waitUntilDone_("applyUpdateStatus", None, False)

    def applyUpdateStatus(self):
        """Apply update status on main thread."""
        status = self._update_status
        if not self._update_menu_item or not status:
            return

        if not status.checked:
            self._update_menu_item.setTitle_("Unable to check for updates")
            self._update_menu_item.setEnabled_(False)
        elif status.update_available:
            self._update_menu_item.setTitle_(f"⬆ Update available ({status.latest_version})")
            self._update_menu_item.setEnabled_(True)
        else:
            self._update_menu_item.setTitle_("✓ Up to date")
            self._update_menu_item.setEnabled_(False)

    def setUpdateInProgress(self):
        """Show update in progress state (thread-safe)."""
        self._pending_update_title = "⏳ Updating..."
        self._pending_update_enabled = False
        self.performSelectorOnMainThread_withObject_waitUntilDone_("applyUpdateTitle", None, False)

    def setUpdateComplete(self):
        """Show update complete state (thread-safe)."""
        self._pending_update_title = "✓ Updated! Restart to apply"
        self._pending_update_enabled = False
        self.performSelectorOnMainThread_withObject_waitUntilDone_("applyUpdateTitle", None, False)

    def setUpdateFailed(self):
        """Show update failed state (thread-safe)."""
        self._pending_update_title = "✗ Update failed - Click to retry"
        self._pending_update_enabled = True
        self.performSelectorOnMainThread_withObject_waitUntilDone_("applyUpdateTitle", None, False)

    def applyUpdateTitle(self):
        """Apply pending update title on main thread."""
        if self._update_menu_item:
            if hasattr(self, "_pending_update_title"):
                self._update_menu_item.setTitle_(self._pending_update_title)
            if hasattr(self, "_pending_update_enabled"):
                self._update_menu_item.setEnabled_(self._pending_update_enabled)

    def triggerUpdate_(self, sender):
        """Handle update menu item click."""
        if self._callbacks.get("on_update"):
            self._callbacks["on_update"]()

    def transcribeFile_(self, sender):
        """Handle transcribe file menu item."""
        if self._callbacks.get("on_transcribe_file"):
            self._callbacks["on_transcribe_file"]()

    def quit_(self, sender):
        """Handle quit menu item."""
        if self._callbacks.get("on_quit"):
            self._callbacks["on_quit"]()
        NSApplication.sharedApplication().terminate_(None)


def validate_hotkey(hotkey_str: str, timeout: float = 5.0) -> bool:
    """Validate a hotkey by waiting for user to press it.

    Creates a temporary event tap to listen for the specified hotkey.
    Returns True if the user presses the correct combination within timeout.

    Args:
        hotkey_str: Hotkey string like "cmd+alt+v".
        timeout: Seconds to wait for keypress (default 5.0).

    Returns:
        True if correct hotkey pressed within timeout, False otherwise.
    """
    try:
        config = parse_hotkey(hotkey_str)
    except Exception:
        return False

    result = {"validated": False, "done": False}
    tap = None
    run_loop_source = None

    def event_callback(proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            if tap:
                Quartz.CGEventTapEnable(tap, True)
            return event

        if event_type != Quartz.kCGEventKeyDown:
            return event

        keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        flags = Quartz.CGEventGetFlags(event)

        # Mask to just modifier flags
        modifier_only_flags = flags & (
            Quartz.kCGEventFlagMaskCommand
            | Quartz.kCGEventFlagMaskShift
            | Quartz.kCGEventFlagMaskAlternate
            | Quartz.kCGEventFlagMaskControl
        )

        if keycode == config["keycode"] and modifier_only_flags == config["modifier_mask"]:
            result["validated"] = True
            result["done"] = True
        else:
            # Wrong key pressed
            result["done"] = True

        return None  # Suppress the event

    # Create event tap
    mask = 1 << Quartz.kCGEventKeyDown
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionDefault,
        mask,
        event_callback,
        None,
    )

    if tap is None:
        return False

    # Create run loop source
    run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(),
        run_loop_source,
        Quartz.kCFRunLoopCommonModes,
    )

    # Enable tap
    Quartz.CGEventTapEnable(tap, True)

    # Poll for result or timeout
    start = time.time()
    while not result["done"] and (time.time() - start) < timeout:
        Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.05, False)

    # Cleanup
    Quartz.CGEventTapEnable(tap, False)
    Quartz.CFRunLoopRemoveSource(
        Quartz.CFRunLoopGetCurrent(),
        run_loop_source,
        Quartz.kCFRunLoopCommonModes,
    )
    Quartz.CFMachPortInvalidate(tap)

    return result["validated"]


def run_menubar_app(
    hotkey: str,
    on_quit: Callable[[], None] | None = None,
    on_hotkey_change: Callable[[str], None] | None = None,
    on_update: Callable[[], None] | None = None,
    on_transcribe_file: Callable[[], None] | None = None,
    version: str = "",
) -> MenuBarApp:
    """Create and run the menu bar app.

    Args:
        hotkey: Hotkey string to display in menu.
        on_quit: Callback when user quits from menu.
        on_hotkey_change: Callback when user changes hotkey (receives new hotkey string).
        on_update: Callback when user triggers update from menu.
        on_transcribe_file: Callback when user selects transcribe file from menu.
        version: Current app version to display.

    Returns:
        MenuBarApp instance for updating state.
    """
    _ = NSApplication.sharedApplication()  # Initialize app (return value unused)

    # Create delegate
    delegate = MenuBarApp.alloc().initWithCallbacks_(
        {
            "on_quit": on_quit,
            "on_hotkey_change": on_hotkey_change,
            "on_update": on_update,
            "on_transcribe_file": on_transcribe_file,
        }
    )
    delegate.setHotkey_(hotkey)
    delegate.setupStatusBar(version=version)

    return delegate


def start_app_loop():
    """Start the NSApplication event loop (blocking)."""
    AppHelper.runEventLoop()


def stop_app_loop():
    """Stop the NSApplication event loop."""
    AppHelper.stopEventLoop()


def open_file_picker(allowed_extensions: list[str] | None = None) -> str | None:
    """Open file picker dialog and return selected path.

    Args:
        allowed_extensions: List of allowed file extensions (e.g., ["mp3", "wav"]).

    Returns:
        Selected file path as string, or None if cancelled.
    """
    panel = NSOpenPanel.openPanel()
    panel.setCanChooseFiles_(True)
    panel.setCanChooseDirectories_(False)
    panel.setAllowsMultipleSelection_(False)

    if allowed_extensions:
        panel.setAllowedFileTypes_(allowed_extensions)

    if panel.runModal() == 1:  # NSModalResponseOK
        return str(panel.URL().path())
    return None


def show_format_picker() -> str | None:
    """Show format selection dialog.

    Returns:
        'txt' for Plain Text, 'vtt' for VTT subtitles, or None if cancelled.
    """
    alert = NSAlert.alloc().init()
    alert.setMessageText_("Select Output Format")
    alert.setInformativeText_("Choose the format for the transcription:")
    alert.addButtonWithTitle_("Plain Text (.txt)")
    alert.addButtonWithTitle_("VTT Subtitles (.vtt)")
    alert.addButtonWithTitle_("Cancel")

    response = alert.runModal()
    if response == 1000:  # First button
        return "txt"
    elif response == 1001:  # Second button
        return "vtt"
    return None


def save_file_picker(
    suggested_name: str = "transcription",
    initial_dir: str | None = None,
    file_types: list[str] | None = None,
) -> str | None:
    """Open save dialog and return selected path.

    Args:
        suggested_name: Default filename to suggest.
        initial_dir: Initial directory to open dialog in.
        file_types: List of allowed file extensions.

    Returns:
        Selected file path as string, or None if cancelled.
    """
    panel = NSSavePanel.savePanel()
    panel.setNameFieldStringValue_(suggested_name)

    if initial_dir:
        panel.setDirectoryURL_(NSURL.fileURLWithPath_(initial_dir))

    if file_types:
        panel.setAllowedFileTypes_(file_types)

    if panel.runModal() == 1:  # NSModalResponseOK
        return str(panel.URL().path())
    return None
