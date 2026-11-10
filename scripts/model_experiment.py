"""Twelve 4D candidates and their experimental ensemble."""
import argparse
import json
import math
from collections import Counter
from datetime import date
from functools import lru_cache
from heapq import nsmallest
from statistics import fmean

from prediction_engine import rank_numbers, read_draws

OPERATORS = ("magnum", "haolong", "damacai", "sportstoto")
LEGACY_VERSION = "eight-models-v1"
VERSION = "twelve-models-v1"
TARGET_DRAWS = 10
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


def component_scores(rows, as_of):
    long_counts = [Counter() for _ in range(4)]
    decay_counts = [Counter() for _ in range(4)]
    recent_counts = [Counter() for _ in range(4)]
    pair_counts = [Counter() for _ in PAIRS]
    shape_counts = Counter()
    prize_counts = [[Counter() for _ in range(4)] for _ in range(3)]
    transitions = [[Counter() for _ in range(4)] for _ in range(3)]
    whole_counts = Counter()
    previous = None
    sample_size = 0

    for row in rows:
        age = (as_of - row["date"]).days
        if not 0 < age <= 20 * 365.2425:
            continue
        decay = 2 ** (-age / (2 * 365.2425))
        for prize_index, number in enumerate(row["prizes"]):
            whole_counts[number] += 1
            for pos, digit in enumerate(number):
                prize_counts[prize_index][pos][digit] += 1
                if previous is not None:
                    transitions[prize_index][pos][previous[prize_index][pos] + digit] += 1
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
        previous = row["prizes"]

    long = position_probabilities(long_counts)
    decay = position_probabilities(decay_counts)
    prize_probabilities = [position_probabilities(counts) for counts in prize_counts]
    conditional_probabilities = []
    for slot, positions in enumerate(prize_probabilities):
        conditional = []
        for pos, marginal in enumerate(positions):
            if previous is None:
                conditional.append(marginal)
                continue
            prefix = previous[slot][pos]
            counts = {digit: transitions[slot][pos][prefix + digit] for digit in marginal}
            denominator = sum(counts.values()) + 300
            conditional.append({
                digit: (counts[digit] + 300 * prior) / denominator
                for digit, prior in marginal.items()
            })
        conditional_probabilities.append(conditional)
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
        "prize_hierarchy": [],
        "cross_draw_transition": [],
        "whole_number_frequency": [],
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

        scores["prize_hierarchy"].append(math.log(fmean(
            math.prod(pos[digit] for pos, digit in zip(slot, number))
            for slot in prize_probabilities
        )))
        scores["cross_draw_transition"].append(math.log(fmean(
            math.prod(pos[digit] for pos, digit in zip(slot, number))
            for slot in conditional_probabilities
        )))
        scores["whole_number_frequency"].append(math.log(
            (whole_counts[number] + 10_000 * math.exp(blended_score)) / (sample_size + 10_000)
        ))
    return scores


def normalize_scores(scores):
    weights = [math.exp(score) for score in scores]
    total = sum(weights)
    return [weight / total for weight in weights]


def predict_experiment(rows, as_of):
    history = sorted((row for row in rows if row["date"] < as_of), key=lambda row: row["date"])
    scores = component_scores(history, as_of)
    probabilities = {name: normalize_scores(values) for name, values in scores.items()}
    predictions = {
        name: top_three(values, precision=8 if name == "baseline" else 12)
        for name, values in scores.items()
    }

    # Score the 11 component models on earlier, strictly out-of-sample draws.
    validation = history[-12:] if len(history) > 12 else history[1:]
    log_quality = dict.fromkeys(scores, 0.0)
    for draw in validation:
        past_scores = component_scores(history, draw["date"])
        for name, values in past_scores.items():
            log_normalizer = math.log(sum(math.exp(value) for value in values))
            log_quality[name] += fmean(values[int(prize)] - log_normalizer for prize in draw["prizes"])
    average_quality = {name: value / max(1, len(validation)) for name, value in log_quality.items()}
    best = max(average_quality.values())
    weights = {name: math.exp(10 * (value - best)) for name, value in average_quality.items()}
    total = sum(weights.values())
    adaptive = [
        sum(weights[name] * values[index] for name, values in probabilities.items()) / total
        for index in range(len(NUMBERS))
    ]
    predictions["adaptive_fusion"] = top_three(adaptive, 15)
    ensemble = [
        fmean((*components, adaptive[index]))
        for index, components in enumerate(zip(*probabilities.values()))
    ]
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


def evaluate_live(rows, archive, *, version=VERSION, target=TARGET_DRAWS):
    prizes_by_day = {row["date"].isoformat(): row["prizes"] for row in rows}
    samples = [
        (prizes_by_day[day], entry["experiment"])
        for day, entry in sorted(archive.items())
        if day in prizes_by_day and entry.get("experiment", {}).get("version") == version
    ][:target]
    report = evaluate(samples)
    if len(samples) < target:
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
