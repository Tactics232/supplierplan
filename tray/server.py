"""Gehärteter statischer Webserver-Thread; liefert NUR das Web-Root aus."""
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


def is_path_allowed(path: str) -> bool:
    """True, wenn der angefragte URL-Pfad ausgeliefert werden darf."""
    p = (path or "").lower()
    if ".." in p or "%2f" in p or "%5c" in p:
        return False
    if "/." in p or p.startswith("."):
        return False
    if p.endswith(".env"):
        return False
    return True


class HardenedHandler(SimpleHTTPRequestHandler):
    def list_directory(self, path):
        self.send_error(403, "Forbidden")
        return None

    def send_head(self):
        if not is_path_allowed(self.path):
            self.send_error(404, "Not Found")
            return None
        return super().send_head()

    def log_message(self, *args):
        pass


def serve_web(web_dir, port, host="0.0.0.0"):
    """Startet den Server in einem Thread. Gibt (httpd, thread) zurück; Stoppen via
    httpd.shutdown()."""
    handler = partial(HardenedHandler, directory=str(web_dir))
    httpd = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread
