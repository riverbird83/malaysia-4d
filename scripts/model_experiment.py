"""Eight fixed 4D candidates and their equal-weight experimental ensemble."""
import argparse
import json
import math
from collections import Counter
from datetime import date
from functools import lru_cache
from heapq import nsmallest
from statistics import fmean

from prediction_engine import rank_numbers, read_draws

OPERATORS = ("magnum", "haolong")
VERSION = "eight-models-v1"
ADJACENT = ((0, 1), (1, 2), (2, 3))
NONADJACENT = ((0, 2), (0, 3), (1, 3))
PAIRS = ADJACENT + NONADJACENT
NUMBERS = tuple(f"{value:04d}" for value in range(10_000))


@lru_cache(maxsize=10_000)
def features(number):
    pairs = tuple(number[left] + number[right] for left, right in PAIRS)
    shape = (
        tuple(sorted(Counter(number).values())),
        sum(int(digit) % 2 for digit in number),
    )
    return pairs, shape


SHAPE_COUNTS = Counter(features(number)[1] for number in NUMBERS)


def position_probabilities(counts):
    return [
        {digit: (counter[digit] + 1) / (counter.total() + 10) for digit in "0123456789"}
        for counter in counts
    ]


def predict_experiment(rows, as_of):
    long_counts = [Counter() for _ in range(4)]
    decay_counts = [Counter() for _ in range(4)]
    recent_counts = [Counter() for _ in range(4)]
    pair_counts = [Counter() for _ in PAIRS]
    shape_counts = Counter()
    sample_size = 0

    for row in rows:
        age = (as_of - row["date"]).days
        if not 0 < age <= 20 * 365.2425:
            continue
        decay = 2 ** (-age / (2 * 365.2425))
        for number in row["prizes"]:
            sample_size += 1
            for pos, digit in enumerate(number):
                long_counts[pos][digit] += 1
                decay_counts[pos][digit] += decay
                if age < 365.2425:
                    recent_counts[pos][digit] += 1
            pairs, shape = features(number)
            for counter, pair in zip(pair_counts, pairs):
                counter[pair] += 1
            shape_counts[shape] += 1

    long = position_probabilities(long_counts)
    decay = position_probabilities(decay_counts)
    blended = [
        {
            digit: (recent[digit] + 300 * long[pos][digit]) / (recent.total() + 300)
            for digit in "0123456789"
        }
        for pos, recent in enumerate(recent_counts)
    ]
    # Shrink interactions toward the independent-digit and uniform-shape priors.
    pair_lifts = []
    for (left, right), counter in zip(PAIRS, pair_counts):
        lifts = {}
        for first in long[left]:
            for second in long[right]:
                expected = long[left][first] * long[right][second]
                pair = first + second
                probability = (counter[pair] + 1000 * expected) / (sample_size + 1000)
                lifts[pair] = math.log(probability / expected)
        pair_lifts.append(lifts)
    shape_lifts = {
        shape: math.log((shape_counts[shape] / (count / 10_000) + 1000) / (sample_size + 1000))
        for shape, count in SHAPE_COUNTS.items()
    }

    scores = {
        "baseline": [0.0] * len(NUMBERS),
        "time_decay": [],
        "long_history": [],
        "recent_long": [],
        "adjacent_pairs": [],
        "nonadjacent_pairs": [],
        "number_shape": [],
        "regularized_combination": [],
    }
    # Reuse the production ranking, including its tie-break, for the baseline.
    for item in rank_numbers(rows, as_of=as_of, limit=len(NUMBERS)):
        scores["baseline"][int(item["number"])] = item["score"]
    decay_log, long_log, blended_log = (
        [{digit: math.log(value) for digit, value in pos.items()} for pos in probabilities]
        for probabilities in (decay, long, blended)
    )
    for number in NUMBERS:
        pairs, shape = features(number)
        adjacent = fmean(pair_lifts[i][pairs[i]] for i in range(3))
        nonadjacent = fmean(pair_lifts[i][pairs[i]] for i in range(3, 6))
        shape_lift = shape_lifts[shape]
        long_score = sum(pos[digit] for pos, digit in zip(long_log, number))
        blended_score = sum(pos[digit] for pos, digit in zip(blended_log, number))
        scores["time_decay"].append(sum(pos[digit] for pos, digit in zip(decay_log, number)))
        scores["long_history"].append(long_score)
        scores["recent_long"].append(blended_score)
        scores["adjacent_pairs"].append(long_score + adjacent)
        scores["nonadjacent_pairs"].append(long_score + nonadjacent)
        scores["number_shape"].append(long_score + shape_lift)
        scores["regularized_combination"].append(
            blended_score + 0.5 * fmean((adjacent, nonadjacent, shape_lift))
        )

    # Normalize each model over all 10,000 numbers before averaging equally.
    ensemble = [0.0] * len(NUMBERS)
    predictions = {}
    for name, values in scores.items():
        predictions[name] = top_three(values, precision=8 if name == "baseline" else 12)
        weights = [math.exp(value) for value in values]
        total = sum(weights)
        for index, weight in enumerate(weights):
            ensemble[index] += weight / total / len(scores)
    return {"version": VERSION, "models": predictions, "ensemble_top3": top_three(ensemble, 15)}


def top_three(scores, precision):
    indices = nsmallest(3, range(len(scores)), key=lambda index: (-round(scores[index], precision), index))
    return [NUMBERS[index] for index in indices]


def evaluate(samples):
    from export_magnum_report import random_comparison

    counts = {}
    for actual, experiment in samples:
        predictions = {**experiment["models"], "ensemble": experiment["ensemble_top3"]}
        for model, top3 in predictions.items():
            exact = bool(set(top3) & set(actual))
            reordered = any(
                number != prize and sorted(number) == sorted(prize)
                for number in top3 for prize in actual
            )
            count = counts.setdefault(model, {"exact": 0, "reordered": 0})
            count["exact"] += exact
            count["reordered"] += reordered
    random = random_comparison(
        [{"prizes": actual, "predicted": []} for actual, _ in samples]
    )
    return {
        "draws": len(samples),
        "hits": counts,
        "random_rates": {category: metrics["rate"] for category, metrics in random.items()},
    }


def evaluate_live(rows, archive):
    prizes_by_day = {row["date"].isoformat(): row["prizes"] for row in rows}
    samples = [
        (prizes_by_day[day], entry["experiment"])
        for day, entry in sorted(archive.items())
        if day in prizes_by_day and entry.get("experiment", {}).get("version") == VERSION
    ][:10]
    report = evaluate(samples)
    if len(samples) < 10:
        report["gate"] = "collecting"
    elif report["hits"]["ensemble"]["exact"] > report["hits"]["baseline"]["exact"]:
        report["gate"] = "continue_validation"
    else:
        report["gate"] = "did_not_pass"
    return report


def main():
    from archive_magnum_prediction import read_archive

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True, choices=OPERATORS)
    parser.add_argument("--backtest-from", type=date.fromisoformat)
    args = parser.parse_args()
    rows = read_draws(args.operator)
    if args.backtest_from:
        samples = [
            (row["prizes"], predict_experiment(rows, row["date"]))
            for row in rows
            if row["date"] >= args.backtest_from and row["date"] > rows[0]["date"]
        ]
        report = evaluate(samples)
    else:
        report = evaluate_live(rows, read_archive(args.operator))
    print(json.dumps(report, indent=2))



if __name__ == "__main__":
    main()
