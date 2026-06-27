"""Baut Supplierplan.exe (PyInstaller, one-folder) und optional den Inno-Setup-
Installer. Auf dem Dev-PC ausführen.

Build-Abhängigkeiten (pip): pyinstaller, pystray, pillow, tzdata.
(tzdata wird in die .exe gebündelt, damit ZoneInfo auf Windows funktioniert.)
Für den Installer-Schritt zusätzlich Inno Setup 6 (ISCC).

WICHTIG: Es wird in den Windows-TEMP-Ordner gebaut, NICHT ins Projekt — sonst
sperrt OneDrive die dist/-Dateien und der Build bricht mit 'Zugriff verweigert' ab.
"""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Build-Ausgabe außerhalb von OneDrive (Temp) UND in ein frisches, eindeutiges
# Verzeichnis je Build -> PyInstaller muss nie einen (evtl. gesperrten) alten
# dist-Ordner aufräumen (Defender/Indexer/Handles bei Neubau).
BUILD_ROOT = Path(tempfile.gettempdir()) / f"Supplierplan-build-{int(time.time())}"
DIST = BUILD_ROOT / "dist"
WORK = BUILD_ROOT / "build"
APP_OUT = DIST / "Supplierplan"
ASSETS_SRC = [("css", True), ("fonts", True), ("logo.png", False),
              ("sw.js", False), ("config.env.example", False)]


def stage_assets(app_out: Path):
    """Legt assets/ neben die exe (css, fonts, logo, sw.js, config.env.example)."""
    assets = app_out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name, is_dir in ASSETS_SRC:
        src = ROOT / name
        dst = assets / name
        if is_dir and src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif src.exists():
            shutil.copy2(src, dst)


def build_exe():
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
        "--name", "Supplierplan",
        "--distpath", str(DIST),
        "--workpath", str(WORK),
        "--specpath", str(BUILD_ROOT),
        "--add-data", f"{ROOT / 'scripts'}{';' if sys.platform=='win32' else ':'}scripts",
        # Zeitzonen-DB mitliefern: ZoneInfo("Europe/Vienna") braucht tzdata auf
        # Windows. Fehlt das Paket im Build-Python, bricht der Build hier hart ab
        # (gewollt: lieber laut scheitern als still die System-TZ ausliefern).
        "--collect-data", "tzdata",
        str(ROOT / "tray" / "app.py"),
    ]
    subprocess.check_call(cmd, cwd=ROOT)
    stage_assets(APP_OUT)
    print("EXE + assets ->", APP_OUT)


def _find_iscc():
    """ISCC.exe finden: PATH, dann Program Files, dann per-User (winget-Default
    installiert nach %LOCALAPPDATA%\\Programs\\Inno Setup 6)."""
    found = shutil.which("ISCC")
    if found:
        return found
    import os
    candidates = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(str(Path(local) / "Programs" / "Inno Setup 6" / "ISCC.exe"))
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def build_installer():
    iss = ROOT / "tray" / "installer.iss"
    iscc = _find_iscc()
    if not iscc:
        print("Inno Setup (ISCC) nicht gefunden – Installer übersprungen.")
        return
    # Quell-Ordner (Temp) + Ausgabe-Ordner per /D an das iss-Skript geben.
    subprocess.check_call([
        iscc,
        f"/DDistDir={APP_OUT}",
        f"/DOutDir={BUILD_ROOT}",
        str(iss),
    ], cwd=ROOT)
    print("Installer gebaut ->", BUILD_ROOT)


if __name__ == "__main__":
    build_exe()
    build_installer()
