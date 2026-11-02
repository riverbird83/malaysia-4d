# Haolong (Grand Dragon) 4D source inventory

## Scope
- Operator: Grand Dragon 4D / GD Lotto / Haolong (豪龙).
- This operator has its own raw dataset, normalized dataset, model, walk-forward backtest, and reports.
- Never merge Haolong training rows with Magnum, Sports Toto, or Da Ma Cai.
- Current phase: 4D only. Exclude 6D.

## Primary source
- User's preferred result site: https://live4dresult.net/
- Latest result page: https://live4dresult.net/lotto-4d/
- Date archive pattern: https://live4dresult.net/past-results/YYYY-MM-DD/
- Example verified historical pages: 2022-09-23, 2023-08-11, 2025-07-04, 2026-08-14, 2026-11-01.
- The first full crawl (2017-01-01 through 2026-11-01) parsed 891 unique dates from this source, 2022-04-21 through 2026-10-30. It returned `operator_not_found` for 2,701 calendar dates; these are unresolved source gaps, not verified non-draw days.
- The crawl did not establish that this preferred source has complete daily coverage. It must not be used alone to define the full historical range.

## Prize schema
- Main prizes: First, Second, Third (required for a model-training row).
- Special section: 10 prize numbers displayed in a 15-cell layout (3 rows x 5 columns on some dates); explicit `----` placeholders and empty layout cells must remain blank while preserving their positions. Completeness is measured against 10 prize numbers, not 15 visual cells.
- Consolation section: 10 prize numbers displayed in up to 10 cells (2 rows x 5 columns). Preserve missing cells and observed counts in the audit manifest.
- Every 4D value is stored as a four-character string, including leading zeroes.
- Draw sequence is blank unless the source publishes a verified draw number.

## Audit policy
- Raw rows: `data/haolong_draws.csv`.
- Normalized rows: `data/normalized/haolong_draws.csv`.
- Date-level source audit: `data/audit/haolong_coverage.csv`.
- Audit includes status, HTTP status, URL, retrieval time, content SHA-256, parser version, observed Special/Consolation slot counts, and notes.
- A 404 is `page_not_found`, not automatically a non-draw day.
- A loaded page without the operator is `operator_not_found`.
- A page with the operator but missing main prizes is `parse_incomplete`.
- Network/HTTP errors are `fetch_failed`.
- A conflicting re-scrape never silently overwrites an existing record.
- Do not call the historical range complete until every expected date is accounted for, source gaps are cross-checked, all conflicts are resolved, and the normalized file validates.

## Historical boundary
- The current primary-source dataset begins on 2022-04-21, but this is not the operator's historical start.
- Independent historical evidence exists at least as early as 2017-01-21 on `live4d.org/history/YYYY-MM-DD`.
- The `4d2ulive.com/grand-dragon-4d-all` archive reaches at least 2020-06-16 (page 388) and shows daily consecutive records around that date.
- The exact founding date and earliest recoverable historical draw remain unverified. Backfill 2017 onward from secondary archives, reconcile overlaps, and preserve source provenance.

## Model policy
- Train and evaluate Haolong independently.
- Use chronological walk-forward evaluation with strictly prior dates only.
- Compare model and ensemble Top-3 results with a random baseline.
- Report First/Second/Third hit rates separately, with sample size and uncertainty.
- More daily observations do not prove higher per-draw predictability. Ranking scores are not winning probabilities and do not guarantee returns.


## Verified secondary archive evidence (snapshot: 2026-11-02)

- `live4d.org/history/YYYY-MM-DD` has a Grand Dragon record at least as early as 2017-01-21. This is a confirmed archive sample, not a confirmed founding date.
- `4d2ulive.com/grand-dragon-4d-all/page/388/` shows records for 2020-06-16 and 2020-06-17; page 379 shows consecutive records for 2020-08-04 through 2020-08-09.
- Keputusan4D reports 852 distinct Grand Dragon dates from 2024-07-02 through 2026-10-31. The current primary-source CSV contains 469 records in that same date window, so 383 dates require reconciliation against secondary sources. Treat this as a coverage discrepancy until each date is matched; do not auto-label dates as non-draw days.

## Current primary-source import snapshot

- Raw and normalized files: 891 unique records, 2022-04-21 through 2026-10-30.
- First/Second/Third: 891/891 rows complete (100%).
- Special: every row contains 10 valid prize numbers in a 15-cell visual layout (891/891 draws complete).
- Consolation: every row contains 10 valid prize numbers (891/891 draws complete).
- Date audit: 3,592 calendar dates have audit rows; 891 are parsed and 2,701 are `operator_not_found`. There are zero confirmed non-draw days. These 2,701 dates remain unresolved, not cleared.
- No duplicate raw dates or same-source conflicting records were found in this snapshot.
- The strict completion gate remains false until source gaps are reconciled and all expected draw dates are accounted for.

## Independent model boundary

- Prediction CLI requires one explicit operator: `--operator magnum|sportstoto|damacai|haolong`.
- Backtest rejects rows containing more than one operator.
- Each operator's normalized file is loaded independently. Do not train a pooled cross-operator model.
