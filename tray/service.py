"""Hintergrund-Dienst: ruft die bestehenden Fetch-main() auf Timern auf und
betreibt den Webserver. Lenkt die Ausgaben über Umgebungsvariablen ins
beschreibbare Datenverzeichnis."""
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from tray.config_io import read_config_env
from tray.server import serve_web


class Service:
    def __init__(self, data_dir: Path, static_dir=None, log=print):
        self.data_dir = Path(data_dir)
        self.web_dir = self.data_dir / "web"
        self.config_path = self.data_dir / "config.env"
        self.static_dir = static_dir   # Fallback-Wurzel für statische Assets
        self.log = log
        self._timers = []
        self._httpd = None
        self.running = False
        self.last_status = "gestoppt"
        self.last_update = None
        self._lock = threading.Lock()

    def _apply_env(self):
        os.environ["SUPPLIERPLAN_CONFIG"] = str(self.config_path)
        os.environ["SUPPLIERPLAN_WEBROOT"] = str(self.web_dir)
        os.environ["SUPPLIERPLAN_DATA"] = str(self.data_dir / "data")

    def _cfg_int(self, key, default):
        try:
            return max(10, int(read_config_env(self.config_path).get(key, default)))
        except (ValueError, TypeError):
            return default

    def run_untis_once(self):
        self._apply_env()
        try:
            from scripts import fetch_untis
            fetch_untis.main()
            with self._lock:
                self.last_update = datetime.now().strftime("%H:%M")
                self.last_status = f"Läuft · Stand {self.last_update}"
        except Exception as e:
            self._record_error("Untis", e)

    def run_trains_once(self):
        self._apply_env()
        try:
            from scripts import fetch_trains
            fetch_trains.main()
        except Exception as e:
            self._record_error("Züge", e)

    def _record_error(self, what, exc):
        msg = f"Fehler ({what}): {exc}"
        with self._lock:
            self.last_status = msg
        try:
            (self.data_dir / "data").mkdir(parents=True, exist_ok=True)
            with open(self.data_dir / "data" / "app.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} {msg}\n")
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass

    def _schedule(self, fn, interval):
        if not self.running:
            return
        fn()
        t = threading.Timer(interval, self._schedule, args=(fn, interval))
        t.daemon = True
        t.start()
        self._timers.append(t)

    def start(self):
        if self.running:
            return
        self.web_dir.mkdir(parents=True, exist_ok=True)
        self._apply_env()
        self.running = True
        port = self._cfg_int("SERVER_PORT", 8080)
        try:
            self._httpd, _ = serve_web(self.web_dir, port, static_dir=self.static_dir)
        except Exception as e:
            self.running = False
            self._record_error("Server", e)
            return
        u_iv = self._cfg_int("UNTIS_INTERVAL_SECONDS", 300)
        t_iv = self._cfg_int("TRAIN_INTERVAL_SECONDS", 60)
        threading.Thread(target=self._schedule, args=(self.run_untis_once, u_iv), daemon=True).start()
        threading.Thread(target=self._schedule, args=(self.run_trains_once, t_iv), daemon=True).start()
        self.last_status = "Läuft"

    def stop(self):
        self.running = False
        for t in self._timers:
            t.cancel()
        self._timers = []
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        self.last_status = "gestoppt"
