#!/usr/bin/env python3
"""
fetch_trains.py – holt die nächsten Abfahrten einer Bahnhaltestelle direkt
über die ÖBB HAFAS mgate.exe-API und schreibt sie in data/trains.json.
Läuft per Cron jede Minute (separater Job vom Untis-Cron).

Stdlib-only: nutzt urllib für die HTTP-Anfrage, keine externen Dependencies.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Any


try:
    from zoneinfo import ZoneInfo
    try:
        TZ = ZoneInfo("Europe/Vienna")
    except Exception:
        TZ = None
except ImportError:
    TZ = None


BASE_DIR    = Path(__file__).resolve().parent.parent

def resolve_config_path() -> Path:
    """Pfad zur config.env. Bevorzugt $SUPPLIERPLAN_CONFIG, damit die Datei mit
    Geheimnissen außerhalb des Webroots liegen kann; sonst Projekt-Root (dev)."""
    env_path = os.environ.get("SUPPLIERPLAN_CONFIG", "").strip()
    return Path(env_path) if env_path else BASE_DIR / "config.env"

CONFIG_FILE = resolve_config_path()
DATA_DIR    = BASE_DIR / "data"
OUTPUT      = DATA_DIR / "trains.json"


def _now_local():
    return datetime.now(TZ) if TZ else datetime.now()


# ── Pure logic (testbar, ohne externe Calls) ──────────────────────
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
    """Wandelt ein Leg-Objekt (Duck-Typ mit name, direction, dateTime, delay,
    cancelled, platform) in ein JSON-konformes dict um."""
    planned_dt = leg.dateTime
    delay = leg.delay or timedelta(0)
    delay_minutes = max(0, int(delay.total_seconds() // 60))
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


def filter_by_product_prefix(legs: Iterable[Any], prefixes: Iterable[str]) -> list:
    """Behält nur Legs, deren `name` mit einem der `prefixes` beginnt (case-insensitive).
    Wenn `prefixes` leer ist, wird die Liste unverändert zurückgegeben.
    Convention: Prefixes enden meist mit einem Leerzeichen (z.B. 'S ') damit 'S 3'
    matcht, aber 'SR 1' nicht."""
    plist = [p.lower() for p in prefixes if p]
    if not plist:
        return list(legs)
    return [
        leg for leg in legs
        if any((leg.name or "").lower().startswith(p) for p in plist)
    ]


def split_by_direction(legs: Iterable[Any], towards_substrings: Iterable[str],
                       n_per_direction: int = 1) -> dict:
    """Iteriert über Legs (oder Duck-Typ), klassifiziert nach Richtung,
    überspringt cancelled-Einträge und limitiert pro Richtung auf n_per_direction.
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


# ── ÖBB HAFAS mgate Direct-Client ─────────────────────────────────
OEBB_MGATE_URL    = "https://fahrplan.oebb.at/bin/mgate.exe"
OEBB_CLIENT_CONF  = {"id": "OEBB", "v": "6030600", "type": "AND", "name": "oebbHAFAS"}
OEBB_AUTH         = {"type": "AID", "aid": "OWDL4fE4ixNiPBBm"}


