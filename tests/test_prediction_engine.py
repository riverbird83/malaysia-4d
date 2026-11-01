import unittest
from datetime import date

from prediction_engine import rank_numbers


class PredictionEngineTests(unittest.TestCase):
    def test_returns_three_unique_four_digit_numbers(self):
        history = [
            {"date": date(2025, 1, 1), "operator": "A", "prizes": ["1234", "5678", "9012"]},
            {"date": date(2025, 1, 2), "operator": "B", "prizes": ["1234", "5678", "9012"]},
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


if __name__ == "__main__":
    unittest.main()
