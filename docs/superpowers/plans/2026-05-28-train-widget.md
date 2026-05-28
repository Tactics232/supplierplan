# Train-Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Echtzeit-Anzeige der zwei nächsten Züge (eine pro Richtung) für eine konfigurierbare Wiener Bahnhaltestelle, prominent platziert in der Mitte des Supplierplan-Headers, mit 60-Sekunden-Aktualisierung.

**Architecture:** Eigenes Python-Skript `scripts/fetch_trains.py` läuft per Cron alle 60 Sekunden, holt Daten via `pyhafas` (ÖBB-Profile) und schreibt `data/trains.json` atomar. Browser-JS im bestehenden `index.html` fetched diese JSON alle 60 Sekunden und befüllt einen Widget-Container im Header. Untis-Cron und Zug-Cron sind komplett unabhängig.

**Tech Stack:** Python 3.9+ (stdlib + `pyhafas` als neue Dependency), HTML/CSS/Vanilla-JS, atomare File-Writes via `os.replace`. Test-Runner: `unittest` aus stdlib. Spec: `docs/superpowers/specs/2026-05-28-zuganzeige-design.md`.

---

## File Structure

**Neu:**
- `scripts/fetch_trains.py` — Cron-Skript: lädt Config, ruft pyhafas, schreibt JSON
- `scripts/__init__.py` — leeres Modul-Marker, damit Tests importieren können
- `tests/__init__.py` — leeres Modul-Marker
- `tests/test_fetch_trains.py` — Unit-Tests für pure Logic-Funktionen
- `requirements.txt` — dokumentiert die `pyhafas`-Dependency
- `data/trains.json` — laufzeit-generiert, nicht im Repo (data/ ist bereits gitignored)

**Geändert:**
- `scripts/fetch_untis.py` — `generate_html` bekommt einen Widget-Container im Header + JS-Snippet für JSON-Fetch
- `css/style.css` — Styles für `.train-widget`-Komponente
- `config.env.example` — neue Variablen `TRAIN_*` dokumentiert
- `CLAUDE.md` — neue Sektion „Zug-Widget" + Cron-Setup

**Verantwortlichkeits-Schnitt:**
- `fetch_trains.py` kennt pyhafas, aber sein top-level enthält reine Logik-Funktionen (kein pyhafas-Aufruf) — Tests können diese importieren, ohne pyhafas installiert zu haben. Pyhafas wird **lazy in `main()`** geladen.
- `fetch_untis.py` baut nur einen leeren `<div id="train-widget">` ein und das JS, das alle 60s `data/trains.json` lädt. Kein direkter Bezug zu Zugdaten.

---

## Task 1: Setup — requirements.txt, Test-Skeleton, Branch-Check

**Files:**
- Create: `requirements.txt`
- Create: `scripts/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_fetch_trains.py`

- [ ] **Step 1: Prüfen dass wir im richtigen Branch sind**

```bash
git rev-parse --abbrev-ref HEAD
```
Expected: `feature/train-widget`

Falls nicht: `git checkout feature/train-widget`

- [ ] **Step 2: requirements.txt anlegen**

Inhalt:
```
pyhafas>=0.4.0
```

- [ ] **Step 3: Skript-Marker-Files anlegen**

`scripts/__init__.py` und `tests/__init__.py` — beide leer (nur damit Python diese Verzeichnisse als Module importieren kann).

- [ ] **Step 4: Test-Datei mit Marker-Test anlegen**

`tests/test_fetch_trains.py`:
```python
import unittest


class TestSmokeImport(unittest.TestCase):
    def test_module_can_be_imported(self):
        # Wird in späteren Tasks ersetzt; sichert nur, dass das Test-Setup steht
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Test-Lauf zur Sanity-Probe**

Run (aus dem Projekt-Root):
```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```

Expected: `test_module_can_be_imported (...) ... ok` und `OK`.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt scripts/__init__.py tests/__init__.py tests/test_fetch_trains.py
git commit -m "Train-Widget: Test-Skeleton + requirements.txt"
```

---

## Task 2: `classify_direction` — pure logic, TDD

**Files:**
- Create: `scripts/fetch_trains.py`
- Modify: `tests/test_fetch_trains.py`

- [ ] **Step 1: Failing test schreiben**

Inhalt von `tests/test_fetch_trains.py` ersetzen mit:

```python
import unittest

from scripts.fetch_trains import classify_direction


class TestClassifyDirection(unittest.TestCase):
    def setUp(self):
        self.towards = ["Hbf", "Westbf", "Praterstern", "Heiligenstadt"]

    def test_destination_in_whitelist_is_towards(self):
        self.assertEqual(
            classify_direction("Wien Hauptbahnhof", self.towards),
            "towards",
        )

    def test_destination_not_in_whitelist_is_away(self):
        self.assertEqual(
            classify_direction("St. Pölten Hbf via Tullnerfeld", self.towards),
            "towards",  # "Hbf" matcht — auch via Substring im längeren Namen
        )

    def test_completely_unrelated_destination_is_away(self):
        self.assertEqual(
            classify_direction("Salzburg Hauptbahnhof", ["Westbf", "Praterstern"]),
            "away",
        )

    def test_matching_is_case_insensitive(self):
        self.assertEqual(
            classify_direction("wien hbf", ["HBF"]),
            "towards",
        )

    def test_empty_whitelist_returns_away(self):
        self.assertEqual(
            classify_direction("Wien Hbf", []),
            "away",
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — soll fehlschlagen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```

