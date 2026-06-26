"""
LumberLex — Normalizer (Phase 5)

Orchestrates parser + matcher into a single normalize() call and produces
a fully populated NormalizationResult.

Pipeline (per call to normalize()):
  1. parse()  → ParsedInput   (clean, seller, treatment, dims, grade)
  2. Build match query        (cleaned_input minus dimension spans)
  3. match()  → MatchResult   (fuzzy match against alias index)
  4. Fetch canonical metadata from canonical_index
  5. Apply treatment union rule
  6. Generate warning         (High ambiguity only; text from canonical notes)
  7. Generate explanation     (Option C template)
  8. Assemble NormalizationResult

Public API
──────────
    Normalizer                  class
    Normalizer.from_files()     classmethod — standard startup call site
    Normalizer.normalize()      main entry point per raw string
"""

from __future__ import annotations

import re

from .data_layer import (
    DEFAULT_ALIASES_PATH,
    DEFAULT_CANONICALS_PATH,
    build_lookup,
    load_aliases,
    load_canonicals,
)
from .matcher import match
from .parser import build_alias_token_set, parse
from .schemas import AlternativeMatch, NormalizationResult


class Normalizer:
    """
    Orchestrates the full LumberLex normalization pipeline.

    Instantiate once at startup; call normalize() per request.

    Typical usage:
        normalizer = Normalizer.from_files()
        result = normalizer.normalize("Lowes Whitewood Stud 2x4")

    Or via the convenience function (cached module-level instance):
        from lumberlex import normalize
        result = normalize("Lowes Whitewood Stud 2x4")

    For pytest, pass pre-built dicts to __init__() to avoid filesystem I/O
    in every test:
        alias_index, canonical_index = build_lookup(can_df, ali_df)
        alias_token_set = build_alias_token_set(alias_index)
        display_aliases = dict(zip(ali_df["alias"].str.lower(), ali_df["alias"]))
        normalizer = Normalizer(alias_index, canonical_index,
                                alias_token_set, display_aliases)
    """

    def __init__(
        self,
        alias_index: dict[str, str],
        canonical_index: dict,
        alias_token_set: frozenset[str],
        display_aliases: dict[str, str],
    ) -> None:
        self._alias_index = alias_index
        self._canonical_index = canonical_index
        self._alias_token_set = alias_token_set
        self._display_aliases = display_aliases

    @classmethod
    def from_files(
        cls,
        canonicals_path: str = DEFAULT_CANONICALS_PATH,
        aliases_path: str = DEFAULT_ALIASES_PATH,
    ) -> "Normalizer":
        """
        Load CSVs, build all lookup structures, and return a Normalizer.

        Paths default to the bundled data files inside the installed package.
        Pass explicit paths to use custom canonicals or alias tables.

        Args:
            canonicals_path: path to canonicals.csv (default: bundled)
            aliases_path:    path to aliases.csv    (default: bundled)

        Returns:
            Fully initialised Normalizer instance.
        """
        can_df = load_canonicals(canonicals_path)
        ali_df = load_aliases(aliases_path)
        alias_index, canonical_index = build_lookup(can_df, ali_df)
        alias_token_set = build_alias_token_set(alias_index)
        display_aliases = dict(zip(ali_df["alias"].str.lower(), ali_df["alias"]))
        return cls(alias_index, canonical_index, alias_token_set, display_aliases)

    # ── Main entry point ───────────────────────────────────────────────────────

    def normalize(self, raw: str) -> NormalizationResult:
        """
        Full normalization pipeline for a single raw product name string.

        Args:
            raw: original product name string, e.g. "Lowes Whitewood Stud 2x4"

        Returns:
            NormalizationResult with all 19 fields populated.
        """
        # ── Step 1: Parse ──────────────────────────────────────────────────────
        parsed = parse(raw, self._alias_token_set)

        # ── Step 2: Build match query ──────────────────────────────────────────
        # Strip dimension spans (via ParsedInput.consumed) from cleaned_input.
        # Also strip detected_product_class tokens (appearance, kiln dried,
        # common, outdoor, etc.) — these describe end-use, not species identity,
        # and leaving them in the query can cause false matches against aliases
        # like "Appearance Pine" when the product-class token dominates the
        # fuzzy score.
        # Seller name and treatment tokens remain (Decision A / Decision V).
        # Known trade-off: inputs where the product-class token IS the
        # discriminating signal (e.g. "Appearance Pine", "Common Pine") may
        # score lower post-strip. See docs/KNOWN_CHALLENGES.md §2.
        query = parsed.cleaned_input
        for span in parsed.consumed:
            query = query.replace(span, " ")
        if parsed.detected_product_class:
            query = query.replace(parsed.detected_product_class, " ")
        query = re.sub(r"\s+", " ", query).strip()

        # ── Step 3: Fuzzy match ────────────────────────────────────────────────
        match_result = match(
            query,
            self._alias_index,
            top_n=3,
            display_aliases=self._display_aliases,
        )

        # ── Step 4: Canonical metadata ─────────────────────────────────────────
        # manual_review_required drives the UNKNOWN outcome. When True, all
        # metadata fields remain None and normalized_name = "UNKNOWN".
        if match_result.manual_review_required:
            canonical_name = "UNKNOWN"
            entry = None
        else:
            canonical_name = match_result.best.canonical_name
            entry = self._canonical_index.get(canonical_name)

        # ── Step 5: Treatment — union rule ─────────────────────────────────────
        # Parser-detected treatment takes priority (explicit signal from raw).
        # Canonical treatment is the fallback (catches brand names like
        # YellaWood that imply treatment without containing a keyword).
        canonical_treatment = (entry.treatment if entry and entry.treatment else None)
        treatment = parsed.detected_treatment or canonical_treatment

        # ── Step 6: Warning — High ambiguity only ──────────────────────────────
        # Text is the canonical's own notes field — no separate warning strings
        # to maintain. Medium and Low ambiguity do not trigger a warning.
        warning: str | None = None
        if entry is not None and entry.ambiguity_level == "High":
            warning = entry.notes

        # ── Step 7: Explanation ────────────────────────────────────────────────
        explanation = self._build_explanation(parsed, match_result, canonical_name, entry)

        # ── Step 8: Assemble NormalizationResult ──────────────────────────────
        if match_result.best is not None and not match_result.manual_review_required:
            confidence = match_result.best.confidence
            best_alias: str | None = match_result.best.alias
            alternative_matches = [
                AlternativeMatch(
                    alias=c.alias,
                    canonical_name=c.canonical_name,
                    score=c.raw_score,
                )
                for c in match_result.alternatives
            ]
        else:
            # UNKNOWN: confidence is still real (shows how close the best was),
            # but alias fields are None / empty — we do not commit to a wrong match.
            confidence = match_result.best.confidence if match_result.best else 0.0
            best_alias = None
            alternative_matches = []

        return NormalizationResult(
            # Input
            original_input=parsed.original_input,
            cleaned_input=parsed.cleaned_input,
            # Core result
            normalized_name=canonical_name,
            species_group=entry.species_group if entry else None,
            category=entry.category if entry else None,
            ambiguity_level=entry.ambiguity_level if entry else None,
            treatment=treatment,
            # Parser output
            detected_size=parsed.detected_size,
            size_label=parsed.size_label,
            detected_seller=parsed.detected_seller,
            detected_grade=parsed.detected_grade,
            detected_product_class=parsed.detected_product_class,
            unrecognized_tokens=parsed.unrecognized_tokens,
            # Matching
            confidence=confidence,
            best_alias_match=best_alias,
            alternative_matches=alternative_matches,
            # Review and explanation
            manual_review_required=match_result.manual_review_required,
            warning=warning,
            explanation=explanation,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_explanation(self, parsed, match_result, canonical_name: str, entry) -> str:
        """
        Build the Option C human-readable explanation string.

        For a successful match: one base sentence (canonical, alias, confidence)
        followed by optional clauses for seller, treatment, and size — each
        included only when the field is not None.

        For UNKNOWN / manual review: a fixed 'could not be matched' sentence.
        """
        if match_result.manual_review_required or match_result.best is None:
            return (
                f"'{parsed.original_input}' could not be matched to a known "
                f"lumber type. The closest candidate scored below the minimum "
                f"confidence threshold. This result requires manual review."
            )

        species_group = entry.species_group if entry else canonical_name
        confidence = match_result.best.confidence
        alias = match_result.best.alias

        parts = [
            f"'{parsed.original_input}' was matched to {canonical_name} "
            f"({species_group}) via the alias '{alias}' with a confidence "
            f"of {confidence:.2f}."
        ]

        if parsed.detected_seller:
            parts.append(
                f"Seller '{parsed.detected_seller}' was detected and "
                f"retained in the search."
            )

        if parsed.detected_treatment:
            parts.append("Pressure treatment was detected in the input.")

        if parsed.detected_size:
            parts.append(
                f"Dimensions '{parsed.detected_size}' were extracted "
                f"before matching."
            )

        return " ".join(parts)
