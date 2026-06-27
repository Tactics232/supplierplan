"""Unit-Tests für die Skipped-day-Logik (übersprungene freie Schultage).

Pure functions, kein Netzwerk. Vokabular: CONTEXT.md „Skipped day".
Wochenenden werden nie angezeigt; Untis-`name` wo brauchbar, sonst
Feiertag (Einzeltag) / Ferien (Block).
"""
import importlib.util
import os
import unittest
from datetime import date

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("fu", os.path.join(_HERE, "scripts", "fetch_untis.py"))
fu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fu)


class BuildHolidayInfo(unittest.TestCase):
    def test_named_single_day(self):
        info = fu.build_holiday_info([
            {"name": "Fronleichnam", "startDate": 20260604, "endDate": 20260604},
        ])
        self.assertEqual(info[date(2026, 6, 4)], ("Fronleichnam", False))

    def test_generic_ferien_name_dropped(self):
        info = fu.build_holiday_info([
            {"name": "Ferien5", "startDate": 20260102, "endDate": 20260106},
        ])
        self.assertEqual(info[date(2026, 1, 2)], (None, True))
        self.assertEqual(info[date(2026, 1, 6)], (None, True))

    def test_date_name_dropped(self):
        info = fu.build_holiday_info([
            {"name": "1.1.", "startDate": 20260101, "endDate": 20260101},
        ])
        self.assertEqual(info[date(2026, 1, 1)], (None, False))

    def test_named_multiday(self):
        info = fu.build_holiday_info([
            {"name": "Sommerferien", "startDate": 20260704, "endDate": 20260906},
        ])
        self.assertEqual(info[date(2026, 7, 4)], ("Sommerferien", True))


class SkippedFreeDays(unittest.TestCase):
    def test_pure_weekend_gap_is_empty(self):
        # Fr 26.6. → Mo 29.6.: dazwischen nur Sa/So
        out = fu.skipped_free_days(date(2026, 6, 26), date(2026, 6, 29), {})
        self.assertEqual(out, [])

    def test_named_holiday_after_weekend(self):
        # Fr 26.6. → Di 30.6.: Sa/So (weg) + Mo 29.6. Fronleichnam
        info = {date(2026, 6, 29): ("Fronleichnam", False)}
        out = fu.skipped_free_days(date(2026, 6, 26), date(2026, 6, 30), info)
        self.assertEqual(out, [("Fronleichnam", "Mo")])

    def test_two_named_days_weekend_excluded(self):
        # Mi 24.6. → Mo 29.6.: Do Fronleichnam, Fr schulautonom frei, Sa/So weg
        info = {date(2026, 6, 25): ("Fronleichnam", False),
                date(2026, 6, 26): ("schulautonom frei", False)}
        out = fu.skipped_free_days(date(2026, 6, 24), date(2026, 6, 29), info)
        self.assertEqual(out, [("Fronleichnam", "Do"), ("schulautonom frei", "Fr")])

    def test_multiday_ferien_block(self):
        # Fr 26.6. → Mo 6.7.: Ferienwoche Mo 29.6.–Fr 3.7. (kein Name), WE drumrum weg
        info = {date(2026, 6, d): (None, True) for d in (29, 30)}
        info.update({date(2026, 7, d): (None, True) for d in (1, 2, 3)})
        out = fu.skipped_free_days(date(2026, 6, 26), date(2026, 7, 6), info)
        self.assertEqual(out, [("Ferien", "Mo–Fr")])

    def test_single_unnamed_feiertag(self):
        info = {date(2026, 6, 29): (None, False)}
        out = fu.skipped_free_days(date(2026, 6, 26), date(2026, 6, 30), info)
        self.assertEqual(out, [("Feiertag", "Mo")])


if __name__ == "__main__":
    unittest.main()
