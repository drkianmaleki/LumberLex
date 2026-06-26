#!/usr/bin/env python3
"""
Phase 4 — Matcher Visual Inspection

Runs the matcher against 6 sample inputs using the real alias index and
prints top-3 results showing raw scores, confidence values, and flags.

These inputs are the cleaned versions of the test_cases.csv rows.
Dimensions are kept in the query strings to show the matcher's raw
behaviour before Phase 5 constructs the final match string.

Usage:
    cd lumberlex/
    python scripts/inspect_matcher.py
"""

from lumberlex.data_layer import (
    DEFAULT_ALIASES_PATH,
    DEFAULT_CANONICALS_PATH,
    build_lookup,
    load_aliases,
    load_canonicals,
)
from lumberlex.matcher import MatchCandidate, MatchResult, match

# Cleaned versions of the 10 test_cases.csv inputs (seller kept, dims kept).
# Phase 5 will strip dims via ParsedInput.consumed before calling match().
SAMPLE_INPUTS: list[str] = [
    "lowes whitewood stud 2x4",
    "syp pt 4x4x8",
    "douglass fir 2x8",
    "hem fir 2x6",
    "random unknown board xyz",
    "3/4 birch ply cabinet panel",
]


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _fmt_row(
    input_s: str,
    alias: str,
    canonical: str,
    score: str,
    conf: str,
    flags: str = "",
) -> str:
    return (
        f"  {_clip(input_s, 32):<32}"
        f"  {_clip(alias, 22):<22}"
        f"  {_clip(canonical, 38):<38}"
        f"  {score:>5}"
        f"  {conf:>5}"
        f"  {flags}"
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    # Load data layer
    can_df = load_canonicals(DEFAULT_CANONICALS_PATH)
    ali_df = load_aliases(DEFAULT_ALIASES_PATH)
    alias_index, _ = build_lookup(can_df, ali_df)

    # Build display map: lowercase → original case
    display_aliases: dict[str, str] = dict(
        zip(ali_df["alias"].str.lower(), ali_df["alias"])
    )

    print()
    print("Phase 4 — Matcher Visual Inspection")
    print("=" * 110)
    print(
        "  Note: dimension tokens are still in the query strings here.\n"
        "  Phase 5 will strip them via ParsedInput.consumed before calling match().\n"
        "  Scores labelled 'exact' mean the exact alias dict hit fired (Pass 1).\n"
    )

    header = _fmt_row("Input (cleaned)", "Best alias", "Canonical", "Score", "Conf", "Flags")
    divider = "-" * len(header)
    print(header)
    print(divider)

    for raw_query in SAMPLE_INPUTS:
        result: MatchResult = match(
            raw_query,
            alias_index,
            top_n=3,
            display_aliases=display_aliases,
        )

        if result.best is None:
            print(_fmt_row(raw_query, "—", "—", "—", "—", "NO MATCH"))
            print()
            continue

        b: MatchCandidate = result.best

        flags = []
        if result.manual_review_required:
            flags.append("REVIEW REQUIRED")
        if b.raw_score >= 100.0:
            flags.append("exact")

        print(_fmt_row(
            raw_query,
            b.alias,
            b.canonical_name,
            f"{b.raw_score:.0f}",
            f"{b.confidence:.2f}",
            " | ".join(flags),
        ))

        for i, alt in enumerate(result.alternatives, 1):
            print(_fmt_row(
                f"  └─ alt {i}",
                alt.alias,
                alt.canonical_name,
                f"{alt.raw_score:.0f}",
                f"{alt.confidence:.2f}",
            ))

        print()

    print(divider)
    print("  Scores  : raw RapidFuzz token_sort_ratio (0–100)")
    print("  Conf    : business-rule confidence (0.0–1.0) from config/thresholds.yml")
    print("  Flags   : REVIEW REQUIRED = score below manual_review_threshold")
    print()


if __name__ == "__main__":
    main()
