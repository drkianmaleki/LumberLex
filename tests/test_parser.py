"""
Phase 3 — Parser Tests

Groups:
  A. Cleaning
  B. Dimension extraction (10+ format variations)
  C. Treatment detection
  D. Seller detection
  E. Grade detection and unrecognized_tokens
  F. End-to-end parse() against all 10 test_cases.csv rows
"""

import csv
from pathlib import Path

import pytest

from lumberlex.data_layer import (
    DEFAULT_ALIASES_PATH,
    DEFAULT_CANONICALS_PATH,
    build_lookup,
    load_aliases,
    load_canonicals,
)
from lumberlex.parser import (
    ParsedInput,
    build_alias_token_set,
    clean,
    detect_grade,
    detect_seller,
    detect_treatment,
    extract_dimensions,
    parse,
)

# test_cases.csv stays in data/ at the project root (not bundled in the library)
_TEST_CASES_PATH = Path(__file__).parent.parent / "data" / "test_cases.csv"

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def alias_token_set():
    can_df = load_canonicals(DEFAULT_CANONICALS_PATH)
    ali_df = load_aliases(DEFAULT_ALIASES_PATH)
    alias_index, _ = build_lookup(can_df, ali_df)
    return build_alias_token_set(alias_index)


@pytest.fixture(scope="module")
def test_cases():
    rows = []
    with open(_TEST_CASES_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows
# ===========================================================================
# A. Cleaning
# ===========================================================================

class TestClean:

    def test_lowercase(self):
        assert clean("SPF KD") == "spf kd"

    def test_whitespace_collapsed(self):
        assert clean("Spruce  Pine   Fir") == "spruce pine fir"

    def test_strip_leading_trailing(self):
        assert clean("  SPF  ") == "spf"

    def test_letter_slash_letter_becomes_space(self):
        assert clean("Spruce/Pine/Fir") == "spruce pine fir"

    def test_digit_slash_digit_preserved(self):
        assert "7/16" in clean("7/16 OSB")
        assert "3/4" in clean("3/4 Birch Plywood")

    def test_mixed_slash(self):
        # Letter/digit boundary → space
        result = clean("spruce/pine/fir 7/16x4x8")
        assert "spruce pine fir" in result
        assert "7/16" in result

    def test_letter_adjacent_hyphen_normalised_to_space(self):
        # Phase 6 patch: letter-adjacent hyphens → spaces, matching the
        # existing slash rule. "Hem-Fir" becomes "hem fir", not "hem-fir".
        assert "hem fir" in clean("Hem-Fir 2x6")
        assert "hem-fir" not in clean("Hem-Fir 2x6")

    def test_period_removed(self):
        result = clean("No. 2 SPF")
        assert "." not in result
        assert "no 2 spf" == result

    def test_comma_removed(self):
        result = clean("SPF, KD")
        assert "," not in result

    def test_already_clean_unchanged(self):
        assert clean("spf kd") == "spf kd"


# ===========================================================================
# B. Dimension extraction
# ===========================================================================

class TestExtractDimensions:

    def _size(self, text):
        size, _, _, _ = extract_dimensions(clean(text))
        return size

    def _label(self, text):
        _, label, _, _ = extract_dimensions(clean(text))
        return label

    # ── Standard integer dimensions ──────────────────────────────────────

    def test_two_part_integer(self):
        assert self._size("Hem Fir 2x6") == "2x6"

    def test_two_part_integer_spaces(self):
        assert self._size("Construction White Wood 2 x 4") == "2x4"

    def test_three_part_integer(self):
        assert self._size("SYP PT 4x4x8") == "4x4x8"

    def test_three_part_large(self):
        assert self._size("SPF 2x10x12") == "2x10x12"

    # ── Fractional thickness ─────────────────────────────────────────────

    def test_fractional_prefix_three_part(self):
        assert self._size("SPRUCE PINE FIR 7/16x4x8 Common") == "7/16x4x8"

    def test_fractional_prefix_three_part_spaces(self):
        assert self._size("OSB 15/32 x 4 x 8") == "15/32x4x8"

    def test_three_quarter_three_part(self):
        assert self._size("SPF S4S 3/4x4x8 KD") == "3/4x4x8"

    def test_five_quarter(self):
        assert self._size("Cedar 5/4x6x12") == "5/4x6x12"

    # ── Stud length ──────────────────────────────────────────────────────

    def test_stud_length_fraction(self):
        assert self._size("SPF 2x4x92-5/8") == "2x4x92-5/8"

    def test_stud_length_space_separated(self):
        assert self._size("white wood 2x4x92-5/8") == "2x4x92-5/8"

    # ── Split scan (Pass 2) ──────────────────────────────────────────────

    def test_split_fraction_and_bare_dim(self):
        # 7/16 and 4x8 appear separately
        assert self._size("7/16 OSB sheathing 4x8") == "7/16x4x8"

    def test_fraction_only(self):
        assert self._size("3/4 birch ply cabinet panel") == "3/4"

    def test_half_inch_only(self):
        assert self._size("1/2 Birch Ply") == "1/2"

    # ── No dimensions ────────────────────────────────────────────────────

    def test_no_dimension(self):
        assert self._size("Doug Fir-Larch") is None

    def test_unknown_no_dimension(self):
        assert self._size("random unknown board xyz") is None

    # ── size_label ───────────────────────────────────────────────────────

    def test_label_thickness_only(self):
        assert self._label("3/4 birch ply") == "Thickness"

    def test_label_two_part(self):
        assert self._label("Hem Fir 2x6") == "Thickness × Width"

    def test_label_three_part(self):
        assert self._label("SYP PT 4x4x8") == "Thickness × Width × Length"

    def test_label_none_when_no_dimension(self):
        assert self._label("Doug Fir-Larch") is None

    # ── Fraction whitelist ────────────────────────────────────────────────

    def test_non_whitelist_fraction_flagged(self):
        # 7/15 is not a lumber fraction
        _, _, extra, _ = extract_dimensions(clean("SPF 7/15 board"))
        assert extra is not None
        assert "7/15" in extra

    def test_valid_fraction_not_flagged(self):
        _, _, extra, _ = extract_dimensions(clean("7/16 OSB 4x8"))
        assert extra is None


# ===========================================================================
# C. Treatment detection
# ===========================================================================

class TestDetectTreatment:

    def test_pt_abbreviation(self):
        assert detect_treatment("SYP PT 4x4x8") == "Pressure Treated"

    def test_pt_lowercase(self):
        assert detect_treatment("syp pt 4x4") == "Pressure Treated"

    def test_treated_word(self):
        assert detect_treatment("Treated Pine 4x4") == "Pressure Treated"

    def test_pressure_treated_phrase(self):
        assert detect_treatment("Pressure Treated Southern Yellow Pine") == "Pressure Treated"

    def test_pressure_treated_hyphenated(self):
        assert detect_treatment("pressure-treated pine") == "Pressure Treated"

    def test_acq(self):
        assert detect_treatment("ACQ Treated Pine 2x4") == "Pressure Treated"

    def test_mca(self):
        assert detect_treatment("MCA Treated Pine 2x4") == "Pressure Treated"

    def test_no_treatment(self):
        assert detect_treatment("SPF 2x4") is None

    def test_no_treatment_douglas_fir(self):
        assert detect_treatment("Douglas Fir-Larch 2x8") is None

    def test_no_treatment_hem_fir(self):
        assert detect_treatment("Hem Fir 2x6") is None


# ===========================================================================
# D. Seller detection
# ===========================================================================

class TestDetectSeller:

    def test_lowes(self):
        assert detect_seller("Lowes Whitewood Stud 2x4") == "Lowes"

    def test_home_depot(self):
        assert detect_seller("Home Depot SPF 2x6") == "Home Depot"

    def test_84_lumber(self):
        assert detect_seller("84 Lumber SPF KD 2x4") == "84 Lumber"

    def test_menards(self):
        assert detect_seller("Menards Douglas Fir 2x8") == "Menards"

    def test_builder_supply(self):
        assert detect_seller("Builder Supply SYP 4x4") == "Builder Supply"

    def test_independent_lumberyard(self):
        assert detect_seller("Independent Lumberyard Hem-Fir") == "Independent Lumberyard"

    def test_contractor_catalog(self):
        assert detect_seller("Contractor Catalog OSB 4x8") == "Contractor Catalog"

    def test_vendor_price_sheet(self):
        assert detect_seller("Vendor Price Sheet Cedar 2x6") == "Vendor Price Sheet"

    def test_erp_legacy_import(self):
        assert detect_seller("ERP Legacy Import SPF 2x4") == "ERP Legacy Import"

    def test_local_yard(self):
        assert detect_seller("Local Yard White Pine") == "Local Yard"

    def test_no_seller_spf(self):
        assert detect_seller("SPF 2x4") is None

    def test_no_seller_doug_fir(self):
        assert detect_seller("Doug Fir 2x8") is None

    def test_case_insensitive(self):
        assert detect_seller("lowes SPF 2x4") == "Lowes"


# ===========================================================================
# E. Grade detection and unrecognized_tokens
# ===========================================================================

class TestDetectGrade:

    # ── Formal grades → detected_grade ──────────────────────────────────

    def test_hash_two_detected(self, alias_token_set):
        grade, _, _ = detect_grade("douglas fir-larch #2", alias_token_set)
        assert grade is not None
        assert "#2" in grade

    def test_stud_grade_phrase(self, alias_token_set):
        grade, _, _ = detect_grade("spf stud grade", alias_token_set)
        assert grade is not None
        assert "stud grade" in grade.lower()

    def test_no_2_phrase(self, alias_token_set):
        grade, _, _ = detect_grade("syp no 2", alias_token_set)
        assert grade is not None
        assert "no 2" in grade.lower()

    def test_select_structural_phrase(self, alias_token_set):
        grade, _, _ = detect_grade("douglas fir-larch select structural", alias_token_set)
        assert grade is not None
        assert "select structural" in grade.lower()

    def test_construction_stays_in_alias_vocab(self, alias_token_set):
        # "construction" is in aliases (Construction Whitewood → SPF) so bare
        # "construction" belongs to alias vocab, not grade detection.
        grade, product_class, unrecognized = detect_grade("spf construction", alias_token_set)
        assert grade is None
        assert product_class is None
        assert unrecognized is None

    def test_stud_stays_in_alias_vocab(self, alias_token_set):
        # "stud" is in aliases (Whitewood Stud, SPF Stud, etc.) so bare "stud"
        # belongs to alias vocab. The phrase "stud grade" remains a formal grade.
        grade, product_class, unrecognized = detect_grade("whitewood stud", alias_token_set)
        assert grade is None
        assert product_class is None
        assert unrecognized is None

    def test_stud_grade_phrase_still_detected(self, alias_token_set):
        # The explicit phrase "stud grade" is always formal grade.
        grade, _, _ = detect_grade("spf stud grade", alias_token_set)
        assert grade is not None
        assert "stud grade" in grade.lower()

    # ── Product class terms → detected_product_class ─────────────────────

    def test_appearance_goes_to_product_class(self, alias_token_set):
        _, product_class, _ = detect_grade("ponderosa pine appearance", alias_token_set)
        assert product_class is not None
        assert "appearance" in product_class.lower()

    def test_appearance_not_in_grade(self, alias_token_set):
        grade, _, _ = detect_grade("ponderosa pine appearance", alias_token_set)
        assert grade is None

    def test_kiln_dried_goes_to_product_class(self, alias_token_set):
        _, product_class, _ = detect_grade("hem fir kiln dried", alias_token_set)
        assert product_class is not None
        assert "kiln dried" in product_class.lower()

    def test_rough_sawn_goes_to_product_class(self, alias_token_set):
        _, product_class, _ = detect_grade("cedar rough sawn", alias_token_set)
        assert product_class is not None
        assert "rough sawn" in product_class.lower()

    def test_framing_goes_to_product_class(self, alias_token_set):
        _, product_class, _ = detect_grade("spf framing", alias_token_set)
        assert product_class is not None
        assert "framing" in product_class.lower()

    def test_common_goes_to_product_class(self, alias_token_set):
        _, product_class, _ = detect_grade("pine common", alias_token_set)
        assert product_class is not None
        assert "common" in product_class.lower()

    # ── Ambiguous tokens → unrecognized_tokens ────────────────────────────

    def test_select_alone_goes_to_unrecognized(self, alias_token_set):
        grade, product_class, unrecognized = detect_grade("spf select", alias_token_set)
        assert grade is None
        assert product_class is None
        assert unrecognized is not None
        assert "select" in unrecognized

    def test_prime_goes_to_unrecognized(self, alias_token_set):
        _, _, unrecognized = detect_grade("white pine prime", alias_token_set)
        assert unrecognized is not None
        assert "prime" in unrecognized

    def test_better_alone_goes_to_unrecognized(self, alias_token_set):
        _, _, unrecognized = detect_grade("spf better", alias_token_set)
        assert unrecognized is not None
        assert "better" in unrecognized

    # ── Alias vocab stays in cleaned_input ───────────────────────────────

    def test_kd_stays_in_vocab(self, alias_token_set):
        grade, product_class, unrecognized = detect_grade("spf kd", alias_token_set)
        assert grade is None
        assert product_class is None
        assert unrecognized is None

    def test_s4s_stays_in_vocab(self, alias_token_set):
        grade, product_class, unrecognized = detect_grade("spf s4s", alias_token_set)
        assert grade is None
        assert product_class is None
        assert unrecognized is None

    # ── Clean input — all None ────────────────────────────────────────────

    def test_no_classification_clean_input(self, alias_token_set):
        grade, product_class, unrecognized = detect_grade("spf", alias_token_set)
        assert grade is None
        assert product_class is None
        assert unrecognized is None

    # ── Unknown token → unrecognized ─────────────────────────────────────

    def test_unknown_token_captured(self, alias_token_set):
        _, _, unrecognized = detect_grade("spf xyz999", alias_token_set)
        assert unrecognized is not None
        assert "xyz999" in unrecognized


# ===========================================================================
# F. End-to-end parse() against test_cases.csv
# ===========================================================================

class TestParseEndToEnd:

    def test_lowes_whitewood_stud_2x4(self, alias_token_set):
        result = parse("Lowes Whitewood Stud 2x4", alias_token_set)
        assert result.detected_size == "2x4"
        assert result.detected_seller == "Lowes"
        assert result.detected_treatment is None

    def test_construction_white_wood_space_dim(self, alias_token_set):
        result = parse("Construction White Wood 2 x 4", alias_token_set)
        assert result.detected_size == "2x4"
        assert result.detected_treatment is None

    def test_douglass_fir_typo(self, alias_token_set):
        result = parse("Douglass Fir 2x8", alias_token_set)
        assert result.detected_size == "2x8"
        assert result.detected_treatment is None

    def test_doug_fir_larch_no_size(self, alias_token_set):
        result = parse("Doug Fir-Larch", alias_token_set)
        assert result.detected_size is None
        assert result.detected_treatment is None

    def test_syp_pt_three_part(self, alias_token_set):
        result = parse("SYP PT 4x4x8", alias_token_set)
        assert result.detected_size == "4x4x8"
        assert result.detected_treatment == "Pressure Treated"

    def test_hem_fir_2x6(self, alias_token_set):
        result = parse("Hem Fir 2x6", alias_token_set)
        assert result.detected_size == "2x6"
        assert result.detected_treatment is None

    def test_random_unknown(self, alias_token_set):
        result = parse("random unknown board xyz", alias_token_set)
        assert result.detected_size is None
        assert result.detected_treatment is None

    def test_osb_split_dimension(self, alias_token_set):
        result = parse("7/16 OSB sheathing 4x8", alias_token_set)
        assert result.detected_size == "7/16x4x8"
        assert result.detected_treatment is None

    def test_birch_ply_fraction_only(self, alias_token_set):
        result = parse("3/4 birch ply cabinet panel", alias_token_set)
        assert result.detected_size == "3/4"
        assert result.detected_treatment is None

    def test_pt_yellow_pine(self, alias_token_set):
        result = parse("PT Yellow Pine 4x4", alias_token_set)
        assert result.detected_size == "4x4"
        assert result.detected_treatment == "Pressure Treated"

    def test_parsed_input_has_all_fields(self, alias_token_set):
        result = parse("Lowes Whitewood Stud 2x4", alias_token_set)
        assert isinstance(result, ParsedInput)
        assert result.original_input == "Lowes Whitewood Stud 2x4"
        assert result.cleaned_input is not None
        assert result.size_label == "Thickness × Width"
        assert hasattr(result, "detected_product_class")
        assert hasattr(result, "consumed")

    def test_consumed_populated_when_dims_present(self, alias_token_set):
        """parse() stores the exact dimension spans extracted from input."""
        result = parse("SYP PT 4x4x8", alias_token_set)
        assert isinstance(result.consumed, list)
        assert len(result.consumed) > 0

    def test_consumed_empty_when_no_dims(self, alias_token_set):
        """parse() stores an empty list when no dimensions are extracted."""
        result = parse("Doug Fir-Larch", alias_token_set)
        assert isinstance(result.consumed, list)
        assert len(result.consumed) == 0

    def test_select_sample_goes_to_unrecognized(self, alias_token_set):
        result = parse("WhiteWood 3/4x4x8 Select", alias_token_set)
        assert result.detected_grade is None
        assert result.detected_product_class is None
        assert result.unrecognized_tokens is not None
        assert "select" in result.unrecognized_tokens

    def test_appearance_sample_goes_to_product_class(self, alias_token_set):
        result = parse("YELLAWOOD 15/32 x 4 x 8 Appearance", alias_token_set)
        assert result.detected_product_class is not None
        assert "appearance" in result.detected_product_class.lower()
        assert result.detected_grade is None

    def test_stud_grade_sample(self, alias_token_set):
        result = parse("Pressure-Treated-Yellow-Pine 2x4x8 Stud Grade", alias_token_set)
        assert result.detected_grade is not None
        assert "stud grade" in result.detected_grade.lower()
        assert result.detected_product_class is None

    def test_all_test_cases_sizes(self, alias_token_set, test_cases):
        """All rows with a non-empty expected_size must parse correctly."""
        for row in test_cases:
            expected_size = row["expected_size"].strip()
            if not expected_size:
                continue
            result = parse(row["input"], alias_token_set)
            assert result.detected_size == expected_size, (
                f"Input: {row['input']!r}\n"
                f"Expected size: {expected_size!r}\n"
                f"Got:           {result.detected_size!r}"
            )


# ── Group G — Hyphen normalisation in clean() (Phase 6 retroactive patch) ────

class TestCleanHyphenNormalisation:
    """Phase 6 patch: letter-adjacent hyphens → spaces in clean()."""

    def test_single_hyphen_between_letters(self):
        assert clean("hem-fir") == "hem fir"

    def test_multi_hyphen_compound(self):
        assert clean("spruce-pine-fir") == "spruce pine fir"

    def test_hyphen_rule_mirrors_slash_rule(self):
        # "spruce/pine/fir" and "spruce-pine-fir" must produce the same
        # cleaned string — both separators are purely typographic.
        assert clean("spruce-pine-fir") == clean("spruce/pine/fir")

    def test_digit_adjacent_hyphen_preserved(self):
        # Stud-length suffix "92-5/8": hyphen is between digit and digit,
        # not between two letters — must survive.
        result = clean("2x4x92-5/8")
        assert "92-5/8" in result

    def test_mixed_letter_and_digit_hyphens(self):
        # Letter-adjacent hyphens go; digit-adjacent hyphen stays.
        result = clean("pressure-treated-yellow-pine 2x4x92-5/8")
        assert "pressure treated yellow pine" in result
        assert "92-5/8" in result
