"""
LumberLex — Data Layer (Phase 1)
Loads canonicals.csv and aliases.csv, validates integrity, and builds
the two-level in-memory lookup used by all downstream phases.

Phase 2 patch applied: [treatment_collision] check added to validate().
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Bundled default data paths
# ---------------------------------------------------------------------------
# These point to the CSV files bundled inside the installed package.
# Import and use them whenever you need to load the default canonical/alias
# data without knowing the installation path:
#
#     from lumberlex.data_layer import DEFAULT_CANONICALS_PATH, DEFAULT_ALIASES_PATH
#     can_df = load_canonicals(DEFAULT_CANONICALS_PATH)

_DEFAULT_DATA_DIR = Path(__file__).parent / "_data"
DEFAULT_CANONICALS_PATH: str = str(_DEFAULT_DATA_DIR / "canonicals.csv")
DEFAULT_ALIASES_PATH: str    = str(_DEFAULT_DATA_DIR / "aliases.csv")


# ---------------------------------------------------------------------------
# CanonicalEntry — one entry per canonical lumber type
# ---------------------------------------------------------------------------

@dataclass
class CanonicalEntry:
    canonical_name: str
    species_group: str
    category: str
    treatment: Optional[str]       # None means untreated / not applicable
    ambiguity_level: str           # "Low" | "Medium" | "High"
    notes: str


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_canonicals(path: str) -> pd.DataFrame:
    """Load canonicals.csv. Raises ValueError on missing required columns."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"canonical_name", "species_group", "category",
                "treatment", "ambiguity_level", "notes"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"canonicals.csv missing columns: {missing}")
    # Normalise treatment: "None" string → actual None/NaN → empty string
    df["treatment"] = df["treatment"].replace({"None": ""}).fillna("")
    return df


