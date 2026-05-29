import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.fetch_trains import atomic_write_json
from scripts.fetch_trains import classify_direction
from scripts.fetch_trains import extract_departure
from scripts.fetch_trains import split_by_direction


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


class TestSplitByDirection(unittest.TestCase):
    def setUp(self):
        self.tz = timezone(timedelta(hours=2))
        base = datetime(2026, 5, 28, 14, 0, tzinfo=self.tz)
        # 5 Abfahrten: 3 Richtung Wien, 2 weg
        self.legs = [
            _FakeLeg("S 50", "Wien Hauptbahnhof", base.replace(minute=10)),  # towards
            _FakeLeg("S 50", "St. Pölten Hbf",    base.replace(minute=15)),  # away (no "Wien")
            _FakeLeg("S 50", "Wien Westbahnhof",  base.replace(minute=20)),  # towards
            _FakeLeg("S 50", "Tulln",             base.replace(minute=25)),  # away
            _FakeLeg("REX", "Salzburg",           base.replace(minute=30)),  # away
        ]

    def test_split_mit_n1_pro_richtung(self):
        towards_list = ["Wien"]
        result = split_by_direction(self.legs, towards_list, n_per_direction=1)
        self.assertEqual(len(result["towards"]), 1)
        self.assertEqual(len(result["away"]), 1)
        self.assertEqual(result["towards"][0]["destination"], "Wien Hauptbahnhof")
        self.assertEqual(result["away"][0]["destination"], "St. Pölten Hbf")

    def test_split_mit_n2_pro_richtung(self):
        towards_list = ["Wien"]
        result = split_by_direction(self.legs, towards_list, n_per_direction=2)
        self.assertEqual(len(result["towards"]), 2)
        self.assertEqual(len(result["away"]), 2)

    def test_split_ueberspringt_cancelled(self):
        cancelled = _FakeLeg("S 50", "Wien Hauptbahnhof",
                             datetime(2026, 5, 28, 14, 5, tzinfo=self.tz),
                             cancelled=True)
        legs = [cancelled] + self.legs
        result = split_by_direction(legs, ["Wien"], n_per_direction=1)
        # Cancelled at 14:05 should NOT be taken; next towards is Wien Hauptbahnhof at 14:10
        self.assertNotEqual(result["towards"][0]["planned"], "14:05")
        self.assertEqual(result["towards"][0]["planned"], "14:10")


class TestAtomicWriteJson(unittest.TestCase):
    def test_schreibt_und_liest_korrekt_zurueck(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trains.json"
            data = {"station": "Test", "towards": [], "away": []}
            atomic_write_json(path, data)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, data)

    def test_hinterlaesst_kein_tmp_file_nach_erfolg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trains.json"
            atomic_write_json(path, {"k": "v"})
            self.assertFalse((Path(tmp) / "trains.json.tmp").exists())

    def test_ueberschreibt_bestehende_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trains.json"
            atomic_write_json(path, {"version": 1})
            atomic_write_json(path, {"version": 2})
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["version"], 2)


if __name__ == "__main__":
    unittest.main()
