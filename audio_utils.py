"""
audio_utils.py — Digital Signal Processing & Feature Extraction for VBCUA
Provides waveform-level analytics (energy, silence, zero crossings)
and linguistic filler-word statistics derived from the transcript.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import librosa  # type: ignore[import]
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SAMPLE_RATE: int = 22_050
_SILENCE_TOP_DB: float = 25.0

# Ordered from most to least common — matched case-insensitively
_FILLER_WORDS: list[str] = [
    "um",
    "uh",
    "like",
    "so",
    "actually",
    "basically",
]

# Pre-compile a single regex for all filler words (whole-word, case-insensitive)
_FILLER_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _FILLER_WORDS) + r")\b",
    re.IGNORECASE,
)

# Regex to strip all non-alphanumeric characters except apostrophes
_PUNCTUATION_STRIP_PATTERN: re.Pattern[str] = re.compile(r"[^\w\s']")


# ---------------------------------------------------------------------------
# Signal feature extraction
# ---------------------------------------------------------------------------


def extract_signal_features(file_path: str) -> dict[str, float]:
    """
    Load an audio file and compute acoustic / signal-level features.

    Args:
        file_path: Path to an audio file supported by librosa (WAV, MP3, FLAC…).

    Returns:
        A dictionary with the following float keys:

        ``duration_sec``       – Total duration of the audio clip in seconds.
        ``rms_energy``         – Mean RMS energy across all short-time frames.
        ``zero_crossing_rate`` – Mean zero-crossing rate across all frames.
        ``pause_ratio``        – Fraction of the clip that consists of silence
                                  (i.e. ``silent_duration / total_duration``).

    Raises:
        RuntimeError: If the file cannot be loaded by librosa.
    """
    try:
        y: np.ndarray
        sr: int
        y, sr = librosa.load(file_path, sr=_SAMPLE_RATE, mono=True)
    except Exception as exc:
        logger.exception("librosa failed to load audio file %r", file_path)
        raise RuntimeError(
            f"Could not load audio from '{file_path}': {exc}"
        ) from exc

    # --- Duration -------------------------------------------------------
    duration_sec: float = float(librosa.get_duration(y=y, sr=sr))

    # --- RMS Energy ------------------------------------------------------
    # Shape: (1, n_frames)  →  take mean across the frame axis
    rms_frames: np.ndarray = librosa.feature.rms(y=y)
    rms_energy: float = float(np.mean(rms_frames))

    # --- Zero Crossing Rate ---------------------------------------------
    # Shape: (1, n_frames)  →  take mean across the frame axis
    zcr_frames: np.ndarray = librosa.feature.zero_crossing_rate(y=y)
    zero_crossing_rate: float = float(np.mean(zcr_frames))

    # --- Pause Ratio -----------------------------------------------------
    # librosa.effects.split returns an array of (start, end) sample indices
    # where audio is *above* the silence threshold.
    non_silent_intervals: np.ndarray = librosa.effects.split(y, top_db=_SILENCE_TOP_DB)

    total_non_silent_samples: int = 0
    for interval in non_silent_intervals:
        start_sample: int = int(interval[0])
        end_sample: int = int(interval[1])
        total_non_silent_samples += end_sample - start_sample

    total_samples: int = len(y)
    silent_samples: int = max(0, total_samples - total_non_silent_samples)

    pause_ratio: float
    if total_samples > 0:
        pause_ratio = float(silent_samples / total_samples)
    else:
        pause_ratio = 0.0

    features: dict[str, float] = {
        "duration_sec": duration_sec,
        "rms_energy": rms_energy,
        "zero_crossing_rate": zero_crossing_rate,
        "pause_ratio": pause_ratio,
    }

    logger.info(
        "Signal features extracted — duration=%.2fs, rms=%.6f, zcr=%.6f, pause=%.4f",
        duration_sec,
        rms_energy,
        zero_crossing_rate,
        pause_ratio,
    )

    return features


# ---------------------------------------------------------------------------
# Filler-word statistics
# ---------------------------------------------------------------------------


def calculate_filler_stats(text: str) -> dict[str, Any]:
    """
    Analyse a transcript for filler-word usage.

    The function:
    1. Strips punctuation while preserving contractions.
    2. Tokenises on whitespace.
    3. Counts total word tokens.
    4. Counts tokens that match any filler word (whole-word, case-insensitive).
    5. Computes ``filler_ratio`` safely (handles zero-length transcripts).

    Args:
        text: The raw transcript string.

    Returns:
        A dictionary with keys:

        ``filler_word_count`` (int)   – Number of filler-word occurrences.
        ``total_words``       (int)   – Total number of word tokens.
        ``filler_ratio``      (float) – ``filler_count / total_words`` or 0.0.
        ``filler_breakdown``  (dict)  – Per-filler-word occurrence counts.
    """
    if not text or not text.strip():
        return {
            "filler_word_count": 0,
            "total_words": 0,
            "filler_ratio": 0.0,
            "filler_breakdown": {w: 0 for w in _FILLER_WORDS},
        }

    # Strip punctuation (preserve apostrophes for contractions)
    normalised: str = _PUNCTUATION_STRIP_PATTERN.sub("", text)

    # Tokenise on whitespace
    tokens: list[str] = normalised.split()
    total_words: int = len(tokens)

    if total_words == 0:
        return {
            "filler_word_count": 0,
            "total_words": 0,
            "filler_ratio": 0.0,
            "filler_breakdown": {w: 0 for w in _FILLER_WORDS},
        }

    # Count total filler occurrences using the pre-compiled pattern
    all_matches: list[str] = _FILLER_PATTERN.findall(normalised)
    filler_word_count: int = len(all_matches)

    # Per-word breakdown
    filler_breakdown: dict[str, int] = {word: 0 for word in _FILLER_WORDS}
    for match in all_matches:
        canonical: str = match.lower()
        if canonical in filler_breakdown:
            filler_breakdown[canonical] += 1

    filler_ratio: float = filler_word_count / total_words

    logger.info(
        "Filler stats — total_words=%d, filler_count=%d, ratio=%.4f",
        total_words,
        filler_word_count,
        filler_ratio,
    )

    return {
        "filler_word_count": filler_word_count,
        "total_words": total_words,
        "filler_ratio": filler_ratio,
        "filler_breakdown": filler_breakdown,
    }
