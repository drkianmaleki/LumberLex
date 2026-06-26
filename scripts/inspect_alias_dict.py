"""
LumberLex — Alias Dictionary Inspector  (Phase 1 visual check)

Loads the data layer, runs validation, and prints a full human-readable
report so you can visually confirm the alias table is correct.

Usage (run from the lumberlex/ directory):
    python scripts/inspect_alias_dict.py
"""

from collections import Counter

from lumberlex.data_layer import (
    DEFAULT_ALIASES_PATH,
    DEFAULT_CANONICALS_PATH,
    build_lookup,
    load_aliases,
    load_canonicals,
    validate,
)


def _separator(char: str = "─", width: int = 64) -> str:
    return char * width


def main() -> None:
    print(_separator("="))
    print("  LumberLex — Data Layer Inspector")
    print(_separator("="))

    # ── Load ─────────────────────────────────────────────────────────────────
    can_df = load_canonicals(DEFAULT_CANONICALS_PATH)
    ali_df = load_aliases(DEFAULT_ALIASES_PATH)
    alias_index, canonical_index = build_lookup(can_df, ali_df)

    print(f"\n  Canonicals loaded : {len(canonical_index)}")
    print(f"  Aliases loaded    : {len(alias_index)}")

    # ── Validation ────────────────────────────────────────────────────────────
    warnings = validate(can_df, ali_df)
    print()
    if warnings:
        print(f"  ⚠  {len(warnings)} validation warning(s):")
        for w in warnings:
            print(f"     {w}")
    else:
        print("  ✓  Validation passed — no warnings")

    # ── Alias counts per canonical ────────────────────────────────────────────
    print(f"\n{_separator()}")
    print("  Alias counts per canonical")
    print(_separator())
    counts = Counter(ali_df["canonical_name"])
    for name, count in sorted(counts.items(), key=lambda x: -x[1]):
        bar = "█" * count
        print(f"  {count:3d}  {bar:<26}  {name}")

    # ── Full alias → canonical table ──────────────────────────────────────────
    print(f"\n{_separator()}")
    print("  Full alias → canonical mapping  (keys shown in lookup-ready lowercase)")
    print(_separator())

    col_w = max(len(k) for k in alias_index) + 2
    print(f"  {'Alias':<{col_w}}  Canonical")
    print(f"  {'-' * col_w}  {'-' * 38}")
    for alias_key in sorted(alias_index):
        print(f"  {alias_key:<{col_w}}  {alias_index[alias_key]}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{_separator('=')}")
    print(f"  Done. {len(alias_index)} aliases across {len(canonical_index)} canonicals.")
    if warnings:
        print(f"  {len(warnings)} warning(s) require attention — see above.")
    print(_separator("="))


if __name__ == "__main__":
    main()
