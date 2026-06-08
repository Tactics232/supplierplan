import unittest

from scripts._layout_logic import fit_scale


class TestFitScale(unittest.TestCase):
    def test_passt_ohne_skalierung(self):
        self.assertEqual(fit_scale(100, 200, 0.65), 1.0)

    def test_exakt_passend_bleibt_1(self):
        self.assertEqual(fit_scale(100, 100, 0.65), 1.0)

    def test_skaliert_auf_groessten_passenden_faktor(self):
        self.assertEqual(fit_scale(120, 100, 0.6), 0.80)

    def test_geht_nicht_unter_min(self):
        self.assertEqual(fit_scale(200, 100, 0.65), 0.65)

    def test_available_null_gibt_min(self):
        self.assertEqual(fit_scale(100, 0, 0.65), 0.65)

    def test_leerer_inhalt_bleibt_1(self):
        self.assertEqual(fit_scale(0, 100, 0.65), 1.0)


if __name__ == "__main__":
    unittest.main()
