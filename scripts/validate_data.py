#!/usr/bin/env python3
"""Read-only integrity audit for the three Malaysia 4D CSV datasets.

This tool never edits source data. It reports recoverable formatting issues
(e.g. 123 -> 0123, 1234.0 -> 1234) separately from structural errors.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

DATASETS = {
    "magnum": Path("data/magnum_draws.csv"),
    "sportstoto": Path("data/sportstoto_draws.csv"),
    "damacai": Path("data/damacai_draws.csv"),
}
MAIN_FIELDS = ("prize_1", "prize_2", "prize_3")
NUMBER_RE = re.compile(r"^\d{1,4}(?:\.0+)?$")


def canonical_number(raw: str) -> str | None:
    value = (raw or "").strip()
    if not value:
        return None
    if not NUMBER_RE.fullmatch(value):
        return None
    if "." in value:
        value = value.split(".", 1)[0]
    return value.zfill(4)


def audit_file(operator: str, path: Path) -> dict:
    report = {
        "operator": operator,
        "file": str(path),
        "exists": path.exists(),
        "rows": 0,
        "date_min": None,
        "date_max": None,
        "duplicate_dates": [],
        "duplicate_draw_seq_count": 0,
        "missing_main_prize_rows": [],
        "missing_numbers_by_field": {},
        "number_format_counts": {"already_4_digits": 0, "needs_zero_padding": 0,
                                 "integer_float_artifact": 0, "invalid": 0},
        "invalid_number_examples": [],
        "duplicate_numbers_within_draw": [],
        "status": "ERROR",
    }
    if not path.exists():
        report["error"] = "CSV file not found"
        return report

    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        required = {"date", *MAIN_FIELDS}
        missing_columns = sorted(required - set(fields))
        if missing_columns:
            report["error"] = f"Missing required columns: {missing_columns}"
            return report

        dates = Counter()
        sequences = Counter()
        missing_by_field = Counter()
        date_values = []
        for line_no, row in enumerate(reader, start=2):
            report["rows"] += 1
            draw_date = (row.get("date") or "").strip()
            try:
                date.fromisoformat(draw_date)
                date_values.append(draw_date)
                dates[draw_date] += 1
            except ValueError:
                report.setdefault("invalid_dates", []).append(
                    {"line": line_no, "value": draw_date}
                )

            seq = (row.get("draw_seq") or "").strip()
            if seq:
                sequences[seq] += 1

            for field in MAIN_FIELDS:
                if canonical_number(row.get(field, "")) is None:
                    report["missing_main_prize_rows"].append(
                        {"line": line_no, "field": field, "value": row.get(field, "")}
                    )

            row_numbers = []
            for field in fields:
                if not re.fullmatch(r"(?:prize_[123]|special_\d+|consol_\d+)", field):
                    continue
                raw = (row.get(field) or "").strip()
                if not raw:
                    missing_by_field[field] += 1
                    continue
                normalized = canonical_number(raw)
                if normalized is None:
                    report["number_format_counts"]["invalid"] += 1
                    if len(report["invalid_number_examples"]) < 20:
                        report["invalid_number_examples"].append(
                            {"line": line_no, "field": field, "value": raw}
                        )
                    continue
                if "." in raw:
                    report["number_format_counts"]["integer_float_artifact"] += 1
                elif len(raw) < 4:
                    report["number_format_counts"]["needs_zero_padding"] += 1
                else:
                    report["number_format_counts"]["already_4_digits"] += 1
                row_numbers.append((field, normalized))

            normalized_values = [value for _, value in row_numbers]
            duplicates = [n for n, count in Counter(normalized_values).items() if count > 1]
            if duplicates and len(report["duplicate_numbers_within_draw"]) < 20:
                report["duplicate_numbers_within_draw"].append(
                    {"line": line_no, "date": draw_date, "numbers": duplicates}
                )

        report["date_min"] = min(date_values) if date_values else None
        report["date_max"] = max(date_values) if date_values else None
        report["duplicate_dates"] = [
            {"date": d, "count": count} for d, count in dates.items() if count > 1
        ]
        report["duplicate_draw_seq_count"] = sum(1 for count in sequences.values() if count > 1)
        report["missing_numbers_by_field"] = dict(sorted(missing_by_field.items()))

    critical = (
        bool(report.get("invalid_dates"))
        or bool(report["duplicate_dates"])
        or bool(report["missing_main_prize_rows"])
        or report["number_format_counts"]["invalid"] > 0
        or any(report["missing_numbers_by_field"].values())
    )
    report["status"] = "FAIL" if critical else (
        "PASS_WITH_NORMALIZATION" if (
            report["number_format_counts"]["needs_zero_padding"]
            or report["number_format_counts"]["integer_float_artifact"]
            or report["missing_numbers_by_field"]
            or report["duplicate_draw_seq_count"]
        ) else "PASS"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit 4D CSV data without modifying it")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    reports = [audit_file(name, path) for name, path in DATASETS.items()]
    result = {"datasets": reports}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for item in reports:
            print(
                f"{item['operator']}: {item['status']} | rows={item['rows']} | "
                f"dates={item['date_min']}..{item['date_max']} | "
                f"duplicates(date)={len(item['duplicate_dates'])} | "
                f"bad_numbers={item['number_format_counts']['invalid']}"
            )
            print(f"  number formats: {item['number_format_counts']}")
            print(f"  missing fields: {item['missing_numbers_by_field']}")
            if item["duplicate_draw_seq_count"]:
                print(f"  advisory: {item['duplicate_draw_seq_count']} repeated draw_seq values")
            if item["duplicate_numbers_within_draw"]:
                print("  advisory: repeated winning numbers within a draw are preserved and are not errors")
    return 1 if any(item["status"] == "FAIL" for item in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
