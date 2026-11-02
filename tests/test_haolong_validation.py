import csv
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_haolong as validator


class HaolongValidationTests(unittest.TestCase):
    def _write(self, path, fields, row):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(row)

    def _fixture(self, root, status="parsed"):
        raw_fields = ["date", "prize_1", "prize_2", "prize_3"]
        raw_fields += [f"special_{i}" for i in range(1, 16)]
        raw_fields += [f"consol_{i}" for i in range(1, 11)]
        row = {
            "date": "2026-01-01",
            "prize_1": "0123", "prize_2": "4567", "prize_3": "8901",
        }
        row.update({f"special_{i}": f"{i:04d}" for i in range(1, 11)})
        row.update({f"special_{i}": "" for i in range(11, 16)})
        row.update({f"consol_{i}": f"{i + 100:04d}" for i in range(1, 11)})
        audit_fields = [
            "date", "status", "http_status", "source_url", "fetched_at_utc",
            "content_sha256", "parser_version", "special_slots_observed",
            "special_numbers_found", "consolation_slots_observed",
            "consolation_numbers_found", "note",
        ]
        audit_row = {
            "date": "2026-01-01", "status": status, "http_status": "200",
            "source_url": "https://example.test/2026-01-01",
            "fetched_at_utc": "2026-01-02T00:00:00Z",
            "content_sha256": "abc", "parser_version": "test",
            "special_slots_observed": "15", "special_numbers_found": "10",
            "consolation_slots_observed": "10", "consolation_numbers_found": "10",
            "note": "",
        }
        raw = root / "raw.csv"
        normalized = root / "normalized.csv"
        audit = root / "audit.csv"
        self._write(raw, raw_fields, row)
        self._write(normalized, raw_fields, row)
        self._write(audit, audit_fields, audit_row)
        return raw, normalized, audit

    def test_special_layout_15_cells_means_10_prize_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, normalized, audit = self._fixture(root)
            old = (validator.RAW, validator.NORMALIZED, validator.AUDIT)
            try:
                validator.RAW, validator.NORMALIZED, validator.AUDIT = raw, normalized, audit
                report = validator.validate(date(2026, 1, 1), date(2026, 1, 1))
            finally:
                validator.RAW, validator.NORMALIZED, validator.AUDIT = old
        self.assertEqual(report["special_layout_cells_observed"], 15)
        self.assertEqual(report["special_numbers_found"], 10)
        self.assertEqual(report["special_prize_completeness_rate"], 1.0)
        self.assertEqual(report["consolation_prize_completeness_rate"], 1.0)
        self.assertTrue(report["normalized_matches_raw"])
        self.assertTrue(report["strict_complete"])

    def test_operator_not_found_is_unresolved_not_non_draw(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, normalized, audit = self._fixture(root, status="operator_not_found")
            old = (validator.RAW, validator.NORMALIZED, validator.AUDIT)
            try:
                validator.RAW, validator.NORMALIZED, validator.AUDIT = raw, normalized, audit
                report = validator.validate(date(2026, 1, 1), date(2026, 1, 1))
            finally:
                validator.RAW, validator.NORMALIZED, validator.AUDIT = old
        self.assertEqual(report["unresolved_dates_count"], 1)
        self.assertEqual(report["confirmed_non_draw_days"], 0)
        self.assertFalse(report["strict_complete"])


if __name__ == "__main__":
    unittest.main()
