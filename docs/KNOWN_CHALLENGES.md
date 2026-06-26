# LumberLex — Algorithm Notes, Known Challenges, and Future Work

This document explains how the normalisation engine works, where it is reliable,
where it is fragile, and what improvements would make it stronger. It is written
to be readable without knowledge of the source code.

---

## What the system is trying to do

A seller gives you a string like `"Lowes Whitewood Stud 2x4x8 #2&BTR Kiln Dried"`.
You want to know: what kind of lumber is this actually? The answer you want is
something clean and canonical like `"SPF"` — a name that means the same thing
regardless of which seller wrote the label.

The system holds a table of 201 known aliases (things sellers actually write) and
what canonical type each one maps to. The job is to find the closest alias and
return the canonical type behind it, together with a confidence score and a
human-readable explanation.

---

## The algorithm, step by step

### Step 1 — Cleaning

The raw string is lowercased and lightly normalised. Periods and commas are
removed. Slashes between letters become spaces (`"spruce/pine/fir"` →
`"spruce pine fir"`). Letter-adjacent hyphens become spaces (`"hem-fir"` →
`"hem fir"`). Whitespace is collapsed.

```
"Lowes Whitewood Stud 2x4x8 #2&BTR Kiln Dried"
         ↓
"lowes whitewood stud 2x4x8 #2&btr kiln dried"
```

No interpretation happens here. The string is only tidied up.

---

### Step 2 — Detection passes (run in parallel, not sequentially)

Several detectors scan the cleaned string independently:

**Seller detection.** Checks if the string begins with a known seller name.
`"lowes"` → `detected_seller = "Lowes"`. The seller stays in the string; this
field is for traceability only.

**Treatment detection.** Looks for keywords: `"pt"`, `"treated"`, `"pressure
treated"`, `"acq"`, `"mca"`. If found, `detected_treatment = "Pressure Treated"`.

**Dimension extraction.** A two-pass algorithm finds patterns like `2x4`, `4x4x8`,
`7/16x4x8`, `2x4x92-5/8`. The exact character spans that matched are recorded in
a `consumed` list for later removal.

**Grade and product-class detection.** Scans for formal grade codes (`#2`,
`stud grade`, `select structural`) and end-use descriptors (`appearance`,
`kiln dried`, `common`, `outdoor`). These go into `detected_grade` and
`detected_product_class` respectively.

Example result for `"Lowes Whitewood Stud 2x4x8 #2&BTR Kiln Dried"`:

```
detected_seller        : "Lowes"
detected_treatment     : None
detected_size          : "2x4x8"
detected_grade         : None
detected_product_class : "kiln dried"
consumed               : ["2x4x8"]
```

---

### Step 3 — Building the match query

The string that goes into the fuzzy matcher is constructed by removing everything
that should not influence the species match:

```
start with cleaned_input :  "lowes whitewood stud 2x4x8 #2&btr kiln dried"
strip consumed dimensions :  "lowes whitewood stud        #2&btr kiln dried"
strip product-class tokens:  "lowes whitewood stud #2&btr"
collapse whitespace       :  "lowes whitewood stud #2&btr"
```

Dimensions are stripped because they describe size, not species. Product-class
tokens (`"kiln dried"`, `"appearance"`, `"common"`, `"outdoor"`, etc.) are
stripped because they describe end-use, not species identity.

The seller name and treatment tokens are deliberately kept. Seller context
sometimes disambiguates — a seller known to carry only SYP will never ship SPF
under a similar label — and treatment keywords help the matcher prefer PT aliases
over untreated ones.

---

### Step 4 — Matching

**Pass 1 — Exact dictionary lookup (free, instant).** The query is looked up
directly in the alias table. If it matches a key exactly, the result is returned
immediately with confidence 0.95.

**Pass 2 — Fuzzy matching (when exact lookup misses).** The query is scored
against all 201 aliases using `token_sort_ratio`. The top 3 results are returned.

#### How token_sort_ratio works

It does four things:

1. **Split into tokens** by whitespace (not by hyphens or other characters).
2. **Sort tokens alphabetically.**
3. **Join them back into a string.**
4. **Compute Levenshtein similarity** between the two sorted strings.

