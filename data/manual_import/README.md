# Manual historical draw imports

Manual transcription is an approved recovery path when a result is visible online but cannot be scraped reliably.

## Do not type directly into canonical datasets

Place incoming records in a staging CSV under this directory. Keep one row per operator and draw date. Never combine operators in one canonical file.

## Required record fields

- `operator_id`: exactly one of `magnum`, `sportstoto`, `damacai`, `grand_dragon`
- `draw_date`: ISO date, `YYYY-MM-DD`
- `draw_seq`: official/source draw identifier when available; otherwise blank
- `prize_1`, `prize_2`, `prize_3`
- `special_1` through `special_10`
- `consol_1` through `consol_10`
- `source_type`: `official`, `third_party_archive`, `community_archive`, or `manual_transcription`
- `source_name`
- `source_url`: URL when available
- `evidence_ref`: repository-relative screenshot/archive path or other retrievable evidence reference
- `captured_at_utc`
- `verification_status`: `candidate`, `single_source_checked`, `corroborated`, `conflict`, or `rejected`
- `notes`

## Transcription rules

1. Preserve every winning number as a four-character string, including leading zeroes (for example, `0047`).
2. Transcribe only what the source actually shows. Never infer a missing number from neighboring draws, patterns, or model predictions.
3. If a page shows only First/Second/Third, record the row as incomplete in staging; do not promote it into the full 23-number canonical dataset.
4. Record the exact URL and, where possible, save a screenshot or page snapshot under an operator-specific evidence folder.
5. A second person or a second independent source should verify manual transcriptions where practical. If only one source exists, label it `single_source_checked`, not `corroborated`.
6. If sources disagree, preserve both candidates and mark `conflict`; do not choose one silently.
7. Keep source lineage: two sites copying the same upstream result count as one lineage, not two independent confirmations.

## Promotion to canonical data

A promotion script must validate the operator-specific date range, all 23 four-digit numbers, duplicate dates/IDs, provenance fields, and conflicts before appending to that operator's own CSV. The import must produce an audit entry. A failed or incomplete candidate remains in staging and must not change canonical data.

See `config/historical_collection_policy.json` for the date scopes and release gates.
