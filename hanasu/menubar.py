"""macOS menu bar integration using PyObjC."""

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

from hanasu.config import MODEL_INFO
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

        # Model selection state
        self._current_model = "small"
        self._model_menu_items: dict[str, NSMenuItem] = {}
        self._is_model_cached_fn = None
        self._downloading_models: set[str] = set()
        self._model_submenu = None

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

        # Model submenu
        model_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Model", None, "")
        model_submenu = self._createModelSubmenu()
        model_menu_item.setSubmenu_(model_submenu)
        menu.addItem_(model_menu_item)

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
        # Activate app to ensure dialog gets focus (needed for menu bar apps)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

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

        # Bring dialog to front (menu bar apps can have window ordering issues)
        alert.window().makeKeyAndOrderFront_(None)
        alert.window().setLevel_(3)  # NSModalPanelWindowLevel

        # Run modal
        response = alert.runModal()

        # Check if OK was clicked (first button = 1000)
        if response == 1000:
            new_hotkey = text_field.stringValue().strip()
            if new_hotkey and new_hotkey != self._hotkey_display:
                # Validate hotkey syntax using parse_hotkey
                try:
                    parse_hotkey(new_hotkey)
                    if self._callbacks.get("on_hotkey_change"):
                        self._callbacks["on_hotkey_change"](new_hotkey)
                except Exception as e:
                    # Show error dialog for invalid hotkey
                    error_alert = NSAlert.alloc().init()
                    error_alert.setMessageText_("Invalid Hotkey")
                    error_alert.setInformativeText_(str(e))
                    error_alert.addButtonWithTitle_("OK")
                    error_alert.runModal()

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

    def menuWillOpen_(self, menu):
        """Called when a menu is about to open (NSMenuDelegate).

        Refreshes model cache states when the model submenu is opened.
        """
        if menu == self._model_submenu:
            self.refreshModelStates()

    @objc.python_method
    def _createModelSubmenu(self) -> NSMenu:
        """Create the model selection submenu."""
        submenu = NSMenu.alloc().init()

        # Set delegate for menuWillOpen notification
        submenu.setDelegate_(self)

        # Model order for consistent display
        model_order = ["tiny", "base", "small", "medium", "large"]

        for model in model_order:
            info = MODEL_INFO.get(model, {"label": model})
            title = self._formatModelTitle(model, info)

            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "selectModel:", "")
            item.setTarget_(self)
            item.setRepresentedObject_(model)
            submenu.addItem_(item)
            self._model_menu_items[model] = item

        # Store reference for delegate
        self._model_submenu = submenu

        return submenu

    @objc.python_method
    def _formatModelTitle(self, model: str, info: dict) -> str:
        """Format the title for a model menu item.

        Args:
            model: Model name (e.g., "small").
            info: MODEL_INFO dict entry with 'label' etc.

        Returns:
            Formatted title like "● ✓ small (244MB, balanced)".
        """
        is_current = model == self._current_model
        is_cached = self._is_model_cached_fn(model) if self._is_model_cached_fn else False
        is_downloading = model in self._downloading_models

        if is_downloading:
            return f"  ⏳ {info.get('label', model)} (downloading...)"

        indicator = "● " if is_current else "  "
        cache_icon = "✓ " if is_cached else "↓ "
        return f"{indicator}{cache_icon}{info.get('label', model)}"

    def selectModel_(self, sender):
        """Handle model selection from submenu."""
        model = sender.representedObject()
        if not model:
            return

        # Check if model is cached
        is_cached = self._is_model_cached_fn(model) if self._is_model_cached_fn else False

        if not is_cached:
            # Show confirmation dialog for non-cached model
            info = MODEL_INFO.get(model, {})
            alert = NSAlert.alloc().init()
            alert.setMessageText_(f"Download {model} model?")
            alert.setInformativeText_(
                f"This will download approximately {info.get('size', 'unknown')}.\n"
                "The download will happen in the background."
            )
            alert.addButtonWithTitle_("Download")
            alert.addButtonWithTitle_("Cancel")

            response = alert.runModal()
            if response != 1000:  # Cancel clicked
                return

        if self._callbacks.get("on_model_change"):
            self._callbacks["on_model_change"](model)

    def setCurrentModel_(self, model: str):
        """Update current model indicator (thread-safe).

        Args:
            model: The new current model name.
        """
        self._pending_current_model = model
        self.performSelectorOnMainThread_withObject_waitUntilDone_("applyCurrentModel", None, False)

    def applyCurrentModel(self):
        """Apply current model indicator on main thread."""
        new_model = getattr(self, "_pending_current_model", None)
        if not new_model:
            return

        self._current_model = new_model
        self.refreshModelStates()

    @objc.python_method
    def setModelDownloading_(self, model: str, downloading: bool):
        """Update downloading state for a model (thread-safe).

        Args:
            model: Model name.
            downloading: True if download in progress, False when complete.
        """
        self._pending_download_state = (model, downloading)
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "applyDownloadState", None, False
        )

    def applyDownloadState(self):
        """Apply download state on main thread."""
        state = getattr(self, "_pending_download_state", None)
        if not state:
            return
        model, downloading = state

        if downloading:
            self._downloading_models.add(model)
        else:
            self._downloading_models.discard(model)

        # Update the specific menu item
        if model in self._model_menu_items:
            item = self._model_menu_items[model]
            info = MODEL_INFO.get(model, {"label": model})
            title = self._formatModelTitle(model, info)
            item.setTitle_(title)
            item.setEnabled_(not downloading)

    @objc.python_method
    def refreshModelStates(self):
        """Refresh all model menu item titles based on current state."""
        for model, item in self._model_menu_items.items():
            info = MODEL_INFO.get(model, {"label": model})
            title = self._formatModelTitle(model, info)
            item.setTitle_(title)


def run_menubar_app(
    hotkey: str,
    on_quit: Callable[[], None] | None = None,
    on_hotkey_change: Callable[[str], None] | None = None,
    on_update: Callable[[], None] | None = None,
    on_transcribe_file: Callable[[], None] | None = None,
    on_model_change: Callable[[str], None] | None = None,
    version: str = "",
    current_model: str = "small",
    is_model_cached: Callable[[str], bool] | None = None,
) -> MenuBarApp:
    """Create and run the menu bar app.

    Args:
        hotkey: Hotkey string to display in menu.
        on_quit: Callback when user quits from menu.
        on_hotkey_change: Callback when user changes hotkey (receives new hotkey string).
        on_update: Callback when user triggers update from menu.
        on_transcribe_file: Callback when user selects transcribe file from menu.
        on_model_change: Callback when user selects a different model.
        version: Current app version to display.
        current_model: Currently selected model name.
        is_model_cached: Function to check if a model is downloaded.

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
            "on_model_change": on_model_change,
        }
    )
    delegate.setHotkey_(hotkey)
    delegate._current_model = current_model
    delegate._is_model_cached_fn = is_model_cached
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
