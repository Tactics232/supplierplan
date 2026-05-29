#!/usr/bin/env python3
"""
fetch_trains.py – holt die nächsten Abfahrten einer Bahnhaltestelle via pyhafas
und schreibt sie in data/trains.json.
Läuft per Cron jede Minute (separater Job vom Untis-Cron).
"""

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Iterable, Any


def atomic_write_json(path: Path, data: dict) -> None:
    """Schreibt JSON atomar: erst .tmp, dann os.replace.
    So sieht der Leser nie eine halbgeschriebene Datei."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


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
