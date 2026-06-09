"""Einstieg der Tray-App: pystray-Icon, Menü, Single-Instance, Wiring."""
import os
import sys
import threading
import webbrowser
from pathlib import Path

import pystray

from tray import paths, icons
from tray.service import Service
from tray.config_io import read_config_env, write_config_env
from tray.autostart import (WinRegistry, APP_NAME, enable_autostart,
                            disable_autostart, is_autostart)
from tray.gui import open_config_window

SINGLE_INSTANCE_PORT = 50573


def _acquire_single_instance():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
        return s
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
    lock = _acquire_single_instance()
    if lock is None:
        print("Supplierplan läuft bereits.")
        return

    data_dir = _ensure_data_dir()
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

    def on_settings(icon, item):
        threading.Thread(
            target=lambda: open_config_window(
                data_dir / "config.env",
                template_path=paths.app_dir() / "assets" / "config.env.example",
                on_saved=service.run_untis_once,
                test_connection=_test_connection),
            daemon=True).start()

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


if __name__ == "__main__":
    main()
