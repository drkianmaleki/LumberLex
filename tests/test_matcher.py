"""
tests/test_matcher.py — Phase 4: Matcher

31 tests across 9 groups:
  1. Exact alias lookup          (4)
  2. Fuzzy match correctness     (5)
  3. Low confidence / unknown    (3)
  4. score_to_confidence bands   (8, parametrised)
  5. Band boundary conditions    (2)
  6. Result structure            (3)
  7. Ordering                    (2)
  8. display_aliases             (2)
  9. Edge cases                  (2)
"""

import pytest

from lumberlex.config import (
    CONFIDENCE_EXACT_MATCH,
    CONFIDENCE_SCORE_70_TO_79,
    CONFIDENCE_SCORE_80_TO_89,
    CONFIDENCE_SCORE_90_PLUS,
    CONFIDENCE_SUB_THRESHOLD_SCALE,
    MANUAL_REVIEW_THRESHOLD,
)
from lumberlex.matcher import MatchCandidate, MatchResult, match, score_to_confidence


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def alias_idx() -> dict[str, str]:
    """
    Minimal alias index for matcher unit tests.
    Keys are lowercase (matching Phase 1 alias_index convention).
    Covers all canonicals needed by the test suite.
    """
    return {
        # SPF
        "spf": "SPF",
        "whitewood stud": "SPF",
        "whitewood": "SPF",
        "construction whitewood": "SPF",
        "spruce pine fir": "SPF",
        "spruce-pine-fir": "SPF",
        "white wood": "SPF",
        "spf lumber": "SPF",
        # Douglas Fir-Larch
        "doug fir": "Douglas Fir-Larch",
        "douglas fir": "Douglas Fir-Larch",
        "douglas fir-larch": "Douglas Fir-Larch",
        "df-l": "Douglas Fir-Larch",
        "d fir": "Douglas Fir-Larch",
        "dfl": "Douglas Fir-Larch",
        # Pressure Treated Southern Yellow Pine
        "syp pt": "Pressure Treated Southern Yellow Pine",
        "pt syp": "Pressure Treated Southern Yellow Pine",
        "pt yellow pine": "Pressure Treated Southern Yellow Pine",
        "pressure treated pine": "Pressure Treated Southern Yellow Pine",
        # Hem-Fir
        "hem fir": "Hem-Fir",
        "hem-fir": "Hem-Fir",
        "hemfir": "Hem-Fir",
        "hemlock fir": "Hem-Fir",
        # OSB
        "osb": "OSB",
        "osb sheathing": "OSB",
        "7/16 osb": "OSB",
        "oriented strand board": "OSB",
        # Birch Plywood
        "birch ply": "Birch Plywood",
        "baltic birch": "Birch Plywood",
        "birch plywood": "Birch Plywood",
        "cabinet birch": "Birch Plywood",
    }


@pytest.fixture
def display_idx() -> dict[str, str]:
    """Original-case display aliases (lowercase → original case)."""
    return {
        "spf": "SPF",
        "whitewood stud": "Whitewood Stud",
        "whitewood": "Whitewood",
        "construction whitewood": "Construction Whitewood",
        "spruce pine fir": "Spruce Pine Fir",
        "spruce-pine-fir": "Spruce-Pine-Fir",
        "white wood": "White Wood",
        "spf lumber": "SPF Lumber",
        "doug fir": "Doug Fir",
        "douglas fir": "Douglas Fir",
        "douglas fir-larch": "Douglas Fir-Larch",
        "df-l": "DF-L",
        "d fir": "D Fir",
        "dfl": "DFL",
        "syp pt": "SYP PT",
        "pt syp": "PT SYP",
        "pt yellow pine": "PT Yellow Pine",
        "pressure treated pine": "Pressure Treated Pine",
        "hem fir": "Hem Fir",
        "hem-fir": "Hem-Fir",
        "hemfir": "Hemfir",
        "hemlock fir": "Hemlock Fir",
        "osb": "OSB",
        "osb sheathing": "OSB Sheathing",
        "7/16 osb": "7/16 OSB",
        "oriented strand board": "Oriented Strand Board",
        "birch ply": "Birch Ply",
        "baltic birch": "Baltic Birch",
        "birch plywood": "Birch Plywood",
        "cabinet birch": "Cabinet Birch",
    }


# ── Group 1: Exact alias lookup ────────────────────────────────────────────────

