import csv
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_other_top3 as updater


class FullPrizeRefreshTests(unittest.TestCase):
    def test_retry_upgrades_known_top_three_without_duplicates_or_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/normalized").mkdir(parents=True)
            (root / "data/audit").mkdir()
            path = root / "data/normalized/haolong_draws.csv"
            raw = root / "data/haolong_draws.csv"
            supplement = root / "data/grand_dragon_top3_supplement.csv"
            fields = ["draw_seq", "date", "year", "month", "day"]
            for prefix, count in (("prize", 3), ("special", 15), ("consol", 10)):
                fields.extend(f"{prefix}_{i}" for i in range(1, count + 1))
            for file in (path, raw):
                file.write_text(",".join(fields) + "\n")
            main = ["0001", "0012", "0123"]
            special = [f"{i:04d}" for i in range(20, 30)]
            consolation = [f"{i:04d}" for i in range(30, 40)]
            day = datetime(2026, 11, 15).date()
            now = datetime(2026, 11, 15, 13, tzinfo=timezone.utc)
            known = []
            replies = {}

            def get(requested):
                return {"data": {"date": str(requested), "results": replies.get(requested, [])}}

            def backup(requested):
                raise ValueError("no fallback on test date")

            def result(prizes, consolation_numbers):
                return dict(operator="gd", date=str(day), status="checked", draw_no="",
                            first=prizes[0], second=prizes[1], third=prizes[2],
                            special=special, consolation=consolation_numbers)

            with (
                patch.object(updater, "ROOT", root),
                patch.dict(updater.DATASETS, {"haolong": path}),
                patch.dict(updater.TOP3_SUPPLEMENTS, {"haolong": supplement}),
                patch.object(updater, "read_draws", return_value=known),
            ):
                replies[day] = [result(main, [])]
                updater.refresh(now, get, backup, grand_dragon_only=True)
                known.append({"date": day, "prizes": main})
                original = path.read_bytes()
                replies[day] = [result(["9999", *main[1:]], consolation)]
                updater.refresh(now, get, backup, grand_dragon_only=True)
                self.assertEqual(path.read_bytes(), original)
                replies[day] = [result(main, consolation)]
                updater.refresh(now, get, backup, grand_dragon_only=True)
                updater.refresh(now, get, backup, grand_dragon_only=True)

            self.assertEqual(path.read_bytes(), raw.read_bytes())
            with path.open(newline="") as handle:
                board, = csv.DictReader(handle)
            self.assertEqual(board["special_1"], "0020")
            self.assertEqual(board["consol_10"], "0039")
            self.assertEqual(len(supplement.read_text().splitlines()), 2)
            self.assertEqual(len((root / "data/audit/recent_full_prize_updates.csv")
                                 .read_text().splitlines()), 2)
