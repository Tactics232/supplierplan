"""Tests für die abgeleitete Klassen-Abwesenheit (ADR 0004).

Im monitor-Modus gilt eine Klasse zusätzlich als ganztägig abwesend, wenn ALLE ihre
Stunden des Tages entfallen (Ausflug nur über Lehrer-Abwesenheiten erfasst).
Fixture = echte weekly/data-Perioden aller Klassen am 03.11.2026, reduziert auf
startTime + cellState (2A/2B/2C auf Ausflug, DFK ohne Stunden).
"""
import importlib.util
import json
import os
import unittest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("fu", os.path.join(_HERE, "scripts", "fetch_untis.py"))
fu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fu)

with open(os.path.join(_HERE, "tests", "fixtures", "absences", "weekly_classes_20261103.json"),
          encoding="utf-8") as f:
    FIX = json.load(f)


class FullyCancelled(unittest.TestCase):
    def test_all_cancel(self):
        self.assertTrue(fu.class_fully_cancelled(FIX["classes"]["2A"]))

    def test_one_lesson_held(self):
        self.assertFalse(fu.class_fully_cancelled(
            [{"startTime": 800, "cellState": "CANCEL"},
             {"startTime": 855, "cellState": "STANDARD"}]))

    def test_no_lessons_is_not_absent(self):
        self.assertFalse(fu.class_fully_cancelled([]))
        self.assertFalse(fu.class_fully_cancelled(FIX["classes"]["DFK"]))


class DerivedRealDay(unittest.TestCase):
    def test_20261103_excursion(self):
        self.assertEqual(fu.derived_class_absences(FIX["classes"]), ["2A", "2B", "2C"])


class Merge(unittest.TestCase):
    def test_derived_added_as_all_day(self):
        self.assertEqual(fu.merge_class_absences([], ["2B", "2A"]),
                         [["2A", ""], ["2B", ""]])

    def test_monitor_entry_wins(self):
        self.assertEqual(fu.merge_class_absences([["2A", "2–4"]], ["2A", "3C"]),
                         [["2A", "2–4"], ["3C", ""]])

    def test_nothing_derived(self):
        self.assertEqual(fu.merge_class_absences([["1A", "ab 5"]], []), [["1A", "ab 5"]])


class ConfigFlag(unittest.TestCase):
    def test_default_on(self):
        self.assertTrue(fu.parse_derive_classes(None))
        self.assertTrue(fu.parse_derive_classes(""))
        self.assertTrue(fu.parse_derive_classes("true"))
        self.assertTrue(fu.parse_derive_classes("quatsch"))

    def test_off(self):
        self.assertFalse(fu.parse_derive_classes("false"))
        self.assertFalse(fu.parse_derive_classes(" False "))


class FakeUntis:
    def __init__(self, periods, fail=False):
        self.periods, self.fail, self.calls = periods, fail, []

    def get_element_periods(self, element_type, element_id, date_obj):
        self.calls.append((element_type, element_id))
        if self.fail:
            raise OSError("timeout")
        return self.periods[element_id]


class FetchClassPeriods(unittest.TestCase):
    def test_queries_every_class_as_type_1(self):
        klassen = [{"id": 1, "name": "2A"}, {"id": 2, "name": "3C"}]
        u = FakeUntis({1: FIX["classes"]["2A"], 2: FIX["classes"]["3C"]})
        got = fu.fetch_class_periods(u, klassen, None)
        self.assertEqual(set(got), {"2A", "3C"})
        self.assertEqual(u.calls, [(1, 1), (1, 2)])

    def test_error_propagates(self):
        with self.assertRaises(OSError):
            fu.fetch_class_periods(FakeUntis({}, fail=True), [{"id": 1, "name": "2A"}], None)


if __name__ == "__main__":
    unittest.main()