Example:

```
query : "lowes whitewood stud #2&btr"
alias : "whitewood stud"

tokens sorted:
  query : "#2&btr lowes stud whitewood"
  alias : "stud whitewood"

Levenshtein ratio on those two sorted strings → score ≈ 68
```

**Why sort first?** Because word order in lumber names is meaningless. `"SPF KD"`
and `"KD SPF"` are the same product. Sorting makes the scorer order-insensitive
so sellers who write words in different sequences still get matched.

---

### Step 5 — Confidence scoring

The raw fuzzy score (0–100) is mapped to a business-rule confidence value
(0.0–1.0):

| Raw score | Confidence | Meaning |
|---|---|---|
| Exact dict hit / score 100 | 0.95 | Alias is literally in the table |
| ≥ 90 | 0.85 | Very strong fuzzy match |
| ≥ 80 | 0.75 | Good match |
| ≥ 70 | 0.70 | Reasonable match — worth checking |
| < 70 | proportional (< 0.54) | Weak — manual review required |

These thresholds were calibrated so all 10 regression test cases meet their
minimum confidence floors. They are hand-tuned numbers, not derived from
first principles.

The bands are intentionally coarse. A score of 90 and a score of 98 both give
0.85. The underlying scores are noisy and false precision would be misleading.

---

### Step 6 — Treatment resolution

Treatment is determined by combining two sources:

```
treatment = parser-detected treatment   OR   canonical's own treatment field
```

Parser detection takes priority. This handles inputs like `"SYP PT 4x4x8"` where
the user wrote the treatment explicitly. The canonical fallback handles brand names
like `"YellaWood"` where the treatment is implied by the product name but no
treatment keyword appears in the input.

---

### Step 7 — Warning and explanation

If the matched canonical has `ambiguity_level = High` (e.g. SPF, Oak, Maple), a
warning is generated from the canonical's own notes field. No separate warning
strings are maintained — the notes field is the single source of truth.

The explanation is a template sentence stating what was matched, via which alias,
at what confidence, with optional clauses for seller, treatment, and dimensions.

---

## A complete worked example

Input: `"SYP PT 4x4x8"`

```
Step 1 — Clean:         "syp pt 4x4x8"
Step 2 — Detect:        treatment="Pressure Treated"  size="4x4x8"  consumed=["4x4x8"]
Step 3 — Match query:   "syp pt"     (4x4x8 stripped; no product-class token)
Step 4 — Exact lookup:  "syp pt" → "Pressure Treated Southern Yellow Pine"  ✓
Step 5 — Confidence:    score=100 → 0.95
Step 6 — Treatment:     parser says "Pressure Treated"; canonical agrees
Result: Pressure Treated Southern Yellow Pine, confidence 0.95
```

Input: `"Douglass Fir 2x8"` (typo in seller label)

```
Step 1 — Clean:         "douglass fir 2x8"
Step 2 — Detect:        size="2x8"  consumed=["2x8"]
Step 3 — Match query:   "douglass fir"
Step 4 — Fuzzy:
  token_sort_ratio("douglass fir", "douglas fir")       = 92  ← one char off
  token_sort_ratio("douglass fir", "douglas fir larch") = 73
  Winner: alias "Douglas Fir" → "Douglas Fir-Larch"
Step 5 — Confidence:    score=92 → 0.85
Result: Douglas Fir-Larch, confidence 0.85
```

---

## Known strengths

**Typo tolerance.** The Levenshtein distance inside `token_sort_ratio` handles
single-character typos and transpositions well. `"Douglass"` → `"Douglas"`,
`"hemlock-fir"` → `"Hem Fir"`.

**Word order independence.** Token sorting means `"KD SPF #2"` and `"SPF #2 KD"`
match the same alias.

**Explicit treatment detection.** Treatment is detected before matching, so
`"PT SYP"` and `"SYP PT"` both identify as Pressure Treated Southern Yellow Pine
regardless of which order the seller wrote the tokens.