Expected: ImportError (`scripts.fetch_trains` existiert noch nicht).

- [ ] **Step 3: Minimale Implementation**

`scripts/fetch_trains.py` neu anlegen:

```python
#!/usr/bin/env python3
"""
fetch_trains.py – holt die nächsten Abfahrten einer Bahnhaltestelle via pyhafas
und schreibt sie in data/trains.json.
Läuft per Cron jede Minute (separater Job vom Untis-Cron).
"""

from typing import Iterable


def classify_direction(destination: str, towards_substrings: Iterable[str]) -> str:
    """Liefert 'towards' wenn destination irgendeinen Substring aus
    towards_substrings enthält (case-insensitive), sonst 'away'."""
    if not destination:
        return "away"
    dest_lower = destination.lower()
    for sub in towards_substrings:
        if sub and sub.strip().lower() in dest_lower:
            return "towards"
    return "away"
```

- [ ] **Step 4: Test laufen lassen — soll passen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```

Expected: `Ran 5 tests in 0.00Xs ... OK`

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_trains.py tests/test_fetch_trains.py
git commit -m "Train-Widget: classify_direction + Tests"
```

---

## Task 3: `extract_departure` — pyhafas-Leg in dict umwandeln, TDD

**Files:**
- Modify: `scripts/fetch_trains.py`
- Modify: `tests/test_fetch_trains.py`

Die Funktion bekommt ein „Leg"-Objekt (pyhafas-Klasse) und liefert das JSON-konforme dict. Wir testen mit Duck-Typed Stubs, damit pyhafas für die Tests nicht installiert sein muss.

- [ ] **Step 1: Failing test schreiben**

In `tests/test_fetch_trains.py` ergänzen (vor `if __name__ ...`):

```python
from datetime import datetime, timedelta, timezone
from scripts.fetch_trains import extract_departure


class _FakeLeg:
    """Duck-typed pyhafas StationBoardLeg-Stub für Tests."""
    def __init__(self, name, direction, planned, delay=None, cancelled=False, platform=None):
        self.name = name
        self.direction = direction
        self.dateTime = planned
        self.delay = delay
        self.cancelled = cancelled
        self.platform = platform


class TestExtractDeparture(unittest.TestCase):
    def setUp(self):
        self.tz = timezone(timedelta(hours=2))
        self.planned = datetime(2026, 5, 28, 14, 23, tzinfo=self.tz)

    def test_pünktlicher_zug(self):
        leg = _FakeLeg("S 50", "Wien Hauptbahnhof", self.planned)
        result = extract_departure(leg)
        self.assertEqual(result["line"], "S 50")
        self.assertEqual(result["destination"], "Wien Hauptbahnhof")
        self.assertEqual(result["planned"], "14:23")
        self.assertEqual(result["actual"], "14:23")
        self.assertEqual(result["delay_minutes"], 0)
        self.assertFalse(result["cancelled"])

    def test_zug_mit_verspätung_2min(self):
        leg = _FakeLeg("S 50", "St. Pölten", self.planned, delay=timedelta(minutes=2))
        result = extract_departure(leg)
        self.assertEqual(result["planned"], "14:23")
        self.assertEqual(result["actual"], "14:25")
        self.assertEqual(result["delay_minutes"], 2)

    def test_cancelled_zug(self):
        leg = _FakeLeg("S 50", "Wien Hbf", self.planned, cancelled=True)
        result = extract_departure(leg)
        self.assertTrue(result["cancelled"])

    def test_platform_string_übernommen(self):
        leg = _FakeLeg("S 50", "Wien Hbf", self.planned, platform="3")
        self.assertEqual(extract_departure(leg)["platform"], "3")

    def test_platform_kann_none_sein(self):
        leg = _FakeLeg("S 50", "Wien Hbf", self.planned, platform=None)
        self.assertIsNone(extract_departure(leg)["platform"])
```

- [ ] **Step 2: Test laufen lassen — soll fehlschlagen**

Expected: `ImportError: cannot import name 'extract_departure' from 'scripts.fetch_trains'`

- [ ] **Step 3: Implementation in `scripts/fetch_trains.py` ergänzen**

Am Anfang Imports erweitern:
```python
from datetime import timedelta
from typing import Iterable, Any
```

Nach `classify_direction` ergänzen:

