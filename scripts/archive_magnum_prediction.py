"""Record today's Magnum prediction before noon Malaysia time."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from prediction_engine import rank_numbers, read_draws

ARCHIVE = Path(__file__).resolve().parents[1] / "data/magnum-live.json"
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
    records = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    run_id = int(os.environ["GITHUB_RUN_ID"])
    if archive_prediction(records, read_draws("magnum"), datetime.now(timezone.utc), run_id):
        ARCHIVE.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        print("Archived today's Top 3 before the Malaysia noon cutoff.")
    else:
        print("No new pre-draw snapshot.")
