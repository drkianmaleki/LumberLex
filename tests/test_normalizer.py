"""
LumberLex — Phase 5 Normalizer Tests

Groups:
  1. Fixture       — Normalizer.from_files() loads without error
  2. All test cases — parametrized against all 10 rows of test_cases.csv
  3. UNKNOWN case  — shape of a no-match result
  4. Warning       — High ambiguity fires; Low and Medium do not
  5. Treatment     — union rule (brand-name fallback + explicit keyword)
  6. Explanation   — present, correct content for match and UNKNOWN
  7. Field completeness — all 19 fields present on every result
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from lumberlex.data_layer import build_lookup, load_aliases, load_canonicals
from lumberlex.normalizer import Normalizer
from lumberlex.parser import build_alias_token_set
from lumberlex.schemas import NormalizationResult

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

from lumberlex.data_layer import DEFAULT_CANONICALS_PATH, DEFAULT_ALIASES_PATH

# Canonicals and aliases: use the library's bundled defaults
CANONICALS_PATH = DEFAULT_CANONICALS_PATH
ALIASES_PATH    = DEFAULT_ALIASES_PATH

# test_cases.csv stays in data/ at the project root (not bundled)
DATA_DIR       = Path(__file__).parent.parent / "data"
TEST_CASES_PATH = DATA_DIR / "test_cases.csv"

# ---------------------------------------------------------------------------
# Shared fixture — built once for the module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def normalizer() -> Normalizer:
    return Normalizer.from_files(CANONICALS_PATH, ALIASES_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_test_cases() -> list[tuple]:
    """
    Read test_cases.csv and return a list of
    (raw, expected_canonical, expected_size, confidence_min) tuples.
    Empty cells are normalised to None.
    """
    df = pd.read_csv(TEST_CASES_PATH)
    cases: list[tuple] = []
    for _, row in df.iterrows():
        raw = str(row["input"]).strip()
        expected_canonical = str(row["expected_canonical"]).strip()

        size_raw = row.get("expected_size", "")
        expected_size = str(size_raw).strip() if pd.notna(size_raw) else None
        if expected_size == "" or expected_size == "nan":
            expected_size = None

        conf_raw = row.get("confidence_min", "")
        confidence_min = float(conf_raw) if pd.notna(conf_raw) else None

        cases.append((raw, expected_canonical, expected_size, confidence_min))
    return cases


# ===========================================================================
# Group 1 — Fixture
# ===========================================================================

class TestFixture:

    def test_from_files_returns_normalizer(self, normalizer):
        assert isinstance(normalizer, Normalizer)

    def test_from_files_with_explicit_paths(self):
        n = Normalizer.from_files(CANONICALS_PATH, ALIASES_PATH)
        assert isinstance(n, Normalizer)

    def test_init_with_prebuilt_dicts(self):
        """__init__ path: pytest fixtures can bypass filesystem."""
        can_df = load_canonicals(CANONICALS_PATH)
        ali_df = load_aliases(ALIASES_PATH)
        alias_index, canonical_index = build_lookup(can_df, ali_df)
        alias_token_set = build_alias_token_set(alias_index)
        display_aliases = dict(zip(ali_df["alias"].str.lower(), ali_df["alias"]))
        n = Normalizer(alias_index, canonical_index, alias_token_set, display_aliases)
        result = n.normalize("Hem Fir 2x6")
        assert result.normalized_name == "Hem-Fir"


# ===========================================================================
# Group 2 — All 10 test cases (parametrized)
# ===========================================================================

@pytest.mark.parametrize(
    "raw,expected_canonical,expected_size,confidence_min",
    _load_test_cases(),
    ids=[row[0] for row in _load_test_cases()],
)
def test_all_test_cases(
    normalizer: Normalizer,
    raw: str,
    expected_canonical: str,
    expected_size: str | None,
    confidence_min: float | None,
) -> None:
    result = normalizer.normalize(raw)
    assert isinstance(result, NormalizationResult)

    if expected_canonical == "UNKNOWN":
        assert result.normalized_name == "UNKNOWN", (
            f"Expected UNKNOWN, got '{result.normalized_name}'"
        )
        assert result.confidence < 0.60, (
            f"UNKNOWN case: confidence must be < 0.60, got {result.confidence:.3f}"
        )
        assert result.manual_review_required is True
    else:
        assert result.normalized_name == expected_canonical, (
            f"Input: {raw!r}\n"
            f"Expected canonical: '{expected_canonical}'\n"
            f"Got:                '{result.normalized_name}'"
        )
        if confidence_min is not None:
            assert result.confidence >= confidence_min, (
                f"Input: {raw!r}\n"
                f"Expected confidence >= {confidence_min}, got {result.confidence:.3f}"
            )
        if expected_size is not None:
            assert result.detected_size == expected_size, (
                f"Input: {raw!r}\n"
                f"Expected size: '{expected_size}'\n"
                f"Got:           '{result.detected_size}'"
            )


# ===========================================================================
# Group 3 — UNKNOWN result shape
# ===========================================================================

class TestUnknownCase:

    def test_unknown_normalized_name(self, normalizer):
        result = normalizer.normalize("random unknown board xyz")
        assert result.normalized_name == "UNKNOWN"

    def test_unknown_low_confidence(self, normalizer):
        result = normalizer.normalize("random unknown board xyz")
        assert result.confidence < 0.60

    def test_unknown_manual_review_true(self, normalizer):
        result = normalizer.normalize("random unknown board xyz")
        assert result.manual_review_required is True

    def test_unknown_metadata_all_none(self, normalizer):
        result = normalizer.normalize("random unknown board xyz")
        assert result.species_group is None
        assert result.category is None
        assert result.ambiguity_level is None

    def test_unknown_best_alias_none(self, normalizer):
        result = normalizer.normalize("random unknown board xyz")
        assert result.best_alias_match is None


# ===========================================================================
# Group 4 — Warning generation
# ===========================================================================

class TestWarning:

    def test_warning_fires_for_high_ambiguity_spf(self, normalizer):
        """SPF has ambiguity_level=High → warning should be set."""
        result = normalizer.normalize("Whitewood Stud 2x4")
        assert result.normalized_name == "SPF"
        assert result.warning is not None
        assert len(result.warning) > 0

    def test_warning_text_comes_from_canonical_notes(self, normalizer):
        """Warning text is the canonical's notes field verbatim."""
        result = normalizer.normalize("Whitewood 2x4")
        assert result.warning is not None
        # The SPF notes mention 'whitewood' and 'trade term'
        assert "whitewood" in result.warning.lower() or "trade" in result.warning.lower()

    def test_warning_not_fired_for_low_ambiguity(self, normalizer):
        """Hem-Fir has ambiguity_level=Low → no warning."""
        result = normalizer.normalize("Hem Fir 2x6")
        assert result.normalized_name == "Hem-Fir"
        assert result.warning is None

    def test_warning_not_fired_for_medium_ambiguity(self, normalizer):
        """Douglas Fir-Larch has ambiguity_level=Medium → no warning."""
        result = normalizer.normalize("Doug Fir 2x8")
        assert result.normalized_name == "Douglas Fir-Larch"
        assert result.warning is None

    def test_warning_not_fired_for_unknown(self, normalizer):
        """UNKNOWN results have no canonical → warning must be None."""
        result = normalizer.normalize("random unknown board xyz")
        assert result.warning is None


