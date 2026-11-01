import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from normalize_data import normalize_number, normalize_file


class NormalizeDataTests(unittest.TestCase):
    def test_four_digit_padding_and_float_artifact(self):
        self.assertEqual(normalize_number("19"), "0019")
        self.assertEqual(normalize_number("893.0"), "0893")
        self.assertEqual(normalize_number("0012"), "0012")
        self.assertEqual(normalize_number(""), "")

    def test_invalid_value_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_number("12A4")

    def test_source_is_preserved_and_output_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.csv"
            output = Path(directory) / "normalized.csv"
            original = "date,prize_1,consol_1\n2025-01-01,19,893.0\n"
            source.write_text(original, encoding="utf-8")
            report = normalize_file(source, output)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "date,prize_1,consol_1\n2025-01-01,0019,0893\n",
            )
            self.assertEqual(report["rows"], 1)


if __name__ == "__main__":
    unittest.main()
