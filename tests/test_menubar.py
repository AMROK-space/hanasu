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