class TestExactLookup:
    def test_exact_match_confidence(self, alias_idx):
        """Exact alias hit returns CONFIDENCE_EXACT_MATCH."""
        result = match("whitewood stud", alias_idx)
        assert result.best is not None
        assert result.best.confidence == pytest.approx(CONFIDENCE_EXACT_MATCH)

    def test_exact_match_canonical(self, alias_idx):
        """Exact alias hit returns the correct canonical name."""
        result = match("syp pt", alias_idx)
        assert result.best is not None
        assert result.best.canonical_name == "Pressure Treated Southern Yellow Pine"

    def test_exact_match_is_case_insensitive(self, alias_idx):
        """Query is lowercased before lookup — uppercase query still finds the alias."""
        result = match("WHITEWOOD STUD", alias_idx)
        assert result.best is not None
        assert result.best.canonical_name == "SPF"

    def test_exact_match_returns_no_alternatives(self, alias_idx):
        """Exact hit returns immediately with an empty alternatives list."""
        result = match("hem fir", alias_idx)
        assert result.alternatives == []
        assert not result.manual_review_required


# ── Group 2: Fuzzy match correctness ──────────────────────────────────────────

class TestFuzzyCorrectness:
    def test_typo_douglass_fir(self, alias_idx):
        """Single-character typo ('douglass') still resolves to Douglas Fir-Larch."""
        result = match("douglass fir", alias_idx)
        assert result.best is not None
        assert result.best.canonical_name == "Douglas Fir-Larch"
        assert result.best.raw_score >= 85

    def test_extra_seller_token(self, alias_idx):
        """Seller prefix ('lowes') is tolerated; correct canonical still returned."""
        result = match("lowes whitewood stud", alias_idx)
        assert result.best is not None
        assert result.best.canonical_name == "SPF"
        assert result.best.raw_score >= MANUAL_REVIEW_THRESHOLD

    def test_extra_modifier_token(self, alias_idx):
        """Extra descriptive token ('western') is tolerated for Hem-Fir."""
        result = match("western hemlock fir", alias_idx)
        assert result.best is not None
        assert result.best.canonical_name == "Hem-Fir"
        assert result.best.raw_score >= MANUAL_REVIEW_THRESHOLD

    def test_extra_token_osb(self, alias_idx):
        """Extra token ('panel') alongside known alias phrase still resolves to OSB."""
        result = match("osb sheathing panel", alias_idx)
        assert result.best is not None
        assert result.best.canonical_name == "OSB"
        assert result.best.raw_score >= MANUAL_REVIEW_THRESHOLD

    def test_partial_phrase_pressure_treated(self, alias_idx):
        """Partial phrase match resolves to Pressure Treated Southern Yellow Pine."""
        result = match("pressure treated lumber", alias_idx)
        assert result.best is not None
        assert result.best.canonical_name == "Pressure Treated Southern Yellow Pine"
        assert result.best.raw_score >= MANUAL_REVIEW_THRESHOLD


# ── Group 3: Low confidence / unknown ─────────────────────────────────────────

class TestLowConfidence:
    def test_unknown_input_low_raw_score(self, alias_idx):
        """Completely unknown input scores below the manual review threshold."""
        result = match("random xyz board", alias_idx)
        assert result.best is not None
        assert result.best.raw_score < MANUAL_REVIEW_THRESHOLD

    def test_unknown_input_manual_review_true(self, alias_idx):
        """Completely unknown input sets manual_review_required = True."""
        result = match("random xyz board", alias_idx)
        assert result.manual_review_required is True

    def test_empty_query_returns_no_match(self, alias_idx):
        """Empty string returns best=None and manual_review_required=True."""
        result = match("", alias_idx)
        assert result.best is None
        assert result.manual_review_required is True


# ── Group 4: score_to_confidence bands (parametrised) ─────────────────────────

class TestScoreToConfidenceBands:
    @pytest.mark.parametrize("score, expected", [
        (100.0, CONFIDENCE_EXACT_MATCH),       # fuzzy-100 treated as exact match
        (95.0,  CONFIDENCE_SCORE_90_PLUS),     # inside ≥ 90 band
        (90.0,  CONFIDENCE_SCORE_90_PLUS),     # floor of ≥ 90 band
        (89.0,  CONFIDENCE_SCORE_80_TO_89),    # ceiling of 80–89 band
        (80.0,  CONFIDENCE_SCORE_80_TO_89),    # floor of 80–89 band
        (79.0,  CONFIDENCE_SCORE_70_TO_79),    # ceiling of 70–79 band
        (70.0,  CONFIDENCE_SCORE_70_TO_79),    # floor of 70–79 band
        (0.0,   0.0),                          # zero score → zero confidence
    ])
    def test_bands(self, score, expected):
        assert score_to_confidence(score) == pytest.approx(expected)


