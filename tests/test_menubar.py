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


class TestOpenFilePicker:
    """Test file picker dialog for selecting audio/video files."""

    def test_open_file_picker_returns_path_when_user_selects(self):
        """open_file_picker returns selected file path when user confirms."""
        from hanasu.menubar import open_file_picker

        with patch("hanasu.menubar.NSOpenPanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.openPanel.return_value = mock_panel
            mock_panel.runModal.return_value = 1  # NSModalResponseOK

            mock_url = MagicMock()
            mock_url.path.return_value = "/Users/test/audio.mp3"
            mock_panel.URL.return_value = mock_url

            result = open_file_picker()

            assert result == "/Users/test/audio.mp3"

    def test_open_file_picker_returns_none_when_user_cancels(self):
        """open_file_picker returns None when user cancels dialog."""
        from hanasu.menubar import open_file_picker

        with patch("hanasu.menubar.NSOpenPanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.openPanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0  # NSModalResponseCancel

            result = open_file_picker()

            assert result is None

    def test_open_file_picker_sets_allowed_extensions(self):
        """open_file_picker filters to specified file types."""
        from hanasu.menubar import open_file_picker

        with patch("hanasu.menubar.NSOpenPanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.openPanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0

            open_file_picker(allowed_extensions=["mp3", "wav", "mp4"])

            mock_panel.setAllowedFileTypes_.assert_called_once_with(["mp3", "wav", "mp4"])

    def test_open_file_picker_configures_panel_correctly(self):
        """open_file_picker sets panel to select files not directories."""
        from hanasu.menubar import open_file_picker

        with patch("hanasu.menubar.NSOpenPanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.openPanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0

            open_file_picker()

            mock_panel.setCanChooseFiles_.assert_called_once_with(True)
            mock_panel.setCanChooseDirectories_.assert_called_once_with(False)
            mock_panel.setAllowsMultipleSelection_.assert_called_once_with(False)


class TestSaveFilePicker:
    """Test save file dialog for selecting output location."""

    def test_save_file_picker_returns_path_when_user_confirms(self):
        """save_file_picker returns selected file path when user confirms."""
        from hanasu.menubar import save_file_picker

        with patch("hanasu.menubar.NSSavePanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.savePanel.return_value = mock_panel
            mock_panel.runModal.return_value = 1  # NSModalResponseOK

            mock_url = MagicMock()
            mock_url.path.return_value = "/Users/test/output.txt"
            mock_panel.URL.return_value = mock_url

            result = save_file_picker()

            assert result == "/Users/test/output.txt"

    def test_save_file_picker_returns_none_when_user_cancels(self):
        """save_file_picker returns None when user cancels dialog."""
        from hanasu.menubar import save_file_picker

        with patch("hanasu.menubar.NSSavePanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.savePanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0  # NSModalResponseCancel

            result = save_file_picker()

            assert result is None

    def test_save_file_picker_sets_suggested_filename(self):
        """save_file_picker sets the default filename suggestion."""
        from hanasu.menubar import save_file_picker

        with patch("hanasu.menubar.NSSavePanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.savePanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0

            save_file_picker(suggested_name="transcription.txt")

            mock_panel.setNameFieldStringValue_.assert_called_once_with("transcription.txt")

    def test_save_file_picker_sets_initial_directory(self):
        """save_file_picker sets the initial directory when provided."""
        from hanasu.menubar import save_file_picker

        with patch("hanasu.menubar.NSSavePanel") as mock_panel_class:
            with patch("hanasu.menubar.NSURL") as mock_nsurl:
                mock_panel = MagicMock()
                mock_panel_class.savePanel.return_value = mock_panel
                mock_panel.runModal.return_value = 0

                mock_url = MagicMock()
                mock_nsurl.fileURLWithPath_.return_value = mock_url

                save_file_picker(initial_dir="/Users/test/documents")

                mock_nsurl.fileURLWithPath_.assert_called_once_with("/Users/test/documents")
                mock_panel.setDirectoryURL_.assert_called_once_with(mock_url)

    def test_save_file_picker_sets_allowed_file_types(self):
        """save_file_picker filters to specified file types."""
        from hanasu.menubar import save_file_picker

        with patch("hanasu.menubar.NSSavePanel") as mock_panel_class:
            mock_panel = MagicMock()
            mock_panel_class.savePanel.return_value = mock_panel
            mock_panel.runModal.return_value = 0

            save_file_picker(file_types=["txt", "vtt"])

            mock_panel.setAllowedFileTypes_.assert_called_once_with(["txt", "vtt"])


class TestTranscribeFileMenuItem:
    """Test Transcribe File menu item."""

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

    def test_menubar_stores_transcribe_file_callback(self):
        """MenuBarApp stores on_transcribe_file callback for later invocation."""
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

                assert delegate._callbacks.get("on_transcribe_file") == transcribe_callback

    def test_transcribe_file_handler_invokes_callback(self):
        """transcribeFile_ handler invokes the on_transcribe_file callback."""
        from hanasu.menubar import MenuBarApp

        with patch("hanasu.menubar.NSStatusBar"):
            callback = MagicMock()
            delegate = MenuBarApp.alloc().initWithCallbacks_({"on_transcribe_file": callback})
            delegate._status_item = MagicMock()

            delegate.transcribeFile_(None)

            callback.assert_called_once()


class TestShowFormatPicker:
    """Test format selection dialog."""

    def test_show_format_picker_returns_txt_for_first_button(self):
        """show_format_picker returns 'txt' when Plain Text button clicked."""
        from hanasu.menubar import show_format_picker

        with patch("hanasu.menubar.NSAlert") as mock_alert_class:
            mock_alert = MagicMock()
            mock_alert_class.alloc.return_value.init.return_value = mock_alert
            mock_alert.runModal.return_value = 1000  # First button

            result = show_format_picker()

            assert result == "txt"

    def test_show_format_picker_returns_vtt_for_second_button(self):
        """show_format_picker returns 'vtt' when VTT button clicked."""
        from hanasu.menubar import show_format_picker

        with patch("hanasu.menubar.NSAlert") as mock_alert_class:
            mock_alert = MagicMock()
            mock_alert_class.alloc.return_value.init.return_value = mock_alert
            mock_alert.runModal.return_value = 1001  # Second button

            result = show_format_picker()

            assert result == "vtt"

    def test_show_format_picker_returns_none_for_cancel(self):
        """show_format_picker returns None when Cancel button clicked."""
        from hanasu.menubar import show_format_picker

        with patch("hanasu.menubar.NSAlert") as mock_alert_class:
            mock_alert = MagicMock()
            mock_alert_class.alloc.return_value.init.return_value = mock_alert
            mock_alert.runModal.return_value = 1002  # Third button (Cancel)

            result = show_format_picker()

            assert result is None

    def test_show_format_picker_configures_dialog(self):
        """show_format_picker sets up dialog with correct buttons."""
        from hanasu.menubar import show_format_picker

        with patch("hanasu.menubar.NSAlert") as mock_alert_class:
            mock_alert = MagicMock()
            mock_alert_class.alloc.return_value.init.return_value = mock_alert
            mock_alert.runModal.return_value = 1002

            show_format_picker()

            mock_alert.setMessageText_.assert_called_once()
            # Should have 3 buttons: Plain Text, VTT, Cancel
            assert mock_alert.addButtonWithTitle_.call_count == 3
