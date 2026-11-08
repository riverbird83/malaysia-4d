"""Record today's operator predictions before noon Malaysia time."""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from model_experiment import OPERATORS as EXPERIMENT_OPERATORS, evaluate_live, predict_experiment
from prediction_engine import rank_numbers, read_draws

ARCHIVE_DIR = Path(__file__).resolve().parents[1] / "data"
OPERATORS = ("magnum", "haolong", "damacai", "sportstoto")


def archive_path(operator):
    return ARCHIVE_DIR / f"{operator}-live.json"


def read_archive(operator):
    path = archive_path(operator)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
MYT = timezone(timedelta(hours=8))


def archive_prediction(records, rows, now, run_id, *, operator=None):
    local = now.astimezone(MYT)
    today = local.date()
    if local.hour >= 12 or today.isoformat() in records:
        return False
    if not rows or rows[-1]["date"] >= today:
        return False

    entry = {
        "recorded_at": local.isoformat(timespec="seconds"),
        "data_through": rows[-1]["date"].isoformat(),
        "top3": [item["number"] for item in rank_numbers(rows, as_of=today)],
        "run_id": run_id,
    }
    if operator in EXPERIMENT_OPERATORS:
        entry["experiment"] = predict_experiment(rows, today)
    records[today.isoformat()] = entry
    return True


def live_summary():
    gate_labels = {
        "collecting": "Collecting",
        "continue_validation": "Continue validation",
        "did_not_pass": "Did not pass",
    }
    print("### Eight-model live comparison")
    print()
    print("| Operator | Settled draws | Baseline exact | Ensemble exact | Baseline reordered | Ensemble reordered | Status |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for operator, name in (("magnum", "Magnum"), ("haolong", "Grand Dragon")):
        report = evaluate_live(read_draws(operator), read_archive(operator))
        baseline = report["hits"].get("baseline", {})
        ensemble = report["hits"].get("ensemble", {})
        print(
            f"| {name} | {report['draws']}/10 | "
            f"{baseline.get('exact', '—')} | {ensemble.get('exact', '—')} | "
            f"{baseline.get('reordered', '—')} | {ensemble.get('reordered', '—')} | "
            f"{gate_labels[report['gate']]} |"
        )


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
            print(f"{operator}: archived today's Top 3 before the Malaysia noon cutoff.")
        else:
            print(f"{operator}: no new pre-draw snapshot.")


if __name__ == "__main__":
    main()
