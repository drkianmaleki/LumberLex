#!/usr/bin/env python3
"""
LumberLex — Live Sample Result Printer (Phase 5)

Replaces the hand-crafted Phase 2 version. Runs the normalizer against the
first N rows of data/test_cases.csv and prints a formatted NormalizationResult
for each row, including a pass/fail indicator against expected_canonical,
expected_size, and confidence_min.

Usage:
    python scripts/print_sample_result.py            # default: all 10 rows
    python scripts/print_sample_result.py --sample 3 # first 3 rows
"""

import argparse
from pathlib import Path

import pandas as pd

from lumberlex.normalizer import Normalizer

# test_cases.csv stays in data/ at the project root (not bundled in the library)
_PROJECT_ROOT = Path(__file__).parent.parent
TEST_CASES    = _PROJECT_ROOT / "data" / "test_cases.csv"

MAX_N = 10
_W = 72  # column width


def _pad(label: str, value: object, flag: str = "") -> str:
    label_col = f"  {label:<24}"
    val_col = str(value) if value is not None else "—"
    return f"{label_col}: {val_col} {flag}".rstrip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print live NormalizationResult for test_cases.csv rows."
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=MAX_N,
        metavar="N",
        help=f"Number of test cases to run (1–{MAX_N}, default: {MAX_N})",
    )
    args = parser.parse_args()
    n = min(max(1, args.sample), MAX_N)

    print("Loading normalizer …")
    normalizer = Normalizer.from_files()   # uses bundled defaults
    print(f"Running {n} test case(s) from data/test_cases.csv\n")
    print("=" * _W)

    df = pd.read_csv(TEST_CASES).head(n)

    for idx, row in df.iterrows():
        raw = str(row["input"]).strip()
        exp_canonical = str(row["expected_canonical"]).strip()

        size_raw = row.get("expected_size", "")
        exp_size = str(size_raw).strip() if pd.notna(size_raw) else None
        if exp_size in ("", "nan"):
            exp_size = None

        conf_raw = row.get("confidence_min", "")
        conf_min = float(conf_raw) if pd.notna(conf_raw) else None

        result = normalizer.normalize(raw)

        # ── Pass / fail evaluation ───────────────────────────────────────
        if exp_canonical == "UNKNOWN":
            ok_canonical = result.normalized_name == "UNKNOWN"
            ok_confidence = result.confidence < 0.60
            ok_size = True
            ok_review = result.manual_review_required is True
        else:
            ok_canonical = result.normalized_name == exp_canonical
            ok_confidence = conf_min is None or result.confidence >= conf_min
            ok_size = exp_size is None or result.detected_size == exp_size
            ok_review = True

        overall = "✓ PASS" if all([ok_canonical, ok_confidence, ok_size, ok_review]) else "✗ FAIL"

        # ── Output ──────────────────────────────────────────────────────
        print(f"\n[{int(idx) + 1}] {raw!r}  →  {overall}")
        print(_pad("normalized_name",
                   result.normalized_name,
                   "✓" if ok_canonical else f"✗  expected: {exp_canonical}"))
        print(_pad("species_group", result.species_group))
        print(_pad("category", result.category))
        print(_pad("ambiguity_level", result.ambiguity_level))
        print(_pad("treatment", result.treatment))
        print(_pad("detected_size",
                   result.detected_size,
                   "✓" if ok_size else f"✗  expected: {exp_size}"))
        conf_note = f"(min: {conf_min})  {'✓' if ok_confidence else '✗'}" if conf_min else ""
        print(_pad("confidence", f"{result.confidence:.3f}", conf_note))
        print(_pad("best_alias_match", result.best_alias_match))
        if result.alternative_matches:
            for i, alt in enumerate(result.alternative_matches, 1):
                print(_pad(f"  alt {i}", f"{alt.alias!r} → {alt.canonical_name} ({alt.score:.0f})"))
        print(_pad("manual_review_required",
                   result.manual_review_required,
                   "✓" if ok_review else "✗"))
        if result.detected_seller:
            print(_pad("detected_seller", result.detected_seller))
        if result.detected_grade:
            print(_pad("detected_grade", result.detected_grade))
        if result.detected_product_class:
            print(_pad("detected_product_class", result.detected_product_class))
        if result.unrecognized_tokens:
            print(_pad("unrecognized_tokens", result.unrecognized_tokens))
        if result.warning:
            print(f"  ⚠  warning: {result.warning}")
        print(f"  explanation: {result.explanation}")
        print("-" * _W)


if __name__ == "__main__":
    main()
