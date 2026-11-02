"""Validate Haolong 4D raw/normalized data and its date-level source audit."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "haolong_draws.csv"
NORMALIZED = ROOT / "data" / "normalized" / "haolong_draws.csv"
AUDIT = ROOT / "data" / "audit" / "haolong_coverage.csv"
SPECIAL_FIELDS = [f"special_{i}" for i in range(1, 16)]
CONSOL_FIELDS = [f"consol_{i}" for i in range(1, 11)]


def read_csv(path: Path) -> tuple[list[dict], list[str]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), reader.fieldnames or []


def valid4(value: str) -> bool:
    return len(value or "") == 4 and (value or "").isdigit()


def validate(start: date | None = None, end: date | None = None) -> dict:
    raw, raw_fields = read_csv(RAW)
    normalized, normalized_fields = read_csv(NORMALIZED)
    audit_rows, audit_fields = read_csv(AUDIT)
    dates = [row.get("date", "") for row in raw]
    duplicate_dates = sorted(d for d, count in Counter(dates).items() if count > 1)
    valid_dates = sorted(d for d in dates if d)
    earliest = valid_dates[0] if valid_dates else None
    latest = valid_dates[-1] if valid_dates else None

    required_raw = {"date", "prize_1", "prize_2", "prize_3", *SPECIAL_FIELDS, *CONSOL_FIELDS}
    missing_raw_columns = sorted(required_raw - set(raw_fields))
    invalid_main_rows = [
        row.get("date", "") for row in raw
        if not all(valid4(row.get(f"prize_{i}", "")) for i in range(1, 4))
    ]
    invalid_number_cells = []
    for row in raw:
        for field in ["prize_1", "prize_2", "prize_3", *SPECIAL_FIELDS, *CONSOL_FIELDS]:
            value = row.get(field, "")
            if value and not valid4(value):
                invalid_number_cells.append(f"{row.get('date')}:{field}={value}")

    normalized_dates = [row.get("date", "") for row in normalized]
    normalized_matches_raw = (
        bool(normalized) and len(normalized) == len(raw)
        and normalized_dates == dates
        and set(required_raw).issubset(set(normalized_fields))
    )

    audit_by_date = {row.get("date", ""): row for row in audit_rows if row.get("date")}
    if start is None and valid_dates:
        start = date.fromisoformat(earliest)
    if end is None and valid_dates:
        end = date.fromisoformat(latest)
    expected_dates = []
    if start and end and end >= start:
        current = start
        while current <= end:
            expected_dates.append(current.isoformat())
            current += timedelta(days=1)
    unaccounted_dates = [d for d in expected_dates if d not in audit_by_date]
    status_counts = Counter(
        audit_by_date[d].get("status", "") for d in expected_dates if d in audit_by_date
    )
    unresolved_statuses = {
        "page_not_found", "operator_not_found", "parse_incomplete",
        "fetch_failed", "conflict", "source_unverified",
    }
    unresolved_dates = [
        d for d in expected_dates
        if d in audit_by_date and audit_by_date[d].get("status") in unresolved_statuses
    ]
    confirmed_non_draw_days = sum(
        audit_by_date[d].get("status") == "confirmed_non_draw_day"
        for d in expected_dates if d in audit_by_date
    )
    parsed_dates = {
        d for d in expected_dates
        if d in audit_by_date and audit_by_date[d].get("status") == "parsed"
    }
    record_dates = set(valid_dates)
    missing_record_for_parsed = sorted(parsed_dates - record_dates)
    main_complete = len(raw) - len(invalid_main_rows)
    special_observed = sum(int(row.get("special_slots_observed") or 0)
                            for row in audit_rows if row.get("date") in record_dates)
    special_numbers = sum(int(row.get("special_numbers_found") or 0)
                          for row in audit_rows if row.get("date") in record_dates)
    consolation_observed = sum(int(row.get("consolation_slots_observed") or 0)
                               for row in audit_rows if row.get("date") in record_dates)
    consolation_numbers = sum(int(row.get("consolation_numbers_found") or 0)
                              for row in audit_rows if row.get("date") in record_dates)

    report = {
        "raw_exists": RAW.exists(),
        "normalized_exists": NORMALIZED.exists(),
        "audit_exists": AUDIT.exists(),
        "raw_rows": len(raw),
        "unique_raw_dates": len(set(valid_dates)),
        "duplicate_dates": duplicate_dates,
        "earliest_date": earliest,
        "latest_date": latest,
        "main_prize_complete_rows": main_complete,
        "main_prize_completeness_rate": round(main_complete / len(raw), 6) if raw else 0,
        "invalid_main_rows": invalid_main_rows,
        "invalid_number_cells": invalid_number_cells[:100],
        "special_slots_observed": special_observed,
        "special_numbers_found": special_numbers,
        "consolation_slots_observed": consolation_observed,
        "consolation_numbers_found": consolation_numbers,
        "normalized_rows": len(normalized),
        "normalized_matches_raw": normalized_matches_raw,
        "audit_rows": len(audit_rows),
        "audit_status_counts_in_range": dict(status_counts),
        "expected_calendar_days": len(expected_dates),
        "audit_calendar_coverage_rate": (
            round((len(expected_dates) - len(unaccounted_dates)) / len(expected_dates), 6)
            if expected_dates else 0
        ),
        "unaccounted_dates": unaccounted_dates[:100],
        "unresolved_dates": unresolved_dates[:100],
        "confirmed_non_draw_days": confirmed_non_draw_days,
        "parsed_audit_dates_without_raw_record": missing_record_for_parsed,
        "missing_raw_columns": missing_raw_columns,
        "missing_audit_columns": sorted(set([
            "date", "status", "source_url", "fetched_at_utc",
            "content_sha256", "parser_version",
        ]) - set(audit_fields)),
    }
    report["strict_complete"] = (
        RAW.exists() and NORMALIZED.exists() and AUDIT.exists()
        and bool(raw) and not duplicate_dates and not invalid_main_rows
        and not invalid_number_cells and normalized_matches_raw
        and not missing_raw_columns and not report["missing_audit_columns"]
        and not unaccounted_dates and not unresolved_dates
        and not missing_record_for_parsed
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Haolong 4D database")
    parser.add_argument("--from", dest="start")
    parser.add_argument("--to", dest="end")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = validate(
        date.fromisoformat(args.start) if args.start else None,
        date.fromisoformat(args.end) if args.end else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and not report["strict_complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
