"""macOS menu bar integration using PyObjC."""

import threading
from typing import Callable, Optional

import objc
from AppKit import (
    NSApplication,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSImage,
    NSFont,
    NSAttributedString,
    NSFontAttributeName,
)
from Foundation import NSObject
from PyObjCTools import AppHelper


class MenuBarApp(NSObject):
    """macOS menu bar application."""

    def initWithCallbacks_(self, callbacks: dict):
        """Initialize with callback functions.

        Args:
            callbacks: Dict with 'on_quit' callback.
        """
        self = objc.super(MenuBarApp, self).init()
        if self is None:
            return None

        self._callbacks = callbacks
        self._status_item = None
        self._status_menu_item = None
        self._is_recording = False
        self._hotkey_display = "?"

        return self

    def setupStatusBar(self):
        """Set up the status bar item and menu."""
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

        # Separator
        menu.addItem_(NSMenuItem.separatorItem())

        # Quit item
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quit:", "q"
        )
        quit_item.setTarget_(self)
        menu.addItem_(quit_item)

        self._status_item.setMenu_(menu)

    def _updateTitle(self):
        """Update the status bar title based on recording state."""
        if self._is_recording:
            # Red circle when recording
            title = "\U0001F534"  # Red circle emoji
        else:
            # Microphone when idle
            title = "\U0001F3A4"  # Microphone emoji

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

    def quit_(self, sender):
        """Handle quit menu item."""
        if self._callbacks.get("on_quit"):
            self._callbacks["on_quit"]()
        NSApplication.sharedApplication().terminate_(None)


def run_menubar_app(
    hotkey: str,
    on_quit: Optional[Callable[[], None]] = None,
) -> MenuBarApp:
    """Create and run the menu bar app.

    Args:
        hotkey: Hotkey string to display in menu.
        on_quit: Callback when user quits from menu.

    Returns:
        MenuBarApp instance for updating state.
    """
    app = NSApplication.sharedApplication()

    # Create delegate
    delegate = MenuBarApp.alloc().initWithCallbacks_({
        "on_quit": on_quit,
    })
    delegate.setHotkey_(hotkey)
    delegate.setupStatusBar()

    return delegate


def start_app_loop():
    """Start the NSApplication event loop (blocking)."""
    AppHelper.runEventLoop()


def stop_app_loop():
    """Stop the NSApplication event loop."""
    AppHelper.stopEventLoop()
