import unittest

from scripts.fetch_untis import compute_absent, extract_absent_periods


def _row(org=None, kuerzel="VtR", std="1", art="subst", klasse="1A",
         kuerzel_absent=False):
    return {
        "kuerzel": kuerzel,
        "org_kuerzel": org or "",
        "std": std,
        "art": art,
        "klasse": klasse,
        "kuerzel_absent": kuerzel_absent,
    }


class TestComputeAbsent(unittest.TestCase):
    def _absent_dict(self, groups, full=None):
        teachers, _ = compute_absent(groups, full)
        return dict(teachers)

    def test_komplett_abwesend_nur_kuerzel(self):
        # Lehrer in full_absent → keine Stundenangabe, egal wie viele Fehl-Stunden
        groups = {"VtR": [_row(org="FaM", std="1"), _row(org="FaM", std="2"),
                          _row(org="FaM", std="4")]}
        self.assertEqual(self._absent_dict(groups, {"FaM"})["FaM"], "")

    def test_teil_abwesend_zeigt_spanne(self):
        # Nicht in full_absent → Spanne min–max der Fehl-Stunden
        groups = {"VtR": [_row(org="WoR", std="5"), _row(org="WoR", std="9")]}
        self.assertEqual(self._absent_dict(groups)["WoR"], "5–9")

    def test_einzelne_stunde_zeigt_zahl(self):
        groups = {"VtR": [_row(org="SaI", std="6")]}
        self.assertEqual(self._absent_dict(groups)["SaI"], "6")

    def test_einzelne_stunde_auch_bei_full_absent_leer(self):
        # Wer komplett fehlt, zeigt nie eine Stunde — auch nicht bei nur einer
        groups = {"VtR": [_row(org="DeF", std="3")]}
        self.assertEqual(self._absent_dict(groups, {"DeF"})["DeF"], "")

    def test_cancel_zeile_macht_lehrer_abwesend(self):
        # type=cancel ohne Vertreter → der Lehrer selbst gilt als abwesend
        groups = {"NeS": [_row(org=None, kuerzel="NeS", std="0", art="cancel",
                               kuerzel_absent=True)]}
        self.assertIn("NeS", self._absent_dict(groups))

    def test_extract_absent_periods_dedupe(self):
        groups = {"VtR": [_row(org="A · B", std="1"), _row(org="A", std="2")]}
        ap = extract_absent_periods(groups)
        self.assertEqual(ap["A"], {"1", "2"})
        self.assertEqual(ap["B"], {"1"})


if __name__ == "__main__":
    unittest.main()
