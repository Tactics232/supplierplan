import unittest

from scripts._layout_logic import fit_scale, distribute_uncapped, paginate_columns


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


class TestDistributeUncapped(unittest.TestCase):
    def test_alles_in_eine_spalte(self):
        self.assertEqual(distribute_uncapped([30, 30, 30], 100), [[0, 1, 2]])

    def test_umbruch_an_budgetgrenze(self):
        self.assertEqual(distribute_uncapped([60, 60, 30], 100), [[0], [1, 2]])

    def test_uebergrosser_block_bekommt_eigene_spalte(self):
        self.assertEqual(distribute_uncapped([150, 40], 100), [[0], [1]])

    def test_leere_eingabe(self):
        self.assertEqual(distribute_uncapped([], 100), [[]])


class TestPaginateColumns(unittest.TestCase):
    def test_passt_in_eine_seite(self):
        cols = [[0], [1], [2]]
        self.assertEqual(paginate_columns(cols, 4), [[[0], [1], [2]]])

    def test_chunkt_in_seiten_zu_max_cols(self):
        cols = [[0], [1], [2], [3], [4]]
        self.assertEqual(
            paginate_columns(cols, 2),
            [[[0], [1]], [[2], [3]], [[4]]],
        )

    def test_max_cols_unter_eins_wird_eins(self):
        self.assertEqual(paginate_columns([[0], [1]], 0), [[[0]], [[1]]])


if __name__ == "__main__":
    unittest.main()
