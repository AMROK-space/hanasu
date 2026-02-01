"""Tests for menu bar integration with update checking."""

from unittest.mock import MagicMock, patch

from hanasu.config import VALID_MODELS
from hanasu.updater import UpdateStatus


class TestMenuBarUpdateIntegration:
    """Test menu bar update status integration."""

    def test_run_menubar_app_accepts_on_update_callback(self):
        """run_menubar_app accepts on_update callback parameter."""
        from hanasu.menubar import run_menubar_app

        # Mock NSApplication and NSStatusBar to avoid actual UI
        with patch("hanasu.menubar.NSApplication") as mock_app:
            with patch("hanasu.menubar.NSStatusBar") as mock_status_bar:
                mock_app.sharedApplication.return_value = MagicMock()
                mock_status_bar.systemStatusBar.return_value.statusItemWithLength_.return_value = (
                    MagicMock()
                )

                update_callback = MagicMock()

                delegate = run_menubar_app(
                    hotkey="cmd+v",
                    on_update=update_callback,
                )

                assert delegate is not None

    def test_menubar_stores_update_callback(self):
        """MenuBarApp stores update callback for later invocation."""
        from hanasu.menubar import run_menubar_app

        with patch("hanasu.menubar.NSApplication") as mock_app:
            with patch("hanasu.menubar.NSStatusBar") as mock_status_bar:
                mock_app.sharedApplication.return_value = MagicMock()
                mock_status_bar.systemStatusBar.return_value.statusItemWithLength_.return_value = (
                    MagicMock()
                )

                update_callback = MagicMock()

                delegate = run_menubar_app(
                    hotkey="cmd+v",
                    on_update=update_callback,
                )

                assert delegate._callbacks.get("on_update") == update_callback

    def test_set_update_status_stores_status(self):
        """setUpdateStatus_ stores the update status."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()

            status = UpdateStatus(
                checked=True,
                update_available=True,
                latest_version="0.2.0",
            )

            delegate.setUpdateStatus_(status)

            assert delegate._update_status == status

    def test_set_update_status_updates_menu_item_when_update_available(self):
        """setUpdateStatus_ updates menu item text when update available."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()
            delegate._update_menu_item = MagicMock()

            status = UpdateStatus(
                checked=True,
                update_available=True,
                latest_version="0.2.0",
            )

            delegate.setUpdateStatus_(status)
            # Simulate main thread execution (in tests, performSelectorOnMainThread doesn't run)
            delegate.applyUpdateStatus()

            # Should update menu item title to show update available
            delegate._update_menu_item.setTitle_.assert_called()
            call_arg = delegate._update_menu_item.setTitle_.call_args[0][0]
            assert "0.2.0" in call_arg

    def test_set_update_status_shows_up_to_date_when_current(self):
        """setUpdateStatus_ shows up-to-date message when no update."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()
            delegate._update_menu_item = MagicMock()

            status = UpdateStatus(
                checked=True,
                update_available=False,
                latest_version="0.1.0",
            )

            delegate.setUpdateStatus_(status)
            # Simulate main thread execution (in tests, performSelectorOnMainThread doesn't run)
            delegate.applyUpdateStatus()

            call_arg = delegate._update_menu_item.setTitle_.call_args[0][0]
            assert "up to date" in call_arg.lower() or "✓" in call_arg


class TestHotkeyValidation:
    """Test hotkey validation using parse_hotkey for syntax checking."""

    def test_change_hotkey_uses_parse_hotkey_for_validation(self):
        """changeHotkey_ uses parse_hotkey to validate hotkey syntax."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                with patch("hanasu.menubar.NSTextField") as mock_textfield_class:
                    with patch("hanasu.menubar.parse_hotkey") as mock_parse:
                        mock_alert = MagicMock()
                        mock_alert_class.alloc.return_value.init.return_value = mock_alert
                        mock_alert.runModal.return_value = 1000  # OK clicked

                        mock_textfield = MagicMock()
                        mock_textfield.stringValue.return_value = "cmd+alt+v"
                        mock_textfield_class.alloc.return_value.initWithFrame_.return_value = (
                            mock_textfield
                        )

                        mock_parse.return_value = {"keycode": 9, "modifier_mask": 0x100000}

                        callback = MagicMock()
                        delegate = MenuBarApp.alloc().initWithCallbacks_(
                            {"on_hotkey_change": callback}
                        )
                        delegate._status_item = MagicMock()
                        delegate._hotkey_display = "cmd+v"

                        delegate.changeHotkey_(None)

                        # Should have called parse_hotkey with the new hotkey
                        mock_parse.assert_called_once_with("cmd+alt+v")
                        # Callback should be called with new hotkey
                        callback.assert_called_once_with("cmd+alt+v")

    def test_change_hotkey_shows_error_on_invalid_hotkey_syntax(self):
        """changeHotkey_ shows error dialog when hotkey syntax is invalid."""
        from hanasu.hotkey import HotkeyParseError
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                with patch("hanasu.menubar.NSTextField") as mock_textfield_class:
                    with patch("hanasu.menubar.parse_hotkey") as mock_parse:
                        # First alert for input dialog
                        mock_input_alert = MagicMock()
                        mock_input_alert.runModal.return_value = 1000  # OK clicked

                        # Second alert for error dialog
                        mock_error_alert = MagicMock()
                        mock_error_alert.runModal.return_value = 1000

                        mock_alert_class.alloc.return_value.init.side_effect = [
                            mock_input_alert,
                            mock_error_alert,
                        ]

                        mock_textfield = MagicMock()
                        mock_textfield.stringValue.return_value = "invalid+hotkey+xyz"
                        mock_textfield_class.alloc.return_value.initWithFrame_.return_value = (
                            mock_textfield
                        )

                        # parse_hotkey raises error for invalid hotkey
                        mock_parse.side_effect = HotkeyParseError("Unknown key: xyz")

                        callback = MagicMock()
                        delegate = MenuBarApp.alloc().initWithCallbacks_(
                            {"on_hotkey_change": callback}
                        )
                        delegate._status_item = MagicMock()
                        delegate._hotkey_display = "cmd+v"

                        delegate.changeHotkey_(None)

                        # Callback should NOT be called for invalid hotkey
                        callback.assert_not_called()

    def test_change_hotkey_calls_callback_for_valid_hotkey(self):
        """changeHotkey_ calls on_hotkey_change callback for valid hotkey."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                with patch("hanasu.menubar.NSTextField") as mock_textfield_class:
                    with patch("hanasu.menubar.parse_hotkey") as mock_parse:
                        mock_alert = MagicMock()
                        mock_alert_class.alloc.return_value.init.return_value = mock_alert
                        mock_alert.runModal.return_value = 1000  # OK clicked

                        mock_textfield = MagicMock()
                        mock_textfield.stringValue.return_value = "cmd+alt+v"
                        mock_textfield_class.alloc.return_value.initWithFrame_.return_value = (
                            mock_textfield
                        )

                        mock_parse.return_value = {"keycode": 9, "modifier_mask": 0x100000}

                        callback = MagicMock()
                        delegate = MenuBarApp.alloc().initWithCallbacks_(
                            {"on_hotkey_change": callback}
                        )
                        delegate._status_item = MagicMock()
                        delegate._hotkey_display = "cmd+v"

                        delegate.changeHotkey_(None)

                        # Callback should be called with new hotkey
                        callback.assert_called_once_with("cmd+alt+v")

    def test_change_hotkey_does_not_call_callback_on_parse_error(self):
        """changeHotkey_ does not call callback if parse_hotkey fails."""
        from hanasu.hotkey import HotkeyParseError
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                with patch("hanasu.menubar.NSTextField") as mock_textfield_class:
                    with patch("hanasu.menubar.parse_hotkey") as mock_parse:
                        mock_alert = MagicMock()
                        mock_alert_class.alloc.return_value.init.return_value = mock_alert
                        mock_alert.runModal.return_value = 1000  # OK clicked

                        mock_textfield = MagicMock()
                        mock_textfield.stringValue.return_value = "invalid"
                        mock_textfield_class.alloc.return_value.initWithFrame_.return_value = (
                            mock_textfield
                        )

                        mock_parse.side_effect = HotkeyParseError("No key specified")

                        callback = MagicMock()
                        delegate = MenuBarApp.alloc().initWithCallbacks_(
                            {"on_hotkey_change": callback}
                        )
                        delegate._status_item = MagicMock()
                        delegate._hotkey_display = "cmd+v"

                        delegate.changeHotkey_(None)

                        # Callback should NOT be called
                        callback.assert_not_called()


class TestModelSubmenu:
    """Test model selection submenu functionality."""

    def test_run_menubar_app_accepts_model_change_callback(self):
        """run_menubar_app accepts on_model_change callback parameter."""
        from hanasu.menubar import run_menubar_app

        with patch("hanasu.menubar.NSApplication") as mock_app:
            with patch("hanasu.menubar.NSStatusBar") as mock_status_bar:
                mock_app.sharedApplication.return_value = MagicMock()
                mock_status_bar.systemStatusBar.return_value.statusItemWithLength_.return_value = (
                    MagicMock()
                )

                model_callback = MagicMock()

                delegate = run_menubar_app(
                    hotkey="cmd+v",
                    on_model_change=model_callback,
                    current_model="small",
                    is_model_cached=lambda m: True,
                )

                assert delegate is not None
                assert delegate._callbacks.get("on_model_change") == model_callback

    def test_menubar_stores_current_model(self):
        """MenuBarApp stores current model for indicator display."""
        from hanasu.menubar import run_menubar_app

        with patch("hanasu.menubar.NSApplication") as mock_app:
            with patch("hanasu.menubar.NSStatusBar") as mock_status_bar:
                mock_app.sharedApplication.return_value = MagicMock()
                mock_status_bar.systemStatusBar.return_value.statusItemWithLength_.return_value = (
                    MagicMock()
                )

                delegate = run_menubar_app(
                    hotkey="cmd+v",
                    current_model="medium",
                    is_model_cached=lambda m: True,
                )

                assert delegate._current_model == "medium"

    def test_menubar_stores_cache_checker_function(self):
        """MenuBarApp stores is_model_cached function for checking download state."""
        from hanasu.menubar import run_menubar_app

        with patch("hanasu.menubar.NSApplication") as mock_app:
            with patch("hanasu.menubar.NSStatusBar") as mock_status_bar:
                mock_app.sharedApplication.return_value = MagicMock()
                mock_status_bar.systemStatusBar.return_value.statusItemWithLength_.return_value = (
                    MagicMock()
                )

                def cache_fn(m):
                    return m == "small"

                delegate = run_menubar_app(
                    hotkey="cmd+v",
                    is_model_cached=cache_fn,
                )

                assert delegate._is_model_cached_fn == cache_fn

    def test_model_submenu_contains_all_valid_models(self):
        """Model submenu should have an item for each valid model."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()
            delegate._is_model_cached_fn = lambda m: True

            delegate.setupStatusBar(version="0.1.0")

            # Should have model_menu_items for all valid models
            assert set(delegate._model_menu_items.keys()) == VALID_MODELS

    def test_select_model_triggers_callback_with_model_name(self):
        """Selecting a model triggers on_model_change callback with model name."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert"):  # Prevent confirmation dialog
                callback = MagicMock()
                delegate = MenuBarApp.alloc().initWithCallbacks_({"on_model_change": callback})
                delegate._status_item = MagicMock()
                delegate._is_model_cached_fn = lambda m: True  # All cached
                delegate._current_model = "small"

                delegate.setupStatusBar(version="0.1.0")

                # Simulate selecting the "medium" model
                mock_sender = MagicMock()
                mock_sender.representedObject.return_value = "medium"
                delegate.selectModel_(mock_sender)

                callback.assert_called_once_with("medium")


class TestDownloadConfirmation:
    """Test download confirmation dialog for non-cached models."""

    def test_cached_model_triggers_callback_immediately(self):
        """Selecting a cached model triggers callback without confirmation."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                callback = MagicMock()
                delegate = MenuBarApp.alloc().initWithCallbacks_({"on_model_change": callback})
                delegate._status_item = MagicMock()
                delegate._is_model_cached_fn = lambda m: True  # All cached
                delegate._current_model = "small"

                delegate.setupStatusBar(version="0.1.0")

                mock_sender = MagicMock()
                mock_sender.representedObject.return_value = "medium"
                delegate.selectModel_(mock_sender)

                # Should NOT show alert for cached model
                mock_alert_class.alloc.assert_not_called()
                # Should call callback immediately
                callback.assert_called_once_with("medium")

    def test_uncached_model_shows_confirmation_dialog(self):
        """Selecting a non-cached model shows confirmation dialog."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                mock_alert = MagicMock()
                mock_alert_class.alloc.return_value.init.return_value = mock_alert
                mock_alert.runModal.return_value = 1000  # OK clicked

                callback = MagicMock()
                delegate = MenuBarApp.alloc().initWithCallbacks_({"on_model_change": callback})
                delegate._status_item = MagicMock()
                delegate._is_model_cached_fn = lambda m: m == "small"  # Only small cached
                delegate._current_model = "small"

                delegate.setupStatusBar(version="0.1.0")

                mock_sender = MagicMock()
                mock_sender.representedObject.return_value = "large"
                delegate.selectModel_(mock_sender)

                # Should show alert for non-cached model
                mock_alert_class.alloc.assert_called_once()
                mock_alert.runModal.assert_called_once()

    def test_confirming_download_triggers_callback(self):
        """Clicking OK in confirmation dialog triggers callback."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                mock_alert = MagicMock()
                mock_alert_class.alloc.return_value.init.return_value = mock_alert
                mock_alert.runModal.return_value = 1000  # OK clicked

                callback = MagicMock()
                delegate = MenuBarApp.alloc().initWithCallbacks_({"on_model_change": callback})
                delegate._status_item = MagicMock()
                delegate._is_model_cached_fn = lambda m: False  # Nothing cached
                delegate._current_model = "small"

                delegate.setupStatusBar(version="0.1.0")

                mock_sender = MagicMock()
                mock_sender.representedObject.return_value = "large"
                delegate.selectModel_(mock_sender)

                # Should call callback after OK
                callback.assert_called_once_with("large")

    def test_canceling_download_does_not_trigger_callback(self):
        """Clicking Cancel in confirmation dialog does not trigger callback."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                mock_alert = MagicMock()
                mock_alert_class.alloc.return_value.init.return_value = mock_alert
                mock_alert.runModal.return_value = 1001  # Cancel clicked

                callback = MagicMock()
                delegate = MenuBarApp.alloc().initWithCallbacks_({"on_model_change": callback})
                delegate._status_item = MagicMock()
                delegate._is_model_cached_fn = lambda m: False  # Nothing cached
                delegate._current_model = "small"

                delegate.setupStatusBar(version="0.1.0")

                mock_sender = MagicMock()
                mock_sender.representedObject.return_value = "large"
                delegate.selectModel_(mock_sender)

                # Should NOT call callback after Cancel
                callback.assert_not_called()


class TestModelStateUpdates:
    """Test model state update methods for menu bar."""

    def test_setCurrentModel_updates_current_model(self):
        """setCurrentModel_ updates the stored current model."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()
            delegate._is_model_cached_fn = lambda m: True
            delegate._current_model = "small"

            delegate.setupStatusBar(version="0.1.0")
            delegate.setCurrentModel_("large")
            # Simulate main thread call
            delegate.applyCurrentModel()

            assert delegate._current_model == "large"

    def test_setModelDownloading_adds_to_downloading_set(self):
        """setModelDownloading_ marks model as downloading."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()
            delegate._is_model_cached_fn = lambda m: True

            delegate.setupStatusBar(version="0.1.0")
            delegate.setModelDownloading_("large", True)
            # Simulate main thread call
            delegate.applyDownloadState()

            assert "large" in delegate._downloading_models

    def test_setModelDownloading_removes_from_downloading_set(self):
        """setModelDownloading_ with False removes model from downloading set."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()
            delegate._is_model_cached_fn = lambda m: True
            delegate._downloading_models = {"large"}

            delegate.setupStatusBar(version="0.1.0")
            delegate.setModelDownloading_("large", False)
            # Simulate main thread call
            delegate.applyDownloadState()

            assert "large" not in delegate._downloading_models

    def test_refreshModelStates_updates_all_menu_items(self):
        """refreshModelStates updates titles for all model menu items."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()
            delegate._is_model_cached_fn = lambda m: m in ["small", "tiny"]
            delegate._current_model = "small"

            delegate.setupStatusBar(version="0.1.0")
            delegate.refreshModelStates()

            # Verify small has current indicator (●) and cached (✓)
            small_item = delegate._model_menu_items["small"]
            small_title = small_item.title()
            assert "●" in small_title
            assert "✓" in small_title

            # Verify large has no current indicator and download icon (↓)
            large_item = delegate._model_menu_items["large"]
            large_title = large_item.title()
            assert "●" not in large_title
            assert "↓" in large_title


class TestMenuDelegate:
    """Test menu delegate for refreshing cache state on submenu open."""

    def test_model_submenu_has_delegate_set(self):
        """Model submenu should have a delegate set for menuWillOpen notifications."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()
            delegate._is_model_cached_fn = lambda m: True

            delegate.setupStatusBar(version="0.1.0")

            # Model submenu should have delegate set
            assert delegate._model_submenu.delegate() is not None

    def test_menuWillOpen_refreshes_model_states(self):
        """menuWillOpen_ should refresh model states when model submenu opens."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            # Track cache check calls
            cache_calls = []

            def tracking_cache_fn(m):
                cache_calls.append(m)
                return m == "small"

            delegate = MenuBarApp.alloc().initWithCallbacks_({})
            delegate._status_item = MagicMock()
            delegate._is_model_cached_fn = tracking_cache_fn

            delegate.setupStatusBar(version="0.1.0")

            # Clear calls from setup
            cache_calls.clear()

            # Simulate menu opening (this should refresh states)
            delegate.menuWillOpen_(delegate._model_submenu)

            # Should have checked cache for all models
            assert len(cache_calls) == 5  # All 5 models checked


class TestOpenFilePicker:
    """Test open_file_picker function for selecting audio/video files."""

    def test_open_file_picker_returns_path_when_file_selected(self):
        """open_file_picker returns file path when user selects file."""
        from hanasu.menubar import open_file_picker

        with patch("hanasu.menubar.NSOpenPanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.openPanel.return_value = mock_panel
            mock_panel.runModal.return_value = 1  # OK button

            mock_url = MagicMock()
            mock_url.path.return_value = "/path/to/audio.mp3"
            mock_panel.URL.return_value = mock_url

            result = open_file_picker()

            assert result == "/path/to/audio.mp3"

    def test_open_file_picker_returns_none_when_cancelled(self):
        """open_file_picker returns None when user cancels."""
        from hanasu.menubar import open_file_picker

        with patch("hanasu.menubar.NSOpenPanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.openPanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0  # Cancel button

            result = open_file_picker()

            assert result is None

    def test_open_file_picker_sets_allowed_extensions(self):
        """open_file_picker sets allowed file types when provided."""
        from hanasu.menubar import open_file_picker

        with patch("hanasu.menubar.NSOpenPanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.openPanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0  # Cancel

            open_file_picker(allowed_extensions=["mp3", "wav", "m4a"])

            mock_panel.setAllowedFileTypes_.assert_called_once_with(["mp3", "wav", "m4a"])


class TestSaveFilePicker:
    """Test save_file_picker function for selecting output location."""

    def test_save_file_picker_returns_path_when_confirmed(self):
        """save_file_picker returns path when user confirms."""
        from hanasu.menubar import save_file_picker

        with patch("hanasu.menubar.NSSavePanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.savePanel.return_value = mock_panel
            mock_panel.runModal.return_value = 1  # OK button

            mock_url = MagicMock()
            mock_url.path.return_value = "/path/to/output.txt"
            mock_panel.URL.return_value = mock_url

            result = save_file_picker()

            assert result == "/path/to/output.txt"

    def test_save_file_picker_returns_none_when_cancelled(self):
        """save_file_picker returns None when user cancels."""
        from hanasu.menubar import save_file_picker

        with patch("hanasu.menubar.NSSavePanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.savePanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0  # Cancel button

            result = save_file_picker()

            assert result is None

    def test_save_file_picker_sets_suggested_name(self):
        """save_file_picker sets the suggested filename."""
        from hanasu.menubar import save_file_picker

        with patch("hanasu.menubar.NSSavePanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.savePanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0

            save_file_picker(suggested_name="interview.txt")

            mock_panel.setNameFieldStringValue_.assert_called_with("interview.txt")

    def test_save_file_picker_sets_initial_directory(self):
        """save_file_picker sets initial directory when provided."""
        from hanasu.menubar import save_file_picker

        with patch("hanasu.menubar.NSSavePanel") as mock_panel_class:
            with patch("hanasu.menubar.NSURL") as mock_nsurl:
                mock_panel = MagicMock()
                mock_panel_class.savePanel.return_value = mock_panel
                mock_panel.runModal.return_value = 0

                mock_dir_url = MagicMock()
                mock_nsurl.fileURLWithPath_.return_value = mock_dir_url

                save_file_picker(initial_dir="/Users/test/transcriptions")

                mock_nsurl.fileURLWithPath_.assert_called_with("/Users/test/transcriptions")
                mock_panel.setDirectoryURL_.assert_called_with(mock_dir_url)


class TestTranscribeFileMenuItem:
    """Test Transcribe File menu item integration."""

    def test_run_menubar_app_accepts_on_transcribe_file_callback(self):
        """run_menubar_app accepts on_transcribe_file callback parameter."""
        from hanasu.menubar import run_menubar_app

        with patch("hanasu.menubar.NSApplication") as mock_app:
            with patch("hanasu.menubar.NSStatusBar") as mock_status_bar:
                mock_app.sharedApplication.return_value = MagicMock()
                mock_status_bar.systemStatusBar.return_value.statusItemWithLength_.return_value = (
                    MagicMock()
                )

                transcribe_callback = MagicMock()

                delegate = run_menubar_app(
                    hotkey="cmd+v",
                    on_transcribe_file=transcribe_callback,
                )

                assert delegate is not None
                assert delegate._callbacks.get("on_transcribe_file") == transcribe_callback

    def test_transcribe_file_menu_item_triggers_callback(self):
        """Clicking Transcribe File menu item triggers callback."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            callback = MagicMock()
            delegate = MenuBarApp.alloc().initWithCallbacks_({"on_transcribe_file": callback})
            delegate._status_item = MagicMock()
            delegate._is_model_cached_fn = lambda m: True

            delegate.transcribeFile_(None)

            callback.assert_called_once()


