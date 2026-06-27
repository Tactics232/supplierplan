"""Einstieg der Tray-App: pystray-Icon, Menü, Single-Instance, Wiring."""
import os
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

# Riskante Imports (pystray, PIL via icons, tkinter via gui) werden LAZY in main()
# importiert, damit ein fehlender/kaputter Import vom Crash-Handler unten gefangen
# und als Fenster + crash.log angezeigt wird (statt --windowed: lautlos abstürzen).
from tray import paths
from tray.service import Service
from tray.config_io import read_config_env, write_config_env
from tray.autostart import (WinRegistry, APP_NAME, enable_autostart,
                            disable_autostart, is_autostart)

HELP_URL = "https://github.com/Tactics232/supplierplan/blob/master/docs/SETTINGS.md"

def _acquire_single_instance(data_dir):
    """Single-Instance über eine exklusiv gesperrte Lock-Datei im Datenverzeichnis.
    Das OS gibt die Sperre beim Prozessende automatisch frei → kein stale lock nach
    Absturz. Rückgabe: offenes File-Handle (Sperre hält, solange es offen bleibt)
    oder None, wenn bereits eine Instanz läuft.

    Warum kein Port: WSL2/Hyper-V reserviert wechselnde TCP-Portbereiche (bind →
    WinError 10013), die sich bei jedem Reboot verschieben. Ein fester Port ist
    damit unbrauchbar. Siehe `netsh interface ipv4 show excludedportrange`."""
    lock_path = data_dir / ".instance.lock"
    try:
        f = open(lock_path, "a+")
        f.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except OSError:
        return None


def _static_dir():
    """Wurzel der statischen Assets: assets/ neben der .exe (gebaut) oder der
    Projektordner (Dev, css/fonts/logo/sw.js liegen direkt dort). assets/ wird nur
    genommen, wenn es die Assets WIRKLICH enthält (assets/css) — ein leerer
    Stray-assets/-Ordner darf nicht gewinnen."""
    app = paths.app_dir()
    assets = app / "assets"
    return assets if (assets / "css").exists() else app


def _ensure_data_dir():
    """Legt das beschreibbare Datenverzeichnis an (web/, data/, config.env aus
    Vorlage). Statische Assets werden NICHT kopiert — der Server liefert sie als
    Fallback aus _static_dir() aus (siehe tray/server.py)."""
    dd = paths.data_dir()
    (dd / "web").mkdir(parents=True, exist_ok=True)
    (dd / "data").mkdir(parents=True, exist_ok=True)
    cfg = dd / "config.env"
    if not cfg.exists():
        tmpl = _static_dir() / "config.env.example"
        if tmpl.exists():
            write_config_env({}, cfg, template=tmpl)
    return dd


def _test_connection(values):
    try:
        from scripts.fetch_untis import WebUntis
        u = WebUntis(url=values.get("UNTIS_URL", ""),
                     school_id=values.get("UNTIS_SCHOOL_ID", ""),
                     user=values.get("UNTIS_USER", ""),
                     password=values.get("UNTIS_PASSWORD", ""))
        u.login(); u.logout()
        return True, "Login erfolgreich"
    except Exception as e:
        return False, str(e)


def main():
    import pystray
    from tray import icons
    from tray.gui import open_config_window

    data_dir = _ensure_data_dir()
    lock = _acquire_single_instance(data_dir)
    if lock is None:
        print("Supplierplan läuft bereits.")
        return

    service = Service(data_dir, static_dir=_static_dir())
    reg = WinRegistry() if os.name == "nt" else None

    def exe_command():
        return f'"{sys.executable}"'

    def refresh_icon(icon):
        icon.icon = icons.make_icon(service.running)
        icon.title = "Supplierplan – " + service.last_status

    def on_start(icon, item):
        service.start(); refresh_icon(icon)

    def on_stop(icon, item):
        service.stop(); refresh_icon(icon)

    win_state = {"open": False, "focus": False}

    def _station_search(term):
        from scripts.fetch_trains import search_stations
        return search_stations(term)

    def _focus_requested():
        if win_state["focus"]:
            win_state["focus"] = False
            return True
        return False

    def on_settings(icon, item):
        # Single-Window: läuft schon eins, nur nach vorne holen (kein zweites Fenster).
        if win_state["open"]:
            win_state["focus"] = True
            return
        win_state["open"] = True

        def run():
            try:
                open_config_window(
                    data_dir / "config.env",
                    template_path=_static_dir() / "config.env.example",
                    on_saved=service.refresh_now,
                    test_connection=_test_connection,
                    on_refresh=service.refresh_now,
                    on_refresh_absences=service.refresh_absences_now,
                    busy_getter=lambda: service.busy,
                    status_getter=lambda: service.last_status,
                    station_search=_station_search,
                    help_url=HELP_URL,
                    focus_requested=_focus_requested,
                    on_close=lambda: win_state.update(open=False))
            finally:
                win_state["open"] = False

        threading.Thread(target=run, daemon=True).start()

    def on_refresh_now(icon, item):
        service.refresh_now()

    def on_refresh_absences(icon, item):
        service.refresh_absences_now()

    def on_open_browser(icon, item):
        port = service._cfg_int("SERVER_PORT", 8080)
        webbrowser.open(f"http://localhost:{port}")

    def toggle_autostart(icon, item):
        if not reg:
            return
        if is_autostart(reg, APP_NAME):
            disable_autostart(reg, APP_NAME)
        else:
            enable_autostart(reg, APP_NAME, exe_command())

    def autostart_checked(item):
        return bool(reg) and is_autostart(reg, APP_NAME)

    def on_quit(icon, item):
        service.stop(); icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Start", on_start, enabled=lambda i: not service.running),
        pystray.MenuItem("Stopp", on_stop, enabled=lambda i: service.running),
        pystray.MenuItem("Einstellungen…", on_settings, default=True),
        pystray.MenuItem("Jetzt aktualisieren", on_refresh_now,
                         enabled=lambda i: service.running and not service.busy),
        pystray.MenuItem("Abwesenheiten aktualisieren", on_refresh_absences,
                         enabled=lambda i: service.running and not service.busy),
        pystray.MenuItem("Im Browser öffnen", on_open_browser),
        pystray.MenuItem("Mit Windows starten", toggle_autostart, checked=autostart_checked),
        pystray.MenuItem("Beenden", on_quit),
    )

    icon = pystray.Icon("Supplierplan", icons.make_icon(False),
                        "Supplierplan – gestoppt", menu)

    cfg = read_config_env(data_dir / "config.env")
    if cfg.get("UNTIS_URL") and cfg.get("UNTIS_USER"):
        service.start()

    def setup(icon):
        icon.visible = True
        refresh_icon(icon)
        def tick():
            while True:
                import time; time.sleep(5)
                try:
                    refresh_icon(icon)
                except Exception:
                    break
        threading.Thread(target=tick, daemon=True).start()

    icon.run(setup)


def _report_crash(text):
    """Schreibt den Traceback in crash.log (neben der .exe und in %TEMP%) und zeigt
    ihn als Fenster (MessageBox), weil --windowed die Konsole verschluckt."""
    import tempfile
    targets = []
    try:
        targets.append(paths.app_dir() / "crash.log")
    except Exception:
        pass
    targets.append(Path(tempfile.gettempdir()) / "Supplierplan-crash.log")
    for p in targets:
        try:
            p.write_text(text, encoding="utf-8")
            break
        except Exception:
            continue
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, text[-1500:], "Supplierplan – Fehler beim Start", 0x10)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _report_crash(traceback.format_exc())
