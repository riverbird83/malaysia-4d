"""Create canonical four-digit CSV copies without modifying source datasets."""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "magnum": ROOT / "data" / "magnum_draws.csv",
    "sportstoto": ROOT / "data" / "sportstoto_draws.csv",
    "damacai": ROOT / "data" / "damacai_draws.csv",
    "haolong": ROOT / "data" / "haolong_draws.csv",
}
NUMBER_FIELD = re.compile(r"^(?:prize_[123]|special_\d+|consol_\d+)$")
VALID_NUMBER = re.compile(r"^\d{1,4}(?:\.0+)?$")


def normalize_number(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if not VALID_NUMBER.fullmatch(value):
        raise ValueError(f"Invalid 4D number: {raw!r}")
    if "." in value:
        value = value.split(".", 1)[0]
    return value.zfill(4)


def normalize_file(source: Path, destination: Path) -> dict:
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    changed = 0
    with source.open("r", newline="", encoding="utf-8-sig") as src, destination.open(
        "w", newline="", encoding="utf-8"
    ) as dst:
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            raise ValueError(f"Missing CSV header: {source}")
        writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            row_count += 1
            for field in reader.fieldnames:
                if NUMBER_FIELD.fullmatch(field):
                    original = row.get(field, "") or ""
                    normalized = normalize_number(original)
                    if normalized != original.strip():
                        changed += 1
                    row[field] = normalized
            writer.writerow(row)
    return {"source": str(source), "destination": str(destination),
            "rows": row_count, "normalized_cells": changed}


def main():
    parser = argparse.ArgumentParser(description="Normalize 4D CSV copies")
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "normalized")
    args = parser.parse_args()
    reports = []
    for key in SOURCES:
        source = args.source_dir / f"{key}_draws.csv"
        destination = args.output_dir / f"{key}_draws.csv"
        if key == "haolong" and not source.exists():
            print("haolong: skipped (raw dataset has not been collected yet)")
            continue
        reports.append(normalize_file(source, destination))
    for report in reports:
        print(f"{report['destination']}: rows={report['rows']} "
              f"normalized_cells={report['normalized_cells']}")
    print("Source CSV files were not modified.")


if __name__ == "__main__":
    main()