# ===========================================================================
# Group 5 — Treatment union rule
# ===========================================================================

class TestTreatmentUnion:

    def test_treatment_from_canonical_brand_name(self, normalizer):
        """
        YellaWood: parser finds no treatment keyword in the raw string.
        Canonical 'Pressure Treated Southern Yellow Pine' has treatment set.
        Union rule: canonical treatment is the fallback → Pressure Treated.
        """
        result = normalizer.normalize("YellaWood 2x4")
        assert result.normalized_name == "Pressure Treated Southern Yellow Pine"
        assert result.treatment == "Pressure Treated"

    def test_treatment_from_parser_explicit_keyword(self, normalizer):
        """
        SYP PT: parser detects 'PT' keyword. Canonical also has treatment.
        Union rule: either source → Pressure Treated.
        """
        result = normalizer.normalize("SYP PT 4x4x8")
        assert result.treatment == "Pressure Treated"

    def test_treatment_none_for_untreated_canonical(self, normalizer):
        """No treatment keyword; canonical (Douglas Fir-Larch) is untreated."""
        result = normalizer.normalize("Doug Fir 2x8")
        assert result.normalized_name == "Douglas Fir-Larch"
        assert result.treatment is None

    def test_treatment_none_for_unknown(self, normalizer):
        """UNKNOWN case: no canonical → treatment from parser only (None here)."""
        result = normalizer.normalize("random unknown board xyz")
        assert result.treatment is None

    def test_treatment_from_acq_keyword(self, normalizer):
        """ACQ is a treatment keyword the parser recognises."""
        result = normalizer.normalize("ACQ Treated Pine 2x4")
        assert result.treatment == "Pressure Treated"