```python
def extract_departure(leg: Any) -> dict:
    """Wandelt ein pyhafas StationBoardLeg (oder Duck-Typ) in ein JSON-konformes dict um.
    Erwartet Attribute: name, direction, dateTime, delay, cancelled, platform.
    """
    planned_dt = leg.dateTime
    delay = leg.delay or timedelta(0)
    delay_minutes = int(delay.total_seconds() // 60)
    actual_dt = planned_dt + delay

    return {
        "line":          leg.name,
        "destination":   leg.direction,
        "planned":       planned_dt.strftime("%H:%M"),
        "actual":        actual_dt.strftime("%H:%M"),
        "delay_minutes": delay_minutes,
        "cancelled":     bool(leg.cancelled),
        "platform":      leg.platform,
    }
```

- [ ] **Step 4: Test laufen lassen — soll passen**

Expected: alle Tests bestanden.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_trains.py tests/test_fetch_trains.py
git commit -m "Train-Widget: extract_departure + Tests"
```

---

## Task 4: `split_by_direction` — Liste in towards/away aufteilen, TDD

**Files:**
- Modify: `scripts/fetch_trains.py`
- Modify: `tests/test_fetch_trains.py`

- [ ] **Step 1: Failing test schreiben**

In `tests/test_fetch_trains.py` ergänzen:

```python
from scripts.fetch_trains import split_by_direction


class TestSplitByDirection(unittest.TestCase):
    def setUp(self):
        self.tz = timezone(timedelta(hours=2))
        base = datetime(2026, 5, 28, 14, 0, tzinfo=self.tz)
        # 5 Abfahrten: 3 Richtung Wien, 2 weg
        self.legs = [
            _FakeLeg("S 50", "Wien Hauptbahnhof", base.replace(minute=10)),  # towards
            _FakeLeg("S 50", "St. Pölten Hbf",    base.replace(minute=15)),  # towards (Hbf matcht!) — hmm
            _FakeLeg("S 50", "Wien Westbahnhof",  base.replace(minute=20)),  # towards
            _FakeLeg("S 50", "Tulln",             base.replace(minute=25)),  # away
            _FakeLeg("REX", "Salzburg",           base.replace(minute=30)),  # away
        ]

    def test_split_mit_n1_pro_richtung(self):
        # Hier nutzen wir eine spezifische Whitelist, die NUR "Wien" matcht,
        # damit der "St. Pölten Hbf"-Fall nicht reinfällt
        towards_list = ["Wien"]
        result = split_by_direction(self.legs, towards_list, n_per_direction=1)
        self.assertEqual(len(result["towards"]), 1)
        self.assertEqual(len(result["away"]), 1)
        self.assertEqual(result["towards"][0]["destination"], "Wien Hauptbahnhof")
        self.assertEqual(result["away"][0]["destination"], "St. Pölten Hbf")

    def test_split_mit_n2_pro_richtung(self):
        towards_list = ["Wien"]
        result = split_by_direction(self.legs, towards_list, n_per_direction=2)
        self.assertEqual(len(result["towards"]), 2)
        self.assertEqual(len(result["away"]), 2)

    def test_split_überspringt_cancelled(self):
        cancelled = _FakeLeg("S 50", "Wien Hauptbahnhof",
                             datetime(2026, 5, 28, 14, 5, tzinfo=self.tz),
                             cancelled=True)
        legs = [cancelled] + self.legs
        result = split_by_direction(legs, ["Wien"], n_per_direction=1)
        # Erster ist cancelled → nicht der erste "towards"
        self.assertNotEqual(result["towards"][0]["planned"], "14:05")
```

- [ ] **Step 2: Test laufen lassen — soll fehlschlagen**

Expected: `ImportError: cannot import name 'split_by_direction'`

- [ ] **Step 3: Implementation ergänzen**

In `scripts/fetch_trains.py`:

```python
def split_by_direction(legs: Iterable[Any], towards_substrings: Iterable[str],
                       n_per_direction: int = 1) -> dict:
    """Iteriert über pyhafas-Legs (oder Duck-Typ), klassifiziert nach Richtung,
    überspringt cancelled-Stunden und limitiert pro Richtung auf n_per_direction.
    Reihenfolge im Input wird beibehalten (Annahme: bereits chronologisch sortiert).
    """
    towards, away = [], []
    for leg in legs:
        if bool(getattr(leg, "cancelled", False)):
            continue
        dep = extract_departure(leg)
        bucket = classify_direction(dep["destination"], towards_substrings)
        target = towards if bucket == "towards" else away
        if len(target) < n_per_direction:
            target.append(dep)
        if len(towards) >= n_per_direction and len(away) >= n_per_direction:
            break
    return {"towards": towards, "away": away}
```

- [ ] **Step 4: Test laufen lassen — soll passen**

Expected: alle Tests bestanden.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_trains.py tests/test_fetch_trains.py
git commit -m "Train-Widget: split_by_direction + Tests"
```

---

