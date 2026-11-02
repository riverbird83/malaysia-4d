# Manual historical draw imports

Manual transcription is an approved recovery path when a result is visible online but cannot be scraped reliably.

## Staging rules

- Do not type directly into canonical datasets.
- Keep one row per operator and draw date.
- Never combine operators in one canonical file.
- Keep candidates in this directory until structural, provenance and conflict checks pass.

## Required record fields

- `operator_id`: one of `magnum`, `sportstoto`, `damacai`, `grand_dragon`
- `draw_date`: ISO date, `YYYY-MM-DD`
- `draw_seq`: official/source draw identifier when available; otherwise blank
- `prize_1`, `prize_2`, `prize_3`
- `special_1` through `special_10`
- `consol_1` through `consol_10`
- `source_type`: exactly `official`, `third_party`, or `manual_transcribed`
- `source_name` and `source_url`
- At least one of `retrieved_at` or `transcribed_at`
- `verification_status`: `corroborated`, `unverified`, `conflict`, or `rejected`
- `verification_notes`: describe what was checked, which prize fields matched, and any source-lineage limitation
- Optional secondary-source fields when another source was checked

## Transcription rules

1. Preserve every winning number as a four-character string, including leading zeroes (for example, `0047`).
2. Transcribe only what the source actually shows. Never infer a missing number from neighboring draws, patterns, or model predictions.
3. A page showing only First/Second/Third is not a complete 23-number draw. It may be used only for a clearly scoped Top-3 dataset, with the verified scope stated in the audit.
4. Record the exact URL. Where possible, preserve an archived page, screenshot or content hash.
5. A third-party or manually transcribed record must be cross-checked against another source. If the full draw cannot be cross-checked, mark it `unverified` and keep it quarantined.
6. If only some prize fields can be corroborated, state the verified scope explicitly; do not label the entire 23-number draw as corroborated.
7. If sources disagree, preserve both candidates and mark `conflict`; do not choose one silently.
8. Two sites copying the same upstream result count as one source lineage, not two independent confirmations.

## Promotion to canonical data

Promotion requires the operator-specific date range, four-digit number validation, duplicate/conflict checks, complete provenance fields and a passing operator-specific model-read test. A partial tranche may be released only with its exact date range, verified prize scope and unresolved counts clearly stated.

See `config/historical_collection_policy.json` for the date scopes and release gates.