# ── Group 5: Band boundary conditions ─────────────────────────────────────────

class TestBandBoundaries:
    def test_score_at_threshold_is_lowest_named_band(self):
        """
        Score exactly at MANUAL_REVIEW_THRESHOLD falls in the 70–79 band,
        confirming the code uses the config constant as its boundary — not
        a hardcoded 70.
        """
        conf = score_to_confidence(float(MANUAL_REVIEW_THRESHOLD))
        assert conf == pytest.approx(CONFIDENCE_SCORE_70_TO_79)

    def test_score_just_below_threshold_uses_proportional_formula(self):
        """
        Score one point below MANUAL_REVIEW_THRESHOLD uses the proportional
        sub-threshold formula and is strictly less than CONFIDENCE_SCORE_70_TO_79.
        """
        score = float(MANUAL_REVIEW_THRESHOLD) - 1.0
        conf = score_to_confidence(score)
        expected = (score / MANUAL_REVIEW_THRESHOLD) * CONFIDENCE_SUB_THRESHOLD_SCALE
        assert conf == pytest.approx(expected)
        assert conf < CONFIDENCE_SCORE_70_TO_79


# ── Group 6: Result structure ──────────────────────────────────────────────────

class TestResultStructure:
    def test_match_result_types(self, alias_idx):
        """match() returns a MatchResult with typed best and alternatives."""
        result = match("lowes whitewood stud", alias_idx, top_n=3)
        assert isinstance(result, MatchResult)
        assert isinstance(result.best, MatchCandidate)
        assert isinstance(result.alternatives, list)
        assert isinstance(result.manual_review_required, bool)

    def test_match_candidate_has_all_fields(self, alias_idx):
        """MatchCandidate exposes all four required fields with correct types."""
        result = match("lowes whitewood stud", alias_idx)
        c = result.best
        assert isinstance(c.alias, str)
        assert isinstance(c.canonical_name, str)
        assert isinstance(c.raw_score, float)
        assert isinstance(c.confidence, float)

    def test_top_n_1_returns_no_alternatives(self, alias_idx):
        """top_n=1 returns best only; alternatives list is empty."""
        result = match("lowes whitewood stud", alias_idx, top_n=1)
        assert result.best is not None
        assert result.alternatives == []


# ── Group 7: Ordering ──────────────────────────────────────────────────────────

class TestOrdering:
    def test_best_has_highest_raw_score(self, alias_idx):
        """best.raw_score is >= every alternative's raw_score."""
        result = match("lowes whitewood stud", alias_idx, top_n=3)
        assert result.best is not None
        for alt in result.alternatives:
            assert result.best.raw_score >= alt.raw_score

    def test_alternatives_are_descending(self, alias_idx):
        """Alternatives are ordered descending by raw_score."""
        result = match("lowes whitewood stud", alias_idx, top_n=3)
        alts = result.alternatives
        for i in range(len(alts) - 1):
            assert alts[i].raw_score >= alts[i + 1].raw_score


# ── Group 8: display_aliases ───────────────────────────────────────────────────

class TestDisplayAliases:
    def test_without_display_aliases_alias_is_lowercase(self, alias_idx):
        """
        Without display_aliases, MatchCandidate.alias is the raw lowercase
        key from alias_index.
        """
        result = match("douglass fir", alias_idx)
        assert result.best is not None
        # Matched alias key is lowercase — no display map provided
        assert result.best.alias == result.best.alias.lower()

    def test_with_display_aliases_original_case_restored(self, alias_idx, display_idx):
        """
        With display_aliases provided, MatchCandidate.alias uses original
        case from the aliases CSV ('Douglas Fir' not 'douglas fir').
        """
        result = match("douglass fir", alias_idx, display_aliases=display_idx)
        assert result.best is not None
        # Matched key is 'douglas fir'; display map gives 'Douglas Fir'
        assert result.best.alias == "Douglas Fir"


# ── Group 9: Edge cases ────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_whitespace_only_query_returns_no_match(self, alias_idx):
        """Whitespace-only query is treated as empty — returns best=None."""
        result = match("   ", alias_idx)
        assert result.best is None
        assert result.manual_review_required is True

    def test_empty_alias_index_returns_no_match(self):
        """Empty alias_index returns best=None and manual_review_required=True."""
        result = match("douglas fir", {})
        assert result.best is None
        assert result.manual_review_required is True
