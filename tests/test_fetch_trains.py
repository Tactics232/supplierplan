import unittest

from scripts.fetch_trains import classify_direction


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
