import os
import unittest
from pathlib import Path

from scripts import fetch_untis, fetch_trains


class TestOutputResolvers(unittest.TestCase):
    def setUp(self):
        for k in ("SUPPLIERPLAN_WEBROOT", "SUPPLIERPLAN_DATA"):
            os.environ.pop(k, None)

    def tearDown(self):
        for k in ("SUPPLIERPLAN_WEBROOT", "SUPPLIERPLAN_DATA"):
            os.environ.pop(k, None)

    def test_webroot_default_ist_base_dir(self):
        self.assertEqual(fetch_untis.resolve_webroot(), fetch_untis.BASE_DIR)

    def test_webroot_aus_env(self):
        os.environ["SUPPLIERPLAN_WEBROOT"] = "/tmp/web"
        self.assertEqual(fetch_untis.resolve_webroot(), Path("/tmp/web"))

    def test_data_out_default(self):
        self.assertEqual(fetch_untis.resolve_data_out(), fetch_untis.BASE_DIR / "data")

    def test_data_out_aus_env(self):
        os.environ["SUPPLIERPLAN_DATA"] = "/tmp/d"
        self.assertEqual(fetch_untis.resolve_data_out(), Path("/tmp/d"))

    def test_trains_data_out_aus_env(self):
        os.environ["SUPPLIERPLAN_DATA"] = "/tmp/d"
        self.assertEqual(fetch_trains.resolve_data_out(), Path("/tmp/d"))


if __name__ == "__main__":
    unittest.main()
