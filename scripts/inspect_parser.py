"""
Phase 3 — Parser Visual Inspection Script

Runs parse() against:
  - All 10 rows of data/test_cases.csv
  - 5 additional inputs from data/lumberlex_sample_database.csv

Prints a formatted table for visual inspection.

Usage:
    cd lumberlex
    python scripts/inspect_parser.py
"""

import csv
from pathlib import Path

from lumberlex.data_layer import (
    DEFAULT_ALIASES_PATH,
    DEFAULT_CANONICALS_PATH,
    build_lookup,
    load_aliases,
    load_canonicals,
)
from lumberlex.parser import build_alias_token_set, parse

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent

can_df = load_canonicals(DEFAULT_CANONICALS_PATH)
ali_df = load_aliases(DEFAULT_ALIASES_PATH)
alias_index, _ = build_lookup(can_df, ali_df)
alias_token_set = build_alias_token_set(alias_index)

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

# 10 test cases
test_inputs = []
with open(_PROJECT_ROOT / "data" / "test_cases.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        test_inputs.append(("test_cases.csv", row["input"], row["expected_size"]))

# 5 additional samples from the database (representative variety)
extra_inputs = [
    ("sample_db", "SPRUCE-PINE-FIR 1x4x8 KD Lumber",             "1x4x8"),
    ("sample_db", "WhiteWood 3/4x4x8 Select",                    "3/4x4x8"),
    ("sample_db", "YELLAWOOD 15/32 x 4 x 8 Appearance",          "15/32x4x8"),
    ("sample_db", "3/4x4x8 Baltic-Birch",                        "3/4x4x8"),
    ("sample_db", "Pressure-Treated-Yellow-Pine 2x4x8 Stud Grade","2x4x8"),
]

all_inputs = test_inputs + extra_inputs

# ---------------------------------------------------------------------------
# Run parser and collect rows
# ---------------------------------------------------------------------------

results = []
for source, raw, expected_size in all_inputs:
    p = parse(raw, alias_token_set)
    size_match = (
        "✓" if p.detected_size == expected_size
        else f"✗ (expected {expected_size or 'None'})"
    ) if expected_size else ("—" if p.detected_size is None else p.detected_size)
    results.append((source, raw, p))

# ---------------------------------------------------------------------------
# Print table
# ---------------------------------------------------------------------------

COLS = [
    ("Source",         12),
    ("Input",          42),
    ("cleaned_input",  35),
    ("size",           14),
    ("label",          26),
    ("seller",         20),
    ("treatment",      18),
    ("grade",          18),
    ("product_class",  18),
    ("unrecognized",   20),
]

SEP = "  "

def _cell(val, width):
    s = str(val) if val is not None else "—"
    if len(s) > width:
        s = s[:width - 1] + "…"
    return s.ljust(width)

header = SEP.join(_cell(name, w) for name, w in COLS)
divider = SEP.join("-" * w for _, w in COLS)

print()
print("=" * len(divider))
print("LumberLex — Phase 3 Parser Inspection")
print("=" * len(divider))
print()
print(header)
print(divider)

for source, raw, p in results:
    row = [
        _cell(source,                   COLS[0][1]),
        _cell(raw,                      COLS[1][1]),
        _cell(p.cleaned_input,          COLS[2][1]),
        _cell(p.detected_size,          COLS[3][1]),
        _cell(p.size_label,             COLS[4][1]),
        _cell(p.detected_seller,        COLS[5][1]),
        _cell(p.detected_treatment,     COLS[6][1]),
        _cell(p.detected_grade,         COLS[7][1]),
        _cell(p.detected_product_class, COLS[8][1]),
        _cell(
            ", ".join(p.unrecognized_tokens) if p.unrecognized_tokens else None,
            COLS[9][1],
        ),
    ]
    print(SEP.join(row))

print()
print(f"Total rows: {len(results)}  ({len(test_inputs)} from test_cases, "
      f"{len(extra_inputs)} from sample_db)")
print()
