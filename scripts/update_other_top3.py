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


def grand_dragon_archive_url(day):
    return f"https://4dresultsnow.com/history/grand-dragon/{day:%Y/%m/%d}"


def parse_grand_dragon(day, html):
    url = grand_dragon_archive_url(day)
    if f'<link rel="canonical" href="{url}"' not in html:
        raise ValueError("Backup page does not identify the requested draw")
    prizes = []
    for label in ("1st Prize", "2nd Prize", "3rd Prize"):
        pattern = rf'>{label}</span>\s*<span\b[^>]*>\s*([0-9]{{4}})\s*</span>'
        matches = re.findall(pattern, html)
        if len(matches) != 1:
            raise ValueError(f"Backup page has no unique {label}")
        prizes.append(matches[0])
    if len(set(prizes)) != 3:
        raise ValueError("Backup page has duplicate main prizes")
    return prizes


def parse_malaya_grand_dragon(day, html):
    prizes = []
    for script in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        for item in json.loads(script).get("@graph", []):
            if item.get("@type") != "Dataset" or item.get("temporalCoverage") != day.isoformat():
                continue
            prizes.extend(
                value["value"].split(" / ")
                for value in item.get("variableMeasured", [])
                if value.get("name") == "Grand Dragon 4D 1st/2nd/3rd prize"
            )
    if (len(prizes) != 1 or len(prizes[0]) != 3 or len(set(prizes[0])) != 3
            or not all(re.fullmatch(r"[0-9]{4}", prize) for prize in prizes[0])):
        raise ValueError("No unique, valid Grand Dragon result for the requested date")
    return prizes[0]


def fetch_grand_dragon(day):
    sources = (
        (grand_dragon_archive_url(day), parse_grand_dragon),
        (f"https://4dmalaya.com/en/results/{day}", parse_malaya_grand_dragon),
    )
    for url, parse in sources:
        try:
            with urlopen(url, timeout=12) as response:
                return parse(day, response.read().decode("utf-8")), url
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            print(f"Grand Dragon backup unavailable at {url}: {error}")
    raise ValueError("No backup source provided a valid result")


def refresh(now, get=fetch, get_grand_dragon=fetch_grand_dragon):
    local = now.astimezone(timezone(timedelta(hours=8)))
    last = local.date() - timedelta(days=local.hour < 20)
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
            print(f"Primary source unavailable for {day}: {error}")
            results = []
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
            known[slug].add(day)
            added[slug].append((day.isoformat(), *prizes, f"{SOURCE}/en/results/{day}",
                                f"{SOURCE}/api/v1/results/{day}", "third_party_4dlivetoday_cc_by_4_0",
                                now.isoformat(timespec="seconds")))

        if day not in known["haolong"]:
            try:
                prizes, url = get_grand_dragon(day)
            except (OSError, ValueError) as error:
                print(f"Grand Dragon backup unavailable for {day}: {error}")
            else:
                added["haolong"].append((day.isoformat(), *prizes, url, url,
                                          "single_source_pending_review",
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
