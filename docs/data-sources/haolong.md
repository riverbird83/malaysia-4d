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
- These examples prove records exist on those dates; they do not prove uninterrupted coverage or the operator's founding date.

## Prize schema
- Main prizes: First, Second, Third (required for a model-training row).
- Special section: up to 15 visible cells (3 rows x 5 columns on some dates); some cells are explicit `----` placeholders and must be stored as blank while preserving their slot positions.
- Consolation section: up to 10 visible cells (2 rows x 5 columns on some dates); some historical pages may expose fewer cells. Preserve the observed count in the audit manifest.
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
- Verified examples exist in 2022, 2023, 2025, and 2026.
- A prior source search found 2017 examples, but the oldest available date and founding year are still unverified.
- Begin the first backfill at 2017-02-01 as a provisional crawl boundary. Keep every date's result status so earlier history can be tested separately and gaps are not hidden.

## Model policy
- Train and evaluate Haolong independently.
- Use chronological walk-forward evaluation with strictly prior dates only.
- Compare model and ensemble Top-3 results with a random baseline.
- Report First/Second/Third hit rates separately, with sample size and uncertainty.
- More daily observations do not prove higher per-draw predictability. Ranking scores are not winning probabilities and do not guarantee returns.
