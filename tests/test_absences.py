"""Unit-Tests für die Abwesenheits-Logik (weekly/data → Anzeige).

Pure functions, kein Netzwerk. Spiegelt die verifizierte cellState-Semantik aus
docs/superpowers/specs/2026-06-27-absence-from-weekly-data-design.md;
Lehrer-Regel seit ADR 0003 über orgId (wer ersetzt wen) statt cellState.
"""
import importlib.util
import json
import os
import unittest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("fu", os.path.join(_HERE, "scripts", "fetch_untis.py"))
fu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fu)

# timegrid: {startTime: (periodNr, start, end)} — Stunden 1..6 auf 0-basierte nr 1..6
TG = {800: (1, 800, 850), 850: (2, 850, 940), 945: (3, 945, 1035),
      1050: (4, 1050, 1140), 1150: (5, 1150, 1240), 1250: (6, 1250, 1340)}


ME = 7      # Lehrer-ID des geprüften Lehrers
OTHER = 99  # ein anderer Lehrer


def lesson(st, cs, *elements):
    """Periode an Startzeit `st` (Ende = Raster-Ende) mit Lehrer-Elementen (id, orgId)."""
    end = TG[st][2] if st in TG else st + 15
    return {"startTime": st, "endTime": end, "cellState": cs,
            "elements": [{"type": 2, "id": i, "orgId": o} for i, o in elements]}


def held(st):       # ich unterrichte regulär
    return lesson(st, "STANDARD", (ME, 0))


def replaced(st):   # ein anderer ersetzt mich
    return lesson(st, "SUBSTITUTION", (OTHER, ME))


def covering(st):   # ICH vertrete jemand anderen (SUBSTITUTION, aber anwesend!)
    return lesson(st, "SUBSTITUTION", (ME, OTHER))


def cancelled(st):
    return lesson(st, "CANCEL", (ME, 0))


class TeacherAbsence(unittest.TestCase):
    def entry(self, periods):
        return fu.teacher_absence_entry(periods, ME, TG)

    def test_fully_absent_returns_empty_string(self):
        self.assertEqual(self.entry([replaced(945), replaced(1050), cancelled(1150)]), "")

    def test_only_cancelled_lessons_counts_as_full_day(self):
        self.assertEqual(self.entry([cancelled(800), cancelled(850)]), "")

    def test_partial_absence_lists_periods(self):
        self.assertEqual(self.entry([held(800), held(850), replaced(945), cancelled(1050)]), "3–4")

    def test_separate_windows_are_not_merged_into_one_range(self):
        self.assertEqual(self.entry([replaced(800), held(850), replaced(945)]), "1, 3")

    def test_substitute_is_present_not_absent(self):
        # Bug 2: SUBSTITUTION, in der ICH vertrete, heißt anwesend
        self.assertIsNone(self.entry([held(800), covering(850), covering(945)]))

    def test_taken_over_break_supervision_is_not_full_absence(self):
        # Bug 1: übernommene Aufsicht (Startzeit nicht im Raster) machte "ganztägig weg"
        sup = lesson(1240, "SUBSTITUTION", (ME, OTHER))
        self.assertIsNone(self.entry([held(800), held(850), sup]))

    def test_cancel_alone_while_teaching_is_class_away_not_teacher(self):
        self.assertIsNone(self.entry([held(800), cancelled(850), cancelled(945)]))

    def test_cancel_counts_when_teacher_is_also_replaced(self):
        self.assertEqual(self.entry([held(800), replaced(850), cancelled(945)]), "2–3")

    def test_fully_present_returns_none(self):
        sup = lesson(840, "BREAKSUPERVISION", (ME, 0))
        self.assertIsNone(self.entry([held(800), sup]))

    def test_no_periods_returns_none(self):
        self.assertIsNone(self.entry([]))


class TeacherAbsenceRealDay(unittest.TestCase):
    """Echte weekly/data-Perioden aller Lehrer am 03.11.2026 (Fixture). Der Monitor
    meldet AlM, BrH, ChC (ab 7), DeF, FaM, GrM, PrA, SeM (5–6), WeN (5–6). Die Schätzung
    darf keinen Anwesenden melden; ChC/WeN sind aus dem Stundenplan nicht erkennbar."""
    def test_20261103(self):
        with open(os.path.join(_HERE, "tests", "fixtures", "absences",
                               "weekly_teachers_20261103.json"), encoding="utf-8") as f:
            fix = json.load(f)
        with open(os.path.join(_HERE, "tests", "fixtures", "absences",
                               "monitor.json"), encoding="utf-8") as f:
            tg = fu.build_timegrid([{"timeUnits": json.load(f)["timegrid"]}])
        got = {}
        for t in fix["teachers"]:
            r = fu.teacher_absence_entry(t["periods"], t["id"], tg)
            if r is not None:
                got[t["name"]] = r
        self.assertEqual(got, {"AlM": "", "BrH": "", "DeF": "", "FaM": "",
                               "GrM": "", "PrA": "", "SeM": "5"})


def cls(*pairs):
    return [{"startTime": st, "endTime": TG[st][2], "cellState": cs, "elements": []}
            for st, cs in pairs]


class ClassAbsence(unittest.TestCase):
    def test_full_day_cancel_is_absent(self):
        periods = cls((800, "CANCEL"), (850, "CANCEL"), (945, "CANCEL"))
        self.assertEqual(fu.class_absence_entry(periods, TG), "1–3")

    def test_single_cancel_is_not_absent(self):
        # eine einzelne Ausfallstunde ist kein "Klasse weg"-Signal
        periods = cls((800, "STANDARD"), (850, "CANCEL"), (945, "STANDARD"))
        self.assertIsNone(fu.class_absence_entry(periods, TG))

    def test_two_consecutive_cancel_is_absent(self):
        periods = cls((800, "STANDARD"), (945, "CANCEL"), (1050, "CANCEL"))
        self.assertEqual(fu.class_absence_entry(periods, TG), "3–4")

    def test_two_isolated_cancels_not_a_block(self):
        # Std 1 und Std 4 entfallen, aber nicht zusammenhängend → kein Block
        periods = cls((800, "CANCEL"), (850, "STANDARD"), (945, "STANDARD"), (1050, "CANCEL"))
        self.assertIsNone(fu.class_absence_entry(periods, TG))

    def test_substitution_counts_as_present_for_class(self):
        # vertretene Stunden = Klasse ist da; nur CANCEL zählt als weg
        periods = cls((800, "SUBSTITUTION"), (850, "SUBSTITUTION"), (945, "STANDARD"))
        self.assertIsNone(fu.class_absence_entry(periods, TG))


class ConsecutiveRuns(unittest.TestCase):
    def test_runs(self):
        self.assertEqual(fu._consecutive_runs([1, 2, 3, 5, 6, 9]), [[1, 2, 3], [5, 6], [9]])
        self.assertEqual(fu._consecutive_runs([]), [])
        self.assertEqual(fu._consecutive_runs([4]), [[4]])


if __name__ == "__main__":
    unittest.main()
