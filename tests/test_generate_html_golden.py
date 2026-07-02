"""Charakterisierungs-Test (Golden File) für generate_html.

Sichert den kompletten HTML-Output gegen eine eingefrorene Referenz ab, damit
der DisplaySettings-Umbau (Baustelle 1) beweisbar byte-identisch bleibt: gleiche
Werte, andere Behälter. now_local() wird auf einen festen Zeitpunkt eingefroren
(sonst wandern Datum + Cache-Bust im Output).

Das Fixture setzt bewusst mehrere Nicht-Default-Config-Werte (theme=light,
eigener plan_title, compact/max_columns, ein Text-Badge „ub", ein Entfall), damit
die Config→HTML-Zuordnung mit in der Referenz steckt.

Referenz neu erzeugen (nur absichtlich!):  GOLDEN_UPDATE=1 python -m unittest ...
"""
import importlib.util
import os
import unittest
from datetime import datetime, timezone, date

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "fu", os.path.join(_HERE, "scripts", "fetch_untis.py"))
fu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fu)

_GOLDEN = os.path.join(_HERE, "tests", "golden", "generate_html_basic.html")
# Fester, tz-bewusster Zeitpunkt → timestamp()/strftime deterministisch auf jeder Maschine.
_FROZEN = datetime(2026, 5, 28, 10, 15, 30, tzinfo=timezone.utc)


def _row(kuerzel, std, sort_key, art, day="today", **extra):
    r = {
        "kuerzel": kuerzel, "org_kuerzel": "", "std": str(std), "sort_key": sort_key,
        "end_time": sort_key + 50, "day": day, "fach": "M", "klasse": "1A",
        "art": art, "raum": "R1", "raum_org": "", "text": "",
    }
    r.update(extra)
    return r


_TEACHERS = {
    "MueL": {"nachname": "Müller", "vorname": "Max"},
    "NeS":  {"nachname": "Schmidt", "vorname": "Nina"},
}


def _fixture():
    """Repräsentatives, aber stabiles Board: heute + morgen, echte Vertretung,
    Entfall, ein Text-Badge, ein Raumwechsel."""
    today_rows = [
        _row("MueL", 2, 850, "subst", org_kuerzel="ScB", text="ub"),
        _row("MueL", 4, 1050, "cancel"),
        _row("NeS", 0, 700, "cancel", kuerzel_absent=True),
    ]
    tom_rows = [
        _row("MueL", 3, 950, "roomchange", day="tomorrow", raum="R2", raum_org="R1"),
        _row("NeS", 5, 1150, "cancel", day="tomorrow", kuerzel_absent=True),
    ]
    indicator = {"state": "running", "nr": 3, "start": "10:00",
                 "end": "10:50", "day_offset": 0}
    return {
        "groups_today": fu.group_by_teacher(today_rows),
        "groups_tomorrow": fu.group_by_teacher(tom_rows),
        "today_date": date(2026, 5, 28),
        "tomorrow_date": date(2026, 5, 29),
        "teacher_lookup": _TEACHERS,
        "indicator": indicator,
        "import_time": datetime(2026, 5, 28, 7, 32, tzinfo=timezone.utc),
    }


def _render():
    """Ruft generate_html mit dem Fixture + fester Config.

    NUR DIESE FUNKTION ändert sich beim DisplaySettings-Umbau (Signatur/Behälter);
    der erzeugte HTML-String (das Golden File) bleibt byte-identisch.
    """
    fx = _fixture()
    settings = fu.DisplaySettings.from_config({
        "PLAN_TITLE": "Vertretungsplan",
        "LOGO_FILE": "logo.png",
        "SHOW_LOGO": "true",
        "THEME": "light",
        "SHOW_CLOCK": "true",
        "TIMEZONE": "Europe/Vienna",
        "COMPACT_COL_WIDTH_PX": "300",
        "MAX_COLUMNS": "3",
        "SCHOOL_NAME": "Test-Schule",
        "SCHOOL_TYPE": "MS",
        "SCHOOL_LOCATION": "Wien",
        "CANCEL_PLACEMENT": "section",
        "PWA_ORIENTATION": "any",
        "TEXT_BADGES": "b,ub,MA",
        "TRAIN_STATION": "",
    })
    return fu.generate_html(
        fx["groups_today"], fx["groups_tomorrow"],
        fx["today_date"], fx["tomorrow_date"],
        fx["teacher_lookup"], fx["indicator"],
        import_time=fx["import_time"],
        settings=settings,
    )


class GenerateHtmlGolden(unittest.TestCase):
    def setUp(self):
        self._orig_now = fu.now_local
        fu.now_local = lambda: _FROZEN

    def tearDown(self):
        fu.now_local = self._orig_now

    def test_output_matches_golden(self):
        html = _render()
        if os.environ.get("GOLDEN_UPDATE") == "1" or not os.path.exists(_GOLDEN):
            os.makedirs(os.path.dirname(_GOLDEN), exist_ok=True)
            with open(_GOLDEN, "w", encoding="utf-8") as f:
                f.write(html)
            self.skipTest("Golden File (neu) geschrieben — erneut laufen zum Vergleich")
        with open(_GOLDEN, encoding="utf-8") as f:
            golden = f.read()
        self.assertEqual(html, golden,
                         "generate_html-Output weicht vom Golden File ab "
                         "(GOLDEN_UPDATE=1 nur bei bewusster Änderung)")


if __name__ == "__main__":
    unittest.main()
