import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prediction_engine as engine
from prediction_engine import rank_numbers, read_draws, normalize_operator


class PredictionEngineTests(unittest.TestCase):
    def test_returns_three_unique_four_digit_numbers(self):
        history = [
            {"date": date(2025, 1, 1), "operator": "A", "prizes": ["1234", "5678", "9012"]},
            {"date": date(2025, 1, 2), "operator": "A", "prizes": ["1234", "5678", "9012"]},
        ]
        result = rank_numbers(history, as_of=date(2025, 1, 3), limit=3)
        self.assertEqual(len(result), 3)
        self.assertEqual(len({item["number"] for item in result}), 3)
        self.assertTrue(all(len(item["number"]) == 4 and item["number"].isdigit() for item in result))

    def test_future_draws_are_excluded(self):
        history = [
            {"date": date(2025, 1, 1), "operator": "A", "prizes": ["1234", "1234", "1234"]},
            {"date": date(2025, 1, 3), "operator": "A", "prizes": ["9999", "9999", "9999"]},
        ]
        before_future = rank_numbers(history, as_of=date(2025, 1, 2), limit=1)
        without_future = rank_numbers(history[:1], as_of=date(2025, 1, 2), limit=1)
        self.assertEqual(before_future, without_future)

    def test_empty_history_is_deterministic(self):
        result = rank_numbers([], as_of=date(2025, 1, 1), limit=3)
        self.assertEqual([item["number"] for item in result], ["0000", "0001", "0002"])

    def test_operator_aliases_and_single_dataset_loading(self):
        self.assertEqual(normalize_operator("Grand Dragon Lotto"), "haolong")
        self.assertEqual(normalize_operator("Sport Toto"), "sportstoto")
        self.assertEqual(normalize_operator("Da Ma Cai"), "damacai")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "haolong.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["date", "prize_1", "prize_2", "prize_3"])
                writer.writeheader()
                writer.writerow({"date": "2025-01-01", "prize_1": "0123", "prize_2": "4567", "prize_3": "8901"})
            original = engine.DATASETS["haolong"]
            try:
                engine.DATASETS["haolong"] = path
                rows = read_draws("haolong")
            finally:
                engine.DATASETS["haolong"] = original
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["operator"], "Haolong")
        self.assertEqual(rows[0]["prizes"], ["0123", "4567", "8901"])


if __name__ == "__main__":
    unittest.main()