## Task 5: `atomic_write_json` — Race-Free File-Writer, TDD

**Files:**
- Modify: `scripts/fetch_trains.py`
- Modify: `tests/test_fetch_trains.py`

- [ ] **Step 1: Failing test schreiben**

In `tests/test_fetch_trains.py` ergänzen:

```python
import json
import tempfile
from pathlib import Path

from scripts.fetch_trains import atomic_write_json


class TestAtomicWriteJson(unittest.TestCase):
    def test_schreibt_und_liest_korrekt_zurück(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trains.json"
            data = {"station": "Test", "towards": [], "away": []}
            atomic_write_json(path, data)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, data)

    def test_hinterlässt_kein_tmp_file_nach_erfolg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trains.json"
            atomic_write_json(path, {"k": "v"})
            self.assertFalse((Path(tmp) / "trains.json.tmp").exists())

    def test_überschreibt_bestehende_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trains.json"
            atomic_write_json(path, {"version": 1})
            atomic_write_json(path, {"version": 2})
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["version"], 2)
```

- [ ] **Step 2: Test laufen lassen — soll fehlschlagen**

Expected: `ImportError: cannot import name 'atomic_write_json'`

- [ ] **Step 3: Implementation**

In `scripts/fetch_trains.py` ergänzen — oben ergänzen:
```python
import json
import os
from pathlib import Path
```

Funktion:

```python
def atomic_write_json(path: Path, data: dict) -> None:
    """Schreibt JSON atomar: erst .tmp, dann os.replace.
    So sieht der Leser nie eine halbgeschriebene Datei."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
```

- [ ] **Step 4: Test laufen lassen — soll passen**

Expected: alle Tests bestanden.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_trains.py tests/test_fetch_trains.py
git commit -m "Train-Widget: atomic_write_json + Tests"
```

---

## Task 6: `load_config` (lokal) + `main()` mit pyhafas-Integration

**Files:**
- Modify: `scripts/fetch_trains.py`
- Modify: `tests/test_fetch_trains.py` (nur load_config-Test, kein Test für main)

Die `main()`-Funktion enthält den pyhafas-Aufruf. Wir testen sie *nicht* im unittest (würde Netzwerk + pyhafas brauchen). Stattdessen gibt es einen manuellen Smoke-Test im nächsten Step.

- [ ] **Step 1: Failing test für load_config schreiben**

In `tests/test_fetch_trains.py` ergänzen:

```python
from scripts.fetch_trains import load_config


