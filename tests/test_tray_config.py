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
    def test_parse_ignoriert_kommentar_und_leerzeilen(self):
        text = "# Kommentar\nUNTIS_USER=Monitor\n\nSERVER_PORT=8080\n"
        self.assertEqual(parse_config_text(text), {
            "UNTIS_USER": "Monitor", "SERVER_PORT": "8080",
        })

    def test_parse_erhaelt_rautezeichen_im_wert(self):
        # Passwort/Token mit '#' darf beim Lesen NICHT abgeschnitten werden
        # (sonst Round-Trip-Korruption Laden->Speichern).
        text = "UNTIS_PASSWORD=p#ss=wort\n"
        self.assertEqual(parse_config_text(text), {"UNTIS_PASSWORD": "p#ss=wort"})

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


from tray.server import is_path_allowed


class TestServerGuard(unittest.TestCase):
    def test_normale_dateien_erlaubt(self):
        self.assertTrue(is_path_allowed("/index.html"))
        self.assertTrue(is_path_allowed("/css/style.css"))
        self.assertTrue(is_path_allowed("/"))

    def test_env_und_dotfiles_blockiert(self):
        self.assertFalse(is_path_allowed("/config.env"))
        self.assertFalse(is_path_allowed("/.git/config"))
        self.assertFalse(is_path_allowed("/secret.env"))

    def test_traversal_blockiert(self):
        self.assertFalse(is_path_allowed("/../config.env"))
        self.assertFalse(is_path_allowed("/..%2fconfig.env"))


from datetime import datetime

from tray.schedule import next_run_time, parse_times


class TestNextRunTime(unittest.TestCase):
    TIMES = ["07:35", "11:00", "16:00"]

    def test_vor_allen_zeiten_heute(self):
        now = datetime(2026, 6, 27, 6, 0)
        self.assertEqual(next_run_time(now, self.TIMES),
                         datetime(2026, 6, 27, 7, 35))

    def test_zwischen_zeiten_naechste_heute(self):
        now = datetime(2026, 6, 27, 9, 0)
        self.assertEqual(next_run_time(now, self.TIMES),
                         datetime(2026, 6, 27, 11, 0))

    def test_nach_allen_zeiten_morgen_frueheste(self):
        now = datetime(2026, 6, 27, 18, 0)
        self.assertEqual(next_run_time(now, self.TIMES),
                         datetime(2026, 6, 28, 7, 35))

    def test_exakt_auf_zeit_nimmt_naechste(self):
        # Strikt nach now: 11:00 selbst zaehlt nicht, 16:00 ist dran.
        now = datetime(2026, 6, 27, 11, 0)
        self.assertEqual(next_run_time(now, self.TIMES),
                         datetime(2026, 6, 27, 16, 0))

    def test_unsortierte_zeiten_egal(self):
        now = datetime(2026, 6, 27, 6, 0)
        self.assertEqual(next_run_time(now, ["16:00", "07:35", "11:00"]),
                         datetime(2026, 6, 27, 7, 35))

    def test_letzte_zeit_exakt_rollt_auf_morgen(self):
        now = datetime(2026, 6, 27, 16, 0)
        self.assertEqual(next_run_time(now, self.TIMES),
                         datetime(2026, 6, 28, 7, 35))

    def test_leere_liste_wirft(self):
        with self.assertRaises(ValueError):
            next_run_time(datetime(2026, 6, 27, 6, 0), [])


import tempfile
import threading
import time

from tray.service import Service


class TestServiceRun(unittest.TestCase):
    def test_refresh_flag_durchgereicht_und_serialisiert(self):
        from scripts import fetch_untis
        with tempfile.TemporaryDirectory() as d:
            svc = Service(d)
            calls = []
            counter = {"cur": 0, "max": 0}
            guard = threading.Lock()
            orig = fetch_untis.main

            def fake(refresh_absences=False):
                calls.append(refresh_absences)
                with guard:
                    counter["cur"] += 1
                    counter["max"] = max(counter["max"], counter["cur"])
                time.sleep(0.05)        # Überlappungsfenster
                with guard:
                    counter["cur"] -= 1

            fetch_untis.main = fake
            try:
                t1 = threading.Thread(target=svc.run_untis_once)
                t2 = threading.Thread(
                    target=svc.run_untis_once, kwargs={"refresh_absences": True})
                t1.start(); t2.start(); t1.join(); t2.join()
            finally:
                fetch_untis.main = orig

            self.assertEqual(counter["max"], 1)            # nie 2 Läufe parallel
            self.assertCountEqual(calls, [False, True])    # beide Modi durchgereicht


class TestGuiConfigSync(unittest.TestCase):
    """Jeder Schlüssel in config.env.example muss im Einstellungen-Fenster
    bearbeitbar sein (und umgekehrt) — sonst driften Vorlage und GUI auseinander."""

    def test_keys_deckungsgleich(self):
        import re
        from tray.gui import TABS

        root = Path(__file__).resolve().parent.parent
        text = (root / "config.env.example").read_text(encoding="utf-8")
        cfg_keys = set(re.findall(r"(?m)^([A-Z_][A-Z0-9_]*)=", text))
        gui_keys = {field[0] for _, fields in TABS for field in fields}

        self.assertEqual(cfg_keys, gui_keys,
                         msg=f"Nur in config: {cfg_keys - gui_keys}; "
                             f"nur im GUI: {gui_keys - cfg_keys}")


class TestParseTimes(unittest.TestCase):
    def test_gueltige_zeiten(self):
        self.assertEqual(parse_times("07:35, 11:00 ,16:00"),
                         [(7, 35), (11, 0), (16, 0)])

    def test_muell_faellt_raus(self):
        self.assertEqual(parse_times("07:35,quatsch,25:99,11:00"),
                         [(7, 35), (11, 0)])

    def test_leer_gibt_leer(self):
        self.assertEqual(parse_times(""), [])


if __name__ == "__main__":
    unittest.main()
