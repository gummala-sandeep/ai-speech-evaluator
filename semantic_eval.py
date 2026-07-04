"""
semantic_eval.py — NLP Semantic Similarity Engine for VBCUA
Uses Sentence-Transformers to embed student and reference texts
and computes their cosine similarity on a [0.0, 1.0] scale.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level model cache
# ---------------------------------------------------------------------------

_st_model: Any | None = None
_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"


def _load_sentence_transformer() -> Any:
    """
    Load the SentenceTransformer model once per process and cache it in the
    module-level ``_st_model`` variable.

    Returns:
        A ``SentenceTransformer`` instance ready for inference.

    Raises:
        RuntimeError: If the ``sentence-transformers`` package is unavailable.
    """
    global _st_model

    if _st_model is not None:
        return _st_model

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]

        logger.info("Loading SentenceTransformer model: %s", _MODEL_NAME)
        _st_model = SentenceTransformer(_MODEL_NAME)
        logger.info("SentenceTransformer model loaded successfully.")
    except ImportError as exc:
        raise RuntimeError(
            "The 'sentence-transformers' package is not installed. "
            "Install it with: pip install sentence-transformers"
        ) from exc

    return _st_model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_semantic_similarity(student_text: str, reference_text: str) -> float:
    """
    Compute the cosine similarity between *student_text* and *reference_text*
    using high-dimensional dense embeddings from the MiniLM-L6-v2 model.

    Algorithm
    ---------
    1. Encode both texts into embedding vectors of dimension 384.
    2. Compute cosine similarity:
       ``cos(θ) = (A · B) / (||A|| × ||B||)``
    3. Clip the result to ``[0.0, 1.0]`` (handles floating-point rounding
       that may push raw values marginally outside this range).

    Args:
        student_text:   The transcribed student explanation.
        reference_text: The ground-truth concept definition to compare against.

    Returns:
        A float in ``[0.0, 1.0]`` where 1.0 represents perfect alignment
        and 0.0 represents complete semantic divergence.

    Raises:
        ValueError:   If either input is empty after stripping.
        RuntimeError: If the embedding model fails to load or encode.
    """
    student_clean: str = student_text.strip()
    reference_clean: str = reference_text.strip()

    if not student_clean:
        logger.warning("student_text is empty — returning similarity 0.0")
        return 0.0

    if not reference_clean:
        logger.warning("reference_text is empty — returning similarity 0.0")
        return 0.0

    model = _load_sentence_transformer()

    try:
        # Encode both texts in a single batched call for efficiency
        embeddings: np.ndarray = model.encode(
            [student_clean, reference_clean],
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2-normalised → dot product == cosine
            show_progress_bar=False,
        )
    except Exception as exc:
        logger.exception("Embedding failed for the provided texts.")
        raise RuntimeError(f"SentenceTransformer encoding error: {exc}") from exc

    student_vec: np.ndarray = embeddings[0]
    reference_vec: np.ndarray = embeddings[1]

    # Because we requested L2-normalised embeddings, cosine similarity
    # reduces to a plain dot product, which is computationally cheaper.
    raw_similarity: float = float(np.dot(student_vec, reference_vec))

    # Clip to strict [0.0, 1.0] bounds to guard against floating-point drift
    similarity: float = float(np.clip(raw_similarity, 0.0, 1.0))

    logger.info(
        "Semantic similarity computed — raw=%.6f, clipped=%.6f",
        raw_similarity,
        similarity,
    )

    return similarity
