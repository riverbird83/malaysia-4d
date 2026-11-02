"""Historical Grand Dragon 4D scraper for live4dresult.net.

This collector is intentionally isolated from the three Malaysian operators.
It crawls date-addressed archive pages and writes raw records only after the
main three prizes are parsed. Missing special/consolation cells stay blank.
"""
from __future__ import annotations

import argparse
import csv
import re
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://live4dresult.net/past-results/{draw_date}/"
OUTPUT = ROOT / "data" / "haolong_draws.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Malaysia4DResearch/1.0)",
    "Accept-Language": "en-US,en;q=0.9",
}
FIELDS = ["draw_seq", "date", "year", "month", "day", "prize_1", "prize_2", "prize_3"] + [
    f"special_{i}" for i in range(1, 11)
] + [f"consol_{i}" for i in range(1, 11)]
NUMBER = re.compile(r"^(?:\d{4}|----)$")


def _section_values(text: str, start: str, end_patterns: tuple[str, ...]) -> list[str]:
    match = re.search(start, text, flags=re.I)
    if not match:
        return []
    tail = text[match.end():]
    stops = [m.start() for pattern in end_patterns
             if (m := re.search(pattern, tail, flags=re.I))]
    if stops:
        tail = tail[:min(stops)]
    return [token for token in re.findall(r"(?<!\d)(?:\d{4}|----)(?!\d)", tail)]


def parse_page(html: str, expected_date: date) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    anchor = re.search(r"Grand\s*Dragon\s*4D\s*豪龙", text, flags=re.I)
    if not anchor:
        return None
    # Bound the extraction to this operator's block to avoid reading the next
    # operator's prize numbers on the same multi-operator results page.
    block = text[anchor.start():]
    next_operator = re.search(
        r"(?:Perdana Lottery 4D|Nine Lotto|Lucky HariHari|Magnum 4D|SportsToto 4D|Da Ma Cai)",
        block[20:], flags=re.I,
    )
    if next_operator:
        block = block[:20 + next_operator.start()]

    date_match = re.search(r"Date:\s*(\d{2})-(\d{2})-(\d{4})", block)
    if date_match:
        actual_date = date(int(date_match.group(3)), int(date_match.group(2)), int(date_match.group(1)))
        if actual_date != expected_date:
            return None
    else:
        actual_date = expected_date

    def main_prize(pattern: str) -> str:
        m = re.search(pattern + r"[^\d]{0,35}(\d{4})", block, flags=re.I)
        return m.group(1) if m else ""

    p1 = main_prize(r"1st Prize")
    p2 = main_prize(r"2nd Prize")
    p3 = main_prize(r"3rd Prize")
    if not all((p1, p2, p3)):
        return None

    special = _section_values(
        block, r"Special\s*特別獎",
        (r"Consolation\s*安慰獎", r"More\s+GrandDragon", r"Perdana Lottery"),
    )
    consolation = _section_values(
        block, r"Consolation\s*安慰獎",
        (r"More\s+GrandDragon", r"Perdana Lottery", r"Nine Lotto"),
    )
    special = ["" if x == "----" else x for x in special[:10]]
    consolation = ["" if x == "----" else x for x in consolation[:10]]
    special += [""] * (10 - len(special))
    consolation += [""] * (10 - len(consolation))

    row = {
        "draw_seq": "",
        "date": actual_date.isoformat(),
        "year": actual_date.year, "month": actual_date.month, "day": actual_date.day,
        "prize_1": p1, "prize_2": p2, "prize_3": p3,
    }
    row.update({f"special_{i+1}": v for i, v in enumerate(special)})
    row.update({f"consol_{i+1}": v for i, v in enumerate(consolation)})
    return row


def collect(start: date, end: date, delay: float = 0.4, output: Path = OUTPUT) -> dict:
    if end < start:
        raise ValueError("end date must not precede start date")
    session = requests.Session()
    session.headers.update(HEADERS)
    records: dict[str, dict] = {}
    failed, not_found, conflicts = [], [], []
    current = start
    while current <= end:
        url = BASE.format(draw_date=current.isoformat())
        try:
            response = session.get(url, timeout=20)
            if response.status_code == 404:
                not_found.append(current.isoformat())
            elif response.status_code != 200:
                failed.append({"date": current.isoformat(), "status": response.status_code})
            else:
                row = parse_page(response.text, current)
                if row is None:
                    not_found.append(current.isoformat())
                else:
                    key = row["date"]
                    if key in records and records[key] != row:
                        conflicts.append(key)
                    records[key] = row
        except requests.RequestException as exc:
            failed.append({"date": current.isoformat(), "error": str(exc)})
        current += timedelta(days=1)
        time.sleep(max(0.0, delay))

    output.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if output.exists():
        with output.open(newline="", encoding="utf-8-sig") as f:
            existing = {r["date"]: r for r in csv.DictReader(f)}
    for key, row in records.items():
        if key in existing and existing[key] != {k: str(v) for k, v in row.items()}:
            conflicts.append(key)
            continue
        existing[key] = {k: str(v) for k, v in row.items()}
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for key in sorted(existing):
            writer.writerow(existing[key])

    return {
        "requested_days": (end - start).days + 1,
        "records_found_this_run": len(records),
        "total_unique_records": len(existing),
        "not_found_or_non_draw_days": len(not_found),
        "fetch_failures": failed,
        "conflicting_dates": sorted(set(conflicts)),
        "output": str(output),
    }


def main():
    parser = argparse.ArgumentParser(description="Collect Grand Dragon 4D history")
    parser.add_argument("--from", dest="start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = collect(date.fromisoformat(args.start), date.fromisoformat(args.end),
                     args.delay, args.output)
    import json
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
