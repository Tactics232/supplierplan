"""Unit-Tests für die Entfall-Platzierung (CANCEL_PLACEMENT: section | inline).

Pure functions, kein Netzwerk. Prüft die in CONTEXT.md („Cancel placement")
festgelegte Semantik gegen build_day_content:
- section (Default): Entfälle in eigener Sektion, cancel-only-Lehrer ohne Block
- inline: Entfälle bleiben im Lehrer-Block, cancel-only-Lehrer mit vollem Kopf
"""
import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("fu", os.path.join(_HERE, "scripts", "fetch_untis.py"))
fu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fu)


def _row(kuerzel, std, sort_key, art, **extra):
    r = {
        "kuerzel": kuerzel, "org_kuerzel": "", "std": str(std), "sort_key": sort_key,
        "end_time": sort_key + 50, "day": "today", "fach": "M", "klasse": "1A",
        "art": art, "raum": "R1", "raum_org": "", "text": "",
    }
    r.update(extra)
    return r


TEACHERS = {
    "MueL": {"nachname": "Müller", "vorname": "Max"},
    "NeS":  {"nachname": "Schmidt", "vorname": "Nina"},
}


def _groups():
    # MueL: echte Vertretung (Std 2) + Entfall (Std 4); NeS: nur Entfall (Std 0)
    rows = [
        _row("MueL", 2, 850, "subst"),
        _row("MueL", 4, 1050, "cancel"),
        _row("NeS", 0, 700, "cancel", kuerzel_absent=True),
    ]
    return fu.group_by_teacher(rows)


class CancelPlacement(unittest.TestCase):
    def setUp(self):
        self._orig = fu.CANCEL_PLACEMENT

    def tearDown(self):
        fu.CANCEL_PLACEMENT = self._orig

    def test_section_mode_extracts_cancel_section(self):
        fu.CANCEL_PLACEMENT = "section"
        html = fu.build_day_content(_groups(), TEACHERS, "today")
        # eigene „Entfallende Stunden"-Sektion existiert
        self.assertIn('data-block="cancel"', html)
        # cancel-only-Lehrer NeS bekommt KEINEN eigenen Block
        self.assertNotIn('data-key="NeS"', html)
        # Lehrer mit regulärer Stunde behält seinen Block
        self.assertIn('data-key="MueL"', html)

    def test_inline_mode_keeps_cancels_in_blocks(self):
        fu.CANCEL_PLACEMENT = "inline"
        html = fu.build_day_content(_groups(), TEACHERS, "today")
        # keine separate Cancel-Sektion → JS-Cancel-Header bleibt inaktiv
        self.assertNotIn('data-block="cancel"', html)
        # cancel-only-Lehrer NeS bekommt einen vollen Block samt Kopf
        self.assertIn('data-key="NeS"', html)
        self.assertIn("Schmidt", html)
        # Lehrer mit gemischten Stunden behält ebenfalls seinen Block
        self.assertIn('data-key="MueL"', html)


if __name__ == "__main__":
    unittest.main()
