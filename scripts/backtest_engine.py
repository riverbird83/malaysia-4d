"""Leakage-safe walk-forward backtest for exactly one 4D operator."""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

from prediction_engine import DATASETS, DISPLAY_NAMES, START_DATES, normalize_operator, rank_numbers, read_draws

ROOT = Path(__file__).resolve().parents[1]
PRIZE_FIELDS = ("prize_1", "prize_2", "prize_3")


def run_backtest(rows, *, sample_every=30, max_draws=None, random_trials=1000,
                 seed=20261102, ranker=rank_numbers):
    """Evaluate chronological predictions without mixing operator histories."""
    operators = {row["operator"] for row in rows}
    if len(operators) > 1:
        raise ValueError(f"Mixed operator rows are forbidden: {sorted(operators)}")
    operator = next(iter(operators), None)
    slug = normalize_operator(operator) if operator else None
    start_date = START_DATES[slug] if slug else date.min
    ordered = sorted(
        (row for row in rows if row["date"] >= start_date),
        key=lambda row: row["date"],
    )
    unique_dates = sorted({row["date"] for row in ordered})
    selected_dates = set(unique_dates[::max(1, sample_every)])
    targets = [row for row in ordered if row["date"] in selected_dates]
    if max_draws is not None:
        targets = targets[:max_draws]

    results = []
    rng = random.Random(seed)
    random_hits = 0
    prize_hits = defaultdict(int)
    total_random = 0
    predictions_by_date = {}
    for target_date in sorted({target["date"] for target in targets}):
        history = [row for row in ordered if row["date"] < target_date]
        predictions_by_date[target_date] = [
            item["number"] for item in ranker(history, as_of=target_date, limit=3)
        ]

    for target in targets:
        target_date = target["date"]
        predicted = predictions_by_date[target_date]
        actual = [target["prizes"][i] for i in range(3)]
        actual_set = set(actual)
        hit = bool(set(predicted) & actual_set)

        random_pick_hits = 0
        for _ in range(max(0, random_trials)):
            random_picks = set(rng.sample(range(10000), 3))
            if any(f"{number:04d}" in actual_set for number in random_picks):
                random_pick_hits += 1
        random_hits += random_pick_hits
        total_random += max(0, random_trials)

        for index, field in enumerate(PRIZE_FIELDS):
            if actual[index] in predicted:
                prize_hits[field] += 1

        history_count = sum(row["date"] < target_date for row in ordered)
        results.append({
            "date": target_date.isoformat(),
            "operator": operator,
            "predicted_top3": predicted,
            "actual_first": actual[0],
            "actual_second": actual[1],
            "actual_third": actual[2],
            "hit_any_main_prize": hit,
            "random_hit_rate": (
                random_pick_hits / random_trials if random_trials else None
            ),
            "history_rows": history_count,
        })

    draw_count = len(results)
    hit_draws = sum(row["hit_any_main_prize"] for row in results)
    metrics = {
        "model": "positional-frequency-baseline-v1",
        "operator": operator,
        "sample_every": max(1, sample_every),
        "evaluated_draws": draw_count,
        "model_hit_draws": hit_draws,
        "model_hit_rate": hit_draws / draw_count if draw_count else 0.0,
        "random_trials_per_draw": max(0, random_trials),
        "random_hit_rate": random_hits / total_random if total_random else None,
        "prize_hits": dict(prize_hits),
        "interpretation": (
            "Ranking score is not a winning probability. Backtest performance "
            "does not guarantee future results."
        ),
    }
    return results, metrics


def load_target_rows(operator):
    """Load one selected operator's valid main-prize rows."""
    return read_draws(operator)


def main():
    parser = argparse.ArgumentParser(description="Leakage-safe single-operator 4D backtest")
    parser.add_argument("--operator", required=True, choices=sorted(DATASETS))
    parser.add_argument("--sample-every", type=int, default=30,
                        help="Evaluate every Nth draw (1 = every draw)")
    parser.add_argument("--max-draws", type=int)
    parser.add_argument("--random-trials", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261102)
    parser.add_argument("--output", help="Output directory; defaults to reports/backtest/<operator>")
    args = parser.parse_args()

    rows = load_target_rows(args.operator)
    results, metrics = run_backtest(
        rows, sample_every=args.sample_every, max_draws=args.max_draws,
        random_trials=args.random_trials, seed=args.seed,
    )
    output = ROOT / (args.output or f"reports/backtest/{args.operator}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "date", "operator", "predicted_top3", "actual_first",
            "actual_second", "actual_third", "hit_any_main_prize",
            "random_hit_rate", "history_rows",
        ])
        writer.writeheader()
        for row in results:
            row = dict(row)
            row["predicted_top3"] = "|".join(row["predicted_top3"])
            writer.writerow(row)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