# ===========================================================================
# Group 6 — Explanation
# ===========================================================================

class TestExplanation:

    def test_explanation_present_for_successful_match(self, normalizer):
        result = normalizer.normalize("Hem Fir 2x6")
        assert result.explanation is not None
        assert len(result.explanation) > 0

    def test_explanation_contains_canonical_name(self, normalizer):
        result = normalizer.normalize("Hem Fir 2x6")
        assert "Hem-Fir" in result.explanation

    def test_explanation_present_for_unknown(self, normalizer):
        result = normalizer.normalize("random unknown board xyz")
        assert result.explanation is not None

    def test_explanation_unknown_mentions_manual_review(self, normalizer):
        result = normalizer.normalize("random unknown board xyz")
        assert "manual review" in result.explanation.lower()

    def test_explanation_includes_seller_when_detected(self, normalizer):
        result = normalizer.normalize("Lowes Whitewood Stud 2x4")
        assert "Lowes" in result.explanation

    def test_explanation_includes_treatment_when_detected(self, normalizer):
        result = normalizer.normalize("SYP PT 4x4x8")
        assert "treatment" in result.explanation.lower()

    def test_explanation_includes_size_when_detected(self, normalizer):
        result = normalizer.normalize("Hem Fir 2x6")
        assert "2x6" in result.explanation

    def test_explanation_no_size_clause_when_no_size(self, normalizer):
        result = normalizer.normalize("Doug Fir-Larch")
        assert result.detected_size is None
        # Explanation should not mention a size that wasn't there
        assert "extracted before matching" not in result.explanation


# ===========================================================================
# Group 7 — Field completeness
# ===========================================================================

class TestFieldCompleteness:

    _EXPECTED_FIELDS = {
        "original_input", "cleaned_input", "normalized_name",
        "species_group", "category", "ambiguity_level", "treatment",
        "detected_size", "size_label", "detected_seller",
        "detected_grade", "detected_product_class", "unrecognized_tokens",
        "confidence", "best_alias_match", "alternative_matches",
        "manual_review_required", "warning", "explanation",
    }

    def test_all_19_fields_present_on_successful_match(self, normalizer):
        result = normalizer.normalize("Lowes Whitewood Stud 2x4")
        result_fields = set(NormalizationResult.model_fields.keys())
        assert self._EXPECTED_FIELDS == result_fields

    def test_all_19_fields_present_on_unknown(self, normalizer):
        result = normalizer.normalize("random unknown board xyz")
        result_fields = set(NormalizationResult.model_fields.keys())
        assert self._EXPECTED_FIELDS == result_fields

    def test_result_is_serialisable(self, normalizer):
        """NormalizationResult.model_dump_json() must not raise."""
        result = normalizer.normalize("SYP PT 4x4x8")
        json_str = result.model_dump_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_alternative_matches_are_list(self, normalizer):
        result = normalizer.normalize("Lowes Whitewood Stud 2x4")
        assert isinstance(result.alternative_matches, list)

    def test_confidence_is_in_valid_range(self, normalizer):
        result = normalizer.normalize("Hem Fir 2x6")
        assert 0.0 <= result.confidence <= 1.0


# ── Group 8 — Phase 6 retroactive patches ────────────────────────────────────


