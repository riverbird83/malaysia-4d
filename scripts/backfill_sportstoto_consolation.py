#!/usr/bin/env python3
"""Recover missing Sport Toto Consolation results for 2006-01-01..2011-06-10.

Reads the normalized source, never overwrites populated Consolation cells, and
writes a candidate CSV only when every targeted row is complete. Sources:
1) Sport Toto monthly official archive
2) check4d exact-date fallback
3) 4D2U exact draw-id archive (draw sequence from the source CSV)
"""
from __future__ import annotations

import csv
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper_sportstoto import parse_month_official, parse_date_check4d

SOURCE = ROOT / "data/normalized/sportstoto_draws.csv"
OUTPUT = ROOT / "data/backfill/sportstoto_draws_backfilled.csv"
START_DATE = "2006-01-01"
END_DATE = "2011-06-10"
CONSOL_FIELDS = [f"consol_{i}" for i in range(1, 11)]
DELAY = 0.35
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
session = requests.Session()
session.headers.update(HEADERS)


def complete_consol(record: dict | None) -> bool:
    return bool(record) and all(
        re.fullmatch(r"\d{4}", str(record.get(field, ""))) for field in CONSOL_FIELDS
    )


def parse_4d2u(draw_seq: int, year: int, expected_date: str) -> dict | None:
    """Fetch one 4D2U result by Sports Toto draw ID and validate date + draw ID."""
    draw_id = f"{int(draw_seq)}/{int(year) % 100:02d}"
    url = (
        "https://www.4d2u.com/result.php?drawid="
        + quote(draw_id, safe="")
        + "&lang=E&s=&source=T"
    )
    try:
        response = session.get(url, timeout=20)
        if response.status_code != 200 or len(response.text) < 1500:
            return None
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    if not re.search(r"Sports\s*Toto\s*4D|SportsToto\s*4D", page_text, re.I):
        return None

    id_match = re.search(r"DrawID\s*:?\s*(\d+\s*/\s*\d{2})", page_text, re.I)
    if not id_match or re.sub(r"\s+", "", id_match.group(1)) != draw_id:
        return None

    date_match = re.search(r"Date\s*:?\s*(\d{1,2})/(\d{1,2})/(\d{4})", page_text, re.I)
    if not date_match:
        return None
    actual_date = (
        f"{int(date_match.group(3)):04d}-{int(date_match.group(2)):02d}-{int(date_match.group(1)):02d}"
    )
    if actual_date != expected_date:
        return None

    section = re.search(
        r"Consolation\s+Prize(.*?)(?:Image\s*:?\s*Toto|Toto\s+6/\d+|Jackpot|Permutation)",
        page_text,
        re.I | re.S,
    )
    if not section:
        return None
    values = re.findall(r"(?<!\d)\d{4}(?!\d)", section.group(1))
    if len(values) != 10:
        return None

    record = {
        "draw_seq": int(draw_seq),
        "date": expected_date,
        "year": int(year),
        "month": int(expected_date[5:7]),
        "day": int(expected_date[8:10]),
    }
    for index, value in enumerate(values, 1):
        record[f"consol_{index}"] = value
    return record


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source dataset: {SOURCE}")

    df = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)
    required = {"date", "draw_seq", "year", *CONSOL_FIELDS}
    missing_columns = required - set(df.columns)
    if missing_columns:
        raise SystemExit(f"Missing columns: {sorted(missing_columns)}")

    target_mask = df["date"].between(START_DATE, END_DATE)
    missing_mask = target_mask & df[CONSOL_FIELDS].eq("").any(axis=1)
    targets = df.loc[missing_mask, ["date", "draw_seq", "year"]].copy()
    targets = targets.drop_duplicates(subset=["date"]).sort_values("date")
    target_dates = set(targets["date"])
    print(f"Target rows with missing Consolation: {len(target_dates)}")
    print("Missing rows by year:", dict(sorted(Counter(d[:4] for d in target_dates).items())))

    recovered: dict[str, tuple[dict, str]] = {}

    # Pass 1: official monthly archive.
    for month_key in sorted({d[:7] for d in target_dates}):
        year, month = map(int, month_key.split("-"))
        try:
            records = parse_month_official(year, month) or []
        except Exception as exc:
            print(f"[WARN] Official archive {month_key}: {exc}")
            records = []
        for record in records:
            draw_date = record.get("date", "")
            if draw_date in target_dates and complete_consol(record):
                recovered[draw_date] = (record, "official")
        time.sleep(DELAY)

    print(f"[PASS 1] Official archive recovered {len(recovered)}/{len(target_dates)} dates.")

    # Pass 2: exact-date Check4D, only for still-missing dates.
    for row in targets.itertuples(index=False):
        draw_date = row.date
        if draw_date in recovered:
            continue
        try:
            record = parse_date_check4d(draw_date)
        except Exception as exc:
            print(f"[WARN] Check4D {draw_date}: {exc}")
            record = None
        if complete_consol(record) and record.get("date") == draw_date:
            recovered[draw_date] = (record, "check4d")
        time.sleep(DELAY)

    print(f"[PASS 2] Check4D cumulative recovery: {len(recovered)}/{len(target_dates)} dates.")

    # Pass 3: 4D2U archive, using each row's exact draw sequence.
    for row in targets.itertuples(index=False):
        if row.date in recovered:
            continue
        try:
            record = parse_4d2u(int(row.draw_seq), int(row.year), row.date)
        except Exception as exc:
            print(f"[WARN] 4D2U {row.date} draw {row.draw_seq}: {exc}")
            record = None
        if complete_consol(record):
            recovered[row.date] = (record, "4d2u")
        time.sleep(DELAY)

    print(f"[PASS 3] 4D2U cumulative recovery: {len(recovered)}/{len(target_dates)} dates.")

    updated = df.copy()
    unresolved = []
    source_counts = Counter()
    for row in targets.itertuples(index=False):
        draw_date = row.date
        found = recovered.get(draw_date)
        if not found:
            unresolved.append(draw_date)
            continue

        record, source_name = found
        row_indices = updated.index[updated["date"] == draw_date].tolist()
        if len(row_indices) != 1:
            unresolved.append(draw_date)
            continue
        row_index = row_indices[0]

        conflict = False
        for field in CONSOL_FIELDS:
            value = str(record.get(field, ""))
            if not re.fullmatch(r"\d{4}", value):
                conflict = True
                break
            existing = updated.at[row_index, field]
            if existing and existing != value:
                conflict = True
                break
        if conflict:
            unresolved.append(draw_date)
            print(f"[CONFLICT] Existing values differ; left unchanged: {draw_date}")
            continue

        for field in CONSOL_FIELDS:
            if not updated.at[row_index, field]:
                updated.at[row_index, field] = str(record[field])
        source_counts[source_name] += 1

    if unresolved:
        print("BACKFILL NOT WRITTEN: unresolved or conflicting dates remain.")
        print(f"Unresolved total: {len(unresolved)}")
        print("Unresolved dates (complete list):")
        for draw_date in unresolved:
            print(f"  {draw_date}")
        return 2

    # Final integrity check: all target rows must contain ten four-digit values.
    final_missing = updated.loc[target_mask, CONSOL_FIELDS].eq("").any(axis=1)
    if final_missing.any():
        print(f"BACKFILL NOT WRITTEN: final integrity check found {int(final_missing.sum())} incomplete rows.")
        return 3

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    updated.to_csv(OUTPUT, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"[OK] Candidate saved: {OUTPUT}")
    print(f"[OK] Recovered dates: {len(target_dates)}")
    print(f"[OK] Source breakdown: {dict(source_counts)}")
    print("[OK] Original normalized source was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
