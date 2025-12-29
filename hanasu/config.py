"""Configuration loading and validation for Hanasu."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


VALID_MODELS = {"tiny", "base", "small", "medium", "large"}


@dataclass
class Config:
    """Application configuration."""
    hotkey: str
    model: str
    language: str
    audio_device: Optional[str]
    debug: bool
    clear_clipboard: bool


@dataclass
class Dictionary:
    """User vocabulary dictionary."""
    terms: list[str] = field(default_factory=list)
    replacements: dict[str, str] = field(default_factory=dict)


DEFAULT_CONFIG = {
    "hotkey": "cmd+alt+v",
    "model": "small",
    "language": "en",
    "audio_device": None,
    "debug": False,
    "clear_clipboard": False,
}


def load_config(config_dir: Path) -> Config:
    """Load configuration from config directory.

    Creates config directory if it doesn't exist.
    Returns defaults if no config file exists.
    Merges partial config with defaults.
    Validates config values.
    """
    # Create config directory if missing
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "config.json"

    # Start with defaults
    config_data = DEFAULT_CONFIG.copy()

    # Merge with file config if it exists
    if config_file.exists():
        with open(config_file, "r") as f:
            file_config = json.load(f)

            # Warn about unrecognized keys
            for key in file_config:
                if key not in DEFAULT_CONFIG:
                    logger.warning(f"Unrecognized config key: {key}")

            config_data.update(file_config)

    # Validate
    _validate_config(config_data)

    return Config(
        hotkey=config_data["hotkey"],
        model=config_data["model"],
        language=config_data["language"],
        audio_device=config_data["audio_device"],
        debug=config_data["debug"],
        clear_clipboard=config_data["clear_clipboard"],
    )


def _validate_config(config_data: dict) -> None:
    """Validate configuration values."""
    # Validate model
    if config_data["model"] not in VALID_MODELS:
        raise ConfigValidationError(
            f"Invalid model: {config_data['model']}. "
            f"Must be one of: {', '.join(sorted(VALID_MODELS))}"
        )

    # Validate hotkey
    if not config_data["hotkey"] or not config_data["hotkey"].strip():
        raise ConfigValidationError("Invalid hotkey: cannot be empty")


def load_dictionary(config_dir: Path) -> Dictionary:
    """Load user vocabulary dictionary.

    Returns empty dictionary if file doesn't exist.
    """
    dict_file = config_dir / "dictionary.json"

    if not dict_file.exists():
        return Dictionary()

    with open(dict_file, "r") as f:
        data = json.load(f)

    return Dictionary(
        terms=data.get("terms", []),
        replacements=data.get("replacements", {}),
    )
