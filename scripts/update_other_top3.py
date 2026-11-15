"""Refresh recent 4D results and independently retry incomplete prize boards."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import re
from urllib.request import urlopen

from prediction_engine import DATASETS, ROOT, TOP3_SUPPLEMENTS, read_draws

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


def parse_grand_dragon_board(day, html):
    prizes = parse_grand_dragon(day, html)
    groups = []
    for label in ("Special", "Consolation"):
        blocks = re.findall(rf'>{label} \(10\)</p>\s*<ul\b[^>]*>(.*?)</ul>', html, re.S)
        if len(blocks) != 1:
            return prizes, [], []
        numbers = re.findall(r'<li\b[^>]*>\s*([0-9]{4})\s*</li>', blocks[0])
        groups.append(numbers)
    return prizes, *groups


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
    for url, parse in (
        (grand_dragon_archive_url(day), parse_grand_dragon_board),
        (f"https://4dmalaya.com/en/results/{day}", parse_malaya_grand_dragon),
    ):
        try:
            with urlopen(url, timeout=12) as response:
                html = response.read().decode("utf-8")
            if parse is parse_grand_dragon_board:
                prizes, special, consolation = parse(day, html)
                return prizes, special, consolation, url
            return parse(day, html), [], [], url
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            print(f"Grand Dragon backup unavailable at {url}: {error}")
    raise ValueError("No backup source provided a valid result")


def valid_numbers(values, size):
    return isinstance(values, list) and len(values) == size and all(
        isinstance(value, str) and re.fullmatch(r"[0-9]{4}", value) for value in values
    )


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def complete_board(row):
    for prefix in ("special_", "consol_"):
        numbers = [value for key, value in row.items() if key.startswith(prefix) and value]
        if not valid_numbers(numbers, 10):
            return False
    return True


def append_supplement(path, rows, fields=FIELDS):
    if not rows:
        return
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if handle.tell() == 0:
            writer.writerow(fields)
        writer.writerows(rows)


def write_boards(path, additions):
    if not additions:
        return
    with path.open(newline="", encoding="utf-8") as handle:
        header, *lines = handle.readlines()
    fields = next(csv.reader([header.lstrip("\ufeff")]))
    by_date = {next(csv.reader([line]))[1]: line for line in lines}
    temp = path.with_suffix(".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        handle.write(header)
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        for day in sorted(by_date.keys() | additions.keys()):
            if day in additions:
                row = dict(zip(fields, next(csv.reader([by_date[day]])))) if day in by_date else {}
                row.update(additions[day])
                writer.writerow(row)
            else:
                handle.write(by_date[day])
    temp.replace(path)


def full_board(slug, day, prizes, special, consolation, draw_no, previous, known_ids):
    if not valid_numbers(special, 10) or not valid_numbers(consolation, 10):
        return None
    if previous:
        seq = previous["draw_seq"]
    elif slug == "haolong":
        seq = draw_no or f"GD-{day:%Y%m%d}"
    else:
        match = re.fullmatch(rf"([0-9]+)/{day:%y}", draw_no)
        if not match:
            return None
        seq = match[1]
    if seq and seq in known_ids and known_ids[seq] != day.isoformat():
        return None
    board = dict(draw_seq=seq, date=day.isoformat(), year=str(day.year),
                 month=str(day.month), day=str(day.day))
    for prefix, values in (("prize", prizes), ("special", special), ("consol", consolation)):
        board.update({f"{prefix}_{i}": number for i, number in enumerate(values, 1)})
    if previous and any(
        value and board.get(key, "") != value
        for key, value in previous.items()
        if key.startswith(("prize_", "special_", "consol_"))
    ):
        return None
    return board


def refresh(now, get=fetch, get_grand_dragon=fetch_grand_dragon, *, grand_dragon_only=False):
    local = now.astimezone(timezone(timedelta(hours=8)))
    last = local.date() - timedelta(days=local.hour < 20)
    operators = {"gd": "haolong"} if grand_dragon_only else SOURCE_OPERATORS
    known = {slug: {row["date"]: row["prizes"] for row in read_draws(slug)}
             for slug in operators.values()}
    history = {slug: {row["date"]: row for row in read_csv(DATASETS[slug])[1]}
               for slug in known}
    full = {slug: {day for day, row in rows.items() if complete_board(row)}
            for slug, rows in history.items()}
    ids = {slug: {row["draw_seq"]: day for day, row in rows.items() if row["draw_seq"]}
           for slug, rows in history.items()}
    added = {slug: [] for slug in known}
    boards = {slug: {} for slug in known}
    audit = []
    first = max(last - timedelta(days=9),
                min((max(dates, default=last) for dates in known.values())) - timedelta(days=2))
    pending = {day for slug, days in known.items() for day in days
               if day.isoformat() not in full[slug] and day <= last}
    days = sorted(pending | {first + timedelta(days=i) for i in range((last - first).days + 1)})
    stamp = now.isoformat(timespec="seconds")

    def record_result(slug, day, prizes, special, consolation, draw_no, url, status):
        if not valid_numbers(prizes, 3) or len(set(prizes)) != 3:
            return
        existing = known[slug].get(day)
        if existing and existing != prizes:
            print(f"::warning::{slug} result disagrees with recorded main prizes for {day}")
            return
        if not existing:
            known[slug][day] = prizes
            added[slug].append((day.isoformat(), *prizes, url, url, status, stamp))
        key = day.isoformat()
        board = full_board(slug, day, prizes, special, consolation, draw_no,
                           history[slug].get(key), ids[slug])
        if board:
            if board["draw_seq"]:
                ids[slug][board["draw_seq"]] = key
            boards[slug][key] = board
            full[slug].add(key)
            audit.append((slug, key, url, stamp, status))

    for day in days:
        key = day.isoformat()
        if all(key in dates for dates in full.values()):
            continue
        try:
            data = get(day)["data"]
            if data["date"] != key or not isinstance(data["results"], list):
                raise ValueError("Expected a matching date and results list")
            results = data["results"]
        except (OSError, KeyError, TypeError, ValueError) as error:
            print(f"Primary source unavailable for {day}: {error}")
            results = []
        for source_id, slug in operators.items():
            if key in full[slug] or (day < first and day not in known[slug]):
                continue
            matches = [r for r in results if isinstance(r, dict) and r.get("operator") == source_id]
            if len(matches) != 1:
                continue
            record = matches[0]
            if record.get("date") != key or record.get("status") not in {"history", "checked"}:
                continue
            record_result(slug, day, [record.get(k) for k in ("first", "second", "third")],
                          record.get("special"), record.get("consolation"),
                          str(record.get("draw_no") or ""), f"{SOURCE}/api/v1/results/{day}",
                          "third_party_4dlivetoday_cc_by_4_0")
        if key not in full["haolong"] and (day in known["haolong"] or day >= first):
            try:
                prizes, special, consolation, url = get_grand_dragon(day)
            except (OSError, ValueError) as error:
                print(f"Grand Dragon backup unavailable for {day}: {error}")
            else:
                record_result("haolong", day, prizes, special, consolation, "", url,
                              "grand_dragon_third_party_archive")

    for slug, rows in added.items():
        append_supplement(TOP3_SUPPLEMENTS[slug], rows)
        for path in (DATASETS[slug], ROOT / "data" / DATASETS[slug].name):
            write_boards(path, boards[slug])
        remaining = sum(day.isoformat() not in full[slug] for day in known[slug])
        print(f"{slug}: {len(rows)} new top-three, {len(boards[slug])} full boards, {remaining} pending")
    append_supplement(ROOT / "data/audit/recent_full_prize_updates.csv", audit,
                      ("operator", "date", "source_url", "retrieved_at_utc", "status"))
    if last not in known["haolong"]:
        print(f"::warning::Grand Dragon result for {last} is still missing")
    return added


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grand-dragon-only", action="store_true")
    refresh(datetime.now(timezone.utc), grand_dragon_only=parser.parse_args().grand_dragon_only)
