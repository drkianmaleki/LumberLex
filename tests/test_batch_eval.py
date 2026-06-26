"""
tests/test_batch_eval.py
Phase 6 Stage 2 — Batch evaluation regression assertions.

Runs the full 596-row evaluation against the live normalizer and asserts two
pass/fail thresholds loaded from config/thresholds.yml.

These tests are marked @pytest.mark.slow because they call the normalizer
on every row in the sample database (~5–30 seconds depending on hardware).

  Run slow tests only:   pytest -m slow
  Exclude slow tests:    pytest -m "not slow"   (default recommended)
  Run everything:        pytest
"""

import pytest

from lumberlex.config import BATCH_MIN_TOP1_ACCURACY, BATCH_MAX_FALSE_CONFIDENT_RATE
from lumberlex.evaluator import BatchEvaluator, EvaluationReport


# ---------------------------------------------------------------------------
# Marker — applied to every test in this module
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Session-scoped fixture
# Runs the 596-row evaluation exactly once; both tests share the result.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def report() -> EvaluationReport:
    """
    Loads the normalizer and sample database from their default file paths,
    runs the full batch evaluation, and returns the EvaluationReport.

    Session scope means the 596-row run happens once per pytest session
    regardless of how many tests consume this fixture.
    """
    evaluator = BatchEvaluator.from_files()
    return evaluator.run()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBatchEvaluation:
    """Regression assertions for the 596-row batch evaluation."""

    def test_top1_accuracy_above_floor(self, report: EvaluationReport) -> None:
        """Top-1 accuracy must stay at or above the configured floor.

        Live baseline established post-patch: 75.9% (447 / 589 known rows).
        Floor is set at 75.0% — low enough to tolerate minor alias-table
        edits, strict enough to catch any meaningful normalizer regression.

        Threshold source: config/thresholds.yml  batch_evaluation.min_top1_accuracy
        """
        assert report.top1_accuracy >= BATCH_MIN_TOP1_ACCURACY, (
            f"Top-1 accuracy {report.top1_accuracy:.1%} is below the required "
            f"floor of {BATCH_MIN_TOP1_ACCURACY:.1%}. "
            f"({report.top1_correct} / {report.known_rows} known rows correct.) "
            f"Run `python scripts/batch_eval.py` for a full per-row breakdown."
        )

    def test_zero_false_confident_errors(self, report: EvaluationReport) -> None:
        """False-confident error count must be exactly zero.

        A false-confident error is defined as:
            confidence >= 0.80  AND  normalized_name != expected_canonical
            AND NOT is_unknown_row

        This is the primary safety metric for the normalizer. It is always
        preferable to flag an uncertain result for manual review than to
        return the wrong species with high confidence.

        Threshold source: config/thresholds.yml  batch_evaluation.max_false_confident_rate
        """
        assert report.false_confident_count == 0, (
            f"Found {report.false_confident_count} false-confident error(s) — "
            f"wrong result(s) returned with confidence >= 0.80. "
            f"Run `python scripts/batch_eval.py` for per-row details."
        )
