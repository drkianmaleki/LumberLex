"""
LumberLex — Phase 4: Fuzzy Matcher

Matches a cleaned query string against the alias index using RapidFuzz
token_sort_ratio. Returns a MatchResult with the best candidate, up to
(top_n - 1) alternative candidates, and a manual review flag.

Caller responsibility
─────────────────────
The caller (Phase 5 normalizer) is responsible for preparing the query
string before calling match(). Specifically:
  - Dimension spans should be stripped using ParsedInput.consumed so that
    "2x4", "4x8" etc. do not dilute fuzzy scores.
  - The seller name may remain in the query; token_sort_ratio handles
    extra tokens gracefully (Decision A, Phase 3).
See PROGRESS_SUMMARY.md — Phase 5 pending decisions.

Display aliases
───────────────
alias_index stores lowercase keys, so matched aliases are returned in
lowercase by default. Pass display_aliases (lowercase → original case)
to restore original case in MatchCandidate.alias:

    ali_df = load_aliases(ALIASES_PATH)
    display_aliases = dict(zip(ali_df["alias"].str.lower(), ali_df["alias"]))

Public API
──────────
    MatchCandidate  dataclass: alias, canonical_name, raw_score, confidence
    MatchResult     dataclass: best, alternatives, manual_review_required
    match()         (query, alias_index, top_n, display_aliases) -> MatchResult
    score_to_confidence()  (raw_score) -> float   exposed for Phase 5 calibration
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from .config import (
    CONFIDENCE_EXACT_MATCH,
    CONFIDENCE_SCORE_70_TO_79,
    CONFIDENCE_SCORE_80_TO_89,
    CONFIDENCE_SCORE_90_PLUS,
    CONFIDENCE_SUB_THRESHOLD_SCALE,
    MANUAL_REVIEW_THRESHOLD,
)


# ── Internal types ─────────────────────────────────────────────────────────────

@dataclass
class MatchCandidate:
    """A single alias match candidate returned by the fuzzy matcher."""

    alias: str
    """
    Alias string that matched. Original case if display_aliases was provided
    to match(); lowercase otherwise (alias_index keys are lowercase).
    """

    canonical_name: str
    """Canonical lumber type this alias maps to."""

    raw_score: float
    """Raw RapidFuzz token_sort_ratio score (0–100). Distinct from confidence."""

    confidence: float
    """Business-rule confidence (0.0–1.0), derived from raw_score via bands."""


@dataclass
class MatchResult:
    """Full result from a single match() call."""

    best: MatchCandidate | None
    """
    Highest-scoring candidate. None only when alias_index is empty or
    query is empty/whitespace — both indicate a data or caller error.
    """

    alternatives: list[MatchCandidate] = field(default_factory=list)
    """
    Runner-up candidates, descending by raw_score. Length is at most
    top_n - 1. Phase 5 converts these to AlternativeMatch schema objects.
    """

    manual_review_required: bool = False
    """
    True when best.raw_score < MANUAL_REVIEW_THRESHOLD, or when best is
    None. Phase 5 may add additional conditions (e.g. ambiguity_level).
    """


# ── Confidence mapping ─────────────────────────────────────────────────────────

def score_to_confidence(raw_score: float) -> float:
    """
    Map a RapidFuzz token_sort_ratio score (0–100) to a business-rule
    confidence value (0.0–1.0) using the approved band floor mapping.

    Thresholds are read from config/thresholds.yml — edit that file to
    recalibrate. No source code changes required.

    Band floors
    ───────────
        score >= 100          → CONFIDENCE_EXACT_MATCH   (default 0.95)
        score >= 90           → CONFIDENCE_SCORE_90_PLUS  (default 0.85)
        score 80–89           → CONFIDENCE_SCORE_80_TO_89 (default 0.70)
        score 70–79           → CONFIDENCE_SCORE_70_TO_79 (default 0.55)
        score < threshold     → (score / threshold) * sub_threshold_scale

    Score 100 via fuzzy (possible when token_sort_ratio sorts tokens into
    the same order for non-identical strings) is treated identically to
    an exact dict hit — information quality is equivalent.

    The sub-threshold formula always produces a value < CONFIDENCE_SCORE_70_TO_79,
    guaranteeing a clear separation between reviewable and confident results.

    Exposed as a standalone function so Phase 5 can replace or wrap it
    for calibration without touching the matching logic.
    """
    if raw_score >= 100.0:
        return CONFIDENCE_EXACT_MATCH
    if raw_score >= 90.0:
        return CONFIDENCE_SCORE_90_PLUS
    if raw_score >= 80.0:
        return CONFIDENCE_SCORE_80_TO_89
    if raw_score >= MANUAL_REVIEW_THRESHOLD:
        return CONFIDENCE_SCORE_70_TO_79
    # Sub-threshold: proportional linear, always < CONFIDENCE_SCORE_70_TO_79
    return (raw_score / MANUAL_REVIEW_THRESHOLD) * CONFIDENCE_SUB_THRESHOLD_SCALE


# ── Core matching logic ────────────────────────────────────────────────────────

def match(
    query: str,
    alias_index: dict[str, str],
    top_n: int = 3,
    display_aliases: dict[str, str] | None = None,
) -> MatchResult:
    """
    Match a query string against the alias index.

    Two-pass strategy
    ─────────────────
    Pass 1 — exact dict lookup (O(1)):
        query.lower() is looked up directly in alias_index. On a hit,
        returns immediately with confidence = CONFIDENCE_EXACT_MATCH and
        no alternatives. This is fast, unambiguous, and avoids running
        fuzzy when unnecessary.

    Pass 2 — fuzzy matching (RapidFuzz token_sort_ratio):
        Runs only when Pass 1 misses. Scores query against all alias_index
        keys and returns up to top_n candidates sorted descending by score.

    Parameters
    ──────────
    query : str
        Cleaned string to match. The Phase 5 normalizer strips dimension
        spans (using ParsedInput.consumed) before calling this function.
        The seller name may remain; token_sort_ratio handles extra tokens.
    alias_index : dict[str, str]
        Lowercase alias → canonical_name. Built by Phase 1 build_lookup().
    top_n : int
        Maximum total candidates to return (best + alternatives combined).
        Defaults to 3.
    display_aliases : dict[str, str] | None
        Optional lowercase → original-case mapping. When provided,
        MatchCandidate.alias returns original case ("Whitewood Stud"
        rather than "whitewood stud"). Build with:
            dict(zip(ali_df["alias"].str.lower(), ali_df["alias"]))

    Returns
    ───────
    MatchResult
        best                   : top candidate (None only on empty inputs)
        alternatives           : remaining candidates, descending score
        manual_review_required : True if best.raw_score < threshold
    """
    # Guard: empty query or empty alias_index — nothing to match against.
    if not query or not query.strip() or not alias_index:
        return MatchResult(best=None, alternatives=[], manual_review_required=True)

    q = query.lower().strip()

    # ── Pass 1: exact dict lookup ──────────────────────────────────────
    canonical = alias_index.get(q)
    if canonical is not None:
        display = display_aliases.get(q, q) if display_aliases else q
        best = MatchCandidate(
            alias=display,
            canonical_name=canonical,
            raw_score=100.0,
            confidence=CONFIDENCE_EXACT_MATCH,
        )
        return MatchResult(best=best, alternatives=[], manual_review_required=False)

    # ── Pass 2: fuzzy matching ─────────────────────────────────────────
    lowercase_keys = list(alias_index.keys())

    # process.extract returns (choice, score, index) tuples — rapidfuzz >= 3.0
    results = process.extract(
        q,
        lowercase_keys,
        scorer=fuzz.token_sort_ratio,
        limit=top_n,
    )

    if not results:
        return MatchResult(best=None, alternatives=[], manual_review_required=True)

    candidates: list[MatchCandidate] = []
    for choice, score, _ in results:
        raw = float(score)
        display = display_aliases.get(choice, choice) if display_aliases else choice
        candidates.append(
            MatchCandidate(
                alias=display,
                canonical_name=alias_index[choice],
                raw_score=raw,
                confidence=score_to_confidence(raw),
            )
        )

    best = candidates[0]
    alternatives = candidates[1:]
    manual_review = best.raw_score < MANUAL_REVIEW_THRESHOLD

    return MatchResult(
        best=best,
        alternatives=alternatives,
        manual_review_required=manual_review,
    )
