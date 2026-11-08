"""Refresh sourced top-three results without rewriting the historical full boards."""
import csv
from datetime import datetime, timedelta, timezone
import json
import re
from urllib.request import urlopen

from prediction_engine import TOP3_SUPPLEMENTS, read_draws

SOURCE = "https://4dlivetoday.com"
SOURCE_OPERATORS = {"gd": "haolong", "damacai": "damacai", "toto": "sportstoto"}
FIELDS = ("date", "prize_1", "prize_2", "prize_3", "source_url", "archive_url",
          "source_status", "retrieved_at_utc")


def fetch(day):
    with urlopen(f"{SOURCE}/api/v1/results/{day}", timeout=12) as response:
        return json.load(response)


def refresh(now, get=fetch):
    local = now.astimezone(timezone(timedelta(hours=8)))
    last = local.date() - timedelta(days=local.hour < 21)
    known = {slug: {row["date"] for row in read_draws(slug)} for slug in TOP3_SUPPLEMENTS}
    added = {slug: [] for slug in known}
    first = max(last - timedelta(days=9), min(max(dates) for dates in known.values()) - timedelta(days=2))

    for offset in range((last - first).days + 1):
        day = first + timedelta(days=offset)
        if all(day in dates for dates in known.values()):
            continue
        try:
            data = get(day)["data"]
            if data["date"] != day.isoformat():
                raise ValueError("Response date does not match the request")
            results = data["results"]
            if not isinstance(results, list):
                raise ValueError("Expected a list of results")
        except (OSError, KeyError, TypeError, ValueError) as error:
            print(f"Skipped {day}: {error}")
            continue
        for source_id, slug in SOURCE_OPERATORS.items():
            if day in known[slug]:
                continue
            matches = [r for r in results if isinstance(r, dict) and r.get("operator") == source_id]
            if len(matches) != 1:
                continue
            record = matches[0]
            if record.get("date") != day.isoformat() or record.get("status") not in {"history", "checked"}:
                continue
            prizes = [str(record.get(key, "")) for key in ("first", "second", "third")]
            if len(set(prizes)) != 3 or not all(re.fullmatch(r"[0-9]{4}", prize) for prize in prizes):
                continue
            added[slug].append((day.isoformat(), *prizes, f"{SOURCE}/en/results/{day}",
                                f"{SOURCE}/api/v1/results/{day}", "third_party_4dlivetoday_cc_by_4_0",
                                now.isoformat(timespec="seconds")))

    for slug, rows in added.items():
        path = TOP3_SUPPLEMENTS[slug]
        if rows:
            with path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                if handle.tell() == 0:
                    writer.writerow(FIELDS)
                writer.writerows(rows)
        print(f"{slug}: added {len(rows)} draw(s)")
    return added


if __name__ == "__main__":
    refresh(datetime.now(timezone.utc))
