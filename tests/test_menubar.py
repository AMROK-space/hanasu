"""Tests for menu bar integration with update checking."""

from unittest.mock import MagicMock, patch

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
