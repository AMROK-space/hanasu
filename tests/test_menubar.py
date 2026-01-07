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
    """Test live hotkey validation before committing changes."""

    def test_validate_hotkey_returns_true_on_correct_keypress(self):
        """validate_hotkey returns True when user presses the correct hotkey."""
        from hanasu.menubar import validate_hotkey

        with patch("hanasu.menubar.Quartz") as mock_quartz:
            # Set up constants needed by the code
            mock_quartz.kCGEventKeyDown = 10
            mock_quartz.kCGEventFlagMaskCommand = 0x100000
            mock_quartz.kCGEventFlagMaskShift = 0x20000
            mock_quartz.kCGEventFlagMaskAlternate = 0x80000
            mock_quartz.kCGEventFlagMaskControl = 0x40000

            # Capture the callback when CGEventTapCreate is called
            captured_callback = [None]

            def capture_callback(*args):
                captured_callback[0] = args[4]  # callback is 5th argument
                return MagicMock()

            mock_quartz.CGEventTapCreate.side_effect = capture_callback

            # Set up the event data for "correct" keypress
            mock_event = MagicMock()
            mock_quartz.CGEventGetIntegerValueField.return_value = 9  # 'v' keycode
            mock_quartz.CGEventGetFlags.return_value = mock_quartz.kCGEventFlagMaskCommand

            # Make CFRunLoopRunInMode invoke the callback with correct keypress
            def invoke_callback(*args):
                if captured_callback[0]:
                    captured_callback[0](None, mock_quartz.kCGEventKeyDown, mock_event, None)

            mock_quartz.CFRunLoopRunInMode.side_effect = invoke_callback

            result = validate_hotkey("cmd+v", timeout=0.1)
            assert result is True

    def test_validate_hotkey_returns_false_on_timeout(self):
        """validate_hotkey returns False if user doesn't press hotkey in time."""
        from hanasu.menubar import validate_hotkey

        with patch("hanasu.menubar.Quartz") as mock_quartz:
            # Set up constants needed by the code
            mock_quartz.kCGEventKeyDown = 10
            mock_quartz.kCGEventFlagMaskCommand = 0x100000
            mock_quartz.kCGEventFlagMaskShift = 0x20000
            mock_quartz.kCGEventFlagMaskAlternate = 0x80000
            mock_quartz.kCGEventFlagMaskControl = 0x40000
            mock_quartz.CGEventTapCreate.return_value = MagicMock()

            # Don't invoke callback - should timeout
            result = validate_hotkey("cmd+v", timeout=0.1)
            assert result is False

    def test_validate_hotkey_returns_false_on_wrong_keypress(self):
        """validate_hotkey returns False if user presses wrong hotkey."""
        from hanasu.menubar import validate_hotkey

        with patch("hanasu.menubar.Quartz") as mock_quartz:
            # Set up constants needed by the code
            mock_quartz.kCGEventKeyDown = 10
            mock_quartz.kCGEventFlagMaskCommand = 0x100000
            mock_quartz.kCGEventFlagMaskShift = 0x20000
            mock_quartz.kCGEventFlagMaskAlternate = 0x80000
            mock_quartz.kCGEventFlagMaskControl = 0x40000

            # Capture the callback when CGEventTapCreate is called
            captured_callback = [None]

            def capture_callback(*args):
                captured_callback[0] = args[4]
                return MagicMock()

            mock_quartz.CGEventTapCreate.side_effect = capture_callback

            # Simulate wrong hotkey being pressed ('a' instead of 'v')
            mock_event = MagicMock()
            mock_quartz.CGEventGetIntegerValueField.return_value = 0  # 'a' keycode (not 'v')
            mock_quartz.CGEventGetFlags.return_value = mock_quartz.kCGEventFlagMaskCommand

            # Make CFRunLoopRunInMode invoke the callback with wrong keypress
            def invoke_callback(*args):
                if captured_callback[0]:
                    captured_callback[0](None, mock_quartz.kCGEventKeyDown, mock_event, None)

            mock_quartz.CFRunLoopRunInMode.side_effect = invoke_callback

            result = validate_hotkey("cmd+v", timeout=0.1)
            assert result is False

    def test_change_hotkey_dialog_shows_validation_prompt(self):
        """changeHotkey_ shows validation prompt after user enters new hotkey."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                with patch("hanasu.menubar.NSTextField") as mock_textfield_class:
                    with patch("hanasu.menubar.validate_hotkey") as mock_validate:
                        mock_alert = MagicMock()
                        mock_alert_class.alloc.return_value.init.return_value = mock_alert
                        mock_alert.runModal.return_value = 1000  # OK clicked

                        mock_textfield = MagicMock()
                        mock_textfield.stringValue.return_value = "cmd+alt+v"
                        mock_textfield_class.alloc.return_value.initWithFrame_.return_value = (
                            mock_textfield
                        )

                        mock_validate.return_value = True  # Validation passes

                        delegate = MenuBarApp.alloc().initWithCallbacks_(
                            {"on_hotkey_change": MagicMock()}
                        )
                        delegate._status_item = MagicMock()
                        delegate._hotkey_display = "cmd+v"

                        delegate.changeHotkey_(None)

                        # Should have called validate_hotkey with the new hotkey
                        mock_validate.assert_called_once()
                        call_args = mock_validate.call_args[0]
                        assert call_args[0] == "cmd+alt+v"

    def test_change_hotkey_dialog_calls_callback_only_after_validation(self):
        """changeHotkey_ only calls on_hotkey_change callback if validation passes."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                with patch("hanasu.menubar.NSTextField") as mock_textfield_class:
                    with patch("hanasu.menubar.validate_hotkey") as mock_validate:
                        mock_alert = MagicMock()
                        mock_alert_class.alloc.return_value.init.return_value = mock_alert
                        mock_alert.runModal.return_value = 1000  # OK clicked

                        mock_textfield = MagicMock()
                        mock_textfield.stringValue.return_value = "cmd+alt+v"
                        mock_textfield_class.alloc.return_value.initWithFrame_.return_value = (
                            mock_textfield
                        )

                        mock_validate.return_value = True  # Validation passes

                        callback = MagicMock()
                        delegate = MenuBarApp.alloc().initWithCallbacks_(
                            {"on_hotkey_change": callback}
                        )
                        delegate._status_item = MagicMock()
                        delegate._hotkey_display = "cmd+v"

                        delegate.changeHotkey_(None)

                        # Callback should be called with new hotkey
                        callback.assert_called_once_with("cmd+alt+v")

    def test_change_hotkey_dialog_does_not_call_callback_if_validation_fails(self):
        """changeHotkey_ does not call callback if validation fails."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            with patch("hanasu.menubar.NSAlert") as mock_alert_class:
                with patch("hanasu.menubar.NSTextField") as mock_textfield_class:
                    with patch("hanasu.menubar.validate_hotkey") as mock_validate:
                        mock_alert = MagicMock()
                        mock_alert_class.alloc.return_value.init.return_value = mock_alert
                        mock_alert.runModal.return_value = 1000  # OK clicked

                        mock_textfield = MagicMock()
                        mock_textfield.stringValue.return_value = "cmd+alt+v"
                        mock_textfield_class.alloc.return_value.initWithFrame_.return_value = (
                            mock_textfield
                        )

                        mock_validate.return_value = False  # Validation fails

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

                cache_fn = lambda m: m == "small"

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
                delegate = MenuBarApp.alloc().initWithCallbacks_(
                    {"on_model_change": callback}
                )
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
                delegate = MenuBarApp.alloc().initWithCallbacks_(
                    {"on_model_change": callback}
                )
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
                delegate = MenuBarApp.alloc().initWithCallbacks_(
                    {"on_model_change": callback}
                )
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
                delegate = MenuBarApp.alloc().initWithCallbacks_(
                    {"on_model_change": callback}
                )
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
                delegate = MenuBarApp.alloc().initWithCallbacks_(
                    {"on_model_change": callback}
                )
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
