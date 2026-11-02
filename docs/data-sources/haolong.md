# 4D data coverage and source policy

## Required date ranges
- Magnum: 2006-01-01 through latest verifiable draw.
- Sports Toto: 2006-01-01 through latest verifiable draw.
- Da Ma Cai: 2006-01-01 through latest verifiable draw.
- Grand Dragon (Haolong): 2016-01-01 through latest verifiable draw.

All four operators are independent datasets, feature pipelines, model runs, Top-3 outputs, and walk-forward backtests. Do not pool training records across operators. This phase is 4D only; defer 6D and other products.

## Development priority and release policy
1. Prioritize Grand Dragon data acquisition and its independent 4D engine.
2. Continue backfilling Magnum, Sports Toto, and Da Ma Cai in parallel.
3. Do not wait for all four datasets to be complete. Any operator that meets the minimum usable-data gate may proceed to its own baseline model and walk-forward evaluation while the remaining operators continue backfilling.
4. Report real coverage and blockers. Never label an incomplete dataset complete.

## Source policy: official and third-party are both acceptable
Use official sources where available, but do not reject a real historical result solely because it is hosted by a third-party archive. Search multiple public archives. When automated scraping is blocked, manually transcribe visible historical records or use a semi-automated import workflow.

Every imported row must be traceable through a separate source-audit ledger keyed by operator + draw date + prize/field (or a stable row key), with:
- source_url
- source_type: official, third_party, or manual_transcribed
- retrieved_at or transcribed_at (UTC timestamp)
- verification_status: cross_checked, single_source, unverified, or conflict
- verification_notes
- parser/import batch identifier where applicable

A third-party or manually transcribed record is valid data to preserve, but its verification status must be explicit. Cross-check against another independent source when possible. Never silently promote single-source data to cross_checked.

## Prohibited data fabrication
- Never infer, calculate, randomly generate, copy from adjacent draws, or otherwise fabricate historical winning numbers.
- Never fill a missing result with a model prediction.
- Keep missing values blank. Keep a coverage manifest distinguishing confirmed draw, confirmed non-draw day, page not found, fetch failure, and unresolved gap.
- Preserve conflicting source observations in the audit ledger until reconciled; do not silently overwrite either observation.

## Data format and validation
- Raw CSVs remain operator-specific: data/magnum_draws.csv, data/sportstoto_draws.csv, data/damacai_draws.csv, data/haolong_draws.csv.
- Normalized copies remain under data/normalized/ with matching filenames.
- Preserve all 4D numbers as four-character strings, including leading zeroes.
- Main prizes First/Second/Third are required for model training. Missing or invalid main prizes exclude that draw from training but remain in audit/coverage reporting.
- Special and Consolation are optional auxiliary fields; missing cells remain blank and are not shifted to different positions.
- Keep raw source evidence and audit metadata separate from the normalized training schema unless the schema is deliberately versioned.

## Usable-data gate for independent development
A platform can begin its independent baseline model when:
1. Its requested date range has been scanned and a date coverage manifest exists.
2. All imported main-prize rows have valid dates and three valid four-digit main prizes.
3. Duplicate dates and conflicting records are explicitly resolved or quarantined.
4. Every row has provenance in the audit ledger; single-source third-party/manual rows are allowed but visibly flagged.
5. A normalized copy is generated and validation tests pass.
6. The backtest reports the exact verified/unverified coverage and never treats missing dates as non-draw days without evidence.

Dataset completion requires stronger evidence: all expected draw dates are accounted for, unresolved fetch failures and conflicts are zero, and completeness statistics are reported by prize field. Do not confuse a usable dataset with a complete dataset.

## Grand Dragon source candidates
- User-preferred source: https://live4dresult.net/
- Archive candidate: https://live4dresult.net/grand-dragon-4d-all
- Recent cross-check candidate: https://keputusan4d.com/4d-operators/grand-dragon/

Grand Dragon is the first priority for the 2016-01-01 onward scope. The archive's actual oldest date and daily completeness must be measured, not assumed.
