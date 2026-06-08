"""Lesen/Schreiben der config.env ohne Kommentare/Struktur zu zerstören."""
from pathlib import Path


def parse_config_text(text: str) -> dict:
    """KEY=value-Paare aus config.env-Text. Reine Kommentar-/Leerzeilen werden
    ignoriert. Der WERT wird NICHT an '#' abgeschnitten — sonst würde ein Passwort/
    Token mit '#' beim GUI-Round-Trip (Laden→Speichern) verstümmelt. (Konsistent zu
    load_config in den fetch-Scripts; Inline-Kommentare in config.env vermeiden.)"""
    out = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        out[key.strip()] = val.strip()
    return out


def render_config_env(existing_text: str, values: dict) -> str:
    """Aktualisiert vorhandene KEY=-Zeilen mit values, behält Kommentare/Reihenfolge,
    hängt fehlende Keys am Ende an. Werte werden roh geschrieben (kein Inline-#)."""
    remaining = dict(values)
    lines_out = []
    for line in existing_text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            key = s.split("=", 1)[0].strip()
            if key in remaining:
                lines_out.append(f"{key}={remaining.pop(key)}")
                continue
        lines_out.append(line)
    for key, val in remaining.items():
        lines_out.append(f"{key}={val}")
    return "\n".join(lines_out) + "\n"


def read_config_env(path: Path) -> dict:
    """config.env-Datei → dict (leeres dict, wenn nicht vorhanden)."""
    p = Path(path)
    if not p.exists():
        return {}
    return parse_config_text(p.read_text(encoding="utf-8"))


def write_config_env(values: dict, path: Path, template: Path = None) -> None:
    """Schreibt values in path. Basis ist die vorhandene Datei, sonst das Template,
    sonst leer."""
    p = Path(path)
    if p.exists():
        existing = p.read_text(encoding="utf-8")
    elif template and Path(template).exists():
        existing = Path(template).read_text(encoding="utf-8")
    else:
        existing = ""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_config_env(existing, values), encoding="utf-8")
