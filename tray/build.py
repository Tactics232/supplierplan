"""Baut Supplierplan.exe (PyInstaller, one-folder) und optional den Inno-Setup-
Installer. Auf dem Dev-PC ausführen.

WICHTIG: Es wird in den Windows-TEMP-Ordner gebaut, NICHT ins Projekt — sonst
sperrt OneDrive die dist/-Dateien und der Build bricht mit 'Zugriff verweigert' ab.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Build-Ausgabe außerhalb von OneDrive (Temp) -> keine Sync-Sperren.
BUILD_ROOT = Path(tempfile.gettempdir()) / "Supplierplan-build"
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
        str(ROOT / "tray" / "app.py"),
    ]
    subprocess.check_call(cmd, cwd=ROOT)
    stage_assets(APP_OUT)
    print("EXE + assets ->", APP_OUT)


def build_installer():
    iss = ROOT / "tray" / "installer.iss"
    iscc = shutil.which("ISCC") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not Path(iscc).exists():
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
