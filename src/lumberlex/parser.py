"""
LumberLex — Parser (Phase 3)

Responsibilities:
  - clean()                  Text normalisation (case, punctuation, whitespace)
  - detect_seller()          Hard-coded seller prefix detection
  - detect_treatment()       Treatment token detection
  - extract_dimensions()     Two-pass dimension extraction with fraction whitelist
  - build_alias_token_set()  Build species/type vocabulary from alias index
  - detect_grade()           Two-tier detection → grade / product_class / unrecognized
  - parse()                  Orchestrates all of the above → ParsedInput

ParsedInput is an internal dataclass. Phase 5 (normalizer) assembles a full
NormalizationResult by combining ParsedInput with the matcher's output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ===========================================================================
# Constants
# ===========================================================================

# Hard-coded seller list (sourced from lumberlex_sample_database.csv sellers)
KNOWN_SELLERS: list[str] = [
    "84 Lumber",
    "Home Depot",
    "Independent Lumberyard",
    "Contractor Catalog",
    "Vendor Price Sheet",
    "Builder Supply",
    "ERP Legacy Import",
    "Menards",
    "Lowes",
    "Local Yard",
]

# Sorted longest-first so "84 Lumber" is checked before "84"
_SELLERS_BY_LENGTH = sorted(KNOWN_SELLERS, key=len, reverse=True)

# Treatment vocabulary
_TREATMENT_PATTERNS = [
    r"\bpressure[\s\-]treated\b",
    r"\bpressure\b",   # "pressure" alone is strong enough in lumber context
    r"\btreated\b",
    r"\b(pt)\b",
    r"\bacq\b",
    r"\bmca\b",
]
_TREATMENT_RE = re.compile(
    "|".join(_TREATMENT_PATTERNS),
    re.IGNORECASE,
)

# Lumber fraction whitelist — only denominators that are powers of 2
# and appear in real lumber/panel sizing
_VALID_LUMBER_FRACTIONS: frozenset[str] = frozenset({
    "1/4", "11/32", "3/8", "7/16", "15/32", "1/2",
    "19/32", "5/8", "23/32", "3/4", "7/8", "5/4",
    "1/3",   # occasionally appears in legacy ERP data
})

# A fraction token: digits/digits (e.g. 7/16, 3/4, 15/32)
_FRAC = r"\d+/\d+"
# An integer dimension (1–99)
_INT  = r"\d{1,2}"
# Either form
_DIM  = rf"(?:{_FRAC}|{_INT})"
# The "x" separator, optionally surrounded by spaces
_X    = r"\s*[xX]\s*"
# Stud length suffix: optional "-N/N" (e.g. 92-5/8)
_STUD = rf"(?:-{_FRAC})?"

# Pass 1 handles contiguous 3-part patterns ONLY.
# 2-part patterns (e.g. "2x4", "2x6") are intentionally excluded here so
# that Pass 2 can first check for a floating fraction elsewhere in the string
# (e.g. "7/16 OSB sheathing 4x8" must combine 7/16 with 4x8, not return 4x8
# alone from a two-part match that fires before the fraction is found).
_DIM_PATTERNS_3PART: list[tuple[str, str]] = [
    # 3-part with optional stud suffix: 2x4x92-5/8, 7/16x4x8, 4x4x8
    ("three_part", rf"(?:{_DIM}){_X}(?:{_DIM}){_X}(?:{_INT}{_STUD})"),
]

# ── Formal NLGA/WWPA grade codes (Tier 2 single-word) ──────────────────────
# Only tokens that are unambiguously grade codes and do NOT appear in the alias
# table as species/product descriptors.
#
# Excluded as single tokens — too ambiguous:
#   "stud"         → appears in aliases (Whitewood Stud, SPF Stud, Hem-Fir Stud)
#   "construction" → appears in aliases (Construction Whitewood → SPF)
# Both are still caught as grades via _GRADE_PHRASES ("stud grade").
_GRADE_WORD_PATTERNS = [
    r"#\d+",      # #1, #2, #3 — pure grade codes, never species descriptors
    r"standard",   # NLGA grade; does not appear in alias table
    r"utility",    # NLGA grade; does not appear in alias table
    r"btr",        # abbreviation for "better" in formal grade strings
]
_GRADE_WORD_RE = re.compile(
    r"^(?:" + "|".join(_GRADE_WORD_PATTERNS) + r")$",
    re.IGNORECASE,
)

# Formal grade phrases (Tier 1) — checked as substrings before token splitting
_GRADE_PHRASES: list[str] = [
    "select structural",   # formal NLGA phrase grade
    "stud grade",          # maps to NLGA Stud grade
    "no 2", "no 1", "no 3",
    "no. 2", "no. 1", "no. 3",
    "#2 better", "#2&btr", "#2 & btr",
]

# ── Product class / application terms (Tier 2 single-word) ──────────────────
# Clear application or product-category terms — not formal grades.
_PRODUCT_CLASS_WORD_PATTERNS = [
    r"appearance",   # decorative/visible-use lumber
    r"common",       # common board product class
    r"framing",      # structural framing application
    r"outdoor",      # exterior application
]
_PRODUCT_CLASS_WORD_RE = re.compile(
    r"^(?:" + "|".join(_PRODUCT_CLASS_WORD_PATTERNS) + r")$",
    re.IGNORECASE,
)

# Product class phrases (Tier 1)
_PRODUCT_CLASS_PHRASES: list[str] = [
    "rough sawn",
    "rough-sawn",
    "kiln dried",
    "kiln-dried",
]

# ── Ambiguous tokens — go to unrecognized_tokens ────────────────────────────
# Cannot be confidently classified as grade or product class.
# The fuzzy matcher still sees them via cleaned_input.
_AMBIGUOUS_TOKENS: frozenset[str] = frozenset({
    "select", "prime", "better", "green",
})

# ── Structural English words — silently skipped ──────────────────────────────
# Common words in product descriptions that carry no lumber-specific meaning.
_STRUCTURAL_WORDS: frozenset[str] = frozenset({
    "lumber", "board", "panel", "sheet", "sheathing", "decking",
    "structural", "dimensional", "cabinet", "fence",
    "picket", "interior", "exterior",
    "project", "construction",
    "no", "and", "or", "for", "the", "with",
})


# ===========================================================================
# ParsedInput — internal struct returned by parse()
# ===========================================================================

@dataclass
class ParsedInput:
    original_input: str
    cleaned_input: str
    detected_size: Optional[str] = None
    size_label: Optional[str] = None
    detected_seller: Optional[str] = None
    detected_treatment: Optional[str] = None
    detected_grade: Optional[str] = None
    detected_product_class: Optional[str] = None
    unrecognized_tokens: Optional[list[str]] = field(default=None)
    consumed: list[str] = field(default_factory=list)
    # Exact dimension substrings extracted by extract_dimensions().
    # Phase 5 (Normalizer) strips these from cleaned_input before calling
    # match(), preventing dimension tokens from diluting fuzzy scores.


# ===========================================================================
# build_alias_token_set — called once at startup
# ===========================================================================

def build_alias_token_set(alias_index: dict[str, str]) -> frozenset[str]:
    """
    Tokenise every lowercased alias in alias_index into individual words.
    The resulting frozenset is the authoritative species/type vocabulary —
    any token present here is a known lumber term and stays in cleaned_input.

    Args:
        alias_index: dict[lowercase alias → canonical_name] from build_lookup()

    Returns:
        frozenset of lowercase tokens derived from all alias strings.
    """
    tokens: set[str] = set()
    splitter = re.compile(r"[\s\-/]+")
    for alias in alias_index:
        for tok in splitter.split(alias.lower()):
            tok = tok.strip()
            if tok:
                tokens.add(tok)
    return frozenset(tokens)


# ===========================================================================
# clean — text normalisation
# ===========================================================================

def clean(raw: str) -> str:
    """
    Normalise a raw product name string for comparison.

    Operations applied in order:
    1. Lowercase
    2. Letter-adjacent slashes → space  (Spruce/Pine/Fir → spruce pine fir)
       Digit-adjacent slashes are preserved  (7/16, 3/4, 15/32 stay intact)
    3. Letter-adjacent hyphens → space  (Hem-Fir → hem fir, SY-Pine → sy pine)
       Digit-adjacent hyphens are preserved  (92-5/8 stays intact)
    4. Remove periods and commas
    5. Collapse multiple whitespace characters into a single space
    6. Strip leading and trailing whitespace

    Args:
        raw: original product name string

    Returns:
        Cleaned string ready for downstream processing.
    """
    s = raw.lower()

    # Letter-adjacent slash → space (but preserve digit/digit fractions)
    s = re.sub(r"(?<=[a-z])/(?=[a-z])", " ", s)
    s = re.sub(r"(?<=[a-z])/(?=\d)", " ", s)
    s = re.sub(r"(?<=\d)/(?=[a-z])", " ", s)

    # Letter-adjacent hyphen → space (Hem-Fir → hem fir, SY-Pine → sy pine).
    # Mirrors the slash rule above. Digit-adjacent hyphens (e.g. 92-5/8) are
    # untouched because the lookbehind/lookahead require [a-z] on both sides.
    s = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", s)

    # Remove periods and commas
    s = re.sub(r"[.,]", "", s)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    return s


# ===========================================================================
# detect_seller
# ===========================================================================

def detect_seller(raw: str) -> Optional[str]:
    """
    Check whether raw starts with a known seller name.
    Comparison is case-insensitive; sellers are checked longest-first
    to avoid partial matches.

    Args:
        raw: original (uncleaned) product name

    Returns:
        Matched seller string (from KNOWN_SELLERS) or None.
    """
    lower = raw.lower().strip()
    for seller in _SELLERS_BY_LENGTH:
        if lower.startswith(seller.lower()):
            return seller
    return None


# ===========================================================================
# detect_treatment
# ===========================================================================

def detect_treatment(raw: str) -> Optional[str]:
    """
    Detect treatment indicators in the raw product name.

    Returns "Pressure Treated" if any treatment token is found, else None.
    Detection is done on the raw (not cleaned) string to catch all variants
    before cleaning modifies the text.

    Args:
        raw: original product name string

    Returns:
        "Pressure Treated" or None.
    """
    if _TREATMENT_RE.search(raw):
        return "Pressure Treated"
    return None


# ===========================================================================
# extract_dimensions — two-pass algorithm
# ===========================================================================

def _normalise_dim_string(s: str) -> str:
    """Collapse spaces around 'x' separators: '2 x 4 x 8' → '2x4x8'."""
    return re.sub(r"\s*[xX]\s*", "x", s)


def _validate_fraction(token: str) -> bool:
    """Return True if token is a whitelisted lumber fraction."""
    return token in _VALID_LUMBER_FRACTIONS


def extract_dimensions(
    cleaned: str,
) -> tuple[Optional[str], Optional[str], Optional[list[str]], list[str]]:
    """
    Two-pass dimension extraction.

    Pass 1 — contiguous 3-part pattern scan:
        Tries to match a full 3-part dimension token as a single contiguous
        string. If found, returns immediately.

    Pass 2 — split scan (only if Pass 1 finds nothing):
        Looks independently for a whitelisted fraction token and/or a bare
        NxN/NxNxN pattern. Combines them if both are found.
        Non-whitelist fractions are collected into unrecognized.

    Args:
        cleaned: output of clean()

    Returns:
        (detected_size, size_label, extra_unrecognized, consumed)
        detected_size:      normalised dimension string or None
        size_label:         "Thickness", "Thickness × Width", or
                            "Thickness × Width × Length", or None
        extra_unrecognized: list of fraction-like strings that didn't pass
                            the whitelist, or None
        consumed:           list of exact substrings matched from cleaned
                            so parse() can strip them precisely from the text
    """
    extra_unrecognized: list[str] = []
    consumed: list[str] = []

    # ── Pass 1: contiguous 3-part match only ────────────────────────────
    for label_kind, pattern in _DIM_PATTERNS_3PART:
        m = re.search(pattern, cleaned)
        if m:
            raw_match = m.group(0).strip()
            norm = _normalise_dim_string(raw_match)

            # Validate any fraction components in the match
            parts = re.split(r"x", norm, flags=re.IGNORECASE)
            for part in parts:
                if "/" in part:
                    frac = re.match(r"(\d+/\d+)", part)
                    if frac and not _validate_fraction(frac.group(1)):
                        extra_unrecognized.append(frac.group(1))

            consumed.append(raw_match)
            size_label = _make_size_label(norm)
            return (
                norm,
                size_label,
                extra_unrecognized if extra_unrecognized else None,
                consumed,
            )

    # ── Pass 2: split scan ───────────────────────────────────────────────
    # Find all fraction-like tokens
    frac_matches = re.findall(r"\b\d+/\d+\b", cleaned)
    valid_fracs = []
    for f in frac_matches:
        if _validate_fraction(f):
            valid_fracs.append(f)
        else:
            extra_unrecognized.append(f)

    # Find standalone bare NxN or NxNxN (integers only, no fractions)
    bare_dim_match = re.search(
        r"\b\d{1,2}\s*[xX]\s*\d{1,2}(?:\s*[xX]\s*\d{1,2})?\b",
        cleaned,
    )

    leading_frac = valid_fracs[0] if valid_fracs else None

    if leading_frac and bare_dim_match:
        bare_raw = bare_dim_match.group(0).strip()
        bare = _normalise_dim_string(bare_raw)
        combined = f"{leading_frac}x{bare}"
        consumed.extend([leading_frac, bare_raw])
        size_label = _make_size_label(combined)
        return (
            combined,
            size_label,
            extra_unrecognized if extra_unrecognized else None,
            consumed,
        )

    if leading_frac:
        consumed.append(leading_frac)
        size_label = _make_size_label(leading_frac)
        return (
            leading_frac,
            size_label,
            extra_unrecognized if extra_unrecognized else None,
            consumed,
        )

    if bare_dim_match:
        bare_raw = bare_dim_match.group(0).strip()
        bare = _normalise_dim_string(bare_raw)
        consumed.append(bare_raw)
        size_label = _make_size_label(bare)
        return (
            bare,
            size_label,
            extra_unrecognized if extra_unrecognized else None,
            consumed,
        )

    return (
        None,
        None,
        extra_unrecognized if extra_unrecognized else None,
        consumed,
    )


def _make_size_label(size_str: str) -> str:
    """Assign a human-readable label based on number of dimension components."""
    parts = re.split(r"x", size_str, flags=re.IGNORECASE)
    count = len(parts)
    if count == 1:
        return "Thickness"
    if count == 2:
        return "Thickness × Width"
    return "Thickness × Width × Length"


# ===========================================================================
# detect_grade — two-tier detection
# ===========================================================================

def detect_grade(
    text: str,
    alias_token_set: frozenset[str],
) -> tuple[Optional[str], Optional[str], Optional[list[str]]]:
    """
    Two-tier detection producing three distinct buckets.

    Tier 1 — phrase scan (checked first as substrings):
        _GRADE_PHRASES       → detected_grade
        _PRODUCT_CLASS_PHRASES → detected_product_class

    Tier 2 — token-by-token classification:
        _GRADE_WORD_RE         → detected_grade
        _PRODUCT_CLASS_WORD_RE → detected_product_class
        _AMBIGUOUS_TOKENS      → unrecognized_tokens
        alias_token_set        → keep silently (known species/type vocab)
        _STRUCTURAL_WORDS      → keep silently (common English words)
        digit-only fragments   → keep silently (dimension remnants)
        everything else        → unrecognized_tokens

    Detection priority order within each token:
        grade patterns checked before product_class, both before alias vocab,
        so formal grade codes are never silently swallowed by the vocab check.

    Args:
        text:            cleaned_input with dimensions and seller already
                         stripped (i.e. close to what the matcher receives)
        alias_token_set: frozenset from build_alias_token_set()

    Returns:
        (detected_grade, detected_product_class, unrecognized_tokens)
        Any element may be None if nothing is found for that bucket.
    """
    grade_hits: list[str] = []
    product_class_hits: list[str] = []
    unrecognized: list[str] = []

    working = text.lower()

    # ── Tier 1: phrase scan ──────────────────────────────────────────────
    for phrase in _GRADE_PHRASES:
        phrase_lower = phrase.lower()
        if phrase_lower in working:
            grade_hits.append(phrase)
            working = working.replace(phrase_lower, " ")

    for phrase in _PRODUCT_CLASS_PHRASES:
        phrase_lower = phrase.lower()
        if phrase_lower in working:
            product_class_hits.append(phrase)
            working = working.replace(phrase_lower, " ")

    # ── Tier 2: token-by-token classification ───────────────────────────
    splitter = re.compile(r"[\s\-]+")
    for tok in splitter.split(working):
        tok = tok.strip()
        if not tok:
            continue
        # Formal grade patterns — highest priority
        if _GRADE_WORD_RE.match(tok):
            grade_hits.append(tok)
            continue
        # Product class / application terms
        if _PRODUCT_CLASS_WORD_RE.match(tok):
            product_class_hits.append(tok)
            continue
        # Ambiguous quality descriptors — honest about uncertainty
        if tok in _AMBIGUOUS_TOKENS:
            unrecognized.append(tok)
            continue
        # Known lumber species/type vocabulary — keep silently
        if tok in alias_token_set:
            continue
        # Common structural English words — keep silently
        if tok in _STRUCTURAL_WORDS:
            continue
        # Digit-only fragments (dimension remnants) — silently skip
        if re.match(r"^\d{1,2}$", tok):
            continue
        unrecognized.append(tok)

    detected_grade = ", ".join(grade_hits) if grade_hits else None
    detected_product_class = ", ".join(product_class_hits) if product_class_hits else None
    unrecognized_out = unrecognized if unrecognized else None

    return detected_grade, detected_product_class, unrecognized_out


# ===========================================================================
# parse — main entry point
# ===========================================================================

def parse(raw: str, alias_token_set: frozenset[str]) -> ParsedInput:
    """
    Full parsing pipeline for a single raw product name.

    Pipeline order:
      1. Detect seller (on raw string, before cleaning)
      2. Detect treatment (on raw string)
      3. Clean the string
      4. Extract dimensions from cleaned string
      5. Detect grade / unrecognized tokens from what remains

    The string passed to detect_grade() has dimension tokens stripped,
    so grade detection works on a cleaner token set.

    Args:
        raw:              original product name string
        alias_token_set:  from build_alias_token_set(); built once at startup

    Returns:
        ParsedInput dataclass with all parser-level fields populated.
    """
    # 1. Seller detection (raw)
    detected_seller = detect_seller(raw)

    # 2. Treatment detection (raw)
    detected_treatment = detect_treatment(raw)

    # 3. Clean
    cleaned = clean(raw)

    # 4. Dimension extraction
    detected_size, size_label, dim_unrecognized, consumed = extract_dimensions(cleaned)

    # 5. Build text for grade detection.
    #    Use the exact substrings recorded by extract_dimensions (consumed)
    #    to strip dimension tokens precisely — no regex approximation needed.
    #    This avoids fragment artifacts like "3/" from contiguous dims, or
    #    a stray "x" from space-separated dims like "15/32 x 4 x 8".
    text_for_grade = cleaned
    for span in consumed:
        text_for_grade = text_for_grade.replace(span, " ")

    # Strip seller name — it is a known entity stored in detected_seller
    # and has no business being flagged as an unrecognized grade token.
    if detected_seller:
        seller_pat = re.escape(detected_seller.lower())
        text_for_grade = re.sub(rf"\b{seller_pat}\b", " ", text_for_grade)

    text_for_grade = re.sub(r"\s+", " ", text_for_grade).strip()

    # 6. Grade / product_class / unrecognized detection
    detected_grade, detected_product_class, grade_unrecognized = detect_grade(
        text_for_grade, alias_token_set
    )

    # 7. Merge unrecognized lists
    all_unrecognized: list[str] = []
    if dim_unrecognized:
        all_unrecognized.extend(dim_unrecognized)
    if grade_unrecognized:
        all_unrecognized.extend(grade_unrecognized)

    return ParsedInput(
        original_input=raw,
        cleaned_input=cleaned,
        detected_size=detected_size,
        size_label=size_label,
        detected_seller=detected_seller,
        detected_treatment=detected_treatment,
        detected_grade=detected_grade,
        detected_product_class=detected_product_class,
        unrecognized_tokens=all_unrecognized if all_unrecognized else None,
        consumed=consumed,
    )
