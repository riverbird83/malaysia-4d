import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scrape_haolong import FIELDS, parse_page


class HaolongParserTests(unittest.TestCase):\n    """Regression coverage for source row structure and fixed-width numbers."""
    def test_parse_main_prizes_and_preserve_15_special_slots(self):
        html = """
        <html><body><table>
        <tr><td><h2>Grand Dragon 4D 豪龙</h2></td></tr>
        <tr><td>Date: 04-07-2025 (Fri)</td></tr>
        <tr><td>1st Prize 首獎</td><td>7238</td></tr>
        <tr><td>2nd Prize 二獎</td><td>0866</td></tr>
        <tr><td>3rd Prize 三獎</td><td>2237</td></tr>
        <tr><td>Special 特別獎</td></tr>
        <tr><td>1911</td><td>5906</td><td>3508</td><td>----</td><td>3300</td></tr>
        <tr><td>5992</td><td>3789</td><td>----</td><td>----</td><td>0905</td></tr>
        <tr><td></td><td>2408</td><td>5170</td><td>0872</td><td></td></tr>
        <tr><td>Consolation 安慰獎</td></tr>
        <tr><td>0478</td><td>9218</td><td>0614</td><td>1713</td><td>2901</td></tr>
        <tr><td>0614</td><td>0771</td><td>4876</td><td>1506</td><td>0146</td></tr>
        <tr><td>Perdana Lottery 4D</td></tr>
        </table></body></html>
        """
        row = parse_page(html, date(2025, 7, 4))
        self.assertIsNotNone(row)
        self.assertEqual([row[f"prize_{i}"] for i in range(1, 4)], ["7238", "0866", "2237"])
        self.assertEqual(len([f for f in FIELDS if f.startswith("special_")]), 15)
        self.assertEqual(row["special_1"], "1911")
        self.assertEqual(row["special_4"], "")
        self.assertEqual(row["special_11"], "")
        self.assertEqual(row["special_12"], "2408")
        self.assertEqual(row["special_13"], "5170")
        self.assertEqual(row["special_14"], "0872")
        self.assertEqual(row["special_15"], "")
        self.assertEqual(row["consol_1"], "0478")
        self.assertEqual(row["consol_10"], "0146")
        self.assertEqual(row["draw_seq"], "")

    def test_wrong_page_date_is_rejected(self):
        html = """
        <h2>Grand Dragon 4D 豪龙</h2>
        <p>Date: 02-11-2026</p>
        <p>1st Prize | 0001</p><p>2nd Prize | 0002</p><p>3rd Prize | 0003</p>
        """
        self.assertIsNone(parse_page(html, date(2026, 11, 1)))

    def test_main_prize_missing_is_rejected(self):
        html = """
        <h2>Grand Dragon 4D 豪龙</h2>
        <p>Date: 01-11-2026</p>
        <p>1st Prize | 0001</p><p>2nd Prize | 0002</p>
        """
        self.assertIsNone(parse_page(html, date(2026, 11, 1)))


if __name__ == "__main__":
    unittest.main()
