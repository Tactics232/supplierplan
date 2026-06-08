import unittest
from pathlib import Path

from tray.paths import resolve_data_dir


class TestResolveDataDir(unittest.TestCase):
    def test_neben_exe_wenn_beschreibbar(self):
        exe = Path("/opt/app")
        result = resolve_data_dir(exe, Path("/users/x/AppData/Local"),
                                  can_write=lambda p: True)
        self.assertEqual(result, exe)

    def test_localappdata_wenn_exe_readonly(self):
        exe = Path("/program files/app")
        result = resolve_data_dir(exe, Path("/users/x/AppData/Local"),
                                  can_write=lambda p: False)
        self.assertEqual(result, Path("/users/x/AppData/Local") / "Supplierplan")


if __name__ == "__main__":
    unittest.main()
