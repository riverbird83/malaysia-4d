import unittest

from scripts.backfill_sportstoto_consolation import parse_4d2u_html, complete_consol


SAMPLE_4D2U = """
<html><body>
<div>Source Image: Sports Toto 4D</div>
<div>Date 07/06/2008 (Sat)</div>
<div>DrawID 3015/08</div>
<div>DrawNo #2609</div>
<div>First Prize Second Prize Third Prize</div>
<div>2108 6551 7100</div>
<div>Special Prize</div>
<div>4084 4648 6792 0096 2723 6528 1250 4472 1676 0603</div>
<div>Consolation Prize</div>
<div>0730 9772 0630 5493 5860 1446 9889 8169 3647 1831</div>
<div>Image: Toto 6/52Mega TOTO 6/52</div>
</body></html>
"""


class FourD2UParserTests(unittest.TestCase):
    def test_known_sports_toto_draw_3015(self):
        record = parse_4d2u_html(SAMPLE_4D2U, 3015, 2008, "2008-06-07")
        self.assertTrue(complete_consol(record))
        self.assertEqual(
            [record[f"consol_{i}"] for i in range(1, 11)],
            ["0730", "9772", "0630", "5493", "5860",
             "1446", "9889", "8169", "3647", "1831"],
        )

    def test_rejects_wrong_date(self):
        self.assertIsNone(parse_4d2u_html(SAMPLE_4D2U, 3015, 2008, "2008-06-08"))

    def test_rejects_wrong_draw_id(self):
        self.assertIsNone(parse_4d2u_html(SAMPLE_4D2U, 3016, 2008, "2008-06-07"))


if __name__ == "__main__":
    unittest.main()
