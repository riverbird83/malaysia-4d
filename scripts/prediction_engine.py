"""Transparent baseline ranking engine for Malaysia 4D.

This module ranks all 0000-9999 combinations from historical First/Second/Third
Prize observations. Scores are ranking scores, not calibrated probabilities.
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "Magnum": ROOT / "data" / "normalized" / "magnum_draws.csv",
    "Sport Toto": ROOT / "data" / "normalized" / "sportstoto_draws.csv",
    "Da Ma Cai": ROOT / "data" / "normalized" / "damacai_draws.csv",
}
PRIZE_FIELDS = ("prize_1", "prize_2", "prize_3")
START_DATE = date(2006, 1, 1)
WINDOW_WEIGHTS = ((3, 0.60), (10, 0.25), (20, 0.15))


def read_draws(paths=None, cutoff=None):
    """Read normalized draw rows; retain only valid 4-digit main prizes."""
    paths = paths or DATASETS
    rows = []
    for operator, path in paths.items():
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                try:
                    draw_date = date.fromisoformat(row["date"])
                except (KeyError, ValueError):
                    continue
                if draw_date < START_DATE or (cutoff and draw_date >= cutoff):
                    continue
                prizes = [row.get(field, "").strip() for field in PRIZE_FIELDS]
                if not all(len(n) == 4 and n.isdigit() for n in prizes):
                    continue
                rows.append({"operator": operator, "date": draw_date, "prizes": prizes})
    return sorted(rows, key=lambda item: (item["date"], item["operator"]))


def _age_weight(draw_date, as_of):
    age_days = max(0, (as_of - draw_date).days)
    age_years = age_days / 365.2425
    # Explicit non-overlapping bands: 0-3y, 4-10y, and 11-20y.
    if age_years < 3:
        return 0.60
    if age_years <= 10:
        return 0.25
    if age_years <= 20:
        return 0.15
    return 0.0


def rank_numbers(history, as_of=None, limit=3):
    """Return deterministic top-N combinations using smoothed positional counts."""
    if as_of is None:
        as_of = max((row["date"] for row in history), default=date.today()) + timedelta(days=1)
    position_counts = [Counter() for _ in range(4)]
    total_weight = 0.0
    for row in history:
        if row["date"] >= as_of:
            continue
        weight = _age_weight(row["date"], as_of)
        if not weight:
            continue
        for number in row["prizes"]:
            total_weight += weight
            for pos, digit in enumerate(number):
                position_counts[pos][digit] += weight

    # Laplace smoothing avoids zero-probability combinations.
    denominators = [sum(counts.values()) + 10.0 for counts in position_counts]
    ranked = []
    for value in range(10000):
        number = f"{value:04d}"
        log_score = 0.0
        for pos, digit in enumerate(number):
            probability = (position_counts[pos][digit] + 1.0) / denominators[pos]
            log_score += math.log(probability)
        ranked.append((log_score, number))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"rank": index + 1, "number": number, "score": round(score, 8)}
        for index, (score, number) in enumerate(ranked[:limit])
    ]


def main():
    parser = argparse.ArgumentParser(description="Rank Malaysia 4D number combinations")
    parser.add_argument("--as-of", help="Prediction date YYYY-MM-DD; only earlier draws are used")
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    history = read_draws(cutoff=as_of)
    results = rank_numbers(history, as_of=as_of, limit=args.top)
    print(f"Historical draws used: {len(history)}")
    print("Ranking scores are not winning probabilities.")
    for item in results:
        print(f"{item['rank']}. {item['number']}  score={item['score']}")


if __name__ == "__main__":
    main()
