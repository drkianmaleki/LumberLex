"""
LumberLex — Output Schema (Phase 2)
Defines the single output contract for the entire system.

Phase 2 retroactive patches applied:
  - detected_grade: str | None             (Decision F)
  - unrecognized_tokens: list[str] | None  (approved during Phase 3 design)
  - detected_product_class: str | None     (Option 2 split: formal grades vs
                                            application/category terms)
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# AlternativeMatch — a runner-up candidate from the fuzzy matcher
# ---------------------------------------------------------------------------

class AlternativeMatch(BaseModel):
    alias: str
    canonical_name: str
    score: float = Field(ge=0.0, le=100.0)   # raw RapidFuzz score, 0–100


# ---------------------------------------------------------------------------
# NormalizationResult — 19-field output contract
# ---------------------------------------------------------------------------

class NormalizationResult(BaseModel):

    # ── Input (caller) ──────────────────────────────────────────────────────
    original_input: str
    cleaned_input: str

    # ── Core result (Phase 4 / 5) ───────────────────────────────────────────
    normalized_name: str                              # canonical or "UNKNOWN"
    species_group: Optional[str] = None
    category: Optional[str] = None
    ambiguity_level: Optional[Literal["Low", "Medium", "High"]] = None
    treatment: Optional[str] = None                  # "Pressure Treated" | None

    # ── Parser output (Phase 3) ─────────────────────────────────────────────
    detected_size: Optional[str] = None              # e.g. "2x4", "7/16x4x8"
    size_label: Optional[str] = None                 # e.g. "Thickness × Width"
    detected_seller: Optional[str] = None            # e.g. "Lowes"
    detected_grade: Optional[str] = None             # formal grade: "#2", "stud grade"
    detected_product_class: Optional[str] = None     # application/category: "appearance"
    unrecognized_tokens: Optional[list[str]] = None  # tokens parser couldn't classify

    # ── Matching (Phase 4) ──────────────────────────────────────────────────
    confidence: float = Field(ge=0.0, le=1.0)
    best_alias_match: Optional[str] = None
    alternative_matches: list[AlternativeMatch] = Field(default_factory=list)

    # ── Review and explanation (Phase 5) ────────────────────────────────────
    manual_review_required: bool = False
    warning: Optional[str] = None      # ambiguity warning; UI renders a warning box
    explanation: Optional[str] = None  # human-readable summary
