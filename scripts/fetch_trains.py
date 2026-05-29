#!/usr/bin/env python3
"""
fetch_trains.py – holt die nächsten Abfahrten einer Bahnhaltestelle via pyhafas
und schreibt sie in data/trains.json.
Läuft per Cron jede Minute (separater Job vom Untis-Cron).
"""

from datetime import timedelta
from typing import Iterable, Any


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