class TestLoadConfig(unittest.TestCase):
    def test_liest_key_value_paare(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.env"
            cfg.write_text(
                "# comment\n"
                "TRAIN_STATION=Wien Hütteldorf\n"
                "TRAIN_DIR_TOWARDS=Hbf,Westbf\n"
                "TRAIN_PER_DIRECTION=2\n"
                "\n",
                encoding="utf-8",
            )
            config = load_config(cfg)
            self.assertEqual(config["TRAIN_STATION"], "Wien Hütteldorf")
            self.assertEqual(config["TRAIN_DIR_TOWARDS"], "Hbf,Westbf")
            self.assertEqual(config["TRAIN_PER_DIRECTION"], "2")
```

- [ ] **Step 2: Test laufen lassen — soll fehlschlagen**

Expected: `ImportError: cannot import name 'load_config'`

- [ ] **Step 3: Implementation**

In `scripts/fetch_trains.py` ergänzen (am Anfang nach den Imports):

```python
def load_config(path: Path) -> dict:
    """Liest .env-style key=value-Paare. Kommentare (#) und Leerzeilen werden ignoriert."""
    config = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                config[key.strip()] = val.strip()
    return config
```

- [ ] **Step 4: Test laufen lassen — soll passen**

Expected: alle Tests bestanden.

- [ ] **Step 5: `main()` ergänzen — mit lazy pyhafas-Import**

Am Ende von `scripts/fetch_trains.py`:

```python
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    try:
        TZ = ZoneInfo("Europe/Vienna")
    except Exception:
        TZ = None
except ImportError:
    TZ = None


BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.env"
DATA_DIR    = BASE_DIR / "data"
OUTPUT      = DATA_DIR / "trains.json"


def _now_local():
    return datetime.now(TZ) if TZ else datetime.now()


def main():
    config = load_config(CONFIG_FILE)
    if config.get("TRAIN_DISABLED", "").strip().lower() == "true":
        print("Train-Widget disabled via TRAIN_DISABLED=true", flush=True)
        return

    station_name = config.get("TRAIN_STATION", "").strip()
    if not station_name:
        print("TRAIN_STATION nicht gesetzt - kein fetch", flush=True)
        return

    towards_list = [s.strip() for s in config.get("TRAIN_DIR_TOWARDS", "").split(",") if s.strip()]
    try:
        n_per_dir = int(config.get("TRAIN_PER_DIRECTION", "1"))
    except ValueError:
        n_per_dir = 1

    # Lazy import: pyhafas wird nur im Hauptpfad geladen,
    # so dass tests/ keine pyhafas-Installation benötigen.
    from pyhafas import HafasClient
    from pyhafas.profile import OEBBProfile

    client = HafasClient(OEBBProfile())

    try:
        locations = client.locations(station_name)
        if not locations:
            print(f"Station '{station_name}' nicht gefunden", flush=True)
            return
        station = locations[0]
        print(f"Station: {station.name} (id={station.id})", flush=True)

        legs = client.departures(
            station=station.id,
            date=_now_local(),
            max_trips=20,
        )
        print(f"Departures geholt: {len(legs)}", flush=True)

        result = split_by_direction(legs, towards_list, n_per_dir)
    except Exception as e:
        print(f"pyhafas-Fehler ({type(e).__name__}): {e}", flush=True)
        print("data/trains.json wird NICHT überschrieben - alte Daten bleiben.", flush=True)
        return

    DATA_DIR.mkdir(exist_ok=True)
    payload = {
        "station":     station.name,
        "fetched_at":  _now_local().isoformat(timespec="seconds"),
        "towards":     result["towards"],
        "away":        result["away"],
    }
    atomic_write_json(OUTPUT, payload)
    print(
        f"Fertig: {len(result['towards'])} towards, {len(result['away'])} away → {OUTPUT}",
        flush=True,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Tests nochmal laufen lassen — Smoke-Check dass alles importierbar bleibt**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```

Expected: alle bisherigen Tests grün (load_config + 3 vorige Klassen).

- [ ] **Step 7: Commit**

```bash
git add scripts/fetch_trains.py tests/test_fetch_trains.py
git commit -m "Train-Widget: load_config + main() mit pyhafas (lazy import)"
```

---

## Task 7: pyhafas installieren und Smoke-Test live ausführen

**Files:** keine (manueller Schritt)

Dieser Task ist *einmalig manuell* und nicht im Repo. Pyhafas muss lokal vorhanden sein, damit der echte API-Aufruf testbar ist.

- [ ] **Step 1: pyhafas installieren**

Auf dem Entwickler-Rechner (Windows-Python):
```bash
/mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m pip install pyhafas
```

Expected: „Successfully installed pyhafas-X.Y.Z" + Sub-Dependencies.

- [ ] **Step 2: `config.env` lokal um TRAIN_*-Variablen erweitern**

Manuelle Edit (Claude liest `config.env` nicht — siehe CLAUDE.md). Vom User selbst ergänzt:
```
TRAIN_STATION=Wien Hütteldorf
TRAIN_DIR_TOWARDS=Hbf,Westbf,Praterstern,Heiligenstadt,Floridsdorf,Meidling,Mitte
TRAIN_PER_DIRECTION=1
TRAIN_DISABLED=false
```

- [ ] **Step 3: Smoke-Test ausführen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_trains.py
```

Expected:
- Zeile „Station: Wien Hütteldorf Bahnhof (id=...)"
- Zeile „Departures geholt: N" (N > 0)
- Zeile „Fertig: 1 towards, 1 away → .../data/trains.json"

- [ ] **Step 4: JSON-Datei inspizieren**

```bash
cat /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/data/trains.json
```

Expected: gültiges JSON mit `station`, `fetched_at`, `towards[1]`, `away[1]` — sinnvolle Linien/Destinationen/Zeiten.

- [ ] **Step 5: Bei Problemen Anpassungen**

Falls `station.id` z.B. nicht existiert (pyhafas-API hat sich geändert): nachschauen in `dir(station)` und Code in `main()` anpassen. Die Tests müssen weiterhin grün bleiben.

- [ ] **Step 6: Kein Commit nötig (sofern keine Code-Anpassung). Falls Anpassung:**

```bash
git add scripts/fetch_trains.py
git commit -m "Train-Widget: main() an reale pyhafas-API angepasst (Smoke-Test)"
```

---

## Task 8: Widget-Container in `fetch_untis.py` einbauen

**Files:**
- Modify: `scripts/fetch_untis.py`

Wir bauen einen neuen `<div>` im Header zwischen `header-left` und `header-right` ein. Im Python-Code reicht das, weil der Browser via JS dynamisch befüllt.

- [ ] **Step 1: Helper-Funktion für Widget-HTML hinzufügen**

In `scripts/fetch_untis.py` — vor `def generate_html(...)` ergänzen:

```python
def render_train_widget(enabled: bool) -> str:
    """Liefert den HTML-Stub für das Zug-Widget im Header.
    Inhalt wird zur Laufzeit per JavaScript aus data/trains.json befüllt.
    Bei enabled=False → leerer String (Widget wird nicht ins DOM eingebaut)."""
    if not enabled:
        return ""
    return (
        '<div class="train-widget" id="train-widget" data-state="loading">'
        '<div class="tw-station" id="tw-station">— Zugdaten werden geladen —</div>'
        '<div class="tw-rows">'
        '<div class="tw-bucket" id="tw-towards-row"></div>'
        '<div class="tw-bucket" id="tw-away-row"></div>'
        '</div>'
        '<div class="tw-foot" id="tw-foot"></div>'
        '</div>'
    )
```

- [ ] **Step 2: Widget aus `config.env` an `generate_html` durchreichen**

In `main()` von `fetch_untis.py`, vor dem `generate_html`-Aufruf ergänzen:

```python
        train_enabled = (
            config.get("TRAIN_STATION", "").strip()
            and config.get("TRAIN_DISABLED", "").strip().lower() != "true"
        )
```

`generate_html`-Aufruf erweitern:

```python
        html = generate_html(
            groups_today, groups_tomorrow, today, tomorrow_date,
            teacher_lookup, period_nr, p_start, p_end,
            show_logo=show_logo,
            import_time=import_time,
            train_enabled=bool(train_enabled),
        )
```

- [ ] **Step 3: `generate_html`-Signatur erweitern**

In `scripts/fetch_untis.py` die Funktions-Signatur:

```python
def generate_html(groups_today, groups_tomorrow, today_date, tomorrow_date,
                  teacher_lookup, period_nr, period_start, period_end,
                  show_logo=False, import_time=None, train_enabled=False):
```

- [ ] **Step 4: Widget zwischen Header-Left und Header-Right einsetzen**

In `generate_html`, im HTML-Template-String den Block `<header class="header">` so umbauen:

Alter Block:
```python
    <header class="header">
        <div class="header-left">
            {logo_html}<div>
                <p class="school-name">MS Roda-Roda-Gasse</p>
                <p class="school-sub">Mittelschule · 1210 Wien</p>
            </div>
        </div>
        <div class="header-right">
```

Neuer Block (zusätzlicher `train_widget_html` zwischen den Divs):

```python
    <header class="header">
        <div class="header-left">
            {logo_html}<div>
                <p class="school-name">MS Roda-Roda-Gasse</p>
                <p class="school-sub">Mittelschule · 1210 Wien</p>
            </div>
        </div>
        {train_widget_html}
        <div class="header-right">
```

Und vor dem `return f"""...` String die Variable definieren:
```python
    train_widget_html = render_train_widget(train_enabled)
```

- [ ] **Step 5: HTML lokal generieren und prüfen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```
Dann:
```bash
grep -o 'train-widget' /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html | head -3
```
Expected: mehrere Matches (Container + IDs).

Falls in `config.env` `TRAIN_STATION` (noch) nicht gesetzt ist, kommt kein Match — das ist OK.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "Train-Widget: HTML-Container im Header (leer, JS befüllt)"
```

---

## Task 9: CSS für das Widget

**Files:**
- Modify: `css/style.css`

- [ ] **Step 1: Header-Layout-Anpassung — `flex: 1` für left/right entfernen wäre falsch (würde stretchen). Stattdessen Widget mit fixer Breite.**

Suche in `css/style.css` nach `.header {` (Zeile ~105). Direkt darunter Block einfügen:

```css
/* ── Train-Widget im Header ──────────────────────── */
.train-widget {
    flex: 0 0 360px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--c-border);
    border-radius: 6px;
    padding: 8px 14px;
    font-family: var(--font-d);
    margin: 0 16px;
    max-height: calc(var(--h-header) - 16px);
    overflow: hidden;
}

.tw-station {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--c-muted);
    margin-bottom: 4px;
}

.tw-rows {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.tw-bucket {
    /* Container pro Richtung - wird per JS mit 0..n .tw-row gefüllt */
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.tw-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: var(--c-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.tw-row .tw-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}

.tw-towards .tw-dot { background: #3db060; }
.tw-away .tw-dot    { background: #e05050; }

.tw-row .tw-arrow svg {
    width: 18px;
    height: 14px;
    display: block;
}

.tw-towards .tw-arrow svg { transform: scaleX(1); }
.tw-away    .tw-arrow svg { transform: scaleX(-1); }

.tw-row .tw-line        { font-weight: 700; min-width: 38px; }
.tw-row .tw-time        { font-weight: 700; }
.tw-row .tw-dest        { color: var(--c-text); opacity: 0.85; overflow: hidden; text-overflow: ellipsis; }
.tw-row .tw-delay       { color: var(--c-amber); font-weight: 700; margin-left: auto; }
.tw-row.tw-cancelled    { opacity: 0.5; text-decoration: line-through; }

.tw-foot {
    font-size: 10px;
    color: var(--c-muted);
    margin-top: 4px;
    text-align: right;
    letter-spacing: 0.06em;
}
.tw-foot.stale { color: var(--c-amber); }
```

- [ ] **Step 2: Lokal HTML neu generieren und im Browser kurz prüfen, falls möglich (kein Pflicht-Step jetzt — kommt mit JS in nächster Task zur Wirkung)**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```

Dann `index.html` lokal öffnen — der Widget-Container sollte als leere Box mit „— Zugdaten werden geladen —" sichtbar sein.

- [ ] **Step 3: Commit**

```bash
git add css/style.css
git commit -m "Train-Widget: CSS-Styling der Header-Komponente"
```

---

## Task 10: JavaScript — Widget alle 60s aus JSON befüllen

**Files:**
- Modify: `scripts/fetch_untis.py` (innerhalb des bestehenden `<script>`-Blocks)

- [ ] **Step 1: Im `generate_html`-Template das bestehende JS-Snippet erweitern**

Im `scripts/fetch_untis.py` den existierenden Block ergänzen. Aktueller Block (Ausschnitt):

```python
<script>
(function tick() {{
    var n = new Date();
    ...
    setTimeout(tick, 1000);
}})();

// Auto-Refresh: 60s soft-reload, alle 5 min Hard-Reload mit Cache-Bust
(function () {{
    var tick = 0;
    setInterval(function () {{
        ...
    }}, 60 * 1000);
}})();
</script>
```

Direkt **vor** dem schließenden `</script>` ergänzen:

```python
// ── Train-Widget Updater ──
(function () {{
    var widget = document.getElementById('train-widget');
    if (!widget) return;

    var ARROW_SVG = '<svg viewBox="0 0 20 14"><path d="M2 7h13M11 3l5 4-5 4" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';

    function fmtRow(dep, klass) {{
        var row = document.createElement('div');
        var cancelled = dep.cancelled ? ' tw-cancelled' : '';
        row.className = 'tw-row ' + klass + cancelled;
        // Skelett aufbauen (SVG ist statisch + sicher)
        row.innerHTML =
            '<span class="tw-dot"></span>' +
            '<span class="tw-arrow">' + ARROW_SVG + '</span>' +
            '<span class="tw-line"></span>' +
            '<span class="tw-time"></span>' +
            '<span class="tw-dest"></span>';
        // Werte aus der API via textContent setzen (XSS-safe):
        row.querySelector('.tw-line').textContent = dep.line || '';
        row.querySelector('.tw-time').textContent = dep.actual || dep.planned || '';
        row.querySelector('.tw-dest').textContent = dep.destination || '';
        if (dep.delay_minutes > 0) {{
            var d = document.createElement('span');
            d.className = 'tw-delay';
            d.textContent = '+' + dep.delay_minutes;
            row.appendChild(d);
        }}
        return row;
    }}

    function update(data) {{
        document.getElementById('tw-station').textContent = data.station || '';
        var tCell = document.getElementById('tw-towards-row');
        var aCell = document.getElementById('tw-away-row');
        tCell.innerHTML = '';
        aCell.innerHTML = '';
        (data.towards || []).forEach(function (dep) {{ tCell.appendChild(fmtRow(dep, 'tw-towards')); }});
        (data.away    || []).forEach(function (dep) {{ aCell.appendChild(fmtRow(dep, 'tw-away')); }});

        var foot = document.getElementById('tw-foot');
        var fetched = data.fetched_at ? new Date(data.fetched_at) : null;
        if (fetched && !isNaN(fetched.getTime())) {{
            var ageMin = Math.floor((Date.now() - fetched.getTime()) / 60000);
            foot.textContent = 'Stand: ' + (ageMin <= 0 ? 'jetzt' : 'vor ' + ageMin + ' min');
            foot.className = 'tw-foot' + (ageMin > 5 ? ' stale' : '');
        }} else {{
            foot.textContent = '';
        }}
        widget.setAttribute('data-state', 'ok');
    }}

    function load() {{
        fetch('data/trains.json?cb=' + Date.now(), {{cache: 'no-store'}})
            .then(function (r) {{ return r.ok ? r.json() : null; }})
            .then(function (data) {{ if (data) update(data); }})
            .catch(function () {{ /* JSON nicht erreichbar → DOM unverändert */ }});
    }}

    load();
    setInterval(load, 60 * 1000);
}})();
```

Achte auf die doppelten geschweiften Klammern `{{...}}` — das ist nötig weil der ganze Block in einer Python-f-string ist.

- [ ] **Step 2: HTML generieren und prüfen dass das JS sauber im Output ist**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
grep -c 'Train-Widget Updater' /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
```
Expected: `1`.

- [ ] **Step 3: Im Browser testen**

`index.html` lokal öffnen. Mit DevTools Network-Tab: nach Page-Load sollte ein `GET data/trains.json` sichtbar sein. Wenn Datei vorhanden → Widget wird befüllt; wenn nicht → bleibt bei „— Zugdaten werden geladen —".

- [ ] **Step 4: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "Train-Widget: JS-Update-Loop holt data/trains.json alle 60s"
```

---

## Task 11: `config.env.example` + CLAUDE.md + Cron-Doku

**Files:**
- Modify: `config.env.example`
- Modify: `CLAUDE.md`

- [ ] **Step 1: `config.env.example` erweitern**

Am Ende ergänzen:

```
# ── Zug-Widget (optional) ────────────────────────────────────
# Wenn TRAIN_STATION leer ist, wird das Widget nicht ins HTML eingebaut.
# Eigener Cron-Job alle 60s ruft scripts/fetch_trains.py auf - schreibt data/trains.json.
TRAIN_STATION=Wien Hütteldorf
TRAIN_DIR_TOWARDS=Hbf,Westbf,Praterstern,Heiligenstadt,Floridsdorf,Meidling,Mitte
TRAIN_PER_DIRECTION=1
TRAIN_DISABLED=false
```

- [ ] **Step 2: CLAUDE.md erweitern**

Suche die Sektion „Architektur" (am Anfang von CLAUDE.md). Nach dem ASCII-Diagramm einfügen:

```markdown
### Zug-Widget (separater Datenfluss)
```
Cron jede Minute → scripts/fetch_trains.py
    → pyhafas → ÖBB HAFAS API
    → data/trains.json (atomar geschrieben, alte Datei bleibt bei Fehler)

Browser fetched data/trains.json alle 60s und befüllt #train-widget im Header.
```

Konfiguration in `config.env` über `TRAIN_*`-Variablen. Wenn `TRAIN_STATION` leer oder
`TRAIN_DISABLED=true`, wird das Widget nicht ins HTML eingebaut.
```

Suche die Sektion „Cron-Setup" (falls vorhanden, sonst direkt vor „Konventionen & Sicherheit"):

```markdown
### Cron-Setup auf dem LXC
```cron
*/5  * * * *  cd /var/www/supplierplan && python3 scripts/fetch_untis.py  >> /var/log/supplierplan-untis.log 2>&1
*    * * * *  cd /var/www/supplierplan && python3 scripts/fetch_trains.py >> /var/log/supplierplan-trains.log 2>&1
```

Voraussetzung: `pip3 install -r requirements.txt` auf dem LXC.
```

In Sektion „Offene Punkte / TODOs" als erledigt markieren falls dort etwas zu Zug-Anzeige stand. (Aktuell vermutlich nichts.)

- [ ] **Step 3: Commit**

```bash
git add config.env.example CLAUDE.md
git commit -m "Train-Widget: config.env.example + CLAUDE.md aktualisiert"
```

---

## Task 12: Branch pushen + Pull-Request-Notizen

**Files:** keine

- [ ] **Step 1: Branch zu GitHub pushen**

```bash
git push -u origin feature/train-widget
```

Expected: „* [new branch] feature/train-widget -> feature/train-widget"

- [ ] **Step 2: Status-Check der Tests**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```

Expected: alle Tests grün.

- [ ] **Step 3: Notiz für den User: Cron-Setup auf LXC noch manuell**

Hinweis dass der User folgendes auf dem LXC tun muss:
1. `pip3 install -r requirements.txt`
2. Crontab-Eintrag für `fetch_trains.py` jede Minute hinzufügen
3. `config.env` auf dem LXC um die `TRAIN_*`-Variablen erweitern
4. rsync vom Branch (oder Merge in master + rsync)

- [ ] **Step 4: Merge-Entscheidung dem User überlassen**

Branch bleibt offen für Review. Merge nach `master` erst wenn lokaler Test im Browser bestätigt.

---

## Test-Strategie Übersicht

Was getestet wird (in `tests/test_fetch_trains.py`):
- `classify_direction` — Substring-Logik, case-insensitive, leere Whitelist
- `extract_departure` — Verspätungsfälle, cancelled, Platform
- `split_by_direction` — Aufteilung, Limit pro Richtung, Cancelled-Skip
- `atomic_write_json` — Schreiben, Cleanup von .tmp, Overwrite
- `load_config` — .env-Parser

Was **nicht** automatisiert getestet wird (manueller Smoke-Test):
- pyhafas-Aufruf gegen die echte ÖBB-API (Netzwerk + externe Stabilität)
- Browser-DOM-Update via JavaScript
- Visuelles Rendering im Header

---

## Risiken & Mitigation in Reihenfolge der Tasks

1. **pyhafas-API-Form** kann sich von dem ändern was hier dokumentiert ist. Task 7 fängt das mit dem Smoke-Test ab — falls `station.id` oder `client.departures(...)` anders aussieht, wird im `main()` angepasst (Tests bleiben grün, da sie nicht von pyhafas abhängen).
2. **Header-Layout zu eng** für ein 360px-Widget bei großen Logos/Uhren. Mitigation: `max-width` auf Logo zur Not + Test im Browser nach Task 9.
3. **JSON-Race** bei gleichzeitigem Schreiben/Lesen — abgefangen durch `atomic_write_json` (`os.replace`).
4. **XSS bei Stationsnamen** — nicht via innerHTML, sondern `textContent`. Im JS in Task 10 explizit so umgesetzt.
