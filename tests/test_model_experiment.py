import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from archive_magnum_prediction import archive_prediction
from model_experiment import LEGACY_VERSION, VERSION, evaluate_live, predict_experiment
from prediction_engine import rank_numbers


class ModelExperimentTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 11, 11)
        self.history = [{"date": self.day - timedelta(days=1), "prizes": ["0123", "3120", "5541"]}]

    def test_twelve_candidates_exclude_future_and_match_production_baseline(self):
        future = {"date": self.day, "prizes": ["9999", "8888", "7777"]}
        result = predict_experiment(self.history, self.day)
        self.assertEqual(result, predict_experiment([*self.history, future], self.day))
        self.assertEqual(len(result["models"]), 12)
        self.assertEqual(result["models"]["baseline"], [
            item["number"] for item in rank_numbers(self.history, as_of=self.day)
        ])
        for picks in [*result["models"].values(), result["ensemble_top3"]]:
            self.assertEqual(len(set(picks)), 3)
            self.assertTrue(all(len(pick) == 4 and pick.isdigit() for pick in picks))

    def test_archive_locks_forecasts_and_experiments_for_all_operators(self):
        now = datetime(2026, 11, 11, 4, tzinfo=timezone.utc)
        records = {}
        self.assertFalse(archive_prediction(
            records, self.history, now - timedelta(minutes=1), 1, operator="magnum"
        ))
        self.assertFalse(archive_prediction(
            records, self.history, now + timedelta(days=1), 1, operator="magnum"
        ))
        self.assertTrue(archive_prediction(records, self.history, now, 1, operator="magnum"))
        self.assertFalse(archive_prediction(records, self.history, now, 2, operator="magnum"))
        self.assertEqual(records[str(self.day)]["run_id"], 1)
        self.assertIn("experiment", records[str(self.day)])
        self.assertFalse(archive_prediction(
            {}, self.history, now + timedelta(hours=4), 2, operator="haolong"
        ))
        for operator in ("haolong", "sportstoto", "damacai"):
            with self.subTest(operator=operator):
                records = {}
                self.assertTrue(archive_prediction(records, self.history, now, 1, operator=operator))
                self.assertEqual(len(records[str(self.day)]["experiment"]["models"]), 12)

    def test_gate_uses_first_ten_settled_days_and_exact_matches(self):
        rows = []
        archive = {}
        for offset in range(12):
            day = self.day + timedelta(days=offset)
            rows.append({"date": day, "prizes": ["4321", "2020", "3030"]})
            archive[str(day)] = {"experiment": {
                "version": VERSION,
                "models": {"baseline": ["1111", "2222", "3333"]},
                "ensemble_top3": ["1234", "0000", "4321" if offset == 10 else "5555"],
            }}
        archive[str(rows[-1]["date"])]["experiment"]["version"] = LEGACY_VERSION
        self.assertEqual(evaluate_live(rows, archive, version=LEGACY_VERSION, target=10)["draws"], 1)
        self.assertEqual(evaluate_live(rows[:9], archive)["gate"], "collecting")
        result = evaluate_live(rows, archive)
        self.assertEqual(result["draws"], 10)
        self.assertEqual(result["hits"]["ensemble"], {"exact": 0, "reordered": 10})
        self.assertEqual(result["gate"], "did_not_pass")
        archive[str(self.day)]["experiment"]["ensemble_top3"][0] = "4321"
        self.assertEqual(evaluate_live(rows, archive)["gate"], "continue_validation")

    def test_round_two_waits_for_first_round_and_preserves_locked_records(self):
        from unittest.mock import patch
        from model_experiment import DUAL_VERSION
        rows = [{"date": self.day + timedelta(days=i),
                 "prizes": ["4321", "2020", "3030"]} for i in range(10)]
        records = {str(row["date"]): {"experiment": {
            "version": VERSION, "models": {"baseline": ["1111", "2222", "3333"]},
            "ensemble_top3": ["1234", "0000", "5555"],
        }} for row in rows}
        today = self.day + timedelta(days=10)
        now = datetime.combine(today, datetime.min.time(), timezone.utc) + timedelta(hours=4)
        import copy
        original = copy.deepcopy(records)
        experiment = {"version": VERSION, "models": {}, "ensemble_top3": ["1111", "2222", "3333"]}
        with patch("archive_magnum_prediction.predict_experiment", return_value=experiment):
            self.assertTrue(archive_prediction(records, rows, now, 99, operator="haolong"))
        self.assertEqual(records[str(today)]["experiment"]["version"], DUAL_VERSION)
        for key, value in original.items():
            self.assertEqual(records[key], value)
        self.assertFalse(archive_prediction(records, rows, now, 100, operator="haolong"))

    def test_dual_scoring_keeps_first_ten_forecasts_and_waits_for_complete_board(self):
        from model_experiment import DUAL_VERSION, evaluate_dual
        boards = []
        records = {}
        for offset in range(11):
            day = str(self.day + timedelta(days=offset))
            board = {"date": day}
            for prefix, numbers in (
                ("prize", ["1000", "1001", "1002"]),
                ("special", [f"{n:04d}" for n in range(2000, 2010)]),
                ("consol", [f"{n:04d}" for n in range(3000, 3010)]),
            ):
                board.update({f"{prefix}_{i}": number for i, number in enumerate(numbers, 1)})
            boards.append(board)
            records[day] = {"experiment": {"version": DUAL_VERSION,
                "models": {"baseline": ["2000", "0000", "9999"]},
                "ensemble_top3": ["1000", "2000", "9999"]}}
        boards[0]["consol_10"] = ""
        report = evaluate_dual(boards, records)
        self.assertEqual((report["locked"], report["settled"], report["pending"]), (10, 9, 1))
        self.assertEqual(report["hits"]["baseline"], {"top3": 0, "all23": 9})
        self.assertEqual(report["hits"]["ensemble"], {"top3": 9, "all23": 9})
        boards[0]["consol_10"] = "3009"
        self.assertEqual(evaluate_dual(boards, records)["settled"], 10)
