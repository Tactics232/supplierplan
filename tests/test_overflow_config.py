import unittest

from scripts.fetch_untis import parse_overflow_config


class TestParseOverflowConfig(unittest.TestCase):
    def test_defaults_wenn_leer(self):
        cfg = parse_overflow_config({})
        self.assertEqual(cfg, {
            "scale": True, "scale_min": 0.65,
            "reduce": True, "paginate": True, "page_seconds": 12,
        })

    def test_flags_aus(self):
        cfg = parse_overflow_config({
            "OVERFLOW_SCALE": "false",
            "OVERFLOW_REDUCE": "false",
            "OVERFLOW_PAGINATE": "false",
        })
        self.assertFalse(cfg["scale"])
        self.assertFalse(cfg["reduce"])
        self.assertFalse(cfg["paginate"])

    def test_scale_min_geklemmt(self):
        self.assertEqual(parse_overflow_config({"OVERFLOW_SCALE_MIN": "0.1"})["scale_min"], 0.3)
        self.assertEqual(parse_overflow_config({"OVERFLOW_SCALE_MIN": "2"})["scale_min"], 1.0)

    def test_scale_min_ungueltig_faellt_auf_default(self):
        self.assertEqual(parse_overflow_config({"OVERFLOW_SCALE_MIN": "abc"})["scale_min"], 0.65)

    def test_page_seconds_minimum(self):
        self.assertEqual(parse_overflow_config({"OVERFLOW_PAGE_SECONDS": "1"})["page_seconds"], 3)
        self.assertEqual(parse_overflow_config({"OVERFLOW_PAGE_SECONDS": "x"})["page_seconds"], 12)

    def test_inline_kommentar_wird_ignoriert(self):
        # load_config strippt keine Inline-Kommentare; parse_overflow_config muss
        # "true   # kommentar" trotzdem als True lesen (sonst sind Stufen still aus).
        cfg = parse_overflow_config({
            "OVERFLOW_PAGINATE":    "true   # Stufe 3",
            "OVERFLOW_SCALE":       "false  # aus",
            "OVERFLOW_SCALE_MIN":   "0.7 # kleinster Faktor",
            "OVERFLOW_PAGE_SECONDS": "15 # sekunden",
        })
        self.assertTrue(cfg["paginate"])
        self.assertFalse(cfg["scale"])
        self.assertEqual(cfg["scale_min"], 0.7)
        self.assertEqual(cfg["page_seconds"], 15)


if __name__ == "__main__":
    unittest.main()
