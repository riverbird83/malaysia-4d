"""Append complete, verified Magnum draws to the beta's two CSVs."""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper_magnum import BASE_URL, HEADERS, parse_draw

RAW = ROOT / "data/magnum_draws.csv"
NORMALIZED = ROOT / "data/normalized/magnum_draws.csv"
SOURCES = ROOT / "data/source_snapshots/magnum_updates.csv"
MYT = timezone(timedelta(hours=8))


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = {row["date"]: row for row in reader}
        if not rows or reader.fieldnames is None:
            raise ValueError(f"Empty draw CSV: {path}")
        return reader.fieldnames, rows


def append_rows(path, fields, rows):
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        if handle.tell() == 0:
            writer.writeheader()
        writer.writerows(rows)


def update(through):
    fields, normalized = read_csv(NORMALIZED)
    raw_fields, raw = read_csv(RAW)
    if raw_fields != fields or raw.keys() != normalized.keys():
        raise ValueError("Raw and normalized Magnum history are out of sync")

    latest = max(normalized)
    if latest > through.isoformat():
        raise ValueError(f"Requested end date precedes repository coverage ({latest})")

    # The endpoint may treat its date bound as exclusive.
    url = f"{BASE_URL}/null/{through + timedelta(days=1)}/50"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    items = response.json()
    if not isinstance(items, list) or not items:
        raise ValueError("Magnum API returned no draw history")

    prize_fields = [key for key in fields if key.startswith(("prize_", "special_", "consol_"))]
    dates = {}
    for item in items:
        record = parse_draw(item)
        if record is None:
            raise ValueError("Magnum API returned a draw without a valid date")
        draw_date = date.fromisoformat(record["date"])
        if draw_date < date.fromisoformat(latest) or draw_date > through:
            continue
        numbers = [record.get(key) for key in prize_fields]
        if not record["draw_seq"] or not all(
            isinstance(number, str) and re.fullmatch(r"[0-9]{4}", number) for number in numbers
        ):
            raise ValueError(f"Incomplete Magnum draw: {draw_date}")
        previous = dates.setdefault(record["date"], record)
        if previous != record:
            raise ValueError(f"Conflicting Magnum API records: {draw_date}")

    if latest not in dates or any(
        dates[latest][key] != normalized[latest][key] for key in prize_fields
    ):
        raise ValueError(f"Magnum API does not match the last stored draw ({latest})")

    new_rows = [dates[key] for key in sorted(dates) if key > latest]
    if new_rows:
        append_rows(RAW, fields, new_rows)
        append_rows(NORMALIZED, fields, new_rows)
        collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        append_rows(
            SOURCES,
            ("date", "source_url", "collected_at_utc", "source_status"),
            (dict(date=row["date"], source_url=url, collected_at_utc=collected_at,
                  source_status="official_api") for row in new_rows),
        )
    print(f"Magnum: +{len(new_rows)} complete draw(s); latest {max(dates)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", type=date.fromisoformat, default=datetime.now(MYT).date())
    update(parser.parse_args().through)
