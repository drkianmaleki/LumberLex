"""
src/lumberlex/evaluator.py

Batch evaluation logic for LumberLex.  Runs the full normalizer pipeline
against lumberlex_sample_database.csv and computes accuracy metrics.

Public API (used by scripts/batch_eval.py and tests/test_batch_eval.py):

    evaluator = BatchEvaluator.from_files()
    report    = evaluator.run()

    # Inject a pre-built Normalizer (pytest fixtures — no filesystem I/O):
    evaluator = BatchEvaluator(normalizer)
    report    = evaluator.run(database_path)
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from .data_layer import DEFAULT_ALIASES_PATH, DEFAULT_CANONICALS_PATH
from .normalizer import Normalizer

# ── Default paths ─────────────────────────────────────────────────────────────
#
# Canonicals and aliases: use the bundled defaults from data_layer.
#
# Sample database: NOT bundled (it is a development/test resource, not part
# of the library's core data). Path is resolved relative to the project root
# so that scripts/batch_eval.py finds it when run from a cloned repository.
#
# Path depth note: this file lives at src/lumberlex/evaluator.py, so:
#   Path(__file__).parent              → src/lumberlex/
#   Path(__file__).parent.parent       → src/
#   Path(__file__).parent.parent.parent → project root
#
# _DATABASE_DEFAULT works correctly when the package is installed in editable
# mode (pip install -e .) from the project root. It will not resolve correctly
# for non-editable (wheel) installs because the database is not bundled.
_PROJECT_ROOT     = Path(__file__).parent.parent.parent
_DATABASE_DEFAULT = _PROJECT_ROOT / "data" / "lumberlex_sample_database.csv"

# ── Module constants ──────────────────────────────────────────────────────────
# The sentinel used in the database for rows that should not be matched.
_DB_UNKNOWN_CANONICAL = "UNKNOWN / MANUAL REVIEW"

# Exported so tests and scripts can import the same value without duplicating it.
FALSE_CONFIDENT_THRESHOLD: float = 0.80


# ── Treatment normalisation ───────────────────────────────────────────────────
def _normalize_db_treatment(value: str) -> Optional[str]:
    """
    Map the sample database's treatment string to the same type as
    NormalizationResult.treatment.

    Database values:
        'Pressure Treated'  →  'Pressure Treated'
        'None'              →  None   (untreated row)
        'Unknown'           →  None   (only on UNKNOWN / MANUAL REVIEW rows;
                                       treatment comparison is skipped for those)
    """
    return "Pressure Treated" if value == "Pressure Treated" else None


# ── Internal types (plain dataclasses — not Pydantic; never serialised) ───────

@dataclass
class RowResult:
    """Evaluation outcome for a single database row."""

    record_id: str
    raw_product_name: str
    expected_canonical: str           # from database canonical_name column
    normalized_name: str              # from NormalizationResult
    confidence: float
    manual_review_required: bool

    # Row classification
    is_unknown_row: bool              # expected_canonical == 'UNKNOWN / MANUAL REVIEW'
    is_top1_correct: bool             # normalized_name == expected_canonical;
                                      # always False for unknown rows
    is_top3_correct: bool             # top-1 OR correct canonical in alternatives;
                                      # always False for unknown rows
    is_false_confident: bool          # confidence >= threshold AND wrong canonical
                                      # on a known row

    # Treatment (secondary metric)
    expected_treatment: Optional[str] # None for unknown rows
    actual_treatment: Optional[str]   # from NormalizationResult.treatment
    treatment_match: Optional[bool]   # None for unknown rows

    # Unknown-row flag check
    review_flag_correct: Optional[bool]  # None for known rows;
                                         # True if unknown row triggered manual_review_required


@dataclass
class EvaluationReport:
    """Aggregate results from a full batch run."""

    total_rows: int                   # always 596
    known_rows: int                   # 589 — denominator for accuracy metrics
    unknown_rows: int                 # 7 — evaluated separately

    # ── Primary metrics (known rows only) ─────────────────────────────────────
    top1_correct: int
    top1_accuracy: float              # top1_correct / known_rows
    top3_correct: int
    top3_accuracy: float              # top3_correct / known_rows
    avg_confidence_correct: float     # mean confidence over top-1 correct rows
    manual_review_count: int          # over all 596 rows
    manual_review_rate: float         # manual_review_count / total_rows
    false_confident_count: int
    false_confident_rate: float       # false_confident_count / known_rows

    # ── Secondary metrics (known rows only) ──────────────────────────────────
    treatment_correct: int
    treatment_accuracy: float

    # ── Unknown-row check ─────────────────────────────────────────────────────
    unknown_rows_flagged: int         # of the 7, how many had manual_review_required=True

    # ── Full per-row detail (used by the visual script) ───────────────────────
    row_results: list[RowResult] = field(default_factory=list)


# ── BatchEvaluator ────────────────────────────────────────────────────────────

class BatchEvaluator:
    """
    Orchestrates a full batch run of the normalizer against the sample database.

    Standard call site (scripts/batch_eval.py and pytest):
        evaluator = BatchEvaluator.from_files()
        report    = evaluator.run()

    Lightweight call site (pytest — inject a pre-built Normalizer to avoid
    per-test filesystem I/O, mirroring the Normalizer.from_files() pattern):
        normalizer = Normalizer(alias_index, canonical_index,
                                alias_token_set, display_aliases)
        evaluator  = BatchEvaluator(normalizer)
        report     = evaluator.run(database_path)
    """

    def __init__(self, normalizer: Normalizer) -> None:
        self._normalizer = normalizer

    @classmethod
    def from_files(
        cls,
        canonicals_path: str | Path = DEFAULT_CANONICALS_PATH,
        aliases_path: str | Path = DEFAULT_ALIASES_PATH,
    ) -> "BatchEvaluator":
        """Load CSVs, build the normalizer, return a ready BatchEvaluator."""
        normalizer = Normalizer.from_files(str(canonicals_path), str(aliases_path))
        return cls(normalizer)

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, database_path: str | Path = _DATABASE_DEFAULT) -> EvaluationReport:
        """
        Load the sample database, run every raw_product_name through the
        normalizer, and return an EvaluationReport with full row-level detail.
        """
        df = pd.read_csv(database_path, dtype=str).fillna("")
        row_results = [self._evaluate_row(row) for _, row in df.iterrows()]
        return self._aggregate(row_results)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _evaluate_row(self, row: pd.Series) -> RowResult:
        """Run one database row through the normalizer and classify the result."""
        record_id = row["record_id"]
        raw_product_name = row["raw_product_name"]
        expected_canonical = row["canonical_name"]
        is_unknown_row = expected_canonical == _DB_UNKNOWN_CANONICAL

        result = self._normalizer.normalize(raw_product_name)

        # Top-1: exact canonical match (never possible for unknown rows)
        is_top1_correct = (
            not is_unknown_row
            and result.normalized_name == expected_canonical
        )

        # Top-3: top-1 OR correct canonical appears in alternative_matches
        is_top3_correct = is_top1_correct or (
            not is_unknown_row
            and any(
                alt.canonical_name == expected_canonical
                for alt in result.alternative_matches
            )
        )

        # False-confident: wrong canonical on a known row with high confidence
        is_false_confident = (
            not is_unknown_row
            and not is_top1_correct
            and result.confidence >= FALSE_CONFIDENT_THRESHOLD
        )

        # Treatment: skip unknown rows (their DB value is 'Unknown')
        expected_treatment = (
            None
            if is_unknown_row
            else _normalize_db_treatment(row["treatment"])
        )
        actual_treatment = result.treatment
        treatment_match = (
            None
            if is_unknown_row
            else (actual_treatment == expected_treatment)
        )

        # Unknown-row check: did the normalizer correctly flag it for review?
        review_flag_correct = (
            result.manual_review_required if is_unknown_row else None
        )

        return RowResult(
            record_id=record_id,
            raw_product_name=raw_product_name,
            expected_canonical=expected_canonical,
            normalized_name=result.normalized_name,
            confidence=result.confidence,
            manual_review_required=result.manual_review_required,
            is_unknown_row=is_unknown_row,
            is_top1_correct=is_top1_correct,
            is_top3_correct=is_top3_correct,
            is_false_confident=is_false_confident,
            expected_treatment=expected_treatment,
            actual_treatment=actual_treatment,
            treatment_match=treatment_match,
            review_flag_correct=review_flag_correct,
        )

    @staticmethod
    def _aggregate(row_results: list[RowResult]) -> EvaluationReport:
        """Aggregate per-row results into an EvaluationReport."""
        known = [r for r in row_results if not r.is_unknown_row]
        unknown = [r for r in row_results if r.is_unknown_row]
        known_count = len(known)
        total = len(row_results)

        top1_correct = sum(1 for r in known if r.is_top1_correct)
        top3_correct = sum(1 for r in known if r.is_top3_correct)

        correct_confidences = [r.confidence for r in known if r.is_top1_correct]
        avg_confidence_correct = (
            statistics.mean(correct_confidences) if correct_confidences else 0.0
        )

        manual_review_count = sum(1 for r in row_results if r.manual_review_required)
        false_confident_count = sum(1 for r in known if r.is_false_confident)
        treatment_correct = sum(1 for r in known if r.treatment_match is True)
        unknown_rows_flagged = sum(1 for r in unknown if r.review_flag_correct)

        return EvaluationReport(
            total_rows=total,
            known_rows=known_count,
            unknown_rows=len(unknown),
            top1_correct=top1_correct,
            top1_accuracy=top1_correct / known_count if known_count else 0.0,
            top3_correct=top3_correct,
            top3_accuracy=top3_correct / known_count if known_count else 0.0,
            avg_confidence_correct=avg_confidence_correct,
            manual_review_count=manual_review_count,
            manual_review_rate=manual_review_count / total if total else 0.0,
            false_confident_count=false_confident_count,
            false_confident_rate=(
                false_confident_count / known_count if known_count else 0.0
            ),
            treatment_correct=treatment_correct,
            treatment_accuracy=treatment_correct / known_count if known_count else 0.0,
            unknown_rows_flagged=unknown_rows_flagged,
            row_results=row_results,
        )
