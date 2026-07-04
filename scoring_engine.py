"""
scoring_engine.py — Rule-Based Evaluation Matrix for VBCUA
Implements a deterministic, weighted grading function that combines
semantic alignment, delivery fluency, and audio signal quality into
a single interpretable score and understanding tier.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Threshold constants — centralised for maintainability
# ---------------------------------------------------------------------------

# Semantic similarity thresholds
_SIM_HIGH: float = 0.7
_SIM_MID: float = 0.4

# Filler-word ratio threshold (fraction of total words that are fillers)
_FILLER_CLEAN: float = 0.05

# Pause / silence ratio threshold (fraction of total audio that is silent)
_PAUSE_BALANCED: float = 0.25

# RMS energy threshold (linear amplitude, not dB)
_ENERGY_CONFIDENT: float = 0.01

# Score classification thresholds
_STRONG_THRESHOLD: int = 80
_MODERATE_THRESHOLD: int = 50

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_understanding(
    similarity: float,
    cross_similarity: float,
    filler_ratio: float,
    pause_ratio: float,
    rms_energy: float,
    topic_match: bool = True,
) -> tuple[int, str, str]:
    """
    Compute a deterministic composite understanding score from five metrics.

    Scoring breakdown
    -----------------
    +----------------------------------+----------+----------+
    | Criterion                        | High pts | Low pts  |
    +==================================+==========+==========+
    | Bi-Encoder similarity >0.7       |    25    |          |
    | Bi-Encoder similarity >0.4       |    15    |          |
    | Bi-Encoder similarity ≤0.4       |          |     5    |
    +----------------------------------+----------+----------+
    | Cross-Encoder similarity >0.7    |    25    |          |
    | Cross-Encoder similarity >0.4    |    15    |          |
    | Cross-Encoder similarity ≤0.4    |          |     5    |
    +----------------------------------+----------+----------+
    | Filler ratio < 0.05              |    20    |    10    |
    +----------------------------------+----------+----------+
    | Pause ratio < 0.25               |    15    |     5    |
    +----------------------------------+----------+----------+
    | RMS energy > 0.01                |    15    |     5    |
    +----------------------------------+----------+----------+
    | Max achievable score             |   100    |          |
    +----------------------------------+----------+----------+

    Classification tiers
    --------------------
    * **Strong Understanding**   — score ≥ 80  (hex: #2ecc71)
    * **Moderate Understanding** — score ≥ 50  (hex: #f39c12)
    * **Poor Understanding**     — score < 50  (hex: #e74c3c)
    * **Topic Mismatch**         — topic_match is False (score = 0, hex: #e74c3c)

    Args:
        similarity:       Bi-Encoder similarity in ``[0.0, 1.0]``.
        cross_similarity: Cross-Encoder similarity in ``[0.0, 1.0]``.
        filler_ratio:     Fraction of total words that are filler words.
        pause_ratio:      Fraction of total audio duration that is silence.
        rms_energy:       Mean RMS energy amplitude of the audio signal.
        topic_match:      Boolean indicating if the student's topic matches.

    Returns:
        A three-tuple ``(score, understanding_label, colour_hex)`` where:
        * ``score``               – Integer score in ``[0, 100]``.
        * ``understanding_label`` – Human-readable tier string.
        * ``colour_hex``          – Hex colour code for UI rendering.
    """
    if not topic_match:
        logger.warning("Topic Guardrail triggered Topic Mismatch — returning score 0")
        return (0, "Topic Mismatch", "#e74c3c")

    score: int = 0

    # ------------------------------------------------------------------
    # 1a. Bi-Encoder Content Evaluation (max 25 pts)
    # ------------------------------------------------------------------
    if similarity > _SIM_HIGH:
        score += 25
        logger.debug("Bi-Encoder similarity %.4f > %.1f  → +25 pts", similarity, _SIM_HIGH)
    elif similarity > _SIM_MID:
        score += 15
        logger.debug("Bi-Encoder similarity %.4f > %.1f  → +15 pts", similarity, _SIM_MID)
    else:
        score += 5
        logger.debug("Bi-Encoder similarity %.4f ≤ %.1f  → +5 pts", similarity, _SIM_MID)

    # ------------------------------------------------------------------
    # 1b. Cross-Encoder Content Evaluation (max 25 pts)
    # ------------------------------------------------------------------
    if cross_similarity > _SIM_HIGH:
        score += 25
        logger.debug("Cross-Encoder similarity %.4f > %.1f  → +25 pts", cross_similarity, _SIM_HIGH)
    elif cross_similarity > _SIM_MID:
        score += 15
        logger.debug("Cross-Encoder similarity %.4f > %.1f  → +15 pts", cross_similarity, _SIM_MID)
    else:
        score += 5
        logger.debug("Cross-Encoder similarity %.4f ≤ %.1f  → +5 pts", cross_similarity, _SIM_MID)

    # ------------------------------------------------------------------
    # 2. Filler Word Penalty (max 20 pts)
    # ------------------------------------------------------------------
    if filler_ratio < _FILLER_CLEAN:
        score += 20
        logger.debug("Filler ratio %.4f < %.2f → +20 pts", filler_ratio, _FILLER_CLEAN)
    else:
        score += 10
        logger.debug("Filler ratio %.4f ≥ %.2f → +10 pts", filler_ratio, _FILLER_CLEAN)

    # ------------------------------------------------------------------
    # 3. Pause Balance (max 15 pts)
    # ------------------------------------------------------------------
    if pause_ratio < _PAUSE_BALANCED:
        score += 15
        logger.debug("Pause ratio %.4f < %.2f → +15 pts", pause_ratio, _PAUSE_BALANCED)
    else:
        score += 5
        logger.debug("Pause ratio %.4f ≥ %.2f → +5 pts", pause_ratio, _PAUSE_BALANCED)

    # ------------------------------------------------------------------
    # 4. Audio Delivery (max 15 pts)
    # ------------------------------------------------------------------
    if rms_energy > _ENERGY_CONFIDENT:
        score += 15
        logger.debug("RMS energy %.6f > %.4f → +15 pts", rms_energy, _ENERGY_CONFIDENT)
    else:
        score += 5
        logger.debug("RMS energy %.6f ≤ %.4f → +5 pts", rms_energy, _ENERGY_CONFIDENT)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    understanding_label: str
    colour_hex: str

    if score >= _STRONG_THRESHOLD:
        understanding_label = "Strong Understanding"
        colour_hex = "#2ecc71"
    elif score >= _MODERATE_THRESHOLD:
        understanding_label = "Moderate Understanding"
        colour_hex = "#f39c12"
    else:
        understanding_label = "Poor Understanding"
        colour_hex = "#e74c3c"

    logger.info(
        "Evaluation complete — score=%d, level=%r, colour=%s",
        score,
        understanding_label,
        colour_hex,
    )

    return (score, understanding_label, colour_hex)
