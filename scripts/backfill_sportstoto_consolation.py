#!/usr/bin/env python3
"""One-time official-source backfill for missing Sport Toto Consolation values.

Safety properties:
- Reads the canonicalized copy in data/normalized/.
- Fetches monthly archive pages from Sport Toto's official website only.
- Fills blank Consolation fields only; never overwrites existing values.
- Preserves repeated winning numbers.
- Writes a new output file only if every targeted blank row is fully recovered.
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

# Make repository-root modules importable when this file is executed as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from scraper_sportstoto import parse_month_official

SOURCE = Path("data/normalized/sportstoto_draws.csv")
OUTPUT = Path("data/backfill/sportstoto_draws_backfilled.csv")
START_DATE = "2006-01-01"
END_DATE = "2011-06-10"
DELAY_SECONDS = 0.6
CONSOL_FIELDS = [f"consol_{i}" for i in range(1, 11)]


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source dataset: {SOURCE}")

    df = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)
    required = {"date", *CONSOL_FIELDS}
    missing_columns = required - set(df.columns)
    if missing_columns:
        raise SystemExit(f"Missing columns: {sorted(missing_columns)}")

    target_mask = df["date"].between(START_DATE, END_DATE)
    blank_mask = target_mask & df[CONSOL_FIELDS].eq("").any(axis=1)
    target_missing_dates = set(df.loc[blank_mask, "date"])
    if not target_missing_dates:
        print("No missing Consolation rows in target range.")
        return 0

    print(
        f"Target rows with missing Consolation: {len(target_missing_dates)} "
        f"({min(target_missing_dates)} to {max(target_missing_dates)})"
    )

    official_by_date: dict[str, dict] = {}
    failed_months: list[str] = []
    months_to_fetch = sorted({d[:7] for d in target_missing_dates})
    for month_key in months_to_fetch:
        year, month = map(int, month_key.split("-"))
        key = month_key
        try:
            records = parse_month_official(year, month)
            if records is None:
                failed_months.append(key)
            else:
                for record in records:
                    draw_date = record.get("date", "")
                    if draw_date in target_missing_dates:
                        official_by_date[draw_date] = record
        except Exception as exc:
            print(f"[ERROR] {key}: {exc}")
            failed_months.append(key)
        time.sleep(DELAY_SECONDS)

    # Work on a copy. Do not write anything if any target date is unresolved.
    updated = df.copy()
    recovered_dates = []
    unresolved = []
    for draw_date in sorted(target_missing_dates):
        record = official_by_date.get(draw_date)
        values = [(record or {}).get(f"consol_{i}", "") for i in range(1, 11)]
        if len(values) != 10 or any(not str(v).isdigit() or len(str(v)) != 4 for v in values):
            unresolved.append(draw_date)
            continue

        row_indices = updated.index[updated["date"] == draw_date].tolist()
        if len(row_indices) != 1:
            unresolved.append(draw_date)
            continue

        row_index = row_indices[0]
        for field, value in zip(CONSOL_FIELDS, values):
            if updated.at[row_index, field] == "":
                updated.at[row_index, field] = str(value)
            elif updated.at[row_index, field] != str(value):
                # Existing values are immutable in this backfill.
                unresolved.append(draw_date)
                break
        else:
            recovered_dates.append(draw_date)

    if failed_months or unresolved or len(recovered_dates) != len(target_missing_dates):
        print("BACKFILL NOT WRITTEN: official retrieval was incomplete.")
        print(f"Failed months ({len(failed_months)}): {failed_months[:30]}")
        print(f"Unresolved dates ({len(unresolved)}): {unresolved[:30]}")
        return 2

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    updated.to_csv(OUTPUT, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"[OK] Recovered {len(recovered_dates)} dates.")
    print(f"[OK] Saved verified candidate dataset: {OUTPUT}")
    print("Original and normalized source files were not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