class TestShowFormatPicker:
    """Test show_format_picker function for output format selection."""

    def test_show_format_picker_returns_txt_for_first_button(self):
        """show_format_picker returns 'txt' when first button clicked."""
        from hanasu.menubar import show_format_picker

        with patch("hanasu.menubar.NSAlert") as mock_alert_class:
            mock_alert = MagicMock()
            mock_alert_class.alloc.return_value.init.return_value = mock_alert
            mock_alert.runModal.return_value = 1000  # First button

            result = show_format_picker()

            assert result == "txt"

    def test_show_format_picker_returns_vtt_for_second_button(self):
        """show_format_picker returns 'vtt' when second button clicked."""
        from hanasu.menubar import show_format_picker

        with patch("hanasu.menubar.NSAlert") as mock_alert_class:
            mock_alert = MagicMock()
            mock_alert_class.alloc.return_value.init.return_value = mock_alert
            mock_alert.runModal.return_value = 1001  # Second button

            result = show_format_picker()

            assert result == "vtt"

    def test_show_format_picker_returns_none_for_cancel(self):
        """show_format_picker returns None when cancel button clicked."""
        from hanasu.menubar import show_format_picker

        with patch("hanasu.menubar.NSAlert") as mock_alert_class:
            mock_alert = MagicMock()
            mock_alert_class.alloc.return_value.init.return_value = mock_alert
            mock_alert.runModal.return_value = 1002  # Third button (cancel)

            result = show_format_picker()

            assert result is None


class TestStartAppLoop:
    """Test start_app_loop function."""

    def test_start_app_loop_calls_run_event_loop(self):
        """start_app_loop calls AppHelper.runEventLoop."""
        from hanasu.menubar import start_app_loop

        with patch("hanasu.menubar.AppHelper") as mock_helper:
            start_app_loop()

            mock_helper.runEventLoop.assert_called_once()
