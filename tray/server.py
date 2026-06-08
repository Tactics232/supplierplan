"""Gehärteter statischer Webserver-Thread.

Liefert zwei Wurzeln aus EINEM URL-Raum:
  1. web_dir    – dynamisch erzeugte Dateien (index.html, manifest.json, data/trains.json)
  2. static_dir – mitgelieferte Assets (css/, fonts/, logo.png, sw.js)
So müssen die Assets NICHT ins web_dir kopiert werden (robust gegen Sync-Sperren).
Nur diese beiden Wurzeln sind erreichbar; .env/Dotfiles/Traversal sind blockiert.
"""
import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


def is_path_allowed(path: str) -> bool:
    """True, wenn der angefragte URL-Pfad ausgeliefert werden darf."""
    p = (path or "").lower()
    if ".." in p or "%2f" in p or "%5c" in p:   # Traversal
        return False
    if "/." in p or p.startswith("."):           # Dotfiles (.git, .env-artige)
        return False
    if p.endswith(".env"):                        # config.env & Co.
        return False
    return True


class HardenedHandler(SimpleHTTPRequestHandler):
    static_dir = None  # wird je Server gesetzt (Fallback-Wurzel)

    def translate_path(self, path):
        full = super().translate_path(path)   # gegen web_dir (self.directory)
        if os.path.exists(full):
            return full
        # Fallback: dieselbe Relativ-Position unter static_dir versuchen
        if self.static_dir:
            try:
                rel = os.path.relpath(full, self.directory)
            except ValueError:
                rel = ""
            cand = os.path.join(self.static_dir, rel)
            if os.path.exists(cand):
                return cand
        return full

    def list_directory(self, path):              # kein Directory-Listing
        self.send_error(403, "Forbidden")
        return None

    def send_head(self):
        if not is_path_allowed(self.path):
            self.send_error(404, "Not Found")
            return None
        return super().send_head()

    def log_message(self, *args):                # ruhiges Log
        pass


def serve_web(web_dir, port, host="0.0.0.0", static_dir=None):
    """Startet den Server in einem Thread. Gibt (httpd, thread) zurück; Stoppen via
    httpd.shutdown(). static_dir ist die Fallback-Wurzel für statische Assets."""
    class _Handler(HardenedHandler):
        pass
    _Handler.static_dir = str(static_dir) if static_dir else None
    handler = partial(_Handler, directory=str(web_dir))
    httpd = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread
