#!/usr/bin/env python3
"""Fetch and audit candidate Grand Dragon archive pages without merging their data.

This is a discovery/availability stage, not a draw-result importer. It records
HTTP status, final URL, retrieval time, body hash and page title so source
adapters can be built against reproducible snapshots.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "grand_dragon_sources.json"
OUT = ROOT / "data" / "audit" / "grand_dragon_source_health.csv"
SNAPSHOTS = ROOT / "data" / "source_snapshots" / "grand_dragon"


def safe_name(source_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", source_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--snapshot-dir", type=Path, default=SNAPSHOTS)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; Malaysia4DResearch/1.0; +https://github.com/riverbird83/malaysia-4d)"
    })
    rows = []
    args.snapshot_dir.mkdir(parents=True, exist_ok=True)

    for source in manifest["sources"]:
        started = datetime.now(timezone.utc).isoformat()
        row = {
            "source_id": source["id"],
            "source_url": source["url"],
            "source_role": source["role"],
            "lineage": source.get("lineage", "unknown"),
            "checked_at_utc": started,
            "http_status": "",
            "final_url": "",
            "page_title": "",
            "content_sha256": "",
            "body_bytes": 0,
            "snapshot_file": "",
            "error": "",
        }
        try:
            response = session.get(source["url"], timeout=args.timeout)
            row["http_status"] = response.status_code
            row["final_url"] = response.url
            body = response.content
            row["body_bytes"] = len(body)
            row["content_sha256"] = hashlib.sha256(body).hexdigest()
            soup = BeautifulSoup(body, "html.parser")
            row["page_title"] = soup.title.get_text(" ", strip=True) if soup.title else ""
            if response.ok and body:
                snapshot = args.snapshot_dir / f'{safe_name(source["id"])}.html'
                snapshot.write_bytes(body)
                row["snapshot_file"] = str(snapshot.relative_to(ROOT))
            else:
                row["error"] = f"HTTP {response.status_code}"
        except requests.RequestException as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
        print(f'{source["id"]}: HTTP {row["http_status"] or "ERROR"}; {row["body_bytes"]} bytes; {row["page_title"]}')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    failures = sum(1 for row in rows if not row["http_status"] or int(row["http_status"]) >= 400)
    print(f"Wrote {OUT.relative_to(ROOT)}; {len(rows)} sources checked; {failures} unavailable.")
    # Source outages (403, timeouts, missing archives) are audit findings, not a\n    # pipeline failure. Keep the workflow green so snapshots and health rows are\n    # committed; parser/programming errors still fail naturally before this point.\n    return 0


if __name__ == "__main__":
    sys.exit(main())
