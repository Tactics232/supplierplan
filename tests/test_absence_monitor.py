"""Tests für die Abwesenheits-Quelle "monitor" (ADR 0003).

Fixtures = echte Antworten des WebUntis-Monitor-Endpunkts (Format "Roda Roda 2"),
reduziert auf absentElements, plus das echte Zeitraster der Schule.
"""
import importlib.util
import json
import os
import unittest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("fu", os.path.join(_HERE, "scripts", "fetch_untis.py"))
fu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fu)

with open(os.path.join(_HERE, "tests", "fixtures", "absences", "monitor.json"), encoding="utf-8") as f:
    FIX = json.load(f)
TG = fu.build_timegrid([{"timeUnits": FIX["timegrid"]}])


def bar(day):
    return fu.monitor_absence_entries(FIX["days"][day], TG)


class MonitorRealDays(unittest.TestCase):
    def test_20261103_matches_monitor_in_board_numbering(self):
        # Monitor-Soll: AlM, BrH, ChC (ab 8), DeF, FaM, GrM, PrA, SeM (6-7), WeN (6-7)
        # → Board-Zählung (0. Stunde) eins niedriger.
        self.assertEqual(bar("20261103")["teachers"], [
            ["AlM", ""], ["BrH", ""], ["ChC", "ab 7"], ["DeF", ""], ["FaM", ""],
            ["GrM", ""], ["PrA", ""], ["SeM", "5–6"], ["WeN", "5–6"]])
        self.assertEqual(bar("20261103")["classes"], [])

    def test_multiple_windows_listed_separately(self):
        # BoB 21.10.: 08:55–09:45 und 11:00–11:50
        self.assertIn(["BoB", "2, 4"], bar("20261021")["teachers"])

    def test_from_starting_mid_period(self):
        # DaS 21.10.: FROM 12:55 → Stunde, in die 12:55 fällt
        self.assertIn(["DaS", "ab 6"], bar("20261021")["teachers"])

    def test_from_to_over_several_periods(self):
        # AlC 22.10.: 08:00–11:50
        self.assertIn(["AlC", "1–4"], bar("20261022")["teachers"])


class WindowFormat(unittest.TestCase):
    def w(self, typ, s, e):
        return {"type": typ, "startTime": s, "endTime": e}

    def test_all_day_wins(self):
        self.assertEqual(fu.format_absence_windows(
            [self.w("FROM_TO", 800, 850), self.w("ALL_DAY", 700, 1725)], TG), "")

    def test_single_period(self):
        self.assertEqual(fu.format_absence_windows([self.w("FROM_TO", 855, 945)], TG), "2")

    def test_until_type(self):
        self.assertEqual(fu.format_absence_windows([self.w("TO", 700, 1150)], TG), "bis 4")

    def test_from_in_last_period_stays_ab(self):
        last = max(nr for nr, _, _ in TG.values())
        start = [s for nr, s, _ in TG.values() if nr == last][0]
        self.assertEqual(fu.format_absence_windows([self.w("FROM", start, 1725)], TG), f"ab {last}")

    def test_unknown_type_falls_back_to_range(self):
        self.assertEqual(fu.format_absence_windows([self.w("WHATEVER", 1000, 1150)], TG), "3–4")

    def test_skip_names_are_not_listed(self):
        els = [{"elementType": 2, "elementName": "Z Entfall",
                "absences": [self.w("ALL_DAY", 700, 1725)]}]
        fu.configure_skip_teachers("Z Entfall")
        self.assertEqual(fu.monitor_absence_entries(els, TG)["teachers"], [])

    def test_classes_from_element_type_1(self):
        els = [{"elementType": 1, "elementName": "2A",
                "absences": [self.w("FROM_TO", 800, 1150)]}]
        self.assertEqual(fu.monitor_absence_entries(els, TG)["classes"], [["2A", "1–4"]])


class MonitorUrl(unittest.TestCase):
    def test_parses_school_and_decoded_format(self):
        self.assertEqual(fu.parse_monitor_url(
            "https://s921092.webuntis.com/WebUntis/monitor?school=s921092&monitorType=subst&format=Roda%20Roda%202"),
            ("s921092", "Roda Roda 2"))

    def test_missing_link(self):
        with self.assertRaises(ValueError):
            fu.parse_monitor_url("")

    def test_missing_format(self):
        with self.assertRaises(ValueError):
            fu.parse_monitor_url("https://x.webuntis.com/WebUntis/monitor?school=s1")


class SummaryBar(unittest.TestCase):
    def test_unavailable_is_distinct_from_empty(self):
        html_un = fu.render_summary_bar(fu.ABSENCES_UNAVAILABLE, fu.ABSENCES_UNAVAILABLE)
        html_empty = fu.render_summary_bar([], [])
        self.assertIn("nicht verfügbar", html_un)
        self.assertIn("sum-unavailable", html_un)
        self.assertNotIn("nicht verfügbar", html_empty)

    def test_absence_source_parsing(self):
        self.assertEqual(fu.parse_absence_source(""), "monitor")
        self.assertEqual(fu.parse_absence_source("Weekly"), "weekly")
        self.assertEqual(fu.parse_absence_source("quatsch"), "monitor")


if __name__ == "__main__":
    unittest.main()
