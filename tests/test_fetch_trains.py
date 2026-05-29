import unittest
from datetime import datetime, timedelta, timezone

from scripts.fetch_trains import classify_direction
from scripts.fetch_trains import extract_departure


class _FakeLeg:
    """Duck-typed pyhafas StationBoardLeg-Stub für Tests."""
    def __init__(self, name, direction, planned, delay=None, cancelled=False, platform=None):
        self.name = name
        self.direction = direction
        self.dateTime = planned
        self.delay = delay
        self.cancelled = cancelled
        self.platform = platform


class TestExtractDeparture(unittest.TestCase):
    def setUp(self):
        self.tz = timezone(timedelta(hours=2))
        self.planned = datetime(2026, 5, 28, 14, 23, tzinfo=self.tz)

    def test_puenktlicher_zug(self):
        leg = _FakeLeg("S 50", "Wien Hauptbahnhof", self.planned)
        result = extract_departure(leg)
        self.assertEqual(result["line"], "S 50")
        self.assertEqual(result["destination"], "Wien Hauptbahnhof")
        self.assertEqual(result["planned"], "14:23")
        self.assertEqual(result["actual"], "14:23")
        self.assertEqual(result["delay_minutes"], 0)
        self.assertFalse(result["cancelled"])

    def test_zug_mit_verspaetung_2min(self):
        leg = _FakeLeg("S 50", "St. Pölten", self.planned, delay=timedelta(minutes=2))
        result = extract_departure(leg)
        self.assertEqual(result["planned"], "14:23")
        self.assertEqual(result["actual"], "14:25")
        self.assertEqual(result["delay_minutes"], 2)

    def test_cancelled_zug(self):
        leg = _FakeLeg("S 50", "Wien Hbf", self.planned, cancelled=True)
        result = extract_departure(leg)
        self.assertTrue(result["cancelled"])

    def test_platform_string_uebernommen(self):
        leg = _FakeLeg("S 50", "Wien Hbf", self.planned, platform="3")
        self.assertEqual(extract_departure(leg)["platform"], "3")

    def test_platform_kann_none_sein(self):
        leg = _FakeLeg("S 50", "Wien Hbf", self.planned, platform=None)
        self.assertIsNone(extract_departure(leg)["platform"])


class TestClassifyDirection(unittest.TestCase):
    def setUp(self):
        self.towards = ["Hbf", "Westbf", "Praterstern", "Heiligenstadt"]

    def test_destination_in_whitelist_is_towards(self):
        self.assertEqual(
            classify_direction("Wien Hbf", self.towards),
            "towards",
        )

    def test_substring_match_in_longer_destination_is_towards(self):
        self.assertEqual(
            classify_direction("St. Pölten Hbf via Tullnerfeld", self.towards),
            "towards",  # "Hbf" matcht — auch via Substring im längeren Namen
        )

    def test_completely_unrelated_destination_is_away(self):
        self.assertEqual(
            classify_direction("Salzburg Hauptbahnhof", ["Westbf", "Praterstern"]),
            "away",
        )

    def test_matching_is_case_insensitive(self):
        self.assertEqual(
            classify_direction("wien hbf", ["HBF"]),
            "towards",
        )

    def test_empty_whitelist_returns_away(self):
        self.assertEqual(
            classify_direction("Wien Hbf", []),
            "away",
        )


if __name__ == "__main__":
    unittest.main()
