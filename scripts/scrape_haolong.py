"""Auditable Grand Dragon 4D history collector for live4dresult.net.

The collector is isolated from Magnum, Sports Toto, and Da Ma Cai. It stores
one date per row, preserves four-digit strings, and writes a date-level audit
manifest. A missing page is never automatically classified as a non-draw day.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://live4dresult.net/past-results/{draw_date}/"
OUTPUT = ROOT / "data" / "haolong_draws.csv"
AUDIT = ROOT / "data" / "audit" / "haolong_coverage.csv"
PARSER_VERSION = "haolong-live4dresult-v2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Malaysia4DResearch/1.1)",
    "Accept-Language": "en-US,en;q=0.9",
}
SPECIAL_SLOTS = 15
CONSOLATION_SLOTS = 10
FIELDS = (
    ["draw_seq", "date", "year", "month", "day", "prize_1", "prize_2", "prize_3"]
    + [f"special_{i}" for i in range(1, SPECIAL_SLOTS + 1)]
    + [f"consol_{i}" for i in range(1, CONSOLATION_SLOTS + 1)]
)
AUDIT_FIELDS = [
    "date", "status", "http_status", "source_url", "fetched_at_utc",
    "content_sha256", "parser_version", "special_slots_observed",
    "special_numbers_found", "consolation_slots_observed",
    "consolation_numbers_found", "note",
]


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=5, connect=5, read=5, status=5, backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _tokenize_cell(value: str) -> list[str]:
    value = (value or "").replace("\xa0", " ").strip()
    if "|" in value:
        raw_tokens = value.split("|")
    else:
        raw_tokens = value.split()
    result = []
    for token in raw_tokens:
        token = token.strip()
        if not token:
            result.append("")
        elif token == "----":
            result.append("")
        elif re.fullmatch(r"\d{4}", token):
            result.append(token)
        else:
            # Ignore labels and non-number text; do not extract digits from it.
            continue
    return result


def _section_slots(soup: BeautifulSoup, start_label: str, stop_label: str,
                   expected_slots: int) -> tuple[list[str], int]:
    """Extract result-table cells while preserving explicit empty table cells."""
    rows = soup.find_all("tr")
    start_index = next(
        (i for i, row in enumerate(rows)
         if re.search(start_label, row.get_text(" ", strip=True), flags=re.I)),
        None,
    )
    values: list[str] = []
    if start_index is not None:
        for row in rows[start_index + 1:]:
            row_text = row.get_text(" ", strip=True)
            if re.search(stop_label, row_text, flags=re.I):
                break
            cells = row.find_all(["td", "th"])
            row_values: list[str] = []
            for cell in cells:
                row_values.extend(_tokenize_cell(cell.get_text(" ", strip=True)))
            # Skip layout/ad rows that contain no result token at all.
            if any(v == "" or re.fullmatch(r"\d{4}", v) for v in row_values) and row_values:
                values.extend(row_values)
    else:
        # Text fallback for markup that does not use table rows. Pipe-delimited
        # lines preserve empty first/last cells, unlike get_text(strip=True).
        lines = soup.get_text("\n", strip=False).splitlines()
        active = False
        for line in lines:
            if re.search(start_label, line, flags=re.I):
                active = True
                continue
            if active and re.search(stop_label, line, flags=re.I):
                break
            if active and "|" in line:
                values.extend(_tokenize_cell(line))
    observed = min(len(values), expected_slots)
    values = values[:expected_slots]
    values += [""] * (expected_slots - len(values))
    return values, observed


def _parse_page(html: str, expected_date: date) -> tuple[dict | None, dict]:
    soup = BeautifulSoup(html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    anchor = re.search(r"Grand\s*Dragon\s*4D\s*豪龙", text, flags=re.I)
    if not anchor:
        return None, {}
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
            return None, {"reason": "page_date_mismatch"}
    else:
        return None, {"reason": "date_label_missing"}

    def main_prize(pattern: str) -> str:
        match = re.search(pattern + r"[^\d]{0,35}(\d{4})", block, flags=re.I)
        return match.group(1) if match else ""

    p1 = main_prize(r"1st Prize")
    p2 = main_prize(r"2nd Prize")
    p3 = main_prize(r"3rd Prize")
    if not all((p1, p2, p3)):
        return None, {"reason": "main_prize_incomplete"}

    special, special_observed = _section_slots(
        soup, r"Special\s*特別獎", r"Consolation\s*安慰獎", SPECIAL_SLOTS
    )
    consolation, consolation_observed = _section_slots(
        soup, r"Consolation\s*安慰獎",
        r"(?:More\s+GrandDragon|Perdana Lottery|Nine Lotto|Lucky HariHari)",
        CONSOLATION_SLOTS,
    )
    row = {
        "draw_seq": "",
        "date": actual_date.isoformat(),
        "year": actual_date.year,
        "month": actual_date.month,
        "day": actual_date.day,
        "prize_1": p1,
        "prize_2": p2,
        "prize_3": p3,
    }
    row.update({f"special_{i+1}": value for i, value in enumerate(special)})
    row.update({f"consol_{i+1}": value for i, value in enumerate(consolation)})
    meta = {
        "special_slots_observed": special_observed,
        "special_numbers_found": sum(bool(v) for v in special[:special_observed]),
        "consolation_slots_observed": consolation_observed,
        "consolation_numbers_found": sum(bool(v) for v in consolation[:consolation_observed]),
    }
    return row, meta


def parse_page(html: str, expected_date: date) -> dict | None:
    """Public parser used by tests; returns only the normalized raw draw row."""
    row, _ = _parse_page(html, expected_date)
    return row


def _write_csv(path: Path, fields: list[str], rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow({field: rows[key].get(field, "") for field in fields})


def _load_rows(path: Path) -> tuple[dict[str, dict], list[str]]:
    rows: dict[str, dict] = {}
    duplicates: list[str] = []
    if not path.exists():
        return rows, duplicates
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = row.get("date", "")
            if key in rows:
                duplicates.append(key)
                continue
            rows[key] = {field: row.get(field, "") for field in FIELDS}
    return rows, duplicates


def _load_audit(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {row["date"]: row for row in csv.DictReader(handle) if row.get("date")}


def collect(start: date, end: date, delay: float = 0.6, output: Path = OUTPUT,
            audit_path: Path = AUDIT, resume: bool = False,
            checkpoint_every: int = 100) -> dict:
    if end < start:
        raise ValueError("end date must not precede start date")
    session = make_session()
    records, duplicate_rows = _load_rows(output)
    audit = _load_audit(audit_path)
    conflicts: list[str] = []
    processed = 0
    skipped = 0
    current = start

    def checkpoint() -> None:
        _write_csv(output, FIELDS, records)
        _write_csv(audit_path, AUDIT_FIELDS, audit)

    while current <= end:
        key = current.isoformat()
        if resume and key in records and audit.get(key, {}).get("status") == "parsed":
            skipped += 1
            current += timedelta(days=1)
            continue

        url = BASE.format(draw_date=key)
        fetched_at = datetime.now(timezone.utc).isoformat()
        entry = {
            "date": key, "status": "", "http_status": "", "source_url": url,
            "fetched_at_utc": fetched_at, "content_sha256": "",
            "parser_version": PARSER_VERSION, "special_slots_observed": "",
            "special_numbers_found": "", "consolation_slots_observed": "",
            "consolation_numbers_found": "", "note": "",
        }
        try:
            response = session.get(url, timeout=(10, 30))
            entry["http_status"] = str(response.status_code)
            entry["content_sha256"] = hashlib.sha256(response.content).hexdigest()
            if response.status_code == 404:
                entry["status"] = "page_not_found"
                entry["note"] = "Not classified as a non-draw day; requires cross-source verification."
            elif response.status_code != 200:
                entry["status"] = "fetch_failed"
                entry["note"] = f"HTTP {response.status_code}"
            else:
                soup = BeautifulSoup(response.text, "html.parser")
                visible = soup.get_text(" ", strip=True)
                if not re.search(r"Grand\s*Dragon\s*4D\s*豪龙", visible, flags=re.I):
                    entry["status"] = "operator_not_found"
                    entry["note"] = "Page loaded but Grand Dragon heading was not found."
                else:
                    row, meta = _parse_page(response.text, current)
                    if row is None:
                        entry["status"] = "parse_incomplete"
                        entry["note"] = meta.get("reason", "Unknown parser failure")
                    else:
                        entry["status"] = "parsed"
                        for field, value in meta.items():
                            entry[field] = str(value)
                        previous = records.get(key)
                        if previous and previous != {field: str(row.get(field, "")) for field in FIELDS}:
                            entry["status"] = "conflict"
                            entry["note"] = "New source row differs from the existing stored row; existing row retained."
                            conflicts.append(key)
                        else:
                            records[key] = {field: str(row.get(field, "")) for field in FIELDS}
        except requests.RequestException as exc:
            entry["status"] = "fetch_failed"
            entry["note"] = str(exc)[:500]

        audit[key] = entry
        processed += 1
        if processed % max(1, checkpoint_every) == 0:
            checkpoint()
        current += timedelta(days=1)
        time.sleep(max(0.0, delay))

    checkpoint()
    statuses = Counter(row.get("status", "") for row in audit.values()
                       if start.isoformat() <= row.get("date", "") <= end.isoformat())
    valid_dates = sorted(key for key, row in records.items()
                         if start.isoformat() <= key <= end.isoformat())
    main_complete = sum(
        all(re.fullmatch(r"\d{4}", records[key].get(f"prize_{i}", "")) for i in range(1, 4))
        for key in valid_dates
    )
    special_observed = sum(int(audit.get(key, {}).get("special_slots_observed") or 0) for key in valid_dates)
    special_numbers = sum(int(audit.get(key, {}).get("special_numbers_found") or 0) for key in valid_dates)
    consolation_observed = sum(int(audit.get(key, {}).get("consolation_slots_observed") or 0) for key in valid_dates)
    consolation_numbers = sum(int(audit.get(key, {}).get("consolation_numbers_found") or 0) for key in valid_dates)
    return {
        "requested_days": (end - start).days + 1,
        "processed_this_run": processed,
        "resumed_skipped": skipped,
        "unique_records_in_range": len(valid_dates),
        "earliest_record_in_range": valid_dates[0] if valid_dates else None,
        "latest_record_in_range": valid_dates[-1] if valid_dates else None,
        "main_prize_complete_rows": main_complete,
        "special_slots_observed": special_observed,
        "special_numbers_found": special_numbers,
        "consolation_slots_observed": consolation_observed,
        "consolation_numbers_found": consolation_numbers,
        "audit_status_counts": dict(statuses),
        "duplicate_dates_in_existing_csv": sorted(set(duplicate_rows)),
        "conflicting_dates": sorted(set(conflicts)),
        "output": str(output),
        "audit": str(audit_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Grand Dragon 4D history with audit manifest")
    parser.add_argument("--from", dest="start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--audit", type=Path, default=AUDIT)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--require-records", type=int, default=0,
                        help="Exit non-zero unless at least this many records are parsed.")
    args = parser.parse_args()
    report = collect(
        date.fromisoformat(args.start), date.fromisoformat(args.end),
        args.delay, args.output, args.audit, args.resume, args.checkpoint_every,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["unique_records_in_range"] < args.require_records:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
