# Haolong (Grand Dragon) 4D source inventory

Scope: 4D only. This operator must have its own raw dataset, normalized dataset, model, walk-forward backtest, and report. Never merge its training rows with Magnum, Sports Toto, or Da Ma Cai.

## Candidate sources

- User's preferred source: https://live4dresult.net/
- User-supplied historical archive candidate: https://live4dresult.net/grand-dragon-4d-all
- Historical sample pages independently discovered: https://live4d.org/history/2017-02-09, https://live4d.org/history/2017-03-27, https://live4d.org/history/2017-06-06, https://live4d.org/history/2017-08-18
- Recent cross-check candidate: https://keputusan4d.com/4d-operators/grand-dragon/

## Confirmed evidence and limitations

Historical Grand Dragon 4D result pages exist for dates in February, March, June, and August 2017. This establishes that records are available by 2017, not that the operator began in 2017. A third-party archive reports 852 distinct dates from 2024-07-02 through 2026-10-31; this is a source claim and requires independent verification. No complete daily coverage claim is made yet.

## Data rules

- Import 4D only: First, Second, Third, Special, Consolation.
- Preserve numbers as four-character strings, including leading zeroes.
- Treat `----` and blank cells as missing values, never as numbers.
- Keep raw source HTML or a reproducible source snapshot plus source URL, retrieval timestamp, and parser version in an audit log.
- Do not invent draw IDs or dates.
- Detect duplicate dates and conflicting records. Do not silently overwrite conflicts.
- A record with missing main prizes is excluded from model training and retained in the audit report.
- Special and Consolation may be incomplete; preserve missing slots and completeness counts.

## Next implementation sequence

1. Probe the user-preferred site and its archive pagination; determine the oldest retrievable date and page structure.
2. Build a date-level coverage manifest distinguishing verified draw, no record found, non-draw day, fetch failure, and conflicting source.
3. Import all retrievable dates into `data/haolong_draws.csv` without changing the three existing operators' files.
4. Normalize into `data/normalized/haolong_draws.csv` using the shared four-digit normalization rules.
5. Cross-check a sample and all conflicts against a second archive.
6. Only after coverage and data quality are measured, build the independent Haolong 4D baseline and walk-forward tests.

Daily draw frequency gives more observations over calendar time; it does not establish higher predictability or guarantee returns.
