"""
LumberLex — Lumber product name normalization library.

Quick start:
    from lumberlex import normalize
    result = normalize("Whitewood Stud 2x4")
    print(result.canonical_name)   # SPF
    print(result.confidence)       # 0.95
    print(result.model_dump_json())

For repeated calls in a long-running process, the module-level normalize()
caches the normalizer after the first call. For explicit lifecycle control
or custom data paths, use Normalizer.from_files() directly.
"""

from __future__ import annotations

import threading

from .evaluator import BatchEvaluator, EvaluationReport, RowResult
from .normalizer import Normalizer
from .schemas import AlternativeMatch, NormalizationResult

__all__ = [
    "normalize",
    "NormalizationResult",
    "AlternativeMatch",
    "Normalizer",
    "BatchEvaluator",
    "EvaluationReport",
    "RowResult",
]

# ── Module-level cached normalizer ────────────────────────────────────────────
# Initialized on the first call to normalize(). Subsequent calls are instant.
# The double-checked locking pattern makes initialization thread-safe without
# paying the lock cost on every call once the normalizer is ready.
# The Normalizer itself is stateless after initialization, so concurrent calls
# to normalize() are always safe.
_lock: threading.Lock = threading.Lock()
_default_normalizer: Normalizer | None = None


def normalize(raw: str) -> NormalizationResult:
    """
    Normalize a raw lumber product string using the default bundled data.

    First call initializes the normalizer by loading the bundled CSVs and
    building the in-memory lookup tables (~50ms). Subsequent calls use the
    cached instance and return instantly.

    For explicit lifecycle control or to use custom alias/canonical tables,
    instantiate Normalizer.from_files() directly instead.

    Args:
        raw: Raw lumber product name string (e.g. "Lowes Whitewood Stud 2x4").

    Returns:
        NormalizationResult with canonical name, confidence, treatment,
        detected size, explanation, and all other fields populated.

    Example:
        >>> from lumberlex import normalize
        >>> result = normalize("SYP PT 4x4x8")
        >>> result.canonical_name
        'Pressure Treated Southern Yellow Pine'
        >>> result.confidence
        0.95
    """
    global _default_normalizer
    if _default_normalizer is None:
        with _lock:
            if _default_normalizer is None:
                _default_normalizer = Normalizer.from_files()
    return _default_normalizer.normalize(raw)