def load_aliases(path: str) -> pd.DataFrame:
    """Load aliases.csv. Raises ValueError on missing required columns."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"alias", "canonical_name"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"aliases.csv missing columns: {missing}")
    return df


# ---------------------------------------------------------------------------
# build_lookup — constructs the two dicts used at runtime
# ---------------------------------------------------------------------------

def build_lookup(
    can_df: pd.DataFrame,
    ali_df: pd.DataFrame,
) -> tuple[dict[str, str], dict[str, CanonicalEntry]]:
    """
    Returns:
        alias_index      dict[lowercase alias → canonical_name]   (205 entries)
        canonical_index  dict[canonical_name → CanonicalEntry]    (15 entries)

    Duplicate aliases: first occurrence wins (consistent with validate()).
    """
    # Build canonical index
    canonical_index: dict[str, CanonicalEntry] = {}
    for _, row in can_df.iterrows():
        name = str(row["canonical_name"]).strip()
        if not name:
            continue
        treatment_val = str(row["treatment"]).strip()
        canonical_index[name] = CanonicalEntry(
            canonical_name=name,
            species_group=str(row["species_group"]).strip(),
            category=str(row["category"]).strip(),
            treatment=treatment_val if treatment_val else None,
            ambiguity_level=str(row["ambiguity_level"]).strip(),
            notes=str(row["notes"]).strip(),
        )

    # Build alias index (lowercase keys, first-wins on duplicates).
    # Letter-adjacent hyphens are normalised to spaces so that exact dict
    # lookup succeeds for queries produced by the patched clean() function.
    # Example: alias "Hem-Fir #2" → key "hem fir #2"; a cleaned query
    # "hem-fir #2" also becomes "hem fir #2" after clean(), giving a hit.
    _letter_hyphen_re = re.compile(r"(?<=[a-z])-(?=[a-z])")
    alias_index: dict[str, str] = {}
    for _, row in ali_df.iterrows():
        alias = str(row["alias"]).strip()
        canonical = str(row["canonical_name"]).strip()
        if not alias or not canonical:
            continue
        key = _letter_hyphen_re.sub(" ", alias.lower())
        if key not in alias_index:
            alias_index[key] = canonical

    return alias_index, canonical_index


# ---------------------------------------------------------------------------
# validate — five integrity checks + Phase 2 treatment_collision patch
# ---------------------------------------------------------------------------

VALID_AMBIGUITY_LEVELS = {"Low", "Medium", "High"}
TREATMENT_TOKENS = {"pt", "treated", "pressure-treated"}


def validate(can_df: pd.DataFrame, ali_df: pd.DataFrame) -> list[str]:
    """
    Runs integrity checks on the two DataFrames.
    Returns a list of warning strings; empty list means tables are clean.
    Raises ValueError for fatal problems (empty primary keys).
    """
    warnings: list[str] = []

    # ── Fatal checks ────────────────────────────────────────────────────────
    for _, row in can_df.iterrows():
        if not str(row["canonical_name"]).strip():
            raise ValueError("canonicals.csv contains a row with empty canonical_name")

    for _, row in ali_df.iterrows():
        if not str(row["alias"]).strip():
            raise ValueError("aliases.csv contains a row with empty alias")
        if not str(row["canonical_name"]).strip():
            raise ValueError("aliases.csv contains a row with empty canonical_name")

    # ── [ambiguity_level] ───────────────────────────────────────────────────
    for _, row in can_df.iterrows():
        level = str(row["ambiguity_level"]).strip()
        if level not in VALID_AMBIGUITY_LEVELS:
            warnings.append(
                f"[ambiguity_level] '{row['canonical_name']}' has invalid "
                f"ambiguity_level '{level}'"
            )

    # Build sets for downstream checks
    canonical_names = set(can_df["canonical_name"].str.strip())
    seen_aliases: dict[str, str] = {}

    for _, row in ali_df.iterrows():
        alias_str = str(row["alias"]).strip()
        canonical = str(row["canonical_name"]).strip()
        key = alias_str.lower()

        # ── [duplicate] ─────────────────────────────────────────────────────
        if key in seen_aliases:
            if seen_aliases[key] != canonical:
                warnings.append(
                    f"[duplicate] alias '{alias_str}' maps to both "
                    f"'{seen_aliases[key]}' and '{canonical}'; "
                    f"first occurrence wins"
                )
        else:
            seen_aliases[key] = canonical

        # ── [alias_chain] ───────────────────────────────────────────────────
        if alias_str in canonical_names and alias_str != canonical:
            warnings.append(
                f"[alias_chain] '{alias_str}' is both a canonical name and "
                f"an alias for '{canonical}'"
            )

        # ── [orphan] ────────────────────────────────────────────────────────
        if canonical not in canonical_names:
            warnings.append(
                f"[orphan] alias '{alias_str}' references unknown canonical "
                f"'{canonical}'"
            )

    # ── [treatment_collision] — Phase 2 patch ───────────────────────────────
    # Flag any alias whose tokens include a treatment keyword but whose
    # canonical has an empty treatment field. This would cause the Phase 3
    # parser to strip a meaningful token and potentially mismatch the product.
    untreated_canonicals = set(
        can_df.loc[
            can_df["treatment"].isna() | (can_df["treatment"].str.strip() == ""),
            "canonical_name",
        ]
    )

    for _, row in ali_df.iterrows():
        alias_str = str(row["alias"]).strip()
        canonical = str(row["canonical_name"]).strip()
        if canonical not in untreated_canonicals:
            continue  # canonical is treated — no collision possible
        tokens = set(re.split(r"[\s\-]+", alias_str.lower()))
        colliding = tokens & TREATMENT_TOKENS
        if colliding:
            keyword = next(iter(colliding))
            warnings.append(
                f"[treatment_collision] '{alias_str}' contains treatment "
                f"keyword '{keyword}' but maps to untreated canonical "
                f"'{canonical}'"
            )

    return warnings
