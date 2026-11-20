"""Record today's operator predictions from noon on draw days."""
import argparse
import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from model_experiment import DUAL_VERSION, operator_dual_summary, evaluate_website, LEGACY_VERSION, OPERATORS, TARGET_DRAWS, evaluate_live, predict_experiment
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
        prior = evaluate_live(rows, records)
        if prior["draws"] >= TARGET_DRAWS:
            entry["experiment"]["version"] = DUAL_VERSION
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
    print("| Operator | Settled draws | Website top-three hits | Experimental ensemble hits | Baseline reordered | Ensemble reordered | Status |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
    legacy_counts = []
    for operator in OPERATORS:
        name = OPERATOR_LABELS[operator]
        rows = read_draws(operator)
        archive = read_archive(operator)
        report = evaluate_live(rows, archive)
        legacy = evaluate_live(rows, archive, version=LEGACY_VERSION, target=10)
        legacy_counts.append(f"{name}: {legacy['draws']}")
        website = evaluate_website(rows, archive)
        ensemble = report["hits"].get("ensemble", {})
        print(
            f"| {name} | {report['draws']}/{TARGET_DRAWS} | "
            f"{website['hits']} | {ensemble.get('exact', '—')} | "
            f"{report['hits'].get('baseline', {}).get('reordered', '—')} | {ensemble.get('reordered', '—')} | "
            f"{gate_labels[report['gate']]} |"
        )

    print("\n### Round two: locked forecasts, full prize boards")
    print("| Operator | Settled | Pending boards | Website top-three | Website all-23 | Experimental ensemble top-three | Experimental ensemble all-23 |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for operator in OPERATORS:
        report = operator_dual_summary(operator, read_archive(operator))
        hits = report["hits"].get("ensemble", {})
        website = report["hits"].get("website", {})
        print(f"| {OPERATOR_LABELS[operator]} | {report['settled']}/{TARGET_DRAWS} | "
              f"{report['pending']} | {website.get('top3', 0)} | {website.get('all23', 0)} | "
              f"{hits.get('top3', 0)} | {hits.get('all23', 0)} |")

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