**Loud failure.** When no alias scores above the threshold, the system returns
confidence < 0.54 and flags `manual_review_required = True`. It does not guess
and hide the uncertainty.

---

## Known challenges and limitations

### 1 — Similar short abbreviations are easily confused

`"SPF"` and `"SYP"` differ by one character. When the match query is reduced to
only those three letters — for example after stripping dimensions, product-class
tokens, and seller prefix from `"Kiln Dried SPF 2x4 #2"` — the fuzzy scorer
gives `"SYP"` nearly as high a score as `"SPF"`. The system has no way to prefer
one over the other from character evidence alone.

The alias table partially mitigates this by including compound aliases like
`"KD SPF"`, `"SPF #2"`, `"Kiln Dried SPF"` — so inputs with more context get
exact hits before fuzzy scoring begins. But stripped-down inputs remain fragile.

**Example risk:** `"SPF #2"` as a query scores 83 against alias `"SYP #2"` and
100 against alias `"SPF #2"` (once that alias exists). If `"SPF #2"` were not in
the alias table, `"SYP #2"` would win.

---

### 2 — Product-class tokens serve double duty

Tokens like `"appearance"`, `"common"`, and `"outdoor"` are classified as
product-class descriptors (end-use, not species) and stripped from the match query
before fuzzy matching. This is correct for most inputs: `"PT Pine Appearance"` →
strip `"appearance"` → `"pt pine"` → exact alias hit for Pressure Treated SYP.

However, for Ponderosa Pine, `"Appearance Pine"` and `"Common Pine"` are genuine
trade names — `"appearance"` and `"common"` are the discriminating words, not
noise. Stripping them leaves only `"pine"`, which then fuzzy-matches the wrong
canonical.

**Known regressions from this rule (as of current implementation):**
- `"Appearance Pine"` inputs → may mismatch after stripping `"appearance"`
- `"Common Pine"` inputs → may mismatch after stripping `"common"`

These mismatches all land at confidence ≤ 0.70, below the false-confident
threshold of 0.80, so they are visible to the user and will not be presented as
high-confidence results. But they are wrong.

**Root cause:** The algorithm has no semantic understanding of when a token is a
descriptor versus a species identifier. It applies the strip rule uniformly.

---

### 3 — Concatenated and hyphenated inputs

Some sellers write lumber names as a single concatenated word: `"HemlockFir"`,
`"WesternHemlockFir"`, `"OutdoorTreatedPine"`. The tokeniser splits on whitespace,
so these are treated as a single opaque token with no internal structure.

`"hemlockfir"` does not fuzzy-match `"hemlock fir"` (two-token alias) as well as
it matched the pre-normalisation alias `"hemlock-fir"` (one hyphenated token).
The score drops from ~95 to ~67.

Concatenated inputs are a seller data quality problem, but they are common enough
in real inventories to matter.

---

### 4 — No domain knowledge is embedded in the matcher

The system does not know that `"PT"` in North American framing lumber almost
always means Southern Yellow Pine. It only knows what aliases exist. If a seller
writes `"PT Maple"`, the system will attempt to find `"PT Maple"` in the alias
table. If that alias does not exist, the fuzzy match may land on something
incorrect rather than flagging the input as unusual.

Domain knowledge lives entirely in the alias table. The algorithm is
domain-agnostic. This is a deliberate design choice (data-driven over
code-driven), but it means gaps in the alias table directly produce gaps in
coverage.

---

### 5 — The alias table is a prototype dataset

The 201 aliases were derived from public retail and industry sources and represent
a reasonably broad vocabulary of common North American lumber naming conventions.
They are not a verified commercial product catalog.

Real seller inventories typically contain:
- Proprietary brand names not in any public glossary
- Regional naming conventions that differ from WWPA/NLGA standards
- Legacy SKU codes embedded in product names
- Mix of metric and imperial dimensions
- Encoding artefacts from ERP system exports

The current alias table would need to be significantly extended before it could
handle a real production inventory reliably.

---

### 6 — The confidence thresholds are calibrated on synthetic data

