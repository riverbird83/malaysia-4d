import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scripts import validate_haolong


class GrandDragonStrictValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw.csv"
        self.normalized = self.root / "normalized.csv"
        self.audit = self.root / "audit.csv"
        self.raw_fields = [
            "draw_seq", "date", "year", "month", "day",
            "prize_1", "prize_2", "prize_3",
            *[f"special_{i}" for i in range(1, 16)],
            *[f"consol_{i}" for i in range(1, 11)],
        ]
        self.audit_fields = [
            "date", "status", "source_url", "fetched_at_utc",
            "content_sha256", "parser_version",
            "special_slots_observed", "special_numbers_found",
            "consolation_slots_observed", "consolation_numbers_found", "note",
        ]

    def tearDown(self):
        self.temp.cleanup()

    def write_fixture(self, missing_special=False, missing_consolation=False):
        row = {field: "" for field in self.raw_fields}
        row.update({
            "draw_seq": "GD-001",
            "date": "2026-10-30",
            "year": "2026",
            "month": "10",
            "day": "30",
            "prize_1": "0001",
            "prize_2": "0002",
            "prize_3": "0003",
        })
        for i in range(1, 11):
            row[f"special_{i}"] = f"{i:04d}"
            row[f"consol_{i}"] = f"{i + 10:04d}"
        for i in range(11, 16):
            row[f"special_{i}"] = ""
        if missing_special:
            row["special_10"] = ""
        if missing_consolation:
            row["consol_10"] = ""

        for path in (self.raw, self.normalized):
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.raw_fields)
                writer.writeheader()
                writer.writerow(row)

        with self.audit.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.audit_fields)
            writer.writeheader()
            writer.writerow({
                "date": "2026-10-30",
                "status": "parsed",
                "source_url": "https://example.invalid/draw",
                "fetched_at_utc": "2026-11-02T00:00:00Z",
                "content_sha256": "test",
                "parser_version": "test",
                "special_slots_observed": "15",
                "special_numbers_found": "10",
                "consolation_slots_observed": "10",
                "consolation_numbers_found": "10",
                "note": "",
            })

    def run_validation(self):
        with patch.object(validate_haolong, "RAW", self.raw), \
             patch.object(validate_haolong, "NORMALIZED", self.normalized), \
             patch.object(validate_haolong, "AUDIT", self.audit):
            return validate_haolong.validate(
                start=date(2026, 10, 30), end=date(2026, 10, 30)
            )

    def test_complete_23_number_draw_passes(self):
        self.write_fixture()
        report = self.run_validation()
        self.assertEqual(report["special_complete_rows"], 1)
        self.assertEqual(report["consolation_complete_rows"], 1)
        self.assertTrue(report["strict_complete"])

    def test_missing_special_fails_strict_validation(self):
        self.write_fixture(missing_special=True)
        report = self.run_validation()
        self.assertEqual(report["special_complete_rows"], 0)
        self.assertFalse(report["strict_complete"])

    def test_missing_consolation_fails_strict_validation(self):
        self.write_fixture(missing_consolation=True)
        report = self.run_validation()
        self.assertEqual(report["consolation_complete_rows"], 0)
        self.assertFalse(report["strict_complete"])


if __name__ == "__main__":
    unittest.main()
