"""
scripts/batch_eval.py

Visual batch evaluation runner for LumberLex.

Runs all 596 rows of lumberlex_sample_database.csv through the live normalizer
and prints a formatted evaluation report. Review the numbers here before
proceeding to Stage 2 (config/thresholds.yml + tests/test_batch_eval.py).

Usage:
    python scripts/batch_eval.py
"""

from __future__ import annotations

from lumberlex.evaluator import (
    BatchEvaluator,
    EvaluationReport,
    FALSE_CONFIDENT_THRESHOLD,
)

_WIDTH = 56                # print width for rule lines
_LOW_CONF_DISPLAY = 10     # how many bottom-confidence known rows to show


# ── Formatting helpers ────────────────────────────────────────────────────────

def _rule(char: str = "═") -> None:
    print(char * _WIDTH)


def _section(title: str) -> None:
    print()
    print(f"  {title}")
    print("  " + "─" * (_WIDTH - 2))


def _metric(label: str, value: str) -> None:
    print(f"  {label:<30}: {value}")


# ── Report printer ────────────────────────────────────────────────────────────

def print_report(report: EvaluationReport) -> None:
    _rule()
    print(f"  LumberLex — Batch Evaluation Report")
    print(f"  {report.total_rows} rows  |  "
          f"{report.known_rows} known  |  "
          f"{report.unknown_rows} UNKNOWN / MANUAL REVIEW")
    _rule()

    # ── Primary metrics ───────────────────────────────────────────────────────
    _section("PRIMARY METRICS  (known rows: {})".format(report.known_rows))
    _metric(
        "Top-1 accuracy",
        f"{report.top1_correct} / {report.known_rows}  =  "
        f"{report.top1_accuracy:.1%}",
    )
    _metric(
        "Top-3 accuracy",
        f"{report.top3_correct} / {report.known_rows}  =  "
        f"{report.top3_accuracy:.1%}",
    )
    _metric("Avg confidence (correct)", f"{report.avg_confidence_correct:.3f}")
    _metric(
        "Manual review rate",
        f"{report.manual_review_rate:.1%}  "
        f"({report.manual_review_count} / {report.total_rows})",
    )
    fc_flag = "✓" if report.false_confident_count == 0 else "✗"
    _metric(
        "False-confident errors",
        f"  {report.false_confident_count} / {report.known_rows}  =  "
        f"{report.false_confident_rate:.1%}  {fc_flag}",
    )

    # ── Secondary metrics ─────────────────────────────────────────────────────
    _section("SECONDARY METRICS")
    _metric(
        "Treatment accuracy",
        f"{report.treatment_correct} / {report.known_rows}  =  "
        f"{report.treatment_accuracy:.1%}",
    )

    # ── UNKNOWN / MANUAL REVIEW rows ──────────────────────────────────────────
    _section(f"UNKNOWN / MANUAL REVIEW ROWS  ({report.unknown_rows} rows)")
    flag = "✓" if report.unknown_rows_flagged == report.unknown_rows else "✗"
    _metric(
        "Correctly flagged",
        f"{report.unknown_rows_flagged} / {report.unknown_rows}  {flag}",
    )

    # ── False-confident errors ────────────────────────────────────────────────
    _section("FALSE-CONFIDENT ERRORS")
    false_confident = [r for r in report.row_results if r.is_false_confident]
    if not false_confident:
        print(f"  None  ✓")
    else:
        for r in false_confident:
            print(
                f"  {r.record_id}  |  "
                f"{r.raw_product_name[:46]:<46}  |  "
                f"got: {r.normalized_name}  |  "
                f"expected: {r.expected_canonical}  |  "
                f"conf: {r.confidence:.3f}"
            )

    # ── Lowest-confidence known rows ──────────────────────────────────────────
    _section(f"LOWEST CONFIDENCE — KNOWN ROWS  (bottom {_LOW_CONF_DISPLAY})")
    known = [r for r in report.row_results if not r.is_unknown_row]
    bottom = sorted(known, key=lambda r: r.confidence)[:_LOW_CONF_DISPLAY]
    for r in bottom:
        ok = "✓" if r.is_top1_correct else "✗"
        review = "REVIEW" if r.manual_review_required else ""
        print(
            f"  {r.record_id} | "
            f"{r.raw_product_name[:46]:<46} | "
            f"conf: {r.confidence:.3f}  {review}  {ok}"
        )

    _rule()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading normalizer...")
    evaluator = BatchEvaluator.from_files()
    print("Running batch evaluation...")
    report = evaluator.run()
    print_report(report)


if __name__ == "__main__":
    main()
