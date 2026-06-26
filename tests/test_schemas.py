"""
Phase 2 — Schema Tests
25 original tests + tests for Phase 2 retroactive patch fields:
  detected_grade and unrecognized_tokens.
"""

import json
import pytest

from lumberlex.schemas import AlternativeMatch, NormalizationResult


# ---------------------------------------------------------------------------
# AlternativeMatch
# ---------------------------------------------------------------------------

def test_alternative_match_instantiation():
    m = AlternativeMatch(alias="SPF", canonical_name="SPF", score=92.5)
    assert m.alias == "SPF"
    assert m.canonical_name == "SPF"
    assert m.score == 92.5

def test_alternative_match_score_lower_bound():
    m = AlternativeMatch(alias="X", canonical_name="X", score=0.0)
    assert m.score == 0.0

def test_alternative_match_score_upper_bound():
    m = AlternativeMatch(alias="X", canonical_name="X", score=100.0)
    assert m.score == 100.0

def test_alternative_match_score_out_of_range_raises():
    with pytest.raises(Exception):
        AlternativeMatch(alias="X", canonical_name="X", score=101.0)


# ---------------------------------------------------------------------------
# NormalizationResult — happy path
# ---------------------------------------------------------------------------

def _make_result(**kwargs) -> NormalizationResult:
    defaults = dict(
        original_input="SPF 2x4",
        cleaned_input="spf 2x4",
        normalized_name="SPF",
        confidence=0.90,
    )
    defaults.update(kwargs)
    return NormalizationResult(**defaults)

def test_normalization_result_minimal_construction():
    r = _make_result()
    assert r.normalized_name == "SPF"
    assert r.confidence == 0.90

def test_normalization_result_all_base_fields_present():
    r = _make_result()
    for field in (
        "original_input", "cleaned_input", "normalized_name", "species_group",
        "category", "ambiguity_level", "treatment", "detected_size",
        "size_label", "detected_seller", "detected_grade", "detected_product_class",
        "confidence", "best_alias_match",
        "alternative_matches", "manual_review_required", "warning", "explanation",
        "unrecognized_tokens",
    ):
        assert hasattr(r, field)

def test_normalization_result_optional_defaults_are_none():
    r = _make_result()
    assert r.species_group is None
    assert r.category is None
    assert r.ambiguity_level is None
    assert r.treatment is None
    assert r.detected_size is None
    assert r.size_label is None
    assert r.detected_seller is None
    assert r.detected_grade is None
    assert r.detected_product_class is None
    assert r.best_alias_match is None
    assert r.warning is None
    assert r.explanation is None

def test_normalization_result_alternative_matches_default_empty():
    r = _make_result()
    assert r.alternative_matches == []

def test_normalization_result_manual_review_default_false():
    r = _make_result()
    assert r.manual_review_required is False

def test_normalization_result_with_full_data():
    r = _make_result(
        species_group="Spruce-Pine-Fir",
        category="Dimensional framing lumber",
        ambiguity_level="High",
        treatment=None,
        detected_size="2x4",
        size_label="Thickness × Width",
        detected_seller="Lowes",
        best_alias_match="Whitewood Stud",
        alternative_matches=[
            AlternativeMatch(alias="SPF", canonical_name="SPF", score=88.0)
        ],
        manual_review_required=False,
        warning="Whitewood is a trade term; exact species may vary.",
        explanation="Matched via fuzzy alias.",
    )
    assert r.species_group == "Spruce-Pine-Fir"
    assert r.ambiguity_level == "High"
    assert len(r.alternative_matches) == 1

def test_normalization_result_unknown_shape():
    r = NormalizationResult(
        original_input="random unknown board xyz",
        cleaned_input="random unknown board xyz",
        normalized_name="UNKNOWN",
        confidence=0.28,
        manual_review_required=True,
    )
    assert r.normalized_name == "UNKNOWN"
    assert r.confidence < 0.60
    assert r.manual_review_required is True

def test_normalization_result_full_construction_check():
    r = _make_result(
        species_group="Spruce-Pine-Fir",
        category="Dimensional framing lumber",
        ambiguity_level="High",
        detected_size="2x4",
        size_label="Thickness × Width",
        confidence=0.88,
    )
    assert r.detected_size == "2x4"
    assert r.size_label == "Thickness × Width"


# ---------------------------------------------------------------------------
# NormalizationResult — size_label and detected_seller (Phase 2 new fields)
# ---------------------------------------------------------------------------

