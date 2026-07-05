"""
speech_to_text.py — OpenAI Whisper Transcription Engine for VBCUA
Provides a cached, fault-tolerant interface to the Whisper ASR model.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level model cache — avoids reloading the neural network each call
# ---------------------------------------------------------------------------

_whisper_model: Any | None = None
_WHISPER_MODEL_SIZE: str = "tiny"


def _load_whisper_model() -> Any:
    """
    Load the Whisper model exactly once per process lifetime.
    Subsequent calls return the already-loaded model from the module cache.
    """
    global _whisper_model

    if _whisper_model is not None:
        return _whisper_model

    try:
        import whisper  # type: ignore[import]

        logger.info("Loading Whisper model '%s' — this may take a moment on first run.", _WHISPER_MODEL_SIZE)
        _whisper_model = whisper.load_model(_WHISPER_MODEL_SIZE)
        logger.info("Whisper model loaded successfully.")
    except ImportError as exc:
        raise RuntimeError(
            "The 'openai-whisper' package is not installed. "
            "Install it with: pip install openai-whisper"
        ) from exc

    return _whisper_model


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe the audio file at *file_path* using Whisper and return the
    cleaned transcript text.

    Args:
        file_path: Absolute or relative path to the WAV / MP3 / FLAC audio file.

    Returns:
        The normalised transcript string (leading/trailing whitespace stripped).

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        RuntimeError:      If the Whisper model cannot be loaded or transcription fails.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            f"Audio file not found at path: {file_path!r}"
        )

    model = _load_whisper_model()

    try:
        logger.info("Transcribing audio file: %s", file_path)
        result: dict = model.transcribe(
            file_path,
            fp16=False,          # FP16 disabled for broad CPU compatibility
            language="en",       # Force English for consistent output
            verbose=False,
        )
    except Exception as exc:
        logger.exception("Whisper transcription failed for file %r", file_path)
        raise RuntimeError(
            f"Transcription error for file '{file_path}': {exc}"
        ) from exc

    raw_text: str = result.get("text", "")

    # Normalise: collapse multiple internal spaces and strip outer whitespace
    cleaned_text: str = " ".join(raw_text.split())

    logger.info(
        "Transcription complete. Characters: %d, Words: %d",
        len(cleaned_text),
        len(cleaned_text.split()),
    )

    return cleaned_text
