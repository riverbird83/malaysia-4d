"""Record today's operator predictions from noon on draw days."""
import argparse
import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from model_experiment import LEGACY_VERSION, OPERATORS, TARGET_DRAWS, evaluate_live, predict_experiment
from prediction_engine import rank_numbers, read_draws

ARCHIVE_DIR = Path(__file__).resolve().parents[1] / "data"
OPERATOR_LABELS = {"magnum": "Magnum", "haolong": "Grand Dragon",
                   "damacai": "Da Ma Cai", "sportstoto": "Sports Toto"}


def archive_path(operator):
    return ARCHIVE_DIR / f"{operator}-live.json"


def read_archive(operator):
    path = archive_path(operator)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
MYT = timezone(timedelta(hours=8))
REGULAR_DRAW_WEEKDAYS = {2, 5, 6}
# Listed for Magnum, Da Ma Cai and Sports Toto at https://4dd.co/special-draw.
SPECIAL_DRAW_DATES = {date(2026, 12, 29)}


def is_draw_day(operator, day):
    return operator == "haolong" or day.weekday() in REGULAR_DRAW_WEEKDAYS or day in SPECIAL_DRAW_DATES


def archive_prediction(records, rows, now, run_id, *, operator=None):
    local = now.astimezone(MYT)
    today = local.date()
    if not 12 <= local.hour < 16 or today.isoformat() in records:
        return False
    if not is_draw_day(operator, today):
        return False
    if not rows or rows[-1]["date"] >= today:
        return False

    ranked = rank_numbers(rows, as_of=today)
    entry = {
        "recorded_at": local.isoformat(timespec="seconds"),
        "data_through": rows[-1]["date"].isoformat(),
        "top3": [item["number"] for item in ranked],
        "top3_model_estimates": [1 - (1 - math.exp(item["score"])) ** 3 for item in ranked],
        "run_id": run_id,
    }
    if operator in OPERATORS:
        entry["experiment"] = predict_experiment(rows, today)
    records[today.isoformat()] = entry
    return True


def live_summary():
    gate_labels = {
        "collecting": "Collecting",
        "continue_validation": "Continue validation",
        "did_not_pass": "Did not pass",
    }
    print("### Twelve-model live comparison")
    print()
    print("| Operator | Settled draws | Baseline exact | Ensemble exact | Baseline reordered | Ensemble reordered | Status |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
    legacy_counts = []
    for operator in OPERATORS:
        name = OPERATOR_LABELS[operator]
        rows = read_draws(operator)
        archive = read_archive(operator)
        report = evaluate_live(rows, archive)
        legacy = evaluate_live(rows, archive, version=LEGACY_VERSION, target=10)
        legacy_counts.append(f"{name}: {legacy['draws']}")
        baseline = report["hits"].get("baseline", {})
        ensemble = report["hits"].get("ensemble", {})
        print(
            f"| {name} | {report['draws']}/{TARGET_DRAWS} | "
            f"{baseline.get('exact', '—')} | {ensemble.get('exact', '—')} | "
            f"{baseline.get('reordered', '—')} | {ensemble.get('reordered', '—')} | "
            f"{gate_labels[report['gate']]} |"
        )

    print("\nSettled eight-model records retained separately: " + ", ".join(legacy_counts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        live_summary()
        return

    now = datetime.now(timezone.utc)
    run_id = int(os.environ["GITHUB_RUN_ID"])
    for operator in OPERATORS:
        records = read_archive(operator)
        rows = read_draws(operator)
        if archive_prediction(records, rows, now, run_id, operator=operator):
            archive_path(operator).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
            print(f"{operator}: archived today's Top 3 in the Malaysia draw-day window.")
        else:
            print(f"{operator}: no new pre-draw snapshot.")


if __name__ == "__main__":
    main()
