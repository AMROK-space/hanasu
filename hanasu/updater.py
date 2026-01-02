"""Check for updates against GitHub releases."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)

GITHUB_REPO = "AMROK-space/hanasu"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT = 5
CACHE_DURATION = 24 * 60 * 60  # 24 hours in seconds


@dataclass
class UpdateStatus:
    """Status of update check."""

    checked: bool
    update_available: bool
    latest_version: str | None


def get_latest_version() -> str | None:
    """Fetch the latest release version from GitHub.

    Returns:
        Version string (e.g., "0.2.0") or None if fetch fails.
    """
    request = urllib.request.Request(
        RELEASES_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "hanasu-update-checker",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode())
            tag = data.get("tag_name")
            if not tag:
                return None
            # Strip leading 'v' if present (v0.1.0 -> 0.1.0)
            return tag.lstrip("v") if tag else None
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError) as e:
        logger.warning("Failed to check for updates: %s", e)
        return None


def is_update_available(current_version: str, latest_version: str) -> tuple[bool, str | None]:
    """Check if a newer version is available.

    Args:
        current_version: Current installed version (e.g., "0.1.0")
        latest_version: Latest version from GitHub

    Returns:
        Tuple of (update_available: bool, latest_version: str | None)
    """
    try:
        current = Version(current_version)
        remote = Version(latest_version)
        return remote > current, latest_version
    except InvalidVersion:
        logger.warning("Invalid version format: %s or %s", current_version, latest_version)
        return False, None


def check_for_update(current_version: str, cache_dir: Path | None = None) -> UpdateStatus:
    """Check for updates with caching.

    Args:
        current_version: Current installed version
        cache_dir: Directory for cache file (defaults to ~/.hanasu)

    Returns:
        UpdateStatus with check results
    """
    if cache_dir is None:
        cache_dir = Path.home() / ".hanasu"

    cache_file = cache_dir / "update_cache.json"

    # Check cache first
    if cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text())
            last_check = cache_data.get("last_check", 0)
            cached_version = cache_data.get("latest_version")

            # Use cache if within 24 hours
            if time.time() - last_check < CACHE_DURATION and cached_version:
                available, version = is_update_available(current_version, cached_version)
                return UpdateStatus(
                    checked=True,
                    update_available=available,
                    latest_version=cached_version,
                )
        except (json.JSONDecodeError, KeyError):
            pass  # Cache invalid, fetch fresh

    # Fetch from GitHub
    latest = get_latest_version()
    if latest is None:
        return UpdateStatus(checked=False, update_available=False, latest_version=None)

    # Save to cache
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "last_check": time.time(),
        "latest_version": latest,
    }
    cache_file.write_text(json.dumps(cache_data))

    available, version = is_update_available(current_version, latest)
    return UpdateStatus(
        checked=True,
        update_available=available,
        latest_version=latest,
    )
