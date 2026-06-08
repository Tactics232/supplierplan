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


from tray.config_io import parse_config_text, render_config_env


class TestConfigIO(unittest.TestCase):
    def test_parse_ignoriert_kommentare_und_inline(self):
        text = "# Kommentar\nUNTIS_USER=Monitor\nOVERFLOW_PAGINATE=true   # an\n\n"
        self.assertEqual(parse_config_text(text), {
            "UNTIS_USER": "Monitor", "OVERFLOW_PAGINATE": "true",
        })

    def test_render_aktualisiert_vorhandenen_wert(self):
        existing = "# Login\nUNTIS_USER=Alt\nUNTIS_PASSWORD=geheim\n"
        out = render_config_env(existing, {"UNTIS_USER": "Neu"})
        self.assertIn("UNTIS_USER=Neu", out)
        self.assertIn("UNTIS_PASSWORD=geheim", out)
        self.assertIn("# Login", out)
        self.assertEqual(out.count("UNTIS_USER="), 1)

    def test_render_haengt_neue_keys_an(self):
        out = render_config_env("UNTIS_USER=Mon\n", {"SERVER_PORT": "8080"})
        self.assertIn("UNTIS_USER=Mon", out)
        self.assertIn("SERVER_PORT=8080", out)

    def test_render_passwort_mit_sonderzeichen_wird_nicht_zerstoert(self):
        out = render_config_env("", {"UNTIS_PASSWORD": "p#ss=wort"})
        self.assertIn("UNTIS_PASSWORD=p#ss=wort", out)

    def test_render_leeren_wert_setzt_leeres_feld(self):
        out = render_config_env("CLOUDFLARE_HOST=alt\n", {"CLOUDFLARE_HOST": ""})
        self.assertIn("CLOUDFLARE_HOST=", out)
        self.assertNotIn("CLOUDFLARE_HOST=alt", out)


from tray.autostart import enable_autostart, disable_autostart, is_autostart


class FakeRegistry:
    def __init__(self):
        self.store = {}
    def set_value(self, name, value):
        self.store[name] = value
    def delete_value(self, name):
        self.store.pop(name, None)
    def get_value(self, name):
        return self.store.get(name)


class TestAutostart(unittest.TestCase):
    def test_enable_setzt_eintrag(self):
        reg = FakeRegistry()
        enable_autostart(reg, "Supplierplan", "C:/app/Supplierplan.exe")
        self.assertEqual(reg.get_value("Supplierplan"), "C:/app/Supplierplan.exe")
        self.assertTrue(is_autostart(reg, "Supplierplan"))

    def test_disable_entfernt_eintrag(self):
        reg = FakeRegistry()
        enable_autostart(reg, "Supplierplan", "x")
        disable_autostart(reg, "Supplierplan")
        self.assertFalse(is_autostart(reg, "Supplierplan"))

    def test_is_autostart_false_wenn_fehlt(self):
        self.assertFalse(is_autostart(FakeRegistry(), "Supplierplan"))


if __name__ == "__main__":
    unittest.main()
