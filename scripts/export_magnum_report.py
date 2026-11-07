"""Build the static Magnum prediction and walk-forward report for Pages."""
import argparse
import calendar
import json
from datetime import timedelta
from pathlib import Path

from prediction_engine import rank_numbers, read_draws


def build_report(rows):
    if not rows:
        raise ValueError("No usable Magnum draws")
    latest = rows[-1]
    end = latest["date"]
    previous_year = end.year - 1
    cutoff = end.replace(
        year=previous_year,
        day=min(end.day, calendar.monthrange(previous_year, end.month)[1]),
    )

    def top3(as_of):
        return [item["number"] for item in rank_numbers(rows, as_of=as_of)]

    # Keep at least the last 30 eligible draws even if there are gaps in the year.
    recent_start = max(1, len(rows) - 30)
    backtest = [
        {"date": row["date"].isoformat(), "prizes": row["prizes"],
         "predicted": top3(row["date"])}
        for index, row in reversed(list(enumerate(rows)))
        if row["date"] > rows[0]["date"] and (row["date"] > cutoff or index >= recent_start)
    ]
    as_of = end + timedelta(days=1)
    return {
        "sample_size": len(rows),
        "latest": {"date": end.isoformat(), "prizes": latest["prizes"]},
        "as_of": as_of.isoformat(),
        "top3": top3(as_of),
        "year_cutoff": cutoff.isoformat(),
        "backtest": backtest,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = build_report(read_draws("magnum"))
    args.output.write_text(json.dumps(report, separators=(",", ":")) + "\n", encoding="utf-8")
