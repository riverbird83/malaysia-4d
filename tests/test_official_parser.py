import unittest

from scraper_sportstoto import parse_official_page


OFFICIAL_DECEMBER_2006 = """<html><body>
<div>Draw Date :2/12/2006,Saturday Draw No. :2764/06 Prize payments guaranteed in full TOTO 4D First Prize Second Prize Third Prize 5279 6628 7945 Special Prize 1593 6007 1435 3781 4111 2137 4810 2917 0 5738 3218 0 Consolation Prize 4349 9309 1249 6938 9126 5935 7562 1415 0 8981 8820 0 Toto lotto games - chances to become a millionaire!</div>
<div>Draw Date :3/12/2006,Sunday Draw No. :2765/06 Prize payments guaranteed in full TOTO 4D First Prize Second Prize Third Prize 2161 7045 4390 Special Prize 1304 6771 5523 9273 7286 2811 9003 1163 0 1203 9278 0 Consolation Prize 0171 9778 8327 2211 3335 6146 7155 8092 0 4070 1495 0 Toto lotto games - chances to become a millionaire!</div>
</body></html>"""


class OfficialSportTotoParserTests(unittest.TestCase):
    def test_parses_multiple_draws_from_current_official_page_layout(self):
        records = parse_official_page(OFFICIAL_DECEMBER_2006, 2006, 12)
        self.assertEqual([r["draw_seq"] for r in records], [2764, 2765])
        self.assertEqual([r["date"] for r in records], ["2006-12-02", "2006-12-03"])
        self.assertEqual(
            [records[0][f"consol_{i}"] for i in range(1, 11)],
            ["4349", "9309", "1249", "6938", "9126", "5935", "7562", "1415", "8981", "8820"],
        )
        self.assertEqual(
            [records[1][f"consol_{i}"] for i in range(1, 11)],
            ["0171", "9778", "8327", "2211", "3335", "6146", "7155", "8092", "4070", "1495"],
        )

    def test_filters_requested_month_and_year(self):
        self.assertEqual(parse_official_page(OFFICIAL_DECEMBER_2006, 2006, 11), [])
        self.assertEqual(parse_official_page(OFFICIAL_DECEMBER_2006, 2007, 12), [])

    def test_keeps_leading_zeroes(self):
        records = parse_official_page(OFFICIAL_DECEMBER_2006, 2006, 12)
        self.assertEqual(records[1]["consol_1"], "0171")


if __name__ == "__main__":
    unittest.main()
