"""Tests for update checking functionality."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from hanasu.updater import (
    UpdateStatus,
    check_for_update,
    get_latest_version,
    is_update_available,
)


class TestGetLatestVersion:
    """Test fetching latest version from GitHub."""

    def test_fetches_version_from_github_api(self):
        """Fetches and parses version from GitHub releases API."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"tag_name": "v0.2.0"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("hanasu.updater.urllib.request.urlopen", return_value=mock_response):
            version = get_latest_version()

        assert version == "0.2.0"

    def test_strips_v_prefix_from_tag(self):
        """Strips 'v' prefix from version tag."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"tag_name": "v1.0.0"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("hanasu.updater.urllib.request.urlopen", return_value=mock_response):
            version = get_latest_version()

        assert version == "1.0.0"

    def test_handles_tag_without_v_prefix(self):
        """Works with tags that don't have v prefix."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"tag_name": "0.3.0"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("hanasu.updater.urllib.request.urlopen", return_value=mock_response):
            version = get_latest_version()

        assert version == "0.3.0"

    def test_returns_none_on_network_error(self):
        """Returns None when network request fails."""
        import urllib.error

        with patch(
            "hanasu.updater.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Network error"),
        ):
            version = get_latest_version()

        assert version is None

    def test_returns_none_on_invalid_json(self):
        """Returns None when response is not valid JSON."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not json"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("hanasu.updater.urllib.request.urlopen", return_value=mock_response):
            version = get_latest_version()

        assert version is None

    def test_returns_none_when_tag_name_missing(self):
        """Returns None when response lacks tag_name field."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"name": "Release"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("hanasu.updater.urllib.request.urlopen", return_value=mock_response):
            version = get_latest_version()

        assert version is None


class TestIsUpdateAvailable:
    """Test version comparison logic."""

    def test_returns_true_when_remote_newer(self):
        """Returns True when remote version is newer."""
        available, latest = is_update_available("0.1.0", "0.2.0")

        assert available is True
        assert latest == "0.2.0"

    def test_returns_false_when_versions_equal(self):
        """Returns False when versions match."""
        available, latest = is_update_available("0.1.0", "0.1.0")

        assert available is False
        assert latest == "0.1.0"

    def test_returns_false_when_local_newer(self):
        """Returns False when local version is newer (dev build)."""
        available, latest = is_update_available("0.2.0", "0.1.0")

        assert available is False
        assert latest == "0.1.0"

    def test_handles_major_version_bump(self):
        """Detects major version updates."""
        available, latest = is_update_available("0.9.0", "1.0.0")

        assert available is True
        assert latest == "1.0.0"

    def test_handles_patch_version_bump(self):
        """Detects patch version updates."""
        available, latest = is_update_available("1.0.0", "1.0.1")

        assert available is True
        assert latest == "1.0.1"

    def test_returns_false_on_invalid_version(self):
        """Returns False when version format is invalid."""
        available, latest = is_update_available("0.1.0", "invalid")

        assert available is False
        assert latest is None


class TestCheckForUpdate:
    """Test the main update check function with caching."""

    def test_checks_github_on_first_call(self, tmp_path: Path):
        """First call fetches from GitHub."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"tag_name": "v0.2.0"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("hanasu.updater.urllib.request.urlopen", return_value=mock_response):
            status = check_for_update("0.1.0", cache_dir=tmp_path)

        assert status.checked is True
        assert status.update_available is True
        assert status.latest_version == "0.2.0"

    def test_uses_cache_within_24_hours(self, tmp_path: Path):
        """Uses cached result within 24 hours."""
        # Create cache file with recent check
        cache_file = tmp_path / "update_cache.json"
        cache_data = {
            "last_check": time.time(),
            "latest_version": "0.2.0",
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch("hanasu.updater.urllib.request.urlopen") as mock_urlopen:
            status = check_for_update("0.1.0", cache_dir=tmp_path)

        # Should not make network request
        mock_urlopen.assert_not_called()
        assert status.update_available is True
        assert status.latest_version == "0.2.0"

    def test_refetches_after_24_hours(self, tmp_path: Path):
        """Fetches fresh data after 24 hours."""
        # Create cache file with old check (25 hours ago)
        cache_file = tmp_path / "update_cache.json"
        cache_data = {
            "last_check": time.time() - (25 * 60 * 60),
            "latest_version": "0.2.0",
        }
        cache_file.write_text(json.dumps(cache_data))

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"tag_name": "v0.3.0"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("hanasu.updater.urllib.request.urlopen", return_value=mock_response):
            status = check_for_update("0.1.0", cache_dir=tmp_path)

        assert status.latest_version == "0.3.0"

    def test_returns_unknown_on_network_failure(self, tmp_path: Path):
        """Returns unknown status when network fails and no cache."""
        import urllib.error

        with patch(
            "hanasu.updater.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Network error"),
        ):
            status = check_for_update("0.1.0", cache_dir=tmp_path)

        assert status.checked is False
        assert status.update_available is False
        assert status.latest_version is None

    def test_saves_result_to_cache(self, tmp_path: Path):
        """Saves check result to cache file."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"tag_name": "v0.2.0"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("hanasu.updater.urllib.request.urlopen", return_value=mock_response):
            check_for_update("0.1.0", cache_dir=tmp_path)

        cache_file = tmp_path / "update_cache.json"
        assert cache_file.exists()
        cache_data = json.loads(cache_file.read_text())
        assert cache_data["latest_version"] == "0.2.0"
        assert "last_check" in cache_data


class TestUpdateStatus:
    """Test UpdateStatus dataclass."""

    def test_up_to_date_status(self):
        """Can create up-to-date status."""
        status = UpdateStatus(checked=True, update_available=False, latest_version="0.1.0")

        assert status.checked is True
        assert status.update_available is False

    def test_update_available_status(self):
        """Can create update-available status."""
        status = UpdateStatus(checked=True, update_available=True, latest_version="0.2.0")

        assert status.update_available is True
        assert status.latest_version == "0.2.0"

    def test_unknown_status(self):
        """Can create unknown/failed status."""
        status = UpdateStatus(checked=False, update_available=False, latest_version=None)

        assert status.checked is False
