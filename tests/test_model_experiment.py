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

    def test_archive_locks_forecasts_and_only_experiments_on_selected_operators(self):
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
        records = {}
        self.assertTrue(archive_prediction(records, self.history, now, 1, operator="sportstoto"))
        self.assertNotIn("experiment", records[str(self.day)])

    def test_gate_uses_first_nine_settled_days_and_exact_matches(self):
        rows = []
        archive = {}
        for offset in range(11):
            day = self.day + timedelta(days=offset)
            rows.append({"date": day, "prizes": ["4321", "2020", "3030"]})
            archive[str(day)] = {"experiment": {
                "version": VERSION,
                "models": {"baseline": ["1111", "2222", "3333"]},
                "ensemble_top3": ["1234", "0000", "4321" if offset == 9 else "5555"],
            }}
        archive[str(rows[-1]["date"])]["experiment"]["version"] = LEGACY_VERSION
        self.assertEqual(evaluate_live(rows, archive, version=LEGACY_VERSION, target=10)["draws"], 1)
        self.assertEqual(evaluate_live(rows[:8], archive)["gate"], "collecting")
        result = evaluate_live(rows, archive)
        self.assertEqual(result["draws"], 9)
        self.assertEqual(result["hits"]["ensemble"], {"exact": 0, "reordered": 9})
        self.assertEqual(result["gate"], "did_not_pass")
        archive[str(self.day)]["experiment"]["ensemble_top3"][0] = "4321"
        self.assertEqual(evaluate_live(rows, archive)["gate"], "continue_validation")