def _mgate_request(svc_method: str, params: dict) -> dict:
    """Sendet eine mgate.exe-Anfrage und liefert das svcResL[0].res-dict zurück."""
    body = {
        "id":        "supplierplan",
        "ver":       "1.45",
        "lang":      "deu",
        "auth":      OEBB_AUTH,
        "client":    OEBB_CLIENT_CONF,
        "formatted": False,
        "svcReqL":   [{"meth": svc_method, "req": params}],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        OEBB_MGATE_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent":   "Mozilla/5.0 supplierplan",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    if result.get("err") and result["err"] != "OK":
        raise RuntimeError(f"mgate Fehler: {result.get('err')} {result.get('errTxt','')}")
    svc = result["svcResL"][0]
    if svc.get("err") and svc["err"] != "OK":
        raise RuntimeError(f"mgate svc Fehler: {svc.get('err')} {svc.get('errTxt','')}")
    return svc["res"]


def _resolve_station_lid(name: str) -> tuple:
    """Findet eine Station per LocMatch. Liefert (resolved_name, lid)."""
    res = _mgate_request("LocMatch", {
        "input": {
            "loc":    {"name": name, "type": "S"},
            "maxLoc": 1,
            "field":  "S",
        }
    })
    matches = res.get("match", {}).get("locL", [])
    if not matches:
        raise RuntimeError(f"Keine Station gefunden für '{name}'")
    m = matches[0]
    return m["name"], m["lid"]


def _parse_hafas_time(value: str) -> timedelta:
    """HAFAS-Zeitformat HHMMSS (oder DHHMMSS für nächster Tag) → timedelta seit Tagesbeginn."""
    s = str(value)
    days = 0
    if len(s) == 7:
        days = int(s[0])
        s = s[1:]
    s = s.zfill(6)
    h   = int(s[0:2])
    m   = int(s[2:4])
    sec = int(s[4:6])
    return timedelta(days=days, hours=h, minutes=m, seconds=sec)


class _OebbLeg:
    """Duck-typed Leg-Objekt, identische Attribute wie _FakeLeg in den Tests.
    extract_departure/split_by_direction arbeiten damit unverändert."""
    def __init__(self, name, direction, dateTime, delay=None, cancelled=False, platform=None):
        self.name      = name
        self.direction = direction
        self.dateTime  = dateTime
        self.delay     = delay
        self.cancelled = cancelled
        self.platform  = platform


def _fetch_departures(lid: str, max_jny: int = 12) -> list:
    """Holt das StationBoard für die Location-ID und liefert _OebbLeg-Liste."""
    res = _mgate_request("StationBoard", {
        "type":     "DEP",
        "stbLoc":   {"lid": lid},
        "maxJny":   max_jny,
        "jnyFltrL": [{"type": "PROD", "mode": "INC", "value": 511}],
    })
    common = res.get("common", {})
    prodL  = common.get("prodL", [])

    legs = []
    today = _now_local().date()

    for j in res.get("jnyL", []):
        stbStop = j.get("stbStop", {})

        # Plan-Abfahrtszeit erforderlich
        d_time_s = stbStop.get("dTimeS")
        if not d_time_s:
            continue

        # Datum (kann sich vom heute unterscheiden, z.B. Mitternacht-Übergang)
        date_str = j.get("date", today.strftime("%Y%m%d"))
        try:
            base_date = datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            base_date = today

        planned_dt = datetime.combine(base_date, datetime.min.time()) + _parse_hafas_time(d_time_s)
        if TZ:
            planned_dt = planned_dt.replace(tzinfo=TZ)

        delay = None
        d_time_r = stbStop.get("dTimeR")
        if d_time_r:
            real_dt = datetime.combine(base_date, datetime.min.time()) + _parse_hafas_time(d_time_r)
            if TZ:
                real_dt = real_dt.replace(tzinfo=TZ)
            delay = real_dt - planned_dt

        # Linien-/Produktname (ohne den Zug-Nr.-Zusatz)
        line_name = ""
        prod_x = j.get("prodX")
        if prod_x is not None and 0 <= prod_x < len(prodL):
            line_name = prodL[prod_x].get("name", "").strip()
            line_name = line_name.split(" (")[0]   # 'S 3 (Zug-Nr. 28589)' → 'S 3'

        direction = j.get("dirTxt", "").strip()
        cancelled = bool(stbStop.get("dCncl"))

        platform = stbStop.get("dPlatfR") or stbStop.get("dPlatfS")
        if isinstance(platform, dict):
            platform = platform.get("txt")

        legs.append(_OebbLeg(
            name=line_name,
            direction=direction,
            dateTime=planned_dt,
            delay=delay,
            cancelled=cancelled,
            platform=platform,
        ))
    return legs


# ── Main ──────────────────────────────────────────────────────────
def main():
    if not CONFIG_FILE.exists():
        print(f"config.env nicht gefunden: {CONFIG_FILE}", flush=True)
        return
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

    # Produkt-Filter: z.B. "S" matcht "S 3", "S 50". Leer = alle Produkte (inkl. Bus).
    products_raw = config.get("TRAIN_PRODUCTS", "").strip()
    product_prefixes = [p.strip() + " " for p in products_raw.split(",") if p.strip()]

    try:
        resolved_name, lid = _resolve_station_lid(station_name)
        print(f"Station: {resolved_name} (lid={lid})", flush=True)
        legs = _fetch_departures(lid, max_jny=24)
        print(f"Departures geholt: {len(legs)}", flush=True)
        if product_prefixes:
            legs = filter_by_product_prefix(legs, product_prefixes)
            print(f"Nach Produkt-Filter ({products_raw}): {len(legs)}", flush=True)
        result = split_by_direction(legs, towards_list, n_per_dir)
    except Exception as e:
        print(f"ÖBB-Fehler ({type(e).__name__}): {e}", flush=True)
        print("data/trains.json wird NICHT überschrieben - alte Daten bleiben.", flush=True)
        return

    DATA_DIR.mkdir(exist_ok=True)
    payload = {
        "station":    resolved_name,
        "fetched_at": _now_local().isoformat(timespec="seconds"),
        "towards":    result["towards"],
        "away":       result["away"],
    }
    atomic_write_json(OUTPUT, payload)
    print(
        f"Fertig: {len(result['towards'])} towards, {len(result['away'])} away -> {OUTPUT}",
        flush=True,
    )


if __name__ == "__main__":
    main()
