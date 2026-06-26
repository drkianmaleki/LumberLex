"""
LumberLex — Configuration Loader

Reads thresholds.yml once at import time and exposes all tunable thresholds
as typed module-level constants. Downstream modules import these constants
directly — they never read the YAML file themselves.

    from lumberlex.config import MANUAL_REVIEW_THRESHOLD, CONFIDENCE_EXACT_MATCH

!! Path resolution — Option A (dual-file) !!

Two locations are checked in order:

  1. Developer path  — config/thresholds.yml at the project root.
     Present when the package is installed in editable mode (pip install -e .)
     from a cloned repository. Editing this file takes effect immediately on
     the next import, which is the intended developer workflow.

  2. Bundled fallback — src/lumberlex/_data/thresholds.yml inside the package.
     Used when the library is installed from a wheel (pip install lumberlex)
     and no project-root config/ directory exists.

Both files must contain identical values. The project-root file is the
developer's copy; the bundled file is the deployed copy. Update both when
changing threshold values before releasing a new version.

To adjust a threshold during development: edit config/thresholds.yml and
restart. No source code changes required.
"""

from pathlib import Path

import yaml

# ── Path resolution (Option A) ────────────────────────────────────────────────
# src/lumberlex/config.py → src/lumberlex/ → src/ → project root → config/
_REPO_CONFIG    = Path(__file__).parent.parent.parent / "config" / "thresholds.yml"
_BUNDLED_CONFIG = Path(__file__).parent / "_data" / "thresholds.yml"
_CONFIG_PATH    = _REPO_CONFIG if _REPO_CONFIG.exists() else _BUNDLED_CONFIG


def _load() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"\nLumberLex config file not found.\n"
            f"  Checked : {_REPO_CONFIG}\n"
            f"  Checked : {_BUNDLED_CONFIG}\n"
            f"\nThe bundled config should always be present. If you are working\n"
            f"from a cloned repository, ensure the package is installed:\n"
            f"    pip install -e .\n"
            f"See README.md — Configuration section for details."
        )
    with open(_CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"\nLumberLex config file is empty or not valid YAML.\n"
            f"  Path: {_CONFIG_PATH}"
        )
    return data


_cfg = _load()

# ── Fuzzy matching ────────────────────────────────────────────────────────────
MANUAL_REVIEW_THRESHOLD: int = int(
    _cfg["fuzzy_matching"]["manual_review_threshold"]
)

# ── Confidence bands ──────────────────────────────────────────────────────────
CONFIDENCE_EXACT_MATCH: float         = float(_cfg["confidence_bands"]["exact_match"])
CONFIDENCE_SCORE_90_PLUS: float       = float(_cfg["confidence_bands"]["score_90_plus"])
CONFIDENCE_SCORE_80_TO_89: float      = float(_cfg["confidence_bands"]["score_80_to_89"])
CONFIDENCE_SCORE_70_TO_79: float      = float(_cfg["confidence_bands"]["score_70_to_79"])
CONFIDENCE_SUB_THRESHOLD_SCALE: float = float(_cfg["confidence_bands"]["sub_threshold_scale"])

# ── Batch evaluation pass/fail thresholds (Phase 6 Stage 2) ──────────────────
BATCH_MIN_TOP1_ACCURACY: float        = float(_cfg["batch_evaluation"]["min_top1_accuracy"])
BATCH_MAX_FALSE_CONFIDENT_RATE: float = float(_cfg["batch_evaluation"]["max_false_confident_rate"])
