"""Operator-isolated 4D ranking engine.

Exactly one operator dataset is loaded per prediction run. Scores are ranking
scores, not calibrated probabilities.
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
    "magnum": ROOT / "data" / "normalized" / "magnum_draws.csv",
    "sportstoto": ROOT / "data" / "normalized" / "sportstoto_draws.csv",
    "damacai": ROOT / "data" / "normalized" / "damacai_draws.csv",
    "haolong": ROOT / "data" / "normalized" / "haolong_draws.csv",
}
DISPLAY_NAMES = {
    "magnum": "Magnum",
    "sportstoto": "Sport Toto",
    "damacai": "Da Ma Cai",
    "haolong": "Haolong",
}
ALIASES = {
    "magnum": "magnum",
    "sportstoto": "sportstoto",
    "sporttoto": "sportstoto",
    "toto": "sportstoto",
    "damacai": "damacai",
    "haolong": "haolong",
    "granddragon": "haolong",
    "granddragonlotto": "haolong",
    "gdllotto": "haolong",
}
PRIZE_FIELDS = ("prize_1", "prize_2", "prize_3")
START_DATES = {
    "magnum": date(2006, 1, 1),
    "sportstoto": date(2006, 1, 1),
    "damacai": date(2006, 1, 1),
    "haolong": date(2017, 1, 1),
}


def normalize_operator(operator: str) -> str:
    key = "".join(ch for ch in operator.lower() if ch.isalnum())
    # Keep common aliases explicit and deterministic.
    key = {
        "sportstoto": "sportstoto",
        "granddragon": "granddragon",
        "granddragonlotto": "granddragonlotto",
    }.get(key, key)
    if key not in ALIASES:
        raise ValueError(
            f"Unknown operator {operator!r}; choose one of: {', '.join(DATASETS)}"
        )
    return ALIASES[key]


def read_draws(operator: str, cutoff=None):
    """Read one operator's normalized rows only; cross-operator pooling is forbidden."""
    slug = normalize_operator(operator)
    path = DATASETS[slug]
    rows = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            try:
                draw_date = date.fromisoformat(row["date"])
            except (KeyError, ValueError):
                continue
            if draw_date < START_DATES[slug] or (cutoff and draw_date >= cutoff):
                continue
            prizes = [row.get(field, "").strip() for field in PRIZE_FIELDS]
            if not all(len(number) == 4 and number.isdigit() for number in prizes):
                continue
            rows.append({
                "operator": DISPLAY_NAMES[slug],
                "date": draw_date,
                "prizes": prizes,
            })
    return sorted(rows, key=lambda item: item["date"])


def _age_weight(draw_date, as_of):
    age_days = max(0, (as_of - draw_date).days)
    age_years = age_days / 365.2425
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
    for row in history:
        if row["date"] >= as_of:
            continue
        weight = _age_weight(row["date"], as_of)
        if not weight:
            continue
        for number in row["prizes"]:
            for pos, digit in enumerate(number):
                position_counts[pos][digit] += weight

    denominators = [sum(counts.values()) + 10.0 for counts in position_counts]
    ranked = []
    for value in range(10000):
        number = f"{value:04d}"
        log_score = 0.0
        for pos, digit in enumerate(number):
            probability = (position_counts[pos][digit] + 1.0) / denominators[pos]
            log_score += math.log(probability)
        ranked.append((log_score, number))
    ranked.sort(key=lambda item: (-round(item[0], 8), item[1]))
    return [
        {"rank": index + 1, "number": number, "score": round(score, 8)}
        for index, (score, number) in enumerate(ranked[:limit])
    ]


def main():
    parser = argparse.ArgumentParser(description="Rank one Malaysia 4D operator")
    parser.add_argument("--operator", required=True, choices=sorted(DATASETS),
                        help="Select exactly one independent operator dataset")
    parser.add_argument("--as-of", help="Prediction date YYYY-MM-DD; only earlier draws are used")
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    history = read_draws(args.operator, cutoff=as_of)
    results = rank_numbers(history, as_of=as_of, limit=args.top)
    print(f"Operator: {DISPLAY_NAMES[args.operator]}")
    print(f"Historical draws used: {len(history)}")
    print("Ranking scores are not winning probabilities.")
    for item in results:
        print(f"{item['rank']}. {item['number']}  score={item['score']}")


if __name__ == "__main__":
    main()
