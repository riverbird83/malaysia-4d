"""Record today's operator predictions before noon Malaysia time."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from prediction_engine import rank_numbers, read_draws

ARCHIVE_DIR = Path(__file__).resolve().parents[1] / "data"
OPERATORS = ("magnum", "haolong", "damacai", "sportstoto")


def archive_path(operator):
    return ARCHIVE_DIR / f"{operator}-live.json"


def read_archive(operator):
    path = archive_path(operator)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
MYT = timezone(timedelta(hours=8))


def archive_prediction(records, rows, now, run_id):
    local = now.astimezone(MYT)
    today = local.date()
    if local.hour >= 12 or today.isoformat() in records:
        return False
    if not rows or rows[-1]["date"] >= today:
        return False

    records[today.isoformat()] = {
        "recorded_at": local.isoformat(timespec="seconds"),
        "data_through": rows[-1]["date"].isoformat(),
        "top3": [item["number"] for item in rank_numbers(rows, as_of=today)],
        "run_id": run_id,
    }
    return True


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    run_id = int(os.environ["GITHUB_RUN_ID"])
    for operator in OPERATORS:
        records = read_archive(operator)
        if archive_prediction(records, read_draws(operator), now, run_id):
            archive_path(operator).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
            print(f"{operator}: archived today's Top 3 before the Malaysia noon cutoff.")
        else:
            print(f"{operator}: no new pre-draw snapshot.")
