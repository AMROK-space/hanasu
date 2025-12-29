"""Tests for transcription functionality."""

from unittest.mock import patch, MagicMock
import numpy as np
import pytest

from hanasu.transcriber import Transcriber, apply_replacements
from hanasu.config import Dictionary


class TestTranscriberTranscribe:
    """Test transcription with mlx-whisper."""

    def test_transcribes_audio_to_text(self):
        """Audio buffer is transcribed to text."""
        with patch("hanasu.transcriber.mlx_whisper") as mock_whisper:
            mock_whisper.transcribe.return_value = {
                "text": " Hello, world!"
            }

            transcriber = Transcriber(model="small")
            audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
            result = transcriber.transcribe(audio)

            assert result == "Hello, world!"

    def test_strips_leading_whitespace_from_result(self):
        """Leading/trailing whitespace is stripped from transcription."""
        with patch("hanasu.transcriber.mlx_whisper") as mock_whisper:
            mock_whisper.transcribe.return_value = {
                "text": "   Some text with spaces   "
            }

            transcriber = Transcriber(model="small")
            result = transcriber.transcribe(np.array([0.1], dtype=np.float32))

            assert result == "Some text with spaces"

    def test_returns_empty_string_for_empty_audio(self):
        """Empty audio returns empty string without calling whisper."""
        with patch("hanasu.transcriber.mlx_whisper") as mock_whisper:
            transcriber = Transcriber(model="small")
            result = transcriber.transcribe(np.array([], dtype=np.float32))

            assert result == ""
            mock_whisper.transcribe.assert_not_called()


class TestTranscriberDictionary:
    """Test dictionary context for improved accuracy."""

    def test_prepends_dictionary_terms_as_prompt(self):
        """Dictionary terms are passed as initial_prompt."""
        with patch("hanasu.transcriber.mlx_whisper") as mock_whisper:
            mock_whisper.transcribe.return_value = {"text": "AMROK"}

            dictionary = Dictionary(
                terms=["AMROK", "PyObjC", "mlx-whisper"],
                replacements={},
            )

            transcriber = Transcriber(model="small")
            transcriber.transcribe(
                np.array([0.1], dtype=np.float32),
                dictionary=dictionary,
            )

            # Verify initial_prompt was passed
            call_kwargs = mock_whisper.transcribe.call_args[1]
            assert "initial_prompt" in call_kwargs
            assert "AMROK" in call_kwargs["initial_prompt"]
            assert "PyObjC" in call_kwargs["initial_prompt"]

    def test_applies_replacements_after_transcription(self):
        """Replacement rules are applied to transcribed text."""
        with patch("hanasu.transcriber.mlx_whisper") as mock_whisper:
            mock_whisper.transcribe.return_value = {
                "text": " I use py object see for macOS"
            }

            dictionary = Dictionary(
                terms=[],
                replacements={"py object see": "PyObjC"},
            )

            transcriber = Transcriber(model="small")
            result = transcriber.transcribe(
                np.array([0.1], dtype=np.float32),
                dictionary=dictionary,
            )

            assert result == "I use PyObjC for macOS"


class TestApplyReplacements:
    """Test post-processing replacements."""

    def test_replaces_single_term(self):
        """Single replacement is applied correctly."""
        text = "I love k8s"
        replacements = {"k8s": "Kubernetes"}

        result = apply_replacements(text, replacements)

        assert result == "I love Kubernetes"

    def test_replaces_multiple_terms(self):
        """Multiple replacements are applied correctly."""
        text = "Use k8s and py object see"
        replacements = {
            "k8s": "Kubernetes",
            "py object see": "PyObjC",
        }

        result = apply_replacements(text, replacements)

        assert result == "Use Kubernetes and PyObjC"

    def test_case_insensitive_replacement(self):
        """Replacements are case-insensitive."""
        text = "I use PY OBJECT SEE"
        replacements = {"py object see": "PyObjC"}

        result = apply_replacements(text, replacements)

        assert result == "I use PyObjC"

    def test_empty_replacements_returns_original(self):
        """Empty replacements dict returns original text."""
        text = "Hello world"
        result = apply_replacements(text, {})

        assert result == "Hello world"


class TestTranscriberModel:
    """Test model configuration."""

    def test_uses_correct_model_path(self):
        """Transcriber uses correct mlx-community model path."""
        with patch("hanasu.transcriber.mlx_whisper") as mock_whisper:
            mock_whisper.transcribe.return_value = {"text": "test"}

            transcriber = Transcriber(model="small")
            transcriber.transcribe(np.array([0.1], dtype=np.float32))

            call_kwargs = mock_whisper.transcribe.call_args[1]
            assert "mlx-community/whisper-small-mlx" in call_kwargs["path_or_hf_repo"]

    def test_forces_english_language(self):
        """Transcriber forces English language for speed."""
        with patch("hanasu.transcriber.mlx_whisper") as mock_whisper:
            mock_whisper.transcribe.return_value = {"text": "test"}

            transcriber = Transcriber(model="small", language="en")
            transcriber.transcribe(np.array([0.1], dtype=np.float32))

            call_kwargs = mock_whisper.transcribe.call_args[1]
            assert call_kwargs["language"] == "en"