The confidence band floors (0.95, 0.85, 0.75, 0.70) were tuned so that the 10
regression test cases meet their minimum floors, and validated against a 596-row
synthetic database generated from the same source as the alias table.

Both datasets were created in the same process, by the same people, using the
same vocabulary. There is a real risk that the thresholds reflect the quirks of
this specific dataset rather than the true difficulty of the task on real seller
data. The first time this system is run against a genuinely independent seller
catalog, the accuracy numbers will likely be lower and the false-confident rate
may be higher.

---

### 7 — Grade tokens and species tokens can be identical

Some formal lumber grade codes (`"select"`, `"prime"`, `"#2"`) also appear inside
species aliases (`"Select White Pine"`, `"SPF #2 Better"`). If a grade token is
stripped before matching, context needed to identify the species is lost. If it is
kept, it may inflate scores against aliases that share that grade descriptor but
belong to a different canonical.

The current implementation handles this by not stripping grade tokens — only
dimensions and product-class tokens are stripped. This is a deliberate tradeoff.

---

## Future work

### Short-term (data layer)

- **Extend alias coverage for grade descriptor variants.** Currently `"SPF #2&BTR"`
  exists but `"SYP #2&BTR"` did not (now added). A systematic audit of the
  `{canonical} × {grade form}` matrix would find other gaps.

- **Add hyphenated and concatenated alias variants.** `"HemlockFir"`,
  `"WesternRedCedar"`, `"SprucePineFir"` are common concatenated forms in ERP
  exports. Adding these directly as aliases is simpler than teaching the matcher
  to split them.

- **Add seller-specific aliases.** Lowe's, Home Depot, 84 Lumber, and YellaWood
  each have proprietary naming conventions. A small seller-specific alias
  supplement would dramatically improve accuracy for known sellers.

### Medium-term (algorithm)

- **Minimum token length filter for the alias table.** Aliases shorter than 4
  characters (e.g. `"WO"`, `"RO"`, `"HF"`) cause disproportionate fuzzy matches
  against unrelated inputs. These short aliases are valuable for exact lookup but
  potentially harmful in fuzzy mode. A two-phase approach — exact lookup only for
  short aliases, fuzzy only for longer ones — would reduce false matches without
  losing the exact-match benefit.

- **Context-aware product-class handling.** Rather than unconditionally stripping
  `"appearance"` and `"common"`, only strip them when sufficient other species
  tokens are present in the query. If the only remaining token after dimension
  stripping would be `"pine"`, keep the product-class token to preserve the
  discriminating signal.

- **Grade token stripping with collision detection.** Grade tokens are currently
  kept in the match query. Stripping them before matching would improve scores for
  inputs like `"Hem Fir #2 2x6"` where `"#2"` adds noise. A safe approach would
  strip grade tokens only when no alias containing that grade token maps to the
  same canonical as the species-only alias.

### Long-term (architecture)

- **Human-in-the-loop corrections.** A lightweight interface for a lumber expert
  to mark results as wrong and add the corrected alias. Wrong-with-high-confidence
  results are the most valuable corrections to collect.

- **Seller-specific normalisation profiles.** Different sellers use different
  naming conventions systematically. A per-seller alias supplement (loaded at
  startup alongside the main alias table) would let the system specialise for
  known sellers without polluting the general vocabulary.

- **LLM fallback for genuinely novel inputs.** When fuzzy confidence is below the
  manual review threshold, a secondary pass using an LLM with the canonical list
  as context could recover some fraction of inputs that the alias table cannot
  handle. This is already planned as Phase 7 (chatbot module), but it could also
  be used as a silent fallback before surfacing the manual review flag to the user.

- **Evaluation against independent real-world data.** The most important validation
  step not yet taken. A sample of real seller inventory rows — not generated from
  the same source as the current test data — would reveal whether the current
  accuracy numbers generalise or are specific to this dataset.

---

*Last updated: Phase 6 — Batch Evaluation*
*Total test cases: 10 (test_cases.csv) + 596 (lumberlex_sample_database.csv)*
*Simulation accuracy (596-row database, 6-patch configuration): 88.5% top-1, 0 false-confident errors*
