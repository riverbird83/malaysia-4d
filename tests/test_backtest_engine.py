import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from backtest_engine import run_backtest


class BacktestEngineTests(unittest.TestCase):
    def test_same_day_rows_are_never_in_history(self):
        rows = [
            {"date": date(2025, 1, 1), "operator": "A", "prizes": ["1111", "2222", "3333"]},
            {"date": date(2025, 1, 2), "operator": "A", "prizes": ["4444", "5555", "6666"]},
            {"date": date(2025, 1, 2), "operator": "B", "prizes": ["7777", "8888", "9999"]},
            {"date": date(2025, 1, 3), "operator": "A", "prizes": ["0001", "0002", "0003"]},
        ]
        observed = []

        def fake_ranker(history, as_of=None, limit=3):
            observed.append((as_of, [row["operator"] for row in history]))
            return [{"number": "0001"}, {"number": "0002"}, {"number": "0003"}]

        run_backtest(rows, sample_every=1, random_trials=0, ranker=fake_ranker)
        target_day_two = [item for item in observed if item[0] == date(2025, 1, 2)]
        self.assertEqual(len(target_day_two), 2)
        self.assertTrue(all(len(operators) == 1 and operators == ["A"]
                            for _, operators in target_day_two))

    def test_result_counts_and_random_baseline_are_reported(self):
        rows = [
            {"date": date(2025, 1, 1), "operator": "A", "prizes": ["1111", "2222", "3333"]},
            {"date": date(2025, 1, 2), "operator": "A", "prizes": ["0001", "0002", "0003"]},
        ]
        def fake_ranker(history, as_of=None, limit=3):
            return [{"number": "0001"}, {"number": "0002"}, {"number": "0003"}]
        results, metrics = run_backtest(
            rows, sample_every=1, random_trials=20, seed=7, ranker=fake_ranker
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(metrics["model_hit_draws"], 1)
        self.assertEqual(metrics["evaluated_draws"], 2)
        self.assertIsNotNone(metrics["random_hit_rate"])


if __name__ == "__main__":
    unittest.main()
