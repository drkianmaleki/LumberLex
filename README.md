# 🪵 LumberLex

> **Lumber product name normalization engine**  
> Map inconsistent retail strings like `"Lowes Whitewood Stud 2x4x8 #2&BTR KD"` to canonical lumber types with confidence scoring, treatment detection, and dimension extraction.

![CI](https://github.com/drkianmaleki/LumberLex/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-256%20passing-brightgreen?logo=pytest&logoColor=white)
![Accuracy](https://img.shields.io/badge/top--1%20accuracy-88.5%25-success)
![False Confident](https://img.shields.io/badge/false--confident%20errors-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)

---

## What it does

Different sellers use different names for the same lumber products. **LumberLex** maps inconsistent product strings to a canonical species name with structured metadata:

```python
from lumberlex import normalize

result = normalize("Lowes Whitewood Stud 2x4x8 #2&BTR Kiln Dried")
print(result.normalized_name)  # → "SPF"
print(result.confidence)       # → 0.95
print(result.detected_size)    # → "2x4x8"
print(result.treatment)        # → None
print(result.explanation)      # → "'Lowes Whitewood Stud 2x4x8 #2&BTR Kiln Dried' was
                               #     matched to SPF (SPF) via the alias 'whitewood stud'
                               #     with a confidence of 0.95. Seller 'Lowes' was
                               #     detected and retained in the search. Dimensions
                               #     '2x4x8' were extracted before matching."
```

---

## Highlights

| Metric | Value |
|--------|-------|
| Canonical lumber types | 15 |
| Alias vocabulary | 201 entries |
| Top-1 accuracy (596-row database) | **88.5%** |
| False-confident errors | **0** |
| Automated tests | 256 (mocked) + 3 (live LLM) |
| Python version | ≥ 3.9 |

**Key capabilities:**
- 🎯 **Fuzzy matching** via RapidFuzz `token_sort_ratio` — handles typos (`"Douglass Fir"`), abbreviations (`"DFL"`), and word-order variation (`"KD SPF"` vs `"SPF KD"`)
- 💊 **Treatment detection** — identifies pressure treatment from explicit keywords and implied brand names (e.g. YellaWood)
- 📐 **Dimension extraction** — 2×4, 4×4×8, 7/16×4×8, 2×4×92-5/8, with dimension labels
- 🏪 **Seller identification** — detects known seller prefixes (Lowe's, Home Depot, etc.)
- 🎓 **Grade and product-class detection** — separates formal grade codes (`#2`, `stud grade`) from end-use descriptors (`appearance`, `kiln dried`)
- ⚠️ **Loud failure** — low-confidence results surface a `manual_review_required` flag; nothing is silently mis-matched
- 💬 **Natural-language explanations** — Groq-powered chatbot answers plain-language questions about any result
- 🖥️ **Streamlit UI** — two-tab web interface: normalizer + chatbot

---

## Project Status

All nine phases are complete.

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 — Data Layer | CSV loader, validator, in-memory lookup | ✅ Complete |
| 2 — Output Schema | `NormalizationResult`, `AlternativeMatch` (Pydantic v2) | ✅ Complete |
| 3 — Parser | Cleaning, detection, dimension extraction | ✅ Complete |
| 4 — Matcher | RapidFuzz fuzzy matching, confidence scoring | ✅ Complete |
| 5 — Normalizer | Orchestrator, treatment union rule, explanation | ✅ Complete |
| 6 — Batch Evaluation | 596-row accuracy evaluation, `BatchEvaluator` | ✅ Complete |
| 7 — Library Packaging | pip-installable `lumberlex` package, bundled data | ✅ Complete |
| 8 — Chatbot Module | `explain()` with Groq API, multi-turn history | ✅ Complete |
| 9 — Streamlit UI | Two-tab web app: normalizer + chatbot | ✅ Complete |

---

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd lumberlex

python -m venv .venv                      # create an isolated virtual environment
source .venv/bin/activate                 # macOS/Linux
.venv\Scripts\activate                    # Windows (PowerShell/CMD)

pip install -e .                          # install the lumberlex library (required)
pip install -r requirements.txt           # install dev dependencies (pytest)

# Run all tests (no API key needed)
pytest -m "not llm"                       # 256 tests

# Normalize a product from the command line
python -c "from lumberlex import normalize; r = normalize('Whitewood Stud 2x4'); print(r.normalized_name, r.confidence)"

# Launch the Streamlit web UI
pip install -r apps/streamlit/requirements.txt
streamlit run apps/streamlit/app.py       # opens at http://localhost:8501

# Run the interactive chatbot CLI
pip install -r apps/chatbot/requirements.txt
export GROQ_API_KEY=gsk_your_key_here    # free key at https://console.groq.com
python apps/chatbot/chat.py
```

---

## Usage

### Library API

```python
from lumberlex import normalize, Normalizer, NormalizationResult

# ── One-liner (cached singleton, thread-safe) ──────────────────────────────
result = normalize("SYP PT 4x4x8")
print(result.normalized_name)   # "Pressure Treated Southern Yellow Pine"
print(result.confidence)        # 0.95
print(result.treatment)         # "Pressure Treated"
print(result.detected_size)     # "4x4x8"

# ── UNKNOWN outcome ────────────────────────────────────────────────────────
result = normalize("random board xyz qrs")
print(result.normalized_name)          # "UNKNOWN"
print(result.manual_review_required)   # True
print(result.confidence)               # low; shows how close the best attempt was

# ── Custom data paths ──────────────────────────────────────────────────────
normalizer = Normalizer.from_files(
    canonicals_path="path/to/my_canonicals.csv",
    aliases_path="path/to/my_aliases.csv",
)
result = normalizer.normalize("Some Lumber Product")

# ── Batch evaluation ───────────────────────────────────────────────────────
from lumberlex import BatchEvaluator

evaluator = BatchEvaluator.from_files()
report = evaluator.run("data/lumberlex_sample_database.csv")
print(f"Top-1 accuracy: {report.top1_accuracy:.1%}")   # 88.5%
print(f"False-confident: {report.false_confident_count}")  # 0
```

### Chatbot API

```python
from apps.chatbot import explain

# Standard explanation
response = explain("Whitewood Stud 2x4")
print(response)

# With a pre-computed result (avoids double normalization)
from lumberlex import normalize
result = normalize("PT Southern Yellow Pine 2x6")
response = explain("PT Southern Yellow Pine 2x6", result=result)

# Specific question
response = explain(
    "Douglas Fir-Larch 2x8",
    question="Is this suitable for outdoor framing?",
)

# Multi-turn conversation
history: list[dict] = []
r1 = explain("Whitewood Stud 2x4", history=history)
history += [{"role": "user", "content": "Explain this product."},
            {"role": "assistant", "content": r1}]
r2 = explain("Whitewood Stud 2x4", question="Can I use this outdoors?", history=history)
```

### NormalizationResult fields

```python
result = normalize("Lowes Whitewood Stud 2x4x8 #2&BTR Kiln Dried")
```

| Field | Example | Notes |
|-------|---------|-------|
| `original_input` | `"Lowes Whitewood Stud 2x4x8 #2&BTR Kiln Dried"` | Raw input string |
| `cleaned_input` | `"lowes whitewood stud 2x4x8 #2&btr kiln dried"` | After normalization |
| `normalized_name` | `"SPF"` | Canonical name or `"UNKNOWN"` |
| `species_group` | `"SPF"` | Broader species group |
| `category` | `"Dimensional lumber"` | Product category |
| `ambiguity_level` | `"High"` | `"Low"` / `"Medium"` / `"High"` |
| `treatment` | `None` | `"Pressure Treated"` or `None` |
| `detected_size` | `"2x4x8"` | Extracted dimension string |
| `size_label` | `"Thickness × Width × Length"` | Human-readable dimension label |
| `detected_seller` | `"Lowes"` | Identified seller prefix |
| `detected_grade` | `None` | Formal grade code (`"#2"`, `"stud grade"`) |
| `detected_product_class` | `"kiln dried"` | End-use descriptor |
| `unrecognized_tokens` | `["#2&btr"]` | Tokens parser couldn't classify |
| `confidence` | `0.95` | 0.0–1.0; mapped from fuzzy score |
| `best_alias_match` | `"whitewood stud"` | Alias that drove the match |
| `alternative_matches` | `[AlternativeMatch(...), ...]` | Up to 2 runner-up candidates |
| `manual_review_required` | `False` | `True` when confidence < threshold |
| `warning` | `"SPF is a species group..."` | Set for High-ambiguity canonicals only |
| `explanation` | `"'Lowes ...' was matched to SPF..."` | Human-readable trace |

---

## Repository Structure

```
lumberlex/
│
├── src/
│   └── lumberlex/                       ← pip-installable package
│       ├── __init__.py                  ← public API: normalize(), Normalizer, etc.
│       ├── _data/                       ← bundled defaults (installed with the package)
│       │   ├── canonicals.csv           ← 15 canonical lumber types + metadata
│       │   ├── aliases.csv              ← 201 alias → canonical_name pairs
│       │   └── thresholds.yml           ← bundled fallback config (mirrors config/)
│       ├── config.py                    ← YAML loader, typed threshold constants
│       ├── data_layer.py                ← Phase 1: loader, validator, lookup builder
│       ├── schemas.py                   ← Phase 2: NormalizationResult, AlternativeMatch
│       ├── parser.py                    ← Phase 3: clean, detect, extract, parse
│       ├── matcher.py                   ← Phase 4: fuzzy matching, confidence scoring
│       ├── normalizer.py                ← Phase 5: orchestration, explanation
│       └── evaluator.py                 ← Phase 6: BatchEvaluator, EvaluationReport
│
├── config/
│   └── thresholds.yml                   ← developer copy — edit here to tune thresholds
│
├── data/                                ← development and test resources (not bundled)
│   ├── test_cases.csv                   ← 10 hand-crafted regression test cases
│   ├── lumberlex_sample_database.csv    ← 596-row synthetic evaluation database
│   └── data_dictionary.md               ← schema documentation for all CSV files
│
├── docs/
│   └── KNOWN_CHALLENGES.md              ← algorithm notes, limitations, future work
│
├── apps/
│   ├── README.md                        ← apps-layer setup overview
│   ├── chatbot/                         ← Phase 8: Groq-powered explanation layer
│   │   ├── __init__.py                  ← exposes explain, LLMProvider, GroqProvider
│   │   ├── chatbot.py                   ← LLMProvider ABC, GroqProvider, explain()
│   │   ├── chat.py                      ← interactive REPL (live product + Q&A)
│   │   ├── demo.py                      ← fixed demo — 4 pre-set samples
│   │   ├── README.md                    ← setup, usage, API, architecture
│   │   └── requirements.txt             ← groq + editable lumberlex install
│   └── streamlit/                       ← Phase 9: two-tab web interface
│       ├── app.py                       ← main Streamlit application
│       ├── README.md                    ← setup, usage, session state, architecture
│       └── requirements.txt             ← streamlit + groq + editable lumberlex install
│
├── tests/
│   ├── test_data_layer.py               ← 21 tests (Phase 1)
│   ├── test_schemas.py                  ← 38 tests (Phase 2)
│   ├── test_parser.py                   ← 89 tests (Phase 3)
│   ├── test_matcher.py                  ← 31 tests (Phase 4)
│   ├── test_normalizer.py               ← 55 tests (Phase 5)
│   ├── test_batch_eval.py               ← 10 tests (Phase 6) — 2 marked @slow
│   └── test_chatbot.py                  ← 15 tests (Phase 8) — 3 marked @llm
│
├── scripts/                             ← CLI visual inspection scripts
│   ├── inspect_alias_dict.py            ← alias table + validation output
│   ├── inspect_parser.py                ← parser output table for test cases
│   ├── inspect_matcher.py               ← matcher top-3 results for test cases
│   ├── print_sample_result.py           ← full NormalizationResult for one input
│   └── batch_eval.py                    ← 596-row evaluation report
│
├── conftest.py                          ← pytest marker registration
├── pyproject.toml                       ← package metadata, dependencies, pytest config
└── requirements.txt                     ← dev-only: pytest
```

---

## Installation

### Library only (core engine)

```bash
pip install -e .
```

### With chatbot support

```bash
pip install -e .
pip install -r apps/chatbot/requirements.txt

# Requires a free Groq API key: https://console.groq.com
export GROQ_API_KEY=gsk_your_key_here     # macOS / Linux
$env:GROQ_API_KEY = "gsk_your_key_here"  # Windows PowerShell
```

### With Streamlit UI

```bash
pip install -e .
pip install -r apps/streamlit/requirements.txt

export GROQ_API_KEY=gsk_your_key_here     # required for Tab 2 only
streamlit run apps/streamlit/app.py
```

> **Tab 1 (Normalizer)** is fully offline — no API key or network call. Only the chatbot tab requires Groq.

---

## Testing

```bash
# Standard suite — no API key required (256 tests, ~2s)
pytest -m "not llm"

# Batch evaluation tests only — slow, exercises all 596 rows (~1s)
pytest -m slow -v

# Chatbot mocked tests only — no API key required
pytest tests/test_chatbot.py -m "not llm" -v

# Live Groq tests — requires GROQ_API_KEY
pytest tests/test_chatbot.py -m llm -v

# Full suite breakdown
pytest -m "not slow and not llm" -v      # 244 fast unit tests
pytest -m slow -v                         # 2 batch evaluation tests
pytest tests/test_chatbot.py -m llm -v   # 3 live LLM tests
```

### Test counts by phase

| Phase | File | Tests | Marker |
|-------|------|-------|--------|
| 1 — Data Layer | `test_data_layer.py` | 21 | — |
| 2 — Schema | `test_schemas.py` | 38 | — |
| 3 — Parser | `test_parser.py` | 89 | — |
| 4 — Matcher | `test_matcher.py` | 31 | — |
| 5 — Normalizer | `test_normalizer.py` | 55 | — |
| 6 — Batch Eval | `test_batch_eval.py` | 10 | 2 × `@slow` |
| 8 — Chatbot | `test_chatbot.py` | 15 | 3 × `@llm` |
| **Total (standard)** | | **259** | — |
| **Standard without `@llm`** | | **256** | — |

---

## Configuration

All tunable thresholds live in `config/thresholds.yml`. Edit this file and restart to change behavior — no source code changes required.

**Config discovery order:**
1. `config/thresholds.yml` at the project root *(developer copy — used in editable installs)*
2. `src/lumberlex/_data/thresholds.yml` bundled in the package *(fallback for wheel installs)*

### Available thresholds

```yaml
fuzzy_matching:
  manual_review_threshold: 70      # raw score below which manual_review_required = True

confidence_bands:
  exact_match: 0.95                # exact alias dict hit
  score_90_plus: 0.85              # fuzzy score ≥ 90
  score_80_to_89: 0.70             # fuzzy score 80–89
  score_70_to_79: 0.55             # fuzzy score 70–79
  sub_threshold_scale: 0.54        # scale factor for scores below threshold

batch_evaluation:
  min_top1_accuracy: 0.80          # pass/fail floor for automated batch tests
  max_false_confident_rate: 0.01   # pass/fail ceiling for false-confident rate
```

### Importing constants in code

```python
from lumberlex.config import (
    MANUAL_REVIEW_THRESHOLD,       # int: 70
    CONFIDENCE_EXACT_MATCH,        # float: 0.95
    CONFIDENCE_SCORE_90_PLUS,      # float: 0.85
    CONFIDENCE_SCORE_80_TO_89,     # float: 0.70
    CONFIDENCE_SCORE_70_TO_79,     # float: 0.55
    CONFIDENCE_SUB_THRESHOLD_SCALE,# float: 0.54
    BATCH_MIN_TOP1_ACCURACY,       # float: 0.80
    BATCH_MAX_FALSE_CONFIDENT_RATE,# float: 0.01
)
```

---

## How It Works

The pipeline runs in five steps for every call to `normalize()`:

```
Raw string
    │
    ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Step 1 — Clean                                                      │
│  Lowercase · strip punctuation · normalise hyphens · collapse spaces │
└───────────────────────────────────────────────────────────┬──────────┘
                                                            │
                                                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Step 2 — Detect  (parallel passes, no ordering dependency)          │
│  • Seller prefix       • Treatment keywords                          │
│  • Dimension patterns  • Grade codes / product-class tokens          │
└───────────────────────────────────────────────────────────┬──────────┘
                                                            │
                                                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Step 3 — Build match query                                          │
│  Start from cleaned_input · strip dimension spans · strip            │
│  product-class tokens · collapse whitespace                          │
└───────────────────────────────────────────────────────────┬──────────┘
                                                            │
                                                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Step 4 — Match                                                      │
│  Pass 1: Exact lookup in alias dict (201 entries) → confidence 0.95  │
│  Pass 2: token_sort_ratio against all aliases → top 3 candidates     │
└───────────────────────────────────────────────────────────┬──────────┘
                                                            │
                                                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Step 5 — Assemble                                                   │
│  Fetch canonical metadata · apply treatment union rule               │
│  Generate warning (High ambiguity only) · build explanation          │
└───────────────────────────────────────────────────────────┬──────────┘
                                                            │
                                                            ▼
                                               NormalizationResult (19 fields)
```

### Worked example

Input: `"SYP PT 4x4x8"`

```
Clean :    "syp pt 4x4x8"
Detect:    treatment="Pressure Treated"  size="4x4x8"  consumed=["4x4x8"]
Query :    "syp pt"           ← 4x4x8 stripped; no product-class token present
Match :    exact hit "syp pt" → "Pressure Treated Southern Yellow Pine"
Score :    100 → confidence 0.95
Result:    normalized_name="Pressure Treated Southern Yellow Pine"  confidence=0.95
```

Input: `"Douglass Fir 2x8"` *(typo)*

```
Clean :    "douglass fir 2x8"
Detect:    size="2x8"  consumed=["2x8"]
Query :    "douglass fir"
Match :    token_sort_ratio("douglass fir", "douglas fir") = 92  ← one char off
           Winner: alias "Douglas Fir" → "Douglas Fir-Larch"
Score :    92 → confidence 0.85
Result:    normalized_name="Douglas Fir-Larch"  confidence=0.85
```

For the full algorithm walkthrough, see [`docs/KNOWN_CHALLENGES.md`](docs/KNOWN_CHALLENGES.md).

---

## Visual Inspection Scripts

After `pip install -e .`, these scripts provide a terminal view of each phase's output:

```bash
# Phase 1 — alias table + validation warnings
python scripts/inspect_alias_dict.py

# Phase 3 — parser output for all test cases (tabular)
python scripts/inspect_parser.py

# Phase 4 — matcher top-3 results for all test cases
python scripts/inspect_matcher.py

# Phase 5 — full NormalizationResult for one sample input
python scripts/print_sample_result.py

# Phase 6 — 596-row batch evaluation report
python scripts/batch_eval.py
```

---

## Chatbot Architecture

```
explain(raw, *, result, question, history, provider)
    │
    ├── normalize(raw)                ← skipped if result= provided
    │
    ├── _build_system_prompt(result)  ← injects full NormalizationResult as JSON
    │
    ├── _build_messages(system, user, history)
    │       [system, ...history_turns, new_user_message]
    │
    └── provider.chat(messages)       ← LLMProvider (GroqProvider by default)
```

**Provider abstraction:** The `LLMProvider` ABC makes swapping backends a one-class change. `GroqProvider` (default) uses `llama-3.1-8b-instant`. `ClaudeProvider` is included as a documented stub ready for implementation.

```python
class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict]) -> str: ...

class GroqProvider(LLMProvider): ...    # production default
class ClaudeProvider(LLMProvider): ...  # stub — NotImplementedError; see class docstring
```

---

## Data Model

### canonicals.csv (15 rows)

| Column | Description |
|--------|-------------|
| `canonical_name` | Display name (primary key), e.g. `"SPF"` |
| `species_group` | Broader grouping, e.g. `"SPF"` |
| `category` | Product category, e.g. `"Dimensional lumber"` |
| `treatment` | `"Pressure Treated"` or empty |
| `ambiguity_level` | `"Low"` / `"Medium"` / `"High"` |
| `notes` | Human-readable notes; surfaced as `warning` for High-ambiguity canonicals |

### aliases.csv (201 rows)

| Column | Description |
|--------|-------------|
| `alias` | Raw alias string as sellers write it, e.g. `"Whitewood Stud"` |
| `canonical_name` | Maps to a row in canonicals.csv |

Full schema documentation: [`data/data_dictionary.md`](data/data_dictionary.md)

---

## Known Limitations

See [`docs/KNOWN_CHALLENGES.md`](docs/KNOWN_CHALLENGES.md) for a detailed discussion of:

1. **Short abbreviation confusion** — `"SPF"` vs `"SYP"` differ by one character; stripped-down queries are fragile
2. **Product-class tokens as species identifiers** — `"Appearance Pine"` and `"Common Pine"` lose their discriminating token after stripping
3. **Concatenated and hyphenated inputs** — `"HemlockFir"` as one token scores worse than `"Hemlock Fir"` (two tokens)
4. **No embedded domain knowledge** — all species knowledge lives in the alias table; gaps there become gaps in coverage
5. **Prototype alias vocabulary** — the 201 aliases cover common North American retail naming but are not a verified commercial catalog
6. **Thresholds calibrated on synthetic data** — accuracy figures may differ on genuinely independent real-world inventories
7. **Grade tokens overlap with species tokens** — `"Select"` appears both as a grade and as part of species names

---

## Dependencies

### Core library (`pyproject.toml`)

| Package | Version | Purpose |
|---------|---------|---------|
| `pandas` | ≥ 2.0 | CSV loading and DataFrame operations |
| `pydantic` | ≥ 2.0 | `NormalizationResult` schema and validation |
| `rapidfuzz` | ≥ 3.0 | `token_sort_ratio` fuzzy matching |
| `pyyaml` | ≥ 6.0 | `thresholds.yml` config loading |

### Chatbot layer (`apps/chatbot/requirements.txt`)

| Package | Purpose |
|---------|---------|
| `groq` | Groq API client for `llama-3.1-8b-instant` |

### Streamlit UI (`apps/streamlit/requirements.txt`)

| Package | Purpose |
|---------|---------|
| `streamlit` | Web application framework |
| `groq` | Groq API client (Chatbot tab) |

### Development (`requirements.txt`)

| Package | Purpose |
|---------|---------|
| `pytest` | ≥ 7.0 | Test runner |

---

## Development Setup

```bash
# 1 — Clone and install
git clone <repo-url>
cd lumberlex
pip install -e .
pip install -r requirements.txt

# 2 — Verify the installation
python -c "from lumberlex import normalize; r = normalize('Whitewood Stud 2x4'); print(r.normalized_name, r.confidence)"
# Output: SPF 0.95

# 3 — Run the full test suite
pytest -m "not llm"                     # 256 tests, ~2s

# 4 — Chatbot setup (optional)
pip install -r apps/chatbot/requirements.txt
export GROQ_API_KEY=gsk_your_key_here
python apps/chatbot/demo.py             # 4 fixed samples
python apps/chatbot/chat.py             # interactive REPL

# 5 — Streamlit UI (optional)
pip install -r apps/streamlit/requirements.txt
streamlit run apps/streamlit/app.py
```

### Improving accuracy through data

LumberLex is strictly data-driven — all species knowledge lives in data files, not in the matching algorithm. **Improving the data files is the primary lever for improving accuracy.** No code changes are needed for the most common improvements.

There are two sets of data files with different roles:

#### `src/lumberlex/_data/` — the core knowledge base (bundled with the package)

These are the files the matching engine reads at runtime. Edit these to expand what the system can recognize.

| File | What it controls | How to improve |
|------|-----------------|----------------|
| `aliases.csv` | 201 alias → canonical mappings | **Add rows** to cover new seller strings, regional naming variants, abbreviations, or concatenated forms your inventory actually contains |
| `canonicals.csv` | 15 canonical lumber types + metadata | **Add rows** to introduce entirely new species or product types not yet in the system |
| `thresholds.yml` | Confidence band cutoffs | **Edit values** to tighten or loosen confidence scoring (see Configuration section) |

**To add an alias** (most common improvement):
```
# src/lumberlex/_data/aliases.csv
alias,canonical_name
"Hem-Fir #2 2x6","Hem-Fir"          ← add rows like this
"84 Lumber SYP Stud","Southern Yellow Pine"
```

**To add a canonical** (when covering an entirely new species):
```
# src/lumberlex/_data/canonicals.csv
canonical_name,species_group,category,treatment,ambiguity_level,notes
"Ponderosa Pine","Ponderosa Pine","Dimensional lumber","","Low","..."
```

After any edit to these files, run the validation cycle:
```bash
python scripts/inspect_alias_dict.py   # shows validation warnings instantly
pytest -m "not llm"                    # 256 tests — catches regressions
python scripts/batch_eval.py           # shows accuracy impact across all 596 rows
```

> Only developers can modify these files — no user-editable aliases in v0.

---

#### `data/` — evaluation and regression resources (not bundled, dev-only)

These files are not used at runtime. They exist to measure and validate accuracy.

| File | What it controls | How to improve |
|------|-----------------|----------------|
| `test_cases.csv` | 10 hand-crafted regression tests | **Add rows** to lock in correct behaviour for inputs you care about; every row becomes a permanent automated assertion |
| `lumberlex_sample_database.csv` | 596-row evaluation database | **Add rows** to broaden the accuracy measurement; run `python scripts/batch_eval.py` to see the updated score |
| `data_dictionary.md` | Schema documentation | Update when adding columns or changing field semantics |

**To add a regression test case:**
```
# data/test_cases.csv
input,expected_canonical,expected_size,confidence_min,notes
"SYP Stud 2x4x8","Southern Yellow Pine","2x4x8",0.80,"SYP stud common form"
```

Each new row in `test_cases.csv` is automatically picked up by `tests/test_normalizer.py` — no test code changes needed.

**The data improvement workflow:**

```
1. Identify a failing or low-confidence input
       ↓
2. Add the correct alias to src/lumberlex/_data/aliases.csv
       ↓
3. Add a regression row to data/test_cases.csv so it stays fixed
       ↓
4. Run: pytest -m "not llm"  →  python scripts/batch_eval.py
       ↓
5. Confirm accuracy improved, no regressions introduced
```

---

## Roadmap

- [ ] `ClaudeProvider` implementation (Anthropic SDK)
- [ ] `Normalizer.from_files(config_path=...)` for custom threshold overrides
- [ ] Seller-specific alias supplements (Lowe's, Home Depot, 84 Lumber)
- [ ] Context-aware product-class handling (keep `"appearance"` when it's the only discriminating token)
- [ ] Minimum token-length filter for short aliases in fuzzy mode
- [ ] Evaluation against independent real-world seller data
- [ ] PyPI publishing (structure is ready; deferred pending real-world validation)
