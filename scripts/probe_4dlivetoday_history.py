"""Probe 4D Live Today historical date API without modifying canonical datasets."""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://4dlivetoday.com/api/v1/results"
OPERATORS = {
    "magnum": "Magnum 4D",
    "sportstoto": "Sports Toto 4D",
    "damacai": "Da Ma Cai 1+3D",
    "grand_dragon": "Grand Dragon 4D",
}
API_TO_INTERNAL = {
    "magnum": "magnum",
    "toto": "sportstoto",
    "damacai": "damacai",
    "gd": "grand_dragon",
}
DEFAULT_DATES = [
    "2006-01-01",
    "2006-01-04",
    "2016-01-01",
    "2017-01-01",
    "2019-01-21",
    "2020-03-03",
    "2020-04-11",
    "2020-07-11",
    "2020-09-09",
    "2020-11-07",
    "2020-12-13",
    "2021-01-01",
    "2021-12-31",
    "2022-04-21",
    "2026-10-30",
    "2026-11-01",
]
FIELDS = [
    "date", "operator_id", "operator_name", "api_status", "http_status",
    "draw_no", "first", "second", "third", "special_count",
    "consolation_count", "source_url", "snapshot_path", "note",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", default="",
                        help="Comma-separated ISO dates; blank probes the built-in sample plus dates in data/manual_import/*.csv")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data" / "audit" / "4dlivetoday_probe.csv")
    parser.add_argument("--snapshot-dir", type=Path,
                        default=ROOT / "data" / "source_snapshots" / "4dlivetoday")
    args = parser.parse_args()

    if args.dates.strip():
        date_values = [value.strip() for value in args.dates.split(",") if value.strip()]
    else:
        date_values = list(DEFAULT_DATES)
        candidate_dir = ROOT / "data" / "manual_import"
        candidate_files = sorted(candidate_dir.glob("*.csv"))
        for candidate_file in candidate_files:
            try:
                with candidate_file.open("r", newline="", encoding="utf-8-sig") as handle:
                    for candidate in csv.DictReader(handle):
                        value = (candidate.get("draw_date") or candidate.get("date") or "").strip()
                        if value:
                            date_values.append(value)
            except (OSError, csv.Error) as exc:
                print(f"Skipping unreadable candidate file {candidate_file}: {exc}")

    valid_dates = set()
    invalid_dates = []
    for value in date_values:
        try:
            valid_dates.add(date.fromisoformat(value).isoformat())
        except ValueError:
            invalid_dates.append(value)
    dates = sorted(valid_dates)
    if invalid_dates:
        print(f"Skipped {len(invalid_dates)} invalid candidate date values: {invalid_dates[:10]}")
    print(f"Probing {len(dates)} unique dates (built-in sample plus manual-import candidates).")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "malaysia-4d-historical-audit/1.0 (+https://github.com/riverbird83/malaysia-4d)"
    })
    rows: list[dict] = []
    request_failures = 0

    for index, draw_date in enumerate(dates):
        snapshot = args.snapshot_dir / f"{draw_date}.json"
        row_by_operator: dict[str, dict] = {}
        try:
            response = session.get(f"{BASE_URL}/{draw_date}", timeout=30)
            http_status = response.status_code
            response.raise_for_status()
            payload = response.json()
            snapshot.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            results = payload.get("data", {}).get("results", [])
            if not isinstance(results, list):
                raise ValueError("API data.results is not a list")
            for item in results:
                api_operator_id = item.get("operator", "")
                operator_id = API_TO_INTERNAL.get(api_operator_id)
                if operator_id:
                    row_by_operator[operator_id] = item
            for operator_id, operator_name in OPERATORS.items():
                item = row_by_operator.get(operator_id)
                if item:
                    special = item.get("special") or []
                    consolation = item.get("consolation") or []
                    rows.append({
                        "date": draw_date,
                        "operator_id": operator_id,
                        "operator_name": item.get("operator_name", operator_name),
                        "api_status": item.get("status", "unknown"),
                        "http_status": http_status,
                        "draw_no": item.get("draw_no", ""),
                        "first": item.get("first", ""),
                        "second": item.get("second", ""),
                        "third": item.get("third", ""),
                        "special_count": sum(str(x).isdigit() and len(str(x)) == 4 for x in special),
                        "consolation_count": sum(str(x).isdigit() and len(str(x)) == 4 for x in consolation),
                        "source_url": item.get("url", ""),
                        "snapshot_path": str(snapshot.relative_to(ROOT)),
                        "note": "",
                    })
                else:
                    rows.append({
                        "date": draw_date,
                        "operator_id": operator_id,
                        "operator_name": operator_name,
                        "api_status": "no_record_in_api",
                        "http_status": http_status,
                        "draw_no": "",
                        "first": "",
                        "second": "",
                        "third": "",
                        "special_count": 0,
                        "consolation_count": 0,
                        "source_url": "",
                        "snapshot_path": str(snapshot.relative_to(ROOT)),
                        "note": "No row returned by this API for this operator/date; this is not proof of a non-draw day.",
                    })
            print(f"{draw_date}: HTTP {http_status}, {len(row_by_operator)} supported operator rows")
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            request_failures += 1
            for operator_id, operator_name in OPERATORS.items():
                rows.append({
                    "date": draw_date,
                    "operator_id": operator_id,
                    "operator_name": operator_name,
                    "api_status": "fetch_or_parse_failed",
                    "http_status": locals().get("http_status", ""),
                    "draw_no": "",
                    "first": "",
                    "second": "",
                    "third": "",
                    "special_count": 0,
                    "consolation_count": 0,
                    "source_url": "",
                    "snapshot_path": "",
                    "note": str(exc),
                })
            print(f"{draw_date}: ERROR {exc}")
        if index + 1 < len(dates):
            time.sleep(max(0.0, args.delay))

    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} operator/date audit rows to {args.output}")
    print(f"Saved {len(list(args.snapshot_dir.glob('*.json')))} JSON snapshots to {args.snapshot_dir}")
    if request_failures == len(dates):
        raise SystemExit("All historical API probes failed; see audit notes.")


if __name__ == "__main__":
    main()
