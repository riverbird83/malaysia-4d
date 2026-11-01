# Data Quality Audit — Initial Baseline

**Repository:** `riverbird83/malaysia-4d`  
**Branch:** `data-quality-foundation`  
**Audit date:** 2026-11-01  
**Scope:** Read-only structural inspection of the three CSV files in `data/`. This is not an official-source verification.

## Executive finding

The datasets are useful as a historical starting point, but they are **not yet ready to train or evaluate a prediction model**. The most urgent issue is inconsistent number serialization: 4D values have been stored without leading zeroes, and Sport Toto consolation values contain pandas-style decimal suffixes (for example, `1234.0`). These can be normalized mechanically only after preserving and documenting the raw source values.

## Snapshot

| Operator | Rows | Date range | Duplicate dates | Repeated draw_seq values |
|---|---:|---|---:|---:|
| Magnum | 6,835 | 1985-04-25 – 2026-10-31 | 0 | 998 |
| Sport Toto | 5,689 | 1992-05-06 – 2026-10-31 | 0 | 0 |
| Da Ma Cai | 3,664 | 2005-01-01 – 2026-10-31 | 0 | 0 |

## Findings

### 1. Four-digit numbers are not stored canonically

The CSVs contain 1-, 2-, 3-, and 4-character numeric values. Examples include `19`, `316`, and `777`. A 4D number must be represented as a four-character string, e.g. `0019`, `0316`, `0777`. Numeric types must never be used for winning numbers because they discard leading zeroes.

### 2. Sport Toto consolation values have a serialization defect

The Sport Toto file contains 25,580 consolation cells with values serialized in decimal form (for example, `893.0`, `8224.0`). This is consistent with a numeric dataframe column being converted to floating-point because older rows contain blanks. These values are recoverable as integers, but must be normalized as strings and checked against the source before being treated as verified.

There are 3,130 blank values in each of the ten consolation columns. The current snapshot does not establish whether every blank represents an officially unpublished historical result, a scraper omission, or a parsing failure. Do not fill these blanks by inference.

### 3. Magnum draw_seq is not a unique identifier

Magnum has 998 repeated draw sequence values. Sequence numbers evidently recur across periods/years. Do not use `draw_seq` as a primary key. Use `operator + date` as the business key, and retain draw sequence as descriptive metadata only.

### 4. The automatic update workflow can silently publish incomplete data

The current workflow marks all three scraper steps `continue-on-error: true`, then copies CSV files and updates the dashboard date even if a scraper failed. This can make the website display a new update date while one or more datasets are stale or incomplete.

The workflow needs a validation gate. A failed scraper or failed validation must stop publication; the dashboard update date must reflect the latest successfully validated data, not the workflow execution date.

### 5. Source provenance needs to be recorded per draw

Sport Toto's scraper may fall back to `check4d.com` when its official website blocks requests. The CSV schema does not record which source produced each row. Add provenance metadata (source URL, retrieval timestamp, parser version, verification status) in a separate audit/provenance layer; do not silently label fallback data as official-source verified.

## Required database standard

1. Store every winning number as a **four-character text value** from `0000` through `9999`.
2. Use `operator + draw_date` as the unique key. Keep `draw_seq` non-unique.
3. Preserve raw scraped payloads or raw source extracts separately from normalized records.
4. Record per-row provenance and verification state: `official_verified`, `secondary_source`, or `unverified`.
5. Distinguish a genuinely unpublished historical field from a scraper failure. Missing values remain null; never invent or interpolate results.
6. Validate all 3 main prizes, up to 10 Special and up to 10 Consolation numbers, date validity, duplicates, and source-specific expectations before publishing.
7. Keep a dated immutable snapshot of each published dataset so model backtests can reproduce the exact data available at each historical cutoff.

## Prediction-system implications

No model should be trained or scored against the current CSVs until number normalization and source/missingness audits are complete. After that, evaluate each operator independently first, then test a cross-operator model only if the data and draw mechanisms justify it.

The model's primary target is the **top-three prize outcome**. The Top 3 candidate list must be frozen before each draw. Evaluation must use chronological walk-forward testing and compare against a random Top 3 baseline under the same draw dates and prize definitions. Report hit rates with confidence intervals and separate First/Second/Third hits from any-prize hits.

A model score is a ranking score, not a probability. Only show a probability if it has been calibrated on held-out chronological data and demonstrates calibration quality. If no measurable lift over random selection is found, the system must say so rather than manufacture confidence.

## Audit tooling

`scripts/validate_data.py` is a read-only first-pass validator. It reports structural errors and recoverable formatting issues without changing source CSVs. It is a guardrail, not an official-source verification or a complete data reconciliation system.
