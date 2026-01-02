"""Transcription functionality using mlx-whisper."""

import re

import mlx_whisper
import numpy as np

from hanasu.config import Dictionary

# Model name to mlx-community HuggingFace path
MODEL_PATHS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large": "mlx-community/whisper-large-v3-mlx",
}


class Transcriber:
    """Transcribes audio using mlx-whisper."""

    def __init__(self, model: str = "small", language: str = "en"):
        """Initialize transcriber with model and language.

        Args:
            model: Model size (tiny, base, small, medium, large).
            language: Language code (e.g., 'en' for English).
        """
        self.model = model
        self.language = language
        self.model_path = MODEL_PATHS.get(model, MODEL_PATHS["small"])

    def transcribe(
        self,
        audio: np.ndarray,
        dictionary: Dictionary | None = None,
    ) -> str:
        """Transcribe audio to text.

        Args:
            audio: Audio buffer as numpy array (float32, 16kHz).
            dictionary: Optional dictionary for vocabulary hints.

        Returns:
            Transcribed text.
        """
        # Skip transcription for empty audio
        if len(audio) == 0:
            return ""

        # Build initial prompt from dictionary terms
        initial_prompt = None
        if dictionary and dictionary.terms:
            initial_prompt = "Vocabulary: " + ", ".join(dictionary.terms)

        # Transcribe with mlx-whisper
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self.model_path,
            language=self.language,
            initial_prompt=initial_prompt,
        )

        text = result["text"].strip()

        # Apply replacements if dictionary provided
        if dictionary and dictionary.replacements:
            text = apply_replacements(text, dictionary.replacements)

        return text


def apply_replacements(text: str, replacements: dict[str, str]) -> str:
    """Apply replacement rules to text (case-insensitive).

    Args:
        text: Original text.
        replacements: Dict mapping patterns to replacements.

    Returns:
        Text with replacements applied.
    """
    if not replacements:
        return text

    for pattern, replacement in replacements.items():
        # Case-insensitive replacement
        text = re.sub(re.escape(pattern), replacement, text, flags=re.IGNORECASE)

    return text
