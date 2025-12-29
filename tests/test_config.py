"""Tests for configuration loading and validation."""

import json
import tempfile
from pathlib import Path

import pytest

from hanasu.config import (
    Config,
    load_config,
    save_config,
    load_dictionary,
    DEFAULT_CONFIG,
    ConfigValidationError,
)


class TestLoadConfigDefaults:
    """Test that defaults are used when no config file exists."""

    def test_returns_default_config_when_no_file_exists(self, tmp_path: Path):
        """When config file doesn't exist, return defaults."""
        config = load_config(config_dir=tmp_path)

        assert config.hotkey == "cmd+alt+v"
        assert config.model == "small"
        assert config.language == "en"
        assert config.audio_device is None
        assert config.debug is False

    def test_creates_config_directory_if_missing(self, tmp_path: Path):
        """Config directory is created if it doesn't exist."""
        config_dir = tmp_path / "whisper-dictate"
        assert not config_dir.exists()

        load_config(config_dir=config_dir)

        assert config_dir.exists()


class TestLoadConfigFromFile:
    """Test loading config from JSON file."""

    def test_loads_custom_hotkey_from_file(self, tmp_path: Path):
        """Custom hotkey is loaded from config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"hotkey": "cmd+shift+d"}))

        config = load_config(config_dir=tmp_path)

        assert config.hotkey == "cmd+shift+d"

    def test_loads_custom_model_from_file(self, tmp_path: Path):
        """Custom model is loaded from config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"model": "medium"}))

        config = load_config(config_dir=tmp_path)

        assert config.model == "medium"

    def test_loads_audio_device_from_file(self, tmp_path: Path):
        """Audio device preference is loaded from config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"audio_device": "AirPods Pro"}))

        config = load_config(config_dir=tmp_path)

        assert config.audio_device == "AirPods Pro"

    def test_loads_debug_mode_from_file(self, tmp_path: Path):
        """Debug mode is loaded from config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"debug": True}))

        config = load_config(config_dir=tmp_path)

        assert config.debug is True

    def test_merges_partial_config_with_defaults(self, tmp_path: Path):
        """Partial config is merged with defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"hotkey": "f19"}))

        config = load_config(config_dir=tmp_path)

        # Custom value
        assert config.hotkey == "f19"
        # Defaults preserved
        assert config.model == "small"
        assert config.language == "en"


class TestConfigValidation:
    """Test config validation."""

    def test_rejects_invalid_model_name(self, tmp_path: Path):
        """Invalid model name raises ConfigValidationError."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"model": "invalid-model"}))

        with pytest.raises(ConfigValidationError, match="model"):
            load_config(config_dir=tmp_path)

    def test_accepts_valid_model_names(self, tmp_path: Path):
        """Valid model names are accepted."""
        for model in ["tiny", "base", "small", "medium", "large"]:
            config_file = tmp_path / "config.json"
            config_file.write_text(json.dumps({"model": model}))

            config = load_config(config_dir=tmp_path)
            assert config.model == model

    def test_rejects_empty_hotkey(self, tmp_path: Path):
        """Empty hotkey raises ConfigValidationError."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"hotkey": ""}))

        with pytest.raises(ConfigValidationError, match="hotkey"):
            load_config(config_dir=tmp_path)


class TestLoadDictionary:
    """Test dictionary loading for custom vocabulary."""

    def test_returns_empty_dictionary_when_file_missing(self, tmp_path: Path):
        """When dictionary file doesn't exist, return empty dict."""
        dictionary = load_dictionary(config_dir=tmp_path)

        assert dictionary.terms == []
        assert dictionary.replacements == {}

    def test_loads_terms_from_dictionary_file(self, tmp_path: Path):
        """Custom terms are loaded from dictionary file."""
        dict_file = tmp_path / "dictionary.json"
        dict_file.write_text(json.dumps({
            "terms": ["AMROK", "PyObjC", "mlx-whisper"]
        }))

        dictionary = load_dictionary(config_dir=tmp_path)

        assert "AMROK" in dictionary.terms
        assert "PyObjC" in dictionary.terms
        assert "mlx-whisper" in dictionary.terms

    def test_loads_replacements_from_dictionary_file(self, tmp_path: Path):
        """Replacement rules are loaded from dictionary file."""
        dict_file = tmp_path / "dictionary.json"
        dict_file.write_text(json.dumps({
            "replacements": {
                "py object see": "PyObjC",
                "k8s": "Kubernetes"
            }
        }))

        dictionary = load_dictionary(config_dir=tmp_path)

        assert dictionary.replacements["py object see"] == "PyObjC"
        assert dictionary.replacements["k8s"] == "Kubernetes"


class TestUnrecognizedConfigKeys:
    """Test warnings for unrecognized config keys."""

    def test_warns_on_unrecognized_config_key(self, tmp_path: Path, caplog):
        """Unrecognized config keys trigger a warning."""
        import logging

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "hotkey": "cmd+alt+v",
            "typo_key": "some_value",
        }))

        with caplog.at_level(logging.WARNING):
            load_config(config_dir=tmp_path)

        assert "typo_key" in caplog.text
        assert "unrecognized" in caplog.text.lower()

    def test_warns_on_multiple_unrecognized_keys(self, tmp_path: Path, caplog):
        """Multiple unrecognized keys each trigger warnings."""
        import logging

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "hotkey": "cmd+alt+v",
            "bad_key_1": "value1",
            "bad_key_2": "value2",
        }))

        with caplog.at_level(logging.WARNING):
            load_config(config_dir=tmp_path)

        assert "bad_key_1" in caplog.text
        assert "bad_key_2" in caplog.text

    def test_no_warning_for_valid_keys_only(self, tmp_path: Path, caplog):
        """No warnings when all config keys are recognized."""
        import logging

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "hotkey": "cmd+alt+v",
            "model": "small",
            "language": "en",
        }))

        with caplog.at_level(logging.WARNING):
            load_config(config_dir=tmp_path)

        assert "unrecognized" not in caplog.text.lower()


class TestSaveConfig:
    """Test saving configuration to file."""

    def test_saves_config_to_file(self, tmp_path: Path):
        """save_config writes config to config.json."""
        config = Config(
            hotkey="cmd+shift+k",
            model="small",
            language="en",
            audio_device=None,
            debug=False,
            clear_clipboard=False,
        )

        save_config(config, config_dir=tmp_path)

        config_file = tmp_path / "config.json"
        assert config_file.exists()

        with open(config_file) as f:
            saved = json.load(f)

        assert saved["hotkey"] == "cmd+shift+k"

    def test_preserves_other_config_values(self, tmp_path: Path):
        """save_config preserves all config values."""
        config = Config(
            hotkey="f19",
            model="medium",
            language="es",
            audio_device="AirPods",
            debug=True,
            clear_clipboard=True,
        )

        save_config(config, config_dir=tmp_path)

        with open(tmp_path / "config.json") as f:
            saved = json.load(f)

        assert saved["hotkey"] == "f19"
        assert saved["model"] == "medium"
        assert saved["language"] == "es"
        assert saved["audio_device"] == "AirPods"
        assert saved["debug"] is True
        assert saved["clear_clipboard"] is True

    def test_creates_config_dir_if_missing(self, tmp_path: Path):
        """save_config creates config directory if it doesn't exist."""
        config_dir = tmp_path / "subdir" / ".hanasu"
        config = Config(
            hotkey="cmd+alt+v",
            model="small",
            language="en",
            audio_device=None,
            debug=False,
            clear_clipboard=False,
        )

        save_config(config, config_dir=config_dir)

        assert config_dir.exists()
        assert (config_dir / "config.json").exists()
