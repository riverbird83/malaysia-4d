import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_data import canonical_number


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


if __name__ == "__main__":
    unittest.main()
