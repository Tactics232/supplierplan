"""Unit-Tests für den Lesson indicator (laufende / nächste Stunde).

Pure function, kein Netzwerk. Spiegelt die Zustands-Logik aus
docs/superpowers/plans/2026-06-27-design-anpassungen.md und ADR 0001
(Indicator ist immer sichtbar, rollt in den nächsten Schultag).
"""
import importlib.util
import os
import unittest
from datetime import date

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("fu", os.path.join(_HERE, "scripts", "fetch_untis.py"))
fu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fu)

# timegrid: {startTime: (periodNr, start, end)} — Stunden 1..6
TG = {800: (1, 800, 850), 850: (2, 850, 940), 945: (3, 945, 1035),
      1050: (4, 1050, 1140), 1150: (5, 1150, 1240), 1250: (6, 1250, 1340)}

THU = date(2026, 6, 25)   # Donnerstag (Schultag)
FRI = date(2026, 6, 26)   # Freitag
SAT = date(2026, 6, 27)   # Samstag (kein Schultag)


class LessonIndicator(unittest.TestCase):
    def test_running_midlesson(self):
        ind = fu.lesson_indicator(TG, 1000, THU, set())
        self.assertEqual(ind["state"], "running")
        self.assertEqual(ind["nr"], 3)
        self.assertEqual(ind["start"], "09:45")
        self.assertEqual(ind["end"], "10:35")
        self.assertEqual(ind["day_offset"], 0)

    def test_running_boundary_inclusive(self):
        # genau auf Stundenbeginn → läuft
        ind = fu.lesson_indicator(TG, 945, THU, set())
        self.assertEqual(ind["state"], "running")
        self.assertEqual(ind["nr"], 3)

    def test_break_shows_next_today(self):
        # 09:42 liegt in der Pause zwischen Std 2 (Ende 09:40) und Std 3 (Start 09:45)
        ind = fu.lesson_indicator(TG, 942, THU, set())
        self.assertEqual(ind["state"], "upcoming")
        self.assertEqual(ind["nr"], 3)
        self.assertEqual(ind["day_offset"], 0)
        self.assertEqual(ind["start"], "09:45")

    def test_before_first_lesson(self):
        ind = fu.lesson_indicator(TG, 730, THU, set())
        self.assertEqual(ind["state"], "upcoming")
        self.assertEqual(ind["nr"], 1)
        self.assertEqual(ind["day_offset"], 0)
        self.assertEqual(ind["start"], "08:00")

    def test_after_last_lesson_rolls_to_next_school_day(self):
        ind = fu.lesson_indicator(TG, 1400, THU, set())
        self.assertEqual(ind["state"], "upcoming")
        self.assertEqual(ind["nr"], 1)
        self.assertEqual(ind["start"], "08:00")
        self.assertEqual(ind["day_offset"], 1)
        self.assertEqual(ind["weekday_short"], fu.WEEKDAYS_SHORT[FRI.weekday()])  # "Fr"

    def test_weekend_rolls_to_monday(self):
        ind = fu.lesson_indicator(TG, 1000, SAT, set())
        self.assertEqual(ind["state"], "upcoming")
        self.assertEqual(ind["nr"], 1)
        nxt = fu.next_school_day(SAT, set())
        self.assertEqual(ind["day_offset"], (nxt - SAT).days)
        self.assertEqual(ind["weekday_short"], fu.WEEKDAYS_SHORT[nxt.weekday()])  # "Mo"

    def test_holiday_today_rolls_forward(self):
        # Donnerstag ist Feiertag → nächster Schultag Freitag
        ind = fu.lesson_indicator(TG, 1000, THU, {THU})
        self.assertEqual(ind["state"], "upcoming")
        self.assertEqual(ind["day_offset"], 1)
        self.assertEqual(ind["weekday_short"], fu.WEEKDAYS_SHORT[FRI.weekday()])

    def test_empty_timegrid_returns_none(self):
        self.assertIsNone(fu.lesson_indicator({}, 1000, THU, set()))


if __name__ == "__main__":
    unittest.main()
