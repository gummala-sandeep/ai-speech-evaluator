"""
semantic_eval.py — NLP Semantic Similarity Engine for VBCUA
Uses Sentence-Transformers to embed student and reference texts
and computes their cosine similarity on a [0.0, 1.0] scale.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level model cache
# ---------------------------------------------------------------------------

_st_model: Any | None = None
_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"

_ce_model: Any | None = None
_CE_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"


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


def _load_cross_encoder() -> Any:
    """
    Load the CrossEncoder model once per process and cache it in the
    module-level ``_ce_model`` variable.
    """
    global _ce_model

    if _ce_model is not None:
        return _ce_model

    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import]

        logger.info("Loading CrossEncoder model: %s", _CE_MODEL_NAME)
        _ce_model = CrossEncoder(_CE_MODEL_NAME)
        logger.info("CrossEncoder model loaded successfully.")
    except ImportError as exc:
        raise RuntimeError(
            "The 'sentence-transformers' package is not installed. "
            "Install it with: pip install sentence-transformers"
        ) from exc

    return _ce_model


def compute_cross_encoder_similarity(student_text: str, reference_text: str) -> float:
    """
    Compute a precise similarity score between student_text and reference_text
    using the Cross-Encoder model. Uses a sigmoid to scale logits to [0.0, 1.0].
    """
    student_clean: str = student_text.strip()
    reference_clean: str = reference_text.strip()

    if not student_clean or not reference_clean:
        logger.warning("Empty text passed to Cross-Encoder similarity.")
        return 0.0

    model = _load_cross_encoder()

    try:
        # CrossEncoder predicts on pairs: [(text1, text2)]
        logit = float(model.predict([(student_clean, reference_clean)])[0])
        # Map raw logits to [0.0, 1.0] using sigmoid
        prob = 1.0 / (1.0 + math.exp(-logit))
        similarity = float(np.clip(prob, 0.0, 1.0))
    except Exception as exc:
        logger.exception("Cross-Encoder prediction failed.")
        raise RuntimeError(f"CrossEncoder error: {exc}") from exc

    logger.info(
        "Cross-Encoder similarity computed — logit=%.6f, scaled=%.6f",
        logit,
        similarity,
    )

    return similarity


# Centralized Stopwords list to extract concept core vocabulary
STOPWORDS = {
    "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can", "can't", "cannot",
    "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each",
    "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd",
    "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me",
    "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll",
    "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while",
    "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves"
}


def verify_topic_guardrail(student_text: str, reference_text: str) -> tuple[bool, int, int]:
    """
    Verify if the student's transcript contains core vocabulary from the concept_text.
    Returns: (is_match, overlap_count, threshold)
    """
    # Clean text to keep only alphanumeric characters and split to lowercased words
    ref_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', reference_text.lower()))
    student_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', student_text.lower()))
    
    # Filter core vocab from reference concept
    core_vocab = {w for w in ref_words if w not in STOPWORDS}
    
    # Overlap
    matched = core_vocab.intersection(student_words)
    
    # Threshold: min of 2 and core_vocab size
    threshold = min(2, len(core_vocab))
    is_match = len(matched) >= threshold
    
    logger.info(
        "Topic Guardrail check — core_vocab=%r, matched=%r, threshold=%d, status=%s",
        core_vocab,
        matched,
        threshold,
        "PASS" if is_match else "FAIL"
    )
    
    return is_match, len(matched), threshold
