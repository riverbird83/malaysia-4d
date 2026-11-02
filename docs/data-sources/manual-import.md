# Manual and third-party 4D result import

Manual transcription is an approved recovery path when a public result is visible but cannot be scraped reliably. Third-party records are not rejected merely because they are not hosted by the operator.

## Rules

1. Transcribe only results that are visibly published on a source page, archived image, PDF, or other reproducible evidence.
2. Preserve each number as text with exactly four digits (for example, `0047`).
3. Never infer an unreadable digit, reconstruct a missing result from neighboring dates, or use a model prediction as a historical result.
4. Record one source observation per operator/date/source. If two sources disagree, keep both observations in the audit ledger and quarantine the draw until resolved.
5. Distinguish `cross_checked`, `single_source`, `unverified`, and `conflict`. A manually transcribed record may be usable with `single_source` status; it must not be presented as cross-checked.
6. Keep screenshot/PDF/page URL and retrieval/transcription timestamp so another reviewer can reproduce the entry.
7. A blank or `----` cell stays blank. Do not shift later numbers left to fill a gap.

## Import batch fields

Use these fields in a separate audit ledger (do not add them to the model's draw CSV):

- operator
- draw_date (YYYY-MM-DD)
- prize_field (prize_1, prize_2, prize_3, special_1.., consol_1..)
- number (four-character string or blank)
- source_url
- source_type (official, third_party, manual_transcribed)
- evidence_file (optional path/name for a saved screenshot or PDF)
- transcribed_by
- transcribed_at_utc
- verification_status
- verification_notes
- batch_id

## Release gate

Single-source third-party/manual rows can be retained and used in a separately reported experimental dataset if all three main prizes are readable and the source evidence is preserved. Keep a strict primary dataset containing cross-checked records separately, and report backtests on both tiers separately. Never combine unverified and verified rows without labeling the provenance tier.
