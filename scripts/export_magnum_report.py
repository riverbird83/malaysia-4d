"""Build the static Magnum prediction and walk-forward report for Pages."""
import argparse
import calendar
import json
from datetime import timedelta
from itertools import permutations
from math import comb
from pathlib import Path

from archive_magnum_prediction import ARCHIVE
from prediction_engine import rank_numbers, read_draws


def years_before(day, years):
    year = day.year - years
    return day.replace(year=year, day=min(day.day, calendar.monthrange(year, day.month)[1]))


def random_comparison(draws):
    """Compare against three distinct uniformly chosen numbers per draw."""
    total_combinations = comb(10_000, 3)
    metrics = {}
    for key in ("exact", "reordered"):
        probabilities = []
        observed = 0
        for draw in draws:
            prizes = set(draw["prizes"])
            targets = prizes if key == "exact" else {
                "".join(order)
                for prize in prizes
                for order in permutations(prize)
                if "".join(order) != prize
            }
            observed += bool(targets.intersection(draw["predicted"]))
            probabilities.append(1 - comb(10_000 - len(targets), 3) / total_combinations)

        # Probability that independent random picks match or exceed the model's count.
        distribution = [1.0] + [0.0] * observed
        if observed:
            for probability in probabilities:
                distribution[observed] += distribution[observed - 1] * probability
                for count in range(observed - 1, 0, -1):
                    distribution[count] = (
                        distribution[count] * (1 - probability)
                        + distribution[count - 1] * probability
                    )
                distribution[0] *= 1 - probability
        expected = sum(probabilities)
        metrics[key] = {
            "expected_draws": expected,
            "rate": expected / len(draws) if draws else None,
            "chance_at_least_observed": distribution[observed],
        }
    return metrics


def build_report(rows, archive=None):
    if not rows:
        raise ValueError("No usable Magnum draws")
    latest = rows[-1]
    end = latest["date"]
    cutoff = years_before(end, 1)
    three_year_cutoff = years_before(end, 3)

    def top3(as_of):
        return [item["number"] for item in rank_numbers(rows, as_of=as_of)]

    # Keep at least the last 30 eligible draws even if there are gaps in the year.
    recent_start = max(1, len(rows) - 30)
    backtest = [
        {"date": row["date"].isoformat(), "prizes": row["prizes"],
         "predicted": top3(row["date"])}
        for index, row in reversed(list(enumerate(rows)))
        if row["date"] > rows[0]["date"] and (row["date"] > three_year_cutoff or index >= recent_start)
    ]
    as_of = end + timedelta(days=1)
    prizes_by_date = {row['date'].isoformat(): row['prizes'] for row in rows}
    return {
        "live_predictions": [
            {"date": day, **entry, "prizes": prizes_by_date.get(day)}
            for day, entry in sorted((archive or {}).items(), reverse=True)
        ],
        "sample_size": len(rows),
        "latest": {"date": end.isoformat(), "prizes": latest["prizes"]},
        "as_of": as_of.isoformat(),
        "top3": top3(as_of),
        "year_cutoff": cutoff.isoformat(),
        "three_year_cutoff": three_year_cutoff.isoformat(),
        "random_baseline": random_comparison([
            draw for draw in backtest if draw["date"] > three_year_cutoff.isoformat()
        ]),
        "backtest": backtest,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = build_report(read_draws("magnum"), json.loads(ARCHIVE.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(report, separators=(",", ":")) + "\n", encoding="utf-8")
