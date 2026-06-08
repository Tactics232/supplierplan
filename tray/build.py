"""Baut Supplierplan.exe (PyInstaller, one-folder) und optional den Inno-Setup-
Installer. Auf dem Dev-PC ausführen."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
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
        "--add-data", f"{ROOT / 'scripts'}{';' if sys.platform=='win32' else ':'}scripts",
        str(ROOT / "tray" / "app.py"),
    ]
    subprocess.check_call(cmd, cwd=ROOT)
    app_out = DIST / "Supplierplan"
    stage_assets(app_out)
    print("EXE + assets ->", app_out)


def build_installer():
    iss = ROOT / "tray" / "installer.iss"
    iscc = shutil.which("ISCC") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not Path(iscc).exists():
        print("Inno Setup (ISCC) nicht gefunden – Installer übersprungen.")
        return
    subprocess.check_call([iscc, str(iss)], cwd=ROOT)
    print("Installer gebaut ->", DIST)


if __name__ == "__main__":
    build_exe()
    build_installer()
