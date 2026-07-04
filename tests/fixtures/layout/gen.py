"""Erzeugt drei reproduzierbare Layout-Szenarien als index-artige HTML-Dateien,
um den Browser-Check des Layout-Refactors (ADR 0002) an harten Faellen zu
verankern — unabhaengig davon, wie der echte Schultag gerade aussieht.

Lauf (Windows-Python, WSL hat keins):
  PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe \\
      tests/fixtures/layout/gen.py

Schreibt normal.html / overflow.html / cancel_heavy.html neben dieses Script.
Danach: jede Datei aus dem Projekt-Root serviert im Browser oeffnen (damit
js/layout-core.js + js/layout.js aufloesen) und pruefen:
  - normal:       sauberes 2–4-Spalten-Layout, kein Abschneiden.
  - overflow:     Board skaliert, dann reduziert, dann blaettert; "Morgen" bleibt.
  - cancel_heavy: Entfaelle fliessen ueber echte Spaltengrenzen, genau EINE
                  "Entfallende Stunden"-Ueberschrift je Spalte (Forts. dezent).
Diagnose-Overlay: die Datei mit ?ovdebug=1 oeffnen zeigt die gegriffene Stufe.
"""
import importlib.util
import os
from datetime import datetime, timezone, date

_HERE = os.path.dirname(os.path.abspath(__file__))
# _HERE = tests/fixtures/layout -> drei Ebenen hoch zum Projekt-Root.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_spec = importlib.util.spec_from_file_location(
    "fu", os.path.join(_ROOT, "scripts", "fetch_untis.py"))
fu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fu)

# Fester Zeitpunkt -> deterministischer Output (Datum, Cache-Bust).
_FROZEN = datetime(2026, 5, 28, 8, 5, 0, tzinfo=timezone.utc)
fu.now_local = lambda: _FROZEN


def _row(kuerzel, std, art, day="today", **extra):
    sort_key = 700 + std * 50
    r = {
        "kuerzel": kuerzel, "org_kuerzel": "", "std": str(std), "sort_key": sort_key,
        "end_time": sort_key + 50, "day": day, "fach": "M", "klasse": "1A",
        "art": art, "raum": "R1", "raum_org": "", "text": "",
    }
    r.update(extra)
    return r


_NAMES = ["Aal", "Bär", "Cé", "Dux", "Egg", "Feh", "Gru", "Huf", "Ilz", "Jod",
          "Kern", "Lux", "Mohn", "Nix", "Ohm", "Pux", "Qui", "Rho", "Sud", "Tux"]
_LOOKUP = {n: {"nachname": n + "mann", "vorname": "V"} for n in _NAMES}

_INDICATOR = {"state": "running", "nr": 1, "start": "08:00",
              "end": "08:50", "day_offset": 0}
_CFG = {
    "PLAN_TITLE": "Supplierplan", "LOGO_FILE": "logo.png", "SHOW_LOGO": "true",
    "THEME": "dark", "SHOW_CLOCK": "true", "TIMEZONE": "Europe/Vienna",
    "COMPACT_COL_WIDTH_PX": "320", "MAX_COLUMNS": "4",
    "SCHOOL_NAME": "MS Roda-Roda-Gasse", "SCHOOL_TYPE": "MS",
    "SCHOOL_LOCATION": "Wien", "CANCEL_PLACEMENT": "section",
    "PWA_ORIENTATION": "any", "TEXT_BADGES": "b,ub,MA", "TRAIN_STATION": "",
}


def _write(name, today_rows, tom_rows):
    settings = fu.DisplaySettings.from_config(_CFG)
    html = fu.generate_html(
        fu.group_by_teacher(today_rows), fu.group_by_teacher(tom_rows),
        date(2026, 5, 28), date(2026, 5, 29), _LOOKUP, _INDICATOR,
        import_time=_FROZEN, settings=settings,
    )
    # Die Fixtures liegen unter /tests/fixtures/layout/, die echte index.html im
    # Web-Root. generate_html emittiert relative Asset-Pfade (css/, js/) -> ohne
    # <base> würden sie relativ zur Fixture aufgelöst und 404en. <base href="/">
    # löst sie wieder vom Server-Root (= Projekt-Root) auf.
    html = html.replace("<head>", '<head>\n    <base href="/">', 1)
    out = os.path.join(_HERE, name)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    n = html.count('data-block=')
    print(f"{name}: {len(today_rows)} heute + {len(tom_rows)} morgen -> "
          f"{n} Bloecke, {len(html)} Bytes")


def scenario_normal():
    today = [_row(_NAMES[i], 2 + i, "subst", org_kuerzel=_NAMES[i + 5]) for i in range(4)]
    tom = [_row(_NAMES[i], 3 + i, "roomchange", day="tomorrow",
                raum="R2", raum_org="R1") for i in range(2)]
    _write("normal.html", today, tom)


def scenario_overflow():
    # Viele Blöcke über viele Lehrer -> Skalieren/Reduzieren/Blättern greift.
    today = []
    for i, n in enumerate(_NAMES):
        for s in range(0, 4):
            today.append(_row(n, s, "subst", org_kuerzel=_NAMES[(i + 3) % len(_NAMES)],
                              text=("ub" if s % 2 else "")))
    tom = [_row(_NAMES[i], 4 + (i % 4), "subst", day="tomorrow",
                org_kuerzel=_NAMES[(i + 1) % len(_NAMES)]) for i in range(6)]
    _write("overflow.html", today, tom)


def scenario_cancel_heavy():
    # Grosse Entfall-Sektion (ganze abwesende Klassen) über mehrere Spalten.
    today = [_row(_NAMES[i], 2 + (i % 3), "subst",
                  org_kuerzel=_NAMES[(i + 2) % len(_NAMES)]) for i in range(3)]
    for i, n in enumerate(_NAMES):
        for s in range(0, 5):
            today.append(_row(n, s, "cancel", kuerzel_absent=True, klasse=f"{1+i%4}B"))
    tom = [_row(_NAMES[0], 5, "cancel", day="tomorrow", kuerzel_absent=True)]
    _write("cancel_heavy.html", today, tom)


if __name__ == "__main__":
    scenario_normal()
    scenario_overflow()
    scenario_cancel_heavy()
    print("OK — drei Fixtures geschrieben nach", _HERE)
