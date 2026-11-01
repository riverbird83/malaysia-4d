import unittest
import tempfile
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_data import canonical_number, audit_file


class FourDNumberRules(unittest.TestCase):
    def test_zero_padding(self):
        self.assertEqual(canonical_number("19"), "0019")
        self.assertEqual(canonical_number("316"), "0316")

    def test_float_artifact(self):
        self.assertEqual(canonical_number("893.0"), "0893")
        self.assertEqual(canonical_number("8224.0"), "8224")

    def test_blank_is_missing_not_zero(self):
        self.assertIsNone(canonical_number(""))

    def test_invalid_values_are_rejected(self):
        self.assertIsNone(canonical_number("12A4"))
        self.assertIsNone(canonical_number("12345"))

    def test_duplicate_winning_numbers_are_not_a_normalization_error(self):
        # Number normalization is value-based; duplicates are valid and preserved.
        values = [canonical_number("123"), canonical_number("0123")]
        self.assertEqual(values, ["0123", "0123"])

    def test_legacy_sportstoto_consolation_gap_is_explicitly_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sportstoto.csv"
            fields = ["draw_seq", "date", "prize_1", "prize_2", "prize_3"] + [
                f"special_{i}" for i in range(1, 11)
            ] + [f"consol_{i}" for i in range(1, 11)]
            row = {field: "1234" for field in fields}
            row["draw_seq"] = "1"
            row["date"] = "1992-05-06"
            for i in range(1, 11):
                row[f"consol_{i}"] = ""
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            report = audit_file("sportstoto", path, True)
            self.assertEqual(report["disallowed_missing_number_count"], 0)
            self.assertNotEqual(report["status"], "FAIL")

    def test_recent_sportstoto_consolation_gap_is_not_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sportstoto.csv"
            fields = ["draw_seq", "date", "prize_1", "prize_2", "prize_3"] + [
                f"special_{i}" for i in range(1, 11)
            ] + [f"consol_{i}" for i in range(1, 11)]
            row = {field: "1234" for field in fields}
            row["draw_seq"] = "1"
            row["date"] = "2026-10-31"
            row["consol_1"] = ""
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            report = audit_file("sportstoto", path, True)
            self.assertEqual(report["disallowed_missing_number_count"], 1)
            self.assertEqual(report["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
