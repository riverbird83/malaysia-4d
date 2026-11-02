import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scrape_haolong import parse_page


class HaolongParserTests(unittest.TestCase):
    def test_parse_grand_dragon_block_and_keep_missing_specials_blank(self):
        html = """
        <html><body>
        <h2>Grand Dragon 4D 豪龙</h2>
        <p>Date: 01-11-2026 (Sun)</p>
        <p>1st Prize 首獎 | 0140</p>
        <p>2nd Prize 二獎 | 7264</p>
        <p>3rd Prize 三獎 | 6867</p>
        <p>Special 特別獎 0823 | ---- | ---- | 7883 | 3028
        0215 | 9929 | ---- | 6736 | 1821</p>
        <p>Consolation 安慰獎 4660 | 3248 | 0170 | 3574 | 4384
        5111 | 0208 | 1362 | 9122 | 4505</p>
        <h2>Perdana Lottery 4D</h2><p>1st Prize | 9999</p>
        </body></html>
        """
        row = parse_page(html, date(2026, 11, 1))
        self.assertIsNotNone(row)
        self.assertEqual(row["prize_1"], "0140")
        self.assertEqual(row["prize_2"], "7264")
        self.assertEqual(row["prize_3"], "6867")
        self.assertEqual(row["special_1"], "0823")
        self.assertEqual(row["special_2"], "")
        self.assertEqual(row["consol_1"], "4660")
        self.assertEqual(row["consol_10"], "4505")
        self.assertEqual(row["draw_seq"], "")

    def test_wrong_page_date_is_rejected(self):
        html = "<h2>Grand Dragon 4D 豪龙</h2><p>Date: 02-11-2026</p><p>1st Prize | 0001</p><p>2nd Prize | 0002</p><p>3rd Prize | 0003</p>"
        self.assertIsNone(parse_page(html, date(2026, 11, 1)))


if __name__ == "__main__":
    unittest.main()
