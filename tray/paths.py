"""Pfad-Auflösung für die Tray-App (beschreibbares Datenverzeichnis)."""
import os
import sys
from pathlib import Path


def _default_can_write(path: Path) -> bool:
    """Prüft Schreibbarkeit, indem testweise eine Datei angelegt wird."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def resolve_data_dir(exe_dir: Path, localappdata: Path, can_write=None) -> Path:
    """Beschreibbares Datenverzeichnis: bevorzugt neben der .exe (portabel),
    sonst %LOCALAPPDATA%\\Supplierplan (Installation unter Programme)."""
    can_write = can_write or _default_can_write
    if can_write(exe_dir):
        return exe_dir
    return localappdata / "Supplierplan"


def app_dir() -> Path:
    """Verzeichnis der laufenden .exe bzw. des Scripts (PyInstaller-kompatibel)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Konkret aufgelöstes Datenverzeichnis für diese Maschine."""
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    return resolve_data_dir(app_dir(), local)
