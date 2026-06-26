"""
Phase 1 — Data Layer Tests
20 original tests + 1 Phase 2 retroactive patch test ([treatment_collision]).
"""

import pytest
import pandas as pd

from lumberlex.data_layer import (
    CanonicalEntry,
    DEFAULT_ALIASES_PATH,
    DEFAULT_CANONICALS_PATH,
    build_lookup,
    load_aliases,
    load_canonicals,
    validate,
)

CANONICALS = DEFAULT_CANONICALS_PATH
ALIASES    = DEFAULT_ALIASES_PATH


# ---------------------------------------------------------------------------
# Load shape
# ---------------------------------------------------------------------------

def test_load_canonicals_row_count():
    df = load_canonicals(CANONICALS)
    assert len(df) == 15

def test_load_canonicals_required_columns():
    df = load_canonicals(CANONICALS)
    for col in ("canonical_name", "species_group", "category",
                "treatment", "ambiguity_level", "notes"):
        assert col in df.columns

def test_load_aliases_row_count():
    df = load_aliases(ALIASES)
    assert len(df) == 205  # 201 original + 4 aliases added in Phase 6

def test_load_aliases_required_columns():
    df = load_aliases(ALIASES)
    for col in ("alias", "canonical_name"):
        assert col in df.columns


# ---------------------------------------------------------------------------
# Alias resolution
# ---------------------------------------------------------------------------

def test_alias_resolution_spf():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    alias_index, _ = build_lookup(can_df, ali_df)
    assert alias_index["spf"] == "SPF"

def test_alias_resolution_whitewood_stud():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    alias_index, _ = build_lookup(can_df, ali_df)
    assert alias_index["whitewood stud"] == "SPF"

def test_alias_resolution_case_insensitive():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    alias_index, _ = build_lookup(can_df, ali_df)
    assert alias_index["doug fir"] == "Douglas Fir-Larch"

def test_alias_resolution_treatment():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    alias_index, _ = build_lookup(can_df, ali_df)
    assert alias_index["syp pt"] == "Pressure Treated Southern Yellow Pine"

def test_alias_resolution_hem_fir():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    alias_index, _ = build_lookup(can_df, ali_df)
    assert alias_index["hem fir"] == "Hem-Fir"


# ---------------------------------------------------------------------------
# Canonical index
# ---------------------------------------------------------------------------

def test_canonical_index_size():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    _, canonical_index = build_lookup(can_df, ali_df)
    assert len(canonical_index) == 15

def test_canonical_index_entry_type():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    _, canonical_index = build_lookup(can_df, ali_df)
    assert isinstance(canonical_index["SPF"], CanonicalEntry)

def test_canonical_index_ambiguity_levels():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    _, canonical_index = build_lookup(can_df, ali_df)
    levels = {e.ambiguity_level for e in canonical_index.values()}
    assert levels <= {"Low", "Medium", "High"}

def test_canonical_index_treatment_values():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    _, canonical_index = build_lookup(can_df, ali_df)
    treatments = {e.treatment for e in canonical_index.values()}
    assert "Pressure Treated" in treatments

def test_canonical_index_spf_species_group():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    _, canonical_index = build_lookup(can_df, ali_df)
    assert canonical_index["SPF"].species_group == "Spruce-Pine-Fir"


# ---------------------------------------------------------------------------
# validate() — clean data
# ---------------------------------------------------------------------------

def test_validate_clean_data_returns_no_warnings():
    can_df = load_canonicals(CANONICALS)
    ali_df = load_aliases(ALIASES)
    warnings = validate(can_df, ali_df)
    assert warnings == []


# ---------------------------------------------------------------------------
# validate() — injected problems
# ---------------------------------------------------------------------------

def test_validate_detects_bad_ambiguity_level():
    can_df = pd.DataFrame([{
        "canonical_name": "Test Wood", "species_group": "Test",
        "category": "Test", "treatment": "", "ambiguity_level": "Extreme",
        "notes": "",
    }])
    ali_df = pd.DataFrame([{"alias": "Test Wood", "canonical_name": "Test Wood"}])
    warnings = validate(can_df, ali_df)
    assert any("[ambiguity_level]" in w for w in warnings)

def test_validate_detects_duplicate_alias():
    can_df = pd.DataFrame([
        {"canonical_name": "TypeA", "species_group": "A", "category": "A",
         "treatment": "", "ambiguity_level": "Low", "notes": ""},
        {"canonical_name": "TypeB", "species_group": "B", "category": "B",
         "treatment": "", "ambiguity_level": "Low", "notes": ""},
    ])
    ali_df = pd.DataFrame([
        {"alias": "SharedAlias", "canonical_name": "TypeA"},
        {"alias": "SharedAlias", "canonical_name": "TypeB"},
    ])
    warnings = validate(can_df, ali_df)
    assert any("[duplicate]" in w for w in warnings)

def test_validate_detects_orphan_alias():
    can_df = pd.DataFrame([{
        "canonical_name": "RealWood", "species_group": "R", "category": "R",
        "treatment": "", "ambiguity_level": "Low", "notes": "",
    }])
    ali_df = pd.DataFrame([
        {"alias": "GhostAlias", "canonical_name": "NonExistentWood"},
    ])
    warnings = validate(can_df, ali_df)
    assert any("[orphan]" in w for w in warnings)

def test_validate_empty_canonical_name_raises():
    can_df = pd.DataFrame([{
        "canonical_name": "", "species_group": "X", "category": "X",
        "treatment": "", "ambiguity_level": "Low", "notes": "",
    }])
    ali_df = pd.DataFrame([{"alias": "X", "canonical_name": ""}])
    with pytest.raises(ValueError):
        validate(can_df, ali_df)


# ---------------------------------------------------------------------------
# Phase 2 retroactive patch — [treatment_collision]
# ---------------------------------------------------------------------------

def test_treatment_collision_warning_is_raised():
    """An alias with 'PT' that maps to an untreated canonical should warn."""
    can_df = pd.DataFrame([{
        "canonical_name": "Douglas Fir-Larch",
        "species_group": "Douglas Fir-Larch",
        "category": "Structural lumber",
        "treatment": "",
        "ambiguity_level": "Low",
        "notes": "",
    }])
    ali_df = pd.DataFrame([
        {"alias": "PT Douglas Fir", "canonical_name": "Douglas Fir-Larch"},
    ])
    warnings = validate(can_df, ali_df)
    assert any("[treatment_collision]" in w for w in warnings)


# ── Phase 6 retroactive patch — hyphen normalisation in build_lookup() ────────

def test_alias_keys_have_letter_adjacent_hyphens_normalised():
    """Alias keys with letter-adjacent hyphens must be stored as spaces."""
    can_df = pd.DataFrame([{
        "canonical_name": "Hem-Fir",
        "species_group": "Hem-Fir",
        "category": "Structural lumber",
        "treatment": "",
        "ambiguity_level": "Low",
        "notes": "",
    }])
    ali_df = pd.DataFrame([
        {"alias": "Hem-Fir #2",   "canonical_name": "Hem-Fir"},
        {"alias": "Hem Fir No 2", "canonical_name": "Hem-Fir"},
    ])
    alias_index, _ = build_lookup(can_df, ali_df)
    # Hyphenated alias key must be normalised to space-separated
    assert "hem fir #2" in alias_index,  "hyphenated key should be normalised"
    assert "hem-fir #2" not in alias_index, "original hyphenated key should not exist"
    # Space-separated alias key is unchanged
    assert "hem fir no 2" in alias_index


def test_alias_keys_preserve_digit_adjacent_hyphens():
    """Digit-adjacent hyphens in alias keys are not normalised."""
    can_df = pd.DataFrame([{
        "canonical_name": "SPF",
        "species_group": "Spruce-Pine-Fir",
        "category": "Dimensional framing lumber",
        "treatment": "",
        "ambiguity_level": "High",
        "notes": "",
    }])
    ali_df = pd.DataFrame([
        {"alias": "SPF Stud 2x4x92-5/8", "canonical_name": "SPF"},
    ])
    alias_index, _ = build_lookup(can_df, ali_df)
    # Digit-adjacent hyphen in "92-5/8" must be preserved
    assert "spf stud 2x4x92-5/8" in alias_index
