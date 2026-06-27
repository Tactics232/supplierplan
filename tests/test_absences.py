"""Unit-Tests für die Abwesenheits-Logik (weekly/data → Anzeige).

Pure functions, kein Netzwerk. Spiegelt die verifizierte cellState-Semantik aus
docs/superpowers/specs/2026-06-27-absence-from-weekly-data-design.md.
"""
import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("fu", os.path.join(_HERE, "scripts", "fetch_untis.py"))
fu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fu)

# timegrid: {startTime: (periodNr, start, end)} — Stunden 1..6 auf 0-basierte nr 1..6
TG = {800: (1, 800, 850), 850: (2, 850, 940), 945: (3, 945, 1035),
      1050: (4, 1050, 1140), 1150: (5, 1150, 1240), 1250: (6, 1250, 1340)}


class TeacherAbsence(unittest.TestCase):
    def test_fully_absent_returns_empty_string(self):
        # nur vertretene/entfallene Stunden, keine anwesende → "" (nur Kürzel)
        periods = [(945, "SUBSTITUTION"), (1050, "SUBSTITUTION"), (1150, "CANCEL")]
        self.assertEqual(fu.teacher_absence_entry(periods, TG), "")

    def test_fully_absent_even_if_lessons_only_4_to_7(self):
        # der gemeldete Bug: ganztägig weg, hätte nur Std 4–6 → trotzdem nur Kürzel
        periods = [(1050, "SUBSTITUTION"), (1150, "SUBSTITUTION"), (1250, "CANCEL")]
        self.assertEqual(fu.teacher_absence_entry(periods, TG), "")

    def test_partial_absence_returns_range(self):
        periods = [(800, "STANDARD"), (850, "STANDARD"),
                   (945, "SUBSTITUTION"), (1050, "CANCEL")]
        self.assertEqual(fu.teacher_absence_entry(periods, TG), "3–4")

    def test_partial_single_missing_period(self):
        periods = [(800, "STANDARD"), (945, "SUBSTITUTION")]
        self.assertEqual(fu.teacher_absence_entry(periods, TG), "3")

    def test_fully_present_returns_none(self):
        periods = [(800, "STANDARD"), (850, "BREAKSUPERVISION")]
        self.assertIsNone(fu.teacher_absence_entry(periods, TG))

    def test_no_periods_returns_none(self):
        self.assertIsNone(fu.teacher_absence_entry([], TG))


class ClassAbsence(unittest.TestCase):
    def test_full_day_cancel_is_absent(self):
        periods = [(800, "CANCEL"), (850, "CANCEL"), (945, "CANCEL")]
        self.assertEqual(fu.class_absence_entry(periods, TG), "1–3")

    def test_single_cancel_is_not_absent(self):
        # eine einzelne Ausfallstunde ist kein "Klasse weg"-Signal
        periods = [(800, "STANDARD"), (850, "CANCEL"), (945, "STANDARD")]
        self.assertIsNone(fu.class_absence_entry(periods, TG))

    def test_two_consecutive_cancel_is_absent(self):
        periods = [(800, "STANDARD"), (945, "CANCEL"), (1050, "CANCEL")]
        self.assertEqual(fu.class_absence_entry(periods, TG), "3–4")

    def test_two_isolated_cancels_not_a_block(self):
        # Std 1 und Std 4 entfallen, aber nicht zusammenhängend → kein Block
        periods = [(800, "CANCEL"), (850, "STANDARD"), (945, "STANDARD"), (1050, "CANCEL")]
        self.assertIsNone(fu.class_absence_entry(periods, TG))

    def test_substitution_counts_as_present_for_class(self):
        # vertretene Stunden = Klasse ist da; nur CANCEL zählt als weg
        periods = [(800, "SUBSTITUTION"), (850, "SUBSTITUTION"), (945, "STANDARD")]
        self.assertIsNone(fu.class_absence_entry(periods, TG))


class ConsecutiveRuns(unittest.TestCase):
    def test_runs(self):
        self.assertEqual(fu._consecutive_runs([1, 2, 3, 5, 6, 9]), [[1, 2, 3], [5, 6], [9]])
        self.assertEqual(fu._consecutive_runs([]), [])
        self.assertEqual(fu._consecutive_runs([4]), [[4]])


if __name__ == "__main__":
    unittest.main()