class TestProductClassStripping:
    """Patch C: detected_product_class stripped from match query in Step 2."""

    def test_appearance_stripped_resolves_false_confident_llx0187(
        self, normalizer
    ):
        # Was false-confident: "PT PINE ... Appearance" → Ponderosa Pine (0.85).
        # After patch: "appearance" stripped → "pt pine" → exact alias hit.
        result = normalizer.normalize("PT PINE 2 x 4 x 92-5/8 Appearance")
        assert result.normalized_name == "Pressure Treated Southern Yellow Pine"
        assert result.confidence >= 0.80

    def test_appearance_and_hyphen_norm_resolve_llx0149(self, normalizer):
        # Was false-confident: "SY-Pine ... Appearance" → Ponderosa Pine (0.85).
        # After patch: hyphen norm → "sy pine"; appearance stripped → exact hit.
        result = normalizer.normalize("SY-Pine 2x4x8 Appearance")
        assert result.normalized_name == "Southern Yellow Pine"
        assert result.confidence >= 0.80

    def test_kiln_dried_stripped_leaves_species_tokens_intact(self, normalizer):
        # "kiln dried" is a product-class token; stripping it exposes "spf #2"
        # which now exactly matches the new "SPF #2" alias.
        result = normalizer.normalize("Kiln Dried SPF 2x6x8 #2")
        assert result.normalized_name == "SPF"

    def test_no_product_class_token_behaviour_unchanged(self, normalizer):
        # Regression guard: inputs with no product-class token are unaffected.
        result = normalizer.normalize("SYP PT 4x4x8")
        assert result.normalized_name == "Pressure Treated Southern Yellow Pine"
        assert result.confidence == 0.95

    def test_product_class_none_does_not_strip_anything(self, normalizer):
        # Regression guard: when detected_product_class is None, the branch
        # is skipped entirely and the query is unchanged by that step.
        result = normalizer.normalize("Hem Fir 2x6")
        assert result.normalized_name == "Hem-Fir"
        assert result.confidence == 0.95


class TestNewAliases:
    """Four new rows added to data/aliases.csv in Phase 6."""

    def test_syp_2_btr_resolves_false_confident_llx0134(self, normalizer):
        # Was false-confident: "SYP ... #2&BTR" → SPF (0.85).
        # After alias addition: exact dict hit → Southern Yellow Pine (0.95).
        result = normalizer.normalize("SYP 5/4x6x12 #2&BTR")
        assert result.normalized_name == "Southern Yellow Pine"
        assert result.confidence == 0.95

    def test_hem_fir_2_btr_alias(self, normalizer):
        # Fills the symmetric gap: DFL had #2&BTR but Hem-Fir did not.
        result = normalizer.normalize("Hem-Fir #2&BTR 2x6x8")
        assert result.normalized_name == "Hem-Fir"
        assert result.confidence == 0.95

    def test_pt_southern_yellow_pine_resolves_false_confident_llx0178(
        self, normalizer
    ):
        # Was false-confident: "PT Southern Yellow Pine ..." → untreated SYP.
        # After alias addition: exact dict hit → PT SYP (0.95).
        result = normalizer.normalize("PT Southern Yellow Pine 2x4x10 Kiln Dried")
        assert result.normalized_name == "Pressure Treated Southern Yellow Pine"
        assert result.confidence == 0.95

    def test_spf_2_alias_prevents_syp_collision(self, normalizer):
        # Was a Category C regression: "kiln dried" stripped left "spf #2",
        # which was losing to "syp #2". New alias "SPF #2" gives exact hit.
        result = normalizer.normalize("kiln dried SPF 2x4 #2")
        assert result.normalized_name == "SPF"


class TestHyphenNormalisationEndToEnd:
    """Patches A + B together: clean() and alias keys round-trip correctly."""

    def test_hyphenated_species_name_exact_hit(self, normalizer):
        # "Hem-Fir 2x6" → clean → "hem fir 2x6" → strip "2x6" → "hem fir"
        # alias key "hem fir" (normalised from "Hem-Fir") → exact hit
        result = normalizer.normalize("Hem-Fir 2x6")
        assert result.normalized_name == "Hem-Fir"
        assert result.confidence == 0.95

    def test_spruce_pine_fir_hyphenated(self, normalizer):
        result = normalizer.normalize("Spruce-Pine-Fir 2x4x8")
        assert result.normalized_name == "SPF"

    def test_western_red_cedar_hyphenated(self, normalizer):
        result = normalizer.normalize("Western-Red-Cedar 5/4x6x12")
        assert result.normalized_name == "Western Red Cedar"

    def test_pressure_treated_hyphenated(self, normalizer):
        result = normalizer.normalize("Pressure-Treated-Yellow-Pine 2x4x8")
        assert result.normalized_name == "Pressure Treated Southern Yellow Pine"

    def test_digit_hyphen_survives_to_detected_size(self, normalizer):
        # Stud length "92-5/8" must survive cleaning and dimension extraction.
        result = normalizer.normalize("SPF 2x4x92-5/8 Stud Grade")
        assert result.detected_size == "2x4x92-5/8"
