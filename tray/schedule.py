"""Reine Zeitplan-Logik für den Abwesenheits-Lauf (testbar, ohne Threads/IO).

Der Service feuert den Abwesenheits-Lauf zu festen Lokalzeiten (Cron-deckungsgleich
07:35/11:00/16:00). `next_run_time` berechnet die nächste fällige Wall-Clock-Zeit
strikt nach `now`; der Service macht daraus einen Timer-Delay und stellt nach jedem
Lauf neu scharf.
"""
from datetime import datetime, timedelta

# Cron-deckungsgleiche Default-Zeiten (siehe Crontab im CLAUDE.md).
DEFAULT_ABSENCE_TIMES = ["07:35", "11:00", "16:00"]


def parse_times(spec):
    """"HH:MM,HH:MM,…" → sortierte Liste von (hour, minute). Müll/ungültige
    Uhrzeiten fallen still raus."""
    out = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            h_str, m_str = part.split(":")
            h, m = int(h_str), int(m_str)
        except (ValueError, AttributeError):
            continue
        if 0 <= h <= 23 and 0 <= m <= 59:
            out.append((h, m))
    return sorted(out)


def next_run_time(now: datetime, times) -> datetime:
    """Nächster Zeitpunkt strikt nach `now`, der einer der `times` entspricht.
    `times` als ["HH:MM", …] oder [(h, m), …]; heute wenn noch eine Zeit voraus
    liegt, sonst die früheste am Folgetag.

    ValueError, wenn `times` leer ist (ohne Zeiten gibt es nichts zu planen).
    """
    parsed = times if (times and isinstance(times[0], tuple)) else parse_times(
        ",".join(times) if times else "")
    if not parsed:
        raise ValueError("next_run_time: keine gültigen Zeiten")
    for h, m in parsed:
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate > now:
            return candidate
    h, m = parsed[0]
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=h, minute=m, second=0, microsecond=0)
