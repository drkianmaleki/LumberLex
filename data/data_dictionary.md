# LumberLex — Data Dictionary

This document describes the CSV files that form the core data layer of
LumberLex. They were generated programmatically from the original source files
(`lumberlex_canonical_aliases.csv`, `lumberlex_test_cases.csv`, and
`lumberlex_sample_database.xlsx`) and cleaned into the structure described here.

---

## File Locations (after Phase 7)

| File | Location | Bundled | Purpose |
|------|----------|---------|---------|
| `canonicals.csv` | `src/lumberlex/_data/` | ✅ Yes | One row per canonical lumber type; holds all metadata |
| `aliases.csv` | `src/lumberlex/_data/` | ✅ Yes | Translation table; maps every known alias to a canonical name |
| `thresholds.yml` | `src/lumberlex/_data/` | ✅ Yes | Matching thresholds (bundled fallback; see `config/thresholds.yml` for the developer copy) |
| `test_cases.csv` | `data/` | ❌ No | Regression test inputs with expected outputs for pytest |
| `lumberlex_sample_database.csv` | `data/` | ❌ No | 596-row synthetic seller inventory for batch evaluation |

**Bundled files** (`src/lumberlex/_data/`) are included in the installed package and
available after `pip install lumberlex`. `canonicals.csv` and `aliases.csv` can
be loaded via the library's built-in path constants:

```python
from lumberlex.data_layer import DEFAULT_CANONICALS_PATH, DEFAULT_ALIASES_PATH
```

**Non-bundled files** (`data/`) are development resources included in the
source repository but not distributed with the installed package.

---

## Schema: `canonicals.csv`

**One row per canonical lumber type. 15 rows.**

### Columns

| Column | Type | Values | Description |
|--------|------|--------|-------------|
| `canonical_name` | string | e.g. `SPF`, `Douglas Fir-Larch` | The authoritative name for this lumber type. This is the primary key — every alias in `aliases.csv` maps to one of these values. |
| `species_group` | string | e.g. `Spruce-Pine-Fir`, `Southern Pine` | The biological or commercial species group. May differ from `canonical_name` when the canonical is a treated variant (e.g. `Pressure Treated Southern Yellow Pine` has `species_group = Southern Pine`). |
| `category` | string | e.g. `Dimensional framing lumber`, `Hardwood/appearance board`, `Panel/sheathing` | Broad product category used for display and filtering. |
| `treatment` | string | `Pressure Treated` or *(empty)* | Treatment status. Empty means untreated or treatment not applicable. The string `"None"` from the original source file was replaced with an empty value — an empty cell is cleaner and unambiguous in Python/pandas. |
| `ambiguity_level` | string | `Low`, `Medium`, `High` | How reliably the canonical name identifies a single species. **Low** = well-defined commercial species or group. **Medium** = commercially common but may cover multiple species depending on supplier. **High** = trade/seller term that may not identify an exact species without a grade stamp or supplier confirmation. |
| `notes` | string | free text | Human-readable explanation of ambiguity, common usage patterns, or caveats. Surfaced to the user when a match is found. |

### Ambiguity level reference

| Level | Meaning | Examples |
|-------|---------|---------|
| Low | Single species or well-defined combination | `Hem-Fir`, `OSB`, `MDF` |
| Medium | Common commercial group; species may vary by region or supplier | `Douglas Fir-Larch`, `Southern Yellow Pine`, `Western Red Cedar` |
| High | Trade/seller term; exact species not guaranteed | `SPF`, `Oak`, `Maple` |

---

## Schema: `aliases.csv`

**One row per alias string. 205 rows** (201 original + 4 added in Phase 6).

### Columns

| Column | Type | Description |
|--------|------|-------------|
| `alias` | string | A known seller name, abbreviation, trade term, or variant spelling. Preserved in original mixed case from source data. |
| `canonical_name` | string | The canonical type this alias maps to. Must match a value in `canonicals.csv → canonical_name`. |

### Design notes

- **Case**: Aliases are stored in their natural mixed case. The normalizer
  lowercases both sides at match time, so lookups are case-insensitive.
- **Hyphens**: Letter-adjacent hyphens in alias keys are normalised to spaces
  at build time (e.g. `"Hem-Fir #2"` → key `"hem fir #2"`). Digit-adjacent
  hyphens are preserved (e.g. `"2x4x92-5/8"` stays as-is).
- **Extending the table**: To add a new alias, add one row to `aliases.csv`.
  To add a new canonical type, add one row to `canonicals.csv` and one or more
  rows to `aliases.csv`. No other files need to change.

---

## Schema: `test_cases.csv`

**One row per regression test case. 10 rows.**

### Columns

| Column | Type | Description |
|--------|------|-------------|
| `input` | string | Raw product name string, exactly as a seller might supply it. |
| `expected_canonical` | string | The canonical name the normalizer must return. Use `UNKNOWN` for no-match cases. |
| `expected_size` | string | The dimension string the parser must extract. Empty if no size is present. |
| `confidence_min` | float | The minimum confidence score the normalizer must return. |
| `notes` | string | Human-readable intent note. Not used by pytest assertions. |

---

## Schema: `lumberlex_sample_database.csv`

**596 rows** of synthetic seller inventory used for batch evaluation (Phase 6).

Key columns: `record_id`, `seller`, `raw_product_name`, `canonical_name`,
`treatment`, `species_group`, `category`.

**Note**: The `expected_size_hint` column is corrupted (populated with a
rotating pool rather than derived from `raw_product_name`) and is excluded
from all accuracy assertions. Size accuracy is evaluated against
`test_cases.csv` only.

---

## Sources

The alias vocabulary and canonical definitions were derived from the following
public sources:

| Source | URL | Used for |
|--------|-----|---------|
| Home Depot Lumber Guide | https://www.homedepot.com/c/ab/types-of-lumber/9ba683603be9fa5395fab90567851db | Retail terminology and lumber category names |
| Lowe's Lumber Buying Guide | https://www.lowes.com/n/buying-guide/lumber-buying-guide | Whitewood explanation; SPF and treated lumber categories |
| WWPA Resources | https://www.wwpa.org/resources/ | Species group definitions: Douglas Fir-Larch, Hem-Fir, SPF, Southern Pine |
| SPIB Glossary | https://www.spib.org/glossary | Southern Pine species group; SYP commercial terminology |

> **Important limitation**: The alias vocabulary is a prototype dataset derived
> from public terminology and synthetic seller-style records. It is not a
> verified commercial product catalog. Exact species identification for
> ambiguous terms requires a grade stamp or direct supplier confirmation.