def test_size_label_default_is_none():
    r = _make_result()
    assert r.size_label is None

def test_size_label_accepts_string():
    r = _make_result(size_label="Thickness × Width × Length")
    assert r.size_label == "Thickness × Width × Length"

def test_detected_seller_default_is_none():
    r = _make_result()
    assert r.detected_seller is None

def test_detected_seller_accepts_string():
    r = _make_result(detected_seller="84 Lumber")
    assert r.detected_seller == "84 Lumber"

def test_three_part_size_label_convention():
    r = _make_result(detected_size="4x4x8", size_label="Thickness × Width × Length")
    assert "Length" in r.size_label

def test_thickness_only_size_label():
    r = _make_result(detected_size="3/4", size_label="Thickness")
    assert r.size_label == "Thickness"


# ---------------------------------------------------------------------------
# NormalizationResult — validation
# ---------------------------------------------------------------------------

def test_confidence_below_zero_raises():
    with pytest.raises(Exception):
        _make_result(confidence=-0.01)

def test_confidence_above_one_raises():
    with pytest.raises(Exception):
        _make_result(confidence=1.01)

def test_confidence_boundary_zero():
    r = _make_result(confidence=0.0)
    assert r.confidence == 0.0

def test_confidence_boundary_one():
    r = _make_result(confidence=1.0)
    assert r.confidence == 1.0

def test_invalid_ambiguity_level_raises():
    with pytest.raises(Exception):
        _make_result(ambiguity_level="Extreme")


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def test_model_dump_has_all_keys():
    r = _make_result()
    d = r.model_dump()
    for key in ("original_input", "cleaned_input", "normalized_name",
                "confidence", "alternative_matches"):
        assert key in d

def test_model_dump_nested_alternative_match():
    r = _make_result(
        alternative_matches=[
            AlternativeMatch(alias="Whitewood", canonical_name="SPF", score=85.0)
        ]
    )
    d = r.model_dump()
    assert isinstance(d["alternative_matches"][0], dict)
    assert d["alternative_matches"][0]["alias"] == "Whitewood"

def test_model_dump_json_is_string():
    r = _make_result()
    assert isinstance(r.model_dump_json(), str)

def test_model_dump_json_null_for_none():
    r = _make_result()
    d = json.loads(r.model_dump_json())
    assert d["species_group"] is None
    assert d["detected_size"] is None


# ---------------------------------------------------------------------------
# Phase 2 retroactive patch — detected_grade and unrecognized_tokens
# ---------------------------------------------------------------------------

def test_detected_grade_default_is_none():
    r = _make_result()
    assert r.detected_grade is None

def test_detected_grade_accepts_string():
    r = _make_result(detected_grade="select")
    assert r.detected_grade == "select"

def test_unrecognized_tokens_default_is_none():
    r = _make_result()
    assert r.unrecognized_tokens is None

def test_unrecognized_tokens_accepts_list():
    r = _make_result(unrecognized_tokens=["xyz123", "3/5"])
    assert r.unrecognized_tokens == ["xyz123", "3/5"]

def test_detected_grade_in_model_dump():
    r = _make_result(detected_grade="#2")
    d = r.model_dump()
    assert "detected_grade" in d
    assert d["detected_grade"] == "#2"

def test_unrecognized_tokens_in_model_dump_json():
    r = _make_result(unrecognized_tokens=["weird"])
    d = json.loads(r.model_dump_json())
    assert d["unrecognized_tokens"] == ["weird"]

# ---------------------------------------------------------------------------
# Phase 2 retroactive patch — detected_product_class
# ---------------------------------------------------------------------------

def test_detected_product_class_default_is_none():
    r = _make_result()
    assert r.detected_product_class is None

def test_detected_product_class_accepts_string():
    r = _make_result(detected_product_class="appearance")
    assert r.detected_product_class == "appearance"

def test_detected_product_class_in_model_dump():
    r = _make_result(detected_product_class="framing")
    d = r.model_dump()
    assert "detected_product_class" in d
    assert d["detected_product_class"] == "framing"

def test_detected_product_class_null_in_model_dump_json():
    r = _make_result()
    import json
    d = json.loads(r.model_dump_json())
    assert d["detected_product_class"] is None

def test_grade_and_product_class_independent():
    r = _make_result(detected_grade="#2", detected_product_class="appearance")
    assert r.detected_grade == "#2"
    assert r.detected_product_class == "appearance"
