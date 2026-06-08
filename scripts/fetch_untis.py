#!/usr/bin/env python3
"""
fetch_untis.py – WebUntis Supplierplan Fetcher
Holt den heutigen (und ggf. morgigen) Supplierplan und generiert index.html
"""

import html as _html
import json
import os
import re
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict
try:
    from zoneinfo import ZoneInfo
    try:
        TZ = ZoneInfo("Europe/Vienna")
    except Exception:
        # Windows: TZ-Datenbank fehlt (pip install tzdata)
        TZ = None
except ImportError:
    TZ = None  # Python <3.9

def now_local():
    """Aktuelle Ortszeit (oder System-Zeit falls ZoneInfo nicht verfügbar)."""
    return datetime.now(TZ) if TZ else datetime.now()

def today_local():
    return now_local().date()

def set_timezone(name):
    """Überschreibt die globale Zeitzone aus config.env (TIMEZONE).
    Bei leerem Namen oder fehlender tzdata bleibt der bisherige Fallback."""
    global TZ
    if not name:
        return
    try:
        from zoneinfo import ZoneInfo as _ZI
        TZ = _ZI(name)
    except Exception:
        pass  # ungültige TZ / fehlende tzdata → Fallback unverändert


def esc(s):
    """HTML-escape a value from external data sources."""
    return _html.escape(str(s)) if s is not None else ""

BASE_DIR    = Path(__file__).parent.parent

def resolve_config_path():
    """Pfad zur config.env. Bevorzugt $SUPPLIERPLAN_CONFIG — damit die Datei mit
    Passwort/Token AUSSERHALB des vom Webserver ausgelieferten Verzeichnisses
    liegen kann (z.B. /etc/supplierplan/config.env). Ohne die Variable wird wie
    bisher die Datei im Projekt-Root genutzt (abwärtskompatibel, lokal/dev)."""
    env_path = os.environ.get("SUPPLIERPLAN_CONFIG", "").strip()
    return Path(env_path) if env_path else BASE_DIR / "config.env"

CONFIG_FILE = resolve_config_path()

# Schul-spezifische Defaults — in main() aus config.env überschrieben
# (PLAN_TITLE/LOGO_FILE). Als Modul-Globals, weil an mehreren Render-Stellen genutzt.
PLAN_TITLE = "Supplierplan"
LOGO_FILE  = "logo.png"

# ── Config ────────────────────────────────────────────
def load_config():
    config = {}
    with open(CONFIG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                config[key.strip()] = val.strip()
    return config

# cellState-Werte aus weekly/data, in denen ein Lehrer wirklich anwesend ist
# (normaler Unterricht / Pausenaufsicht). CANCEL + SUBSTITUTION = nicht anwesend.
PRESENT_CELLSTATES = {"STANDARD", "BREAKSUPERVISION"}

# ── WebUntis JSON-RPC Client ──────────────────────────
class WebUntis:
    def __init__(self, url, school_id, user, password):
        self.base_url  = url.rstrip("/")
        self.endpoint  = self.base_url + "/WebUntis/jsonrpc.do"
        self.school_id = school_id
        self.user      = user
        self.password  = password
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def _rpc(self, method, params=None):
        payload = json.dumps({
            "jsonrpc": "2.0", "id": "1",
            "method": method, "params": params or {}
        }).encode()
        url = f"{self.endpoint}?school={urllib.parse.quote(self.school_id)}"
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"}
        )
        with self.opener.open(req, timeout=15) as resp:
            result = json.loads(resp.read())
        if "error" in result:
            raise RuntimeError(f"API [{result['error']['code']}]: {result['error']['message']}")
        return result.get("result")

    def login(self):
        self._rpc("authenticate", {
            "user": self.user, "password": self.password, "client": "supplierplan"
        })

    def logout(self):
        try:
            self._rpc("logout")
        except Exception:
            pass

    def get_substitutions(self, date_int, department_id=0):
        return self._rpc("getSubstitutions", {
            "startDate": date_int, "endDate": date_int, "departmentId": department_id
        })

    def get_timegrid(self):
        return self._rpc("getTimegridUnits")

    def get_teachers(self):
        return self._rpc("getTeachers")

    def get_holidays(self):
        return self._rpc("getHolidays")

    def get_klassen(self):
        return self._rpc("getKlassen")

    def get_weekly_class_absences(self, date_obj):
        """REST weekly/data → {classId: set(startTime)} mit state=ABSENT für Klassen."""
        date_str = date_obj.strftime("%Y-%m-%d")
        url = (f"{self.base_url}/WebUntis/api/public/timetable/weekly/data"
               f"?elementType=1&elementId=0&date={date_str}")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with self.opener.open(req, timeout=15) as resp:
            data = json.loads(resp.read())
        periods = data.get("data", {}).get("result", {}).get("data", {}).get("elementPeriods", {})
        target_int = int(date_obj.strftime("%Y%m%d"))
        absent = {}
        for bucket in periods.values():
            for p in bucket:
                if p.get("date") != target_int:
                    continue
                for e in p.get("elements", []):
                    if (e.get("type") == 1
                            and e.get("state") == "ABSENT"
                            and e.get("orgId", 0) > 0):
                        absent.setdefault(e["orgId"], set()).add(p["startTime"])
        return absent

    def get_teacher_present_periods(self, teacher_id, date_obj):
        """REST weekly/data für EINEN Lehrer → Set der startTimes, in denen er an
        `date_obj` tatsächlich anwesend ist (cellState STANDARD oder
        BREAKSUPERVISION). Entfallene (CANCEL) und weg-vertretene (SUBSTITUTION)
        Stunden zählen NICHT als anwesend.

        ⚠️ Das `state`-Feld am Lehrer-Element ist unbrauchbar (steht auch bei
        entfallenen Stunden auf REGULAR) — maßgeblich ist `cellState` der Periode.
        `elementId=0` liefert Phantom-Daten (falscher Tag); daher echte Lehrer-ID.
        """
        date_str = date_obj.strftime("%Y-%m-%d")
        url = (f"{self.base_url}/WebUntis/api/public/timetable/weekly/data"
               f"?elementType=2&elementId={teacher_id}&date={date_str}")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with self.opener.open(req, timeout=15) as resp:
            data = json.loads(resp.read())
        periods = data.get("data", {}).get("result", {}).get("data", {}).get("elementPeriods", {})
        target_int = int(date_obj.strftime("%Y%m%d"))
        present = set()
        for p in periods.get(str(teacher_id), []):
            if p.get("date") != target_int:
                continue
            if p.get("cellState") in PRESENT_CELLSTATES:
                present.add(p.get("startTime"))
        return present

    def get_latest_import_time(self):
        ms = self._rpc("getLatestImportTime")
        if ms:
            if TZ:
                return datetime.fromtimestamp(ms / 1000, tz=TZ)
            return datetime.fromtimestamp(ms / 1000)
        return None

# ── Zeitraster ────────────────────────────────────────
def build_timegrid(days):
    seen = {}
    if not days:
        return seen
    for unit in days[0].get("timeUnits", []):
        start = unit["startTime"]
        end   = unit["endTime"]
        nr    = int(unit.get("name", 1)) - 1   # 0. Stunde Korrektur
        if start not in seen:
            seen[start] = (nr, start, end)
    return seen

def build_break_lookup(days):
    breaks = {}
    if not days:
        return breaks
    units = days[0].get("timeUnits", [])
    for i, unit in enumerate(units):
        if i + 1 < len(units):
            nr         = int(unit.get("name", i + 1)) - 1
            period_end = unit["endTime"]
            next_start = units[i + 1]["startTime"]
            if next_start > period_end:
                breaks[period_end] = f"{nr}/{nr+1}"
    return breaks

def fmt_time(t):
    h, m = divmod(t, 100)
    return f"{h:02d}:{m:02d}"

def find_current_period(timegrid):
    n = now_local()
    now_t = n.hour * 100 + n.minute
    for start, (nr, s, e) in sorted(timegrid.items()):
        if s <= now_t <= e:
            return nr, fmt_time(s), fmt_time(e)
    return None, None, None

def now_hhmm():
    n = now_local()
    return n.hour * 100 + n.minute

# ── Ferien-Logik ──────────────────────────────────────
def parse_holidays(holidays):
    """Wandelt die Untis-Ferienliste in ein Set von date-Objekten."""
    days = set()
    if not holidays:
        return days
    for h in holidays:
        try:
            start = datetime.strptime(str(h["startDate"]), "%Y%m%d").date()
            end   = datetime.strptime(str(h["endDate"]),   "%Y%m%d").date()
        except (KeyError, ValueError):
            continue
        d = start
        while d <= end:
            days.add(d)
            d += timedelta(days=1)
    return days

def next_school_day(start, holiday_set):
    """Erster Werktag nach `start`, der kein Ferien-/Feiertag ist."""
    d = start + timedelta(days=1)
    while d.weekday() >= 5 or d in holiday_set:
        d += timedelta(days=1)
    return d

# ── Lehrer-Lookup ─────────────────────────────────────
# "---" und "" sind strukturelle Untis-Platzhalter (immer überspringen).
# Schul-eigene Pseudo-Lehrer (z.B. "Z Entfall") kommen via config.env SKIP_TEACHERS
# dazu (siehe configure_skip_teachers, in main aufgerufen).
SKIP_NAMES = {"---", ""}

def configure_skip_teachers(value):
    """Ergänzt SKIP_NAMES um die in config.env (SKIP_TEACHERS) gelisteten
    Pseudo-Lehrer-Kürzel (Komma-getrennt)."""
    for name in (value or "").split(","):
        name = name.strip()
        if name:
            SKIP_NAMES.add(name)

def build_class_id_lookup(klassen):
    """Klassen-ID → Klassen-Name."""
    return {k["id"]: k.get("name", "").strip() for k in (klassen or []) if k.get("id")}


def class_absences_to_list(absent_by_id, id_to_name, timegrid):
    """Wandelt {classId: set(startTime)} in [(name, range_str), ...].
    Range-Logik: einzelne Std → '7', sonst 'min–max'."""
    def start_to_nr(start):
        info = timegrid.get(start)
        return info[0] if info else None

    by_name = {}
    for cid, starts in absent_by_id.items():
        name = id_to_name.get(cid)
        if not name:
            continue
        nrs = {start_to_nr(s) for s in starts}
        nrs.discard(None)
        if nrs:
            by_name[name] = nrs

    def period_range(nrs):
        nums = sorted(nrs)
        if len(nums) == 1:
            return str(nums[0])
        return f"{nums[0]}–{nums[-1]}"

    return [(name, period_range(nrs)) for name, nrs in sorted(by_name.items())]


def build_teacher_lookup(teachers):
    lookup = {}
    for t in teachers:
        kuerzel = t.get("name", "").strip()
        if not kuerzel or kuerzel in SKIP_NAMES:
            continue
        long   = t.get("longName", "").strip()
        parts  = long.split(" ", 1)
        lookup[kuerzel] = {
            "nachname": parts[0] if parts else kuerzel,
            "vorname":  parts[1] if len(parts) > 1 else "",
        }
    return lookup

# ── Datenaufbereitung ─────────────────────────────────
def _dedupe_names(items):
    """Liste von dicts mit 'name' zu Liste eindeutiger Namen ohne '---' / leer."""
    seen, out = set(), []
    for it in items:
        name = (it.get("name") or "").strip()
        if not name or name == "---" or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out

def _is_meaningful_subst(s):
    """True wenn die Substitution überhaupt eine echte Änderung darstellt."""
    typ = s.get("type", "subst")
    if typ in ("cancel", "free"):
        return True
    if any(t.get("orgid") for t in s.get("te", [])):
        return True
    if any(r.get("orgid") for r in s.get("ro", [])):
        return True
    return False

def _has_real_subst_teacher(s):
    """True wenn ein echter Vertretungs-Lehrer im te[] steht (orgid + Name != '---')."""
    return any(
        t.get("orgid") and (t.get("name") or "").strip() not in SKIP_NAMES
        for t in s.get("te", [])
    )

def process_substitutions(substs, timegrid, break_lookup, day="today"):
    rows = []
    for s in substs:
        # ── Filter A: Substitutionen ohne echte Vertretung überspringen ──
        if not _is_meaningful_subst(s):
            continue

        start  = s.get("startTime", 0)
        end    = s.get("endTime", 0)
        lstype = s.get("lstype", "")
        art    = s.get("type", "subst")
        txt    = s.get("txt", "")

        is_break = lstype == "bs"

        # Räume: dedupliziert + Original-Raum für Raumwechsel-Darstellung
        ro_raw   = [r for r in s.get("ro", []) if (r.get("name") or "").strip() not in ("---", "")]
        raum     = " · ".join(_dedupe_names(ro_raw)) or "—"
        raum_org_names = []
        seen_org = set()
        for r in ro_raw:
            org = (r.get("orgname") or "").strip()
            if r.get("orgid") and org and org != (r.get("name") or "").strip() and org not in seen_org:
                seen_org.add(org)
                raum_org_names.append(org)
        raum_org = " · ".join(raum_org_names)

        if is_break:
            std_display = break_lookup.get(start, fmt_time(start))
            klasse  = "—"
            fach    = "Aufsicht"
            # Entfallene/freigestellte Aufsicht bleibt cancel/free (→ landet in
            # „Entfallende Stunden", Lehrer wird als abwesend gewertet). Nur eine
            # tatsächlich stattfindende Aufsichts-Vertretung ist „pause".
            art_out = art if art in ("cancel", "free") else "pause"
        else:
            info        = timegrid.get(start)
            std_display = str(info[0]) if info else "?"
            klasse      = " · ".join(_dedupe_names(s.get("kl", []))) or "—"
            fach        = " · ".join(_dedupe_names(s.get("su", []))) or "—"
            # Raumwechsel ohne Lehrerwechsel: type=subst, aber raum_org gesetzt
            has_te_org = any(t.get("orgid") for t in s.get("te", []))
            art_out    = "roomchange" if (art == "subst" and raum_org and not has_te_org) else art

        has_real_vtr = _has_real_subst_teacher(s)

        # Abwesende Lehrer aus '---'-Markern sammeln (Teamteacher fehlt etc.)
        absent_via_dash = []
        for t in s.get("te", []):
            name = (t.get("name") or "").strip()
            org  = (t.get("orgname") or "").strip()
            if t.get("orgid") and name in SKIP_NAMES and org and org not in absent_via_dash:
                absent_via_dash.append(org)

        real_teacher_names = [
            (t.get("name") or "").strip() for t in s.get("te", [])
            if (t.get("name") or "").strip() not in SKIP_NAMES
        ]

        seen_kuerzel = set()
        covered_orgs = set()   # abwesende Lehrer, die hier real vertreten werden
        for t in s.get("te", []):
            kuerzel = (t.get("name") or "").strip()
            if kuerzel in SKIP_NAMES:
                continue
            has_org = bool(t.get("orgid"))
            # ── Filter B: Co-Lehrer ohne orgid bei echter Vertretung überspringen ──
            if has_real_vtr and not has_org:
                continue
            if kuerzel in seen_kuerzel:
                continue
            seen_kuerzel.add(kuerzel)

            orgname = (t.get("orgname") or "").strip()
            if has_org and orgname:
                org_kuerzel = orgname
            elif absent_via_dash and not has_real_vtr:
                # Pattern te=[---/SaF, BuL]: SaF fehlt, BuL übernimmt → 'SaF→BuL'
                org_kuerzel = " · ".join(absent_via_dash)
            else:
                org_kuerzel = ""

            for o in org_kuerzel.split(" · "):
                if o.strip():
                    covered_orgs.add(o.strip())

            rows.append({
                "kuerzel":     kuerzel,
                "org_kuerzel": org_kuerzel,
                "std":         std_display,
                "sort_key":    start,
                "end_time":    end,
                "day":         day,
                "fach":        fach,
                "klasse":      klasse,
                "art":         art_out,
                "raum":        raum,
                "raum_org":    raum_org,
                "text":        txt,
            })

        # Entfall ohne Vertretung: jeder via '---'/'Z Entfall'-Marker abwesende
        # Lehrer, der NICHT bereits real vertreten wird (covered_orgs), bekommt eine
        # eigene cancel-Zeile. Greift auch in gemischten Einträgen, in denen ein
        # echter Vertreter für einen ANDEREN Lehrer steht — z.B. Pausenaufsichten
        # mit mehreren Aufsicht-Lehrern, von denen einer ersetzt wird und einer
        # entfällt (sonst ginge der Entfall des Abwesenden verloren).
        if absent_via_dash:
            for absent_name in absent_via_dash:
                if absent_name in seen_kuerzel or absent_name in covered_orgs:
                    continue
                rows.append({
                    "kuerzel":        absent_name,
                    "org_kuerzel":    "",
                    "kuerzel_absent": True,
                    "std":            std_display,
                    "sort_key":       start,
                    "end_time":       end,
                    "day":            day,
                    "fach":           fach,
                    "klasse":         klasse,
                    "art":            "cancel",
                    "raum":           raum,
                    "raum_org":       raum_org,
                    "text":           txt,
                })
    return rows

def group_by_teacher(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r["kuerzel"]].append(r)
    for key in groups:
        groups[key].sort(key=lambda r: r["sort_key"])
    return dict(sorted(groups.items()))

def extract_absent_periods(groups):
    """{lehrer_kuerzel: set(std)} aller abwesenden Lehrer eines Tages — gemeinsame
    Quelle für die Anzeige (compute_absent) und für die weekly/data-Abfrage in
    main() (determine_full_absent)."""
    absent_periods = {}
    for rows in groups.values():
        for r in rows:
            if r.get("org_kuerzel"):
                for o in r["org_kuerzel"].split(" · "):
                    o = o.strip()
                    if o:
                        absent_periods.setdefault(o, set()).add(r.get("std", ""))
            elif r.get("kuerzel_absent") or r.get("art") == "cancel":
                # FDKM-Fall oder type=cancel: Lehrer ist selbst abwesend (kein Vertreter)
                absent_periods.setdefault(r["kuerzel"], set()).add(r.get("std", ""))
    return absent_periods


def compute_absent(groups, full_absent_kuerzel=None):
    """`full_absent_kuerzel`: Set der Lehrer-Kürzel, die laut weekly/data den
    ganzen Tag fehlen (keine STANDARD-Stunde). Diese zeigen nur das Kürzel ohne
    Stundenangabe. Ist das Set leer/None (z.B. weekly/data nicht verfügbar),
    fällt jeder mehrstündige Eintrag auf die Range-Anzeige zurück."""
    full_absent_kuerzel = full_absent_kuerzel or set()
    absent_periods  = extract_absent_periods(groups)
    classes_periods = {}
    for rows in groups.values():
        for r in rows:
            if r.get("art") in ("cancel", "free"):
                klasse = r.get("klasse", "")
                if klasse and klasse != "—":
                    for k in klasse.split(" · "):
                        k = k.strip()
                        if k:
                            classes_periods.setdefault(k, set()).add(r.get("std", ""))

    def period_range(kuerzel, stds):
        # Komplett abwesend (weekly/data: keine anwesende Stunde) → nur Kürzel.
        if kuerzel in full_absent_kuerzel:
            return ""
        nums = sorted({int(s) for s in stds if str(s).lstrip("-").isdigit()})
        if not nums:
            return ""
        min_p, max_p = nums[0], nums[-1]
        if min_p == max_p:
            return str(min_p)       # genau eine Stunde → die Zahl
        return f"{min_p}–{max_p}"   # Teil-Abwesenheit → Spanne der Fehl-Stunden

    absent  = [(k, period_range(k, v)) for k, v in sorted(absent_periods.items())]

    def classes_range(stds):
        # Klassen: simple Range (Logik wie ursprünglich, ohne 'ab'-Heuristik)
        nums = sorted({int(s) for s in stds if str(s).lstrip("-").isdigit()})
        if not nums:
            return ""
        if len(nums) == 1:
            return str(nums[0])
        return f"{nums[0]}–{nums[-1]}"

    classes = [(k, classes_range(v)) for k, v in sorted(classes_periods.items())]
    return absent, classes


def determine_full_absent(untis, groups, kuerzel_to_id, date_obj):
    """Set der Lehrer-Kürzel, die an `date_obj` komplett abwesend sind: Lehrer aus
    der Abwesenheitsliste, die laut weekly/data keine einzige anwesende Stunde
    (STANDARD/BREAKSUPERVISION) haben. Pro betroffenem Lehrer ein REST-Call.

    Bei unbekannter ID oder API-Fehler bleibt der Lehrer aus dem Set → er bekommt
    die Stunden-Range (sichere, informativere Rückfallebene)."""
    full = set()
    for kuerzel in extract_absent_periods(groups):
        tid = kuerzel_to_id.get(kuerzel)
        if not tid:
            continue
        try:
            present = untis.get_teacher_present_periods(tid, date_obj)
        except Exception as e:
            print(f"weekly/data Fehler für {kuerzel} ({date_obj}): {e}", flush=True)
            continue
        if not present:
            full.add(kuerzel)
    return full


def render_summary_bar(teachers, classes):
    def fmt(name, periods):
        s = esc(name)
        if periods:
            s += f'<span class="sum-period"> ({esc(periods)})</span>'
        return s
    teachers_str = ", ".join(fmt(n, p) for n, p in teachers) if teachers else "—"
    classes_str  = ", ".join(fmt(n, p) for n, p in classes)  if classes  else "—"
    return (
        f'<div class="summary-bar">'
        f'<span class="sum-item"><span class="sum-label">Abwesende Lehrer:</span> {teachers_str}</span>'
        f'<span class="sum-item"><span class="sum-label">Abwesende Klassen:</span> {classes_str}</span>'
        f'</div>'
    )

# ── HTML Generierung ──────────────────────────────────
# 4-Tupel: (Zeilen-CSS-Klasse, Badge-CSS-Klasse, Lang-Label, Kurz-Label)
ART_MAP = {
    "subst":      ("s-sup",   "b-sup",   "Vertr.",     "V"),
    "cancel":     ("s-ent",   "b-ent",   "Entfall",    "E"),
    "roomchange": ("s-raum",  "b-raum",  "Raum",       "R"),
    "free":       ("s-frei",  "b-frei",  "Freistunde", "F"),
    "pause":      ("s-pause", "b-pause", "Pause",      "P"),
}

WEEKDAYS = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
WEEKDAYS_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTHS   = ["Januar","Februar","März","April","Mai","Juni",
            "Juli","August","September","Oktober","November","Dezember"]

# Bekannte Bemerkungs-Codes mit eigener Farb-Klasse (CSS .tb-*). Andere via
# config.env (TEXT_BADGES) gelistete Codes bekommen das neutrale .text-badge.
_KNOWN_BADGE_CLASSES = {"b": "tb-b", "ub": "tb-ub", "MA": "tb-ma"}
TEXT_BADGES   = dict(_KNOWN_BADGE_CLASSES)
_TEXT_PATTERN = re.compile(r'\b(ub|MA|b)\b')

def configure_text_badges(value):
    """Setzt die als Badge erkannten Bemerkungs-Codes aus config.env (TEXT_BADGES,
    Komma-getrennt). Bekannte Codes behalten ihre Farbe, neue bekommen .text-badge.
    Längere Codes zuerst im Regex, damit z.B. 'ub' nicht als 'b' matcht."""
    global TEXT_BADGES, _TEXT_PATTERN
    codes = [c.strip() for c in (value or "").split(",") if c.strip()]
    if not codes:
        return
    TEXT_BADGES = {c: _KNOWN_BADGE_CLASSES.get(c, "") for c in codes}
    ordered = sorted(codes, key=len, reverse=True)
    _TEXT_PATTERN = re.compile(r'\b(' + "|".join(re.escape(c) for c in ordered) + r')\b')

def render_text(txt):
    if not txt:
        return txt
    txt_escaped = esc(txt)
    def _replace(m):
        # Regex matcht nur konfigurierte Codes → immer als Badge rendern.
        # Bekannte Codes mit Farb-Klasse, neue mit neutralem .text-badge.
        code = m.group(0)
        cls  = TEXT_BADGES.get(code, "")
        klass = f"text-badge {cls}".strip()
        return f'<span class="{klass}">{esc(code)}</span>'
    return _TEXT_PATTERN.sub(_replace, txt_escaped)

def render_teacher_header(kuerzel, teacher_lookup, day="today"):
    info     = teacher_lookup.get(kuerzel, {})
    nachname = info.get("nachname", kuerzel)
    vorname  = info.get("vorname", "")
    name_str = f"{nachname} {vorname}".strip()
    day_cls  = " tomorrow" if day == "tomorrow" else ""
    return (
        f'<tr class="teacher-header{day_cls}">'
        f'<td colspan="{NCOLS}">'
        f'<span class="th-kuerzel">{esc(kuerzel)}</span>'
        f'<span class="th-name">{esc(name_str)}</span>'
        f'</td></tr>'
    )

def render_day_separator(d):
    label = f"Morgen · {WEEKDAYS[d.weekday()]}, {d.day}. {MONTHS[d.month-1]} {d.year}"
    return f'<tr class="day-separator"><td colspan="{NCOLS}">{label}</td></tr>'

def _fach_html(fach: str) -> str:
    """Liefert Fach mit Lang- und Kurz-Variante.
    Kurzform für 'Aufsicht' → 'Aufs.', sonst gleich."""
    short = "Aufs." if fach == "Aufsicht" else fach
    return (
        f'<span class="fach-full">{esc(fach)}</span>'
        f'<span class="fach-short">{esc(short)}</span>'
    )

def _klasse_html(klasse: str) -> str:
    """Begrenzt die Klassen-Anzeige auf max. 2 Einträge, damit eine Zeile
    nicht mehrzeilig umbricht. Rest wird durch '…' angedeutet (vollständige
    Liste im title-Tooltip). r['klasse'] selbst bleibt unverändert, damit
    die 'Abwesende Klassen'-Leiste alle Klassen sieht."""
    if not klasse or klasse == "—":
        return esc(klasse)
    parts = klasse.split(" · ")
    if len(parts) <= 2:
        return esc(klasse)
    shown = " · ".join(parts[:2])
    return f'<span title="{esc(klasse)}">{esc(shown)} …</span>'

# ── Spalten-Definition (Source of Truth) ──────────────
# Reihenfolge hier ändern → COLGROUP, THEAD und jede Datenzeile folgen automatisch.
# Spaltenbreiten bleiben im CSS (col.c-* + .compact-mode-Overrides, klassenbasiert,
# greifen also unabhängig von der Reihenfolge). Jede Zell-Funktion escaped selbst (XSS).
def _kuerzel_cell(r):
    # Leere erste Spalte – trägt nur den farbigen Status-Streifen (CSS :first-child)
    return ""

def _std_cell(r):
    return esc(r["std"])

def _fach_cell(r):
    return _fach_html(r["fach"])

def _klasse_cell(r):
    return _klasse_html(r["klasse"])

def _lehrer_cell(r):
    org = r.get("org_kuerzel", "")
    if org:
        # Bei "Vtr. ohne Lehrer": Bindestrich statt Pfeil (kein echter Vertreter)
        is_vtr_ohne = (r.get("text") or "").strip().lower().startswith("vtr. ohne lehrer")
        sep = " - " if is_vtr_ohne else "&rarr;"
        return (
            f'<s class="lehr-absent">{esc(org)}</s>'
            f'<span class="lehr-arrow">{sep}</span>'
            f'{esc(r["kuerzel"])}'
        )
    if r.get("kuerzel_absent") or r.get("art") == "cancel":
        # Entfall: Lehrer ist abwesend (kein Vertreter), durchgestrichen
        return f'<s class="lehr-absent">{esc(r["kuerzel"])}</s>'
    return esc(r["kuerzel"])

def _art_cell(r):
    _, badge_cls, label_full, label_short = ART_MAP.get(
        r["art"], ("s-sup", "b-sup", r["art"], r["art"][:1].upper())
    )
    return (
        f'<span class="badge {badge_cls}">'
        f'<span class="badge-full">{esc(label_full)}</span>'
        f'<span class="badge-short">{esc(label_short)}</span>'
        f'</span>'
    )

def _raum_cell(r):
    raum_org = r.get("raum_org", "")
    if raum_org:
        return (
            f'<s class="room-absent">{esc(raum_org)}</s>'
            f'<span class="lehr-arrow">&rarr;</span>'
            f'{esc(r["raum"])}'
        )
    return esc(r["raum"])

def _text_cell(r):
    return render_text(r["text"]) or ""

def _row_class(r):
    return ART_MAP.get(r["art"], ("s-sup",))[0]

# (key, header, css_class, cell_fn) — Reihenfolge = Anzeige-Reihenfolge
COLUMNS = [
    ("kuerzel", "",          "c-kuerzel", _kuerzel_cell),
    ("std",     "Std.",      "c-std",     _std_cell),
    ("fach",    "Fach",      "c-fach",    _fach_cell),
    ("klasse",  "Klasse(n)", "c-klasse",  _klasse_cell),
    ("lehrer",  "(Lehrer)",  "c-lehrer",  _lehrer_cell),
    ("art",     "Art",       "c-art",     _art_cell),
    ("raum",    "Raum",      "c-raum",    _raum_cell),
    ("text",    "Text",      "c-text",    _text_cell),
]
NCOLS = len(COLUMNS)

def render_row(r):
    day_cls = " tomorrow" if r.get("day") == "tomorrow" else ""
    cells   = "".join(f'<td class="{css}">{fn(r)}</td>' for _, _, css, fn in COLUMNS)
    return f'<tr class="{_row_class(r)}{day_cls}">{cells}</tr>'

COLGROUP = "<colgroup>" + "".join(f'<col class="{css}">' for _, _, css, _ in COLUMNS) + "</colgroup>"
THEAD = (
    "<thead><tr>"
    + "".join(f'<th class="{css}">{esc(h)}</th>' for _, h, css, _ in COLUMNS)
    + "</tr></thead>"
)

def build_day_content(groups, teacher_lookup, day):
    """Rendert eine flache Tabelle pro Tag. Die Aufteilung in 1–4 Spalten
    übernimmt der Browser zur Laufzeit (Layout-Engine in JavaScript).
    Jede Lehrer-Gruppe ist als `data-block="teacher"` markiert, die
    Cancel-Sektion als `data-block="cancel"`."""

    if not groups:
        msg = (f"Kein {esc(PLAN_TITLE)} für heute" if day == "today"
               else f"Kein {esc(PLAN_TITLE)} für morgen")
        return f'<div class="empty-state"><p>{msg}</p></div>'

    # Trenne Entfall-Zeilen (art=cancel) aus den Lehrer-Gruppen heraus
    cancel_rows    = []
    regular_groups = {}
    for kuerzel, rows in groups.items():
        regs = [r for r in rows if r.get("art") != "cancel"]
        cans = [r for r in rows if r.get("art") == "cancel"]
        if regs:
            regular_groups[kuerzel] = regs
        cancel_rows.extend(cans)

    # Flache HTML-Liste pro Lehrer-Gruppe; ein <tbody> pro Gruppe → data-block-Attribut
    blocks_html = []
    for kuerzel, rows in regular_groups.items():
        body = render_teacher_header(kuerzel, teacher_lookup, day)
        body += "".join(render_row(r) for r in rows)
        blocks_html.append(
            f'<tbody data-block="teacher" data-key="{esc(kuerzel)}">{body}</tbody>'
        )

    # Cancel-Section: jede Entfall-Zeile als eigener data-block="cancel" (ohne
    # Überschrift). Die Layout-Engine verteilt die Zeilen über die Spalten und
    # bricht sie an den echten Spaltengrenzen um — sie setzt die Überschrift
    # („Entfallende Stunden" / „… (Forts.)") pro Spalte selbst und nur dort, wo
    # tatsächlich Entfälle landen (siehe applyLayout / makeCancelHeader).
    if cancel_rows:
        cancel_rows.sort(key=lambda r: (r["sort_key"], r["kuerzel"]))
        for r in cancel_rows:
            blocks_html.append(
                f'<tbody data-block="cancel">{render_row(r)}</tbody>'
            )

    return (
        f'<div class="layout-wrapper cols-1">'
        f'<div class="col"><table>{COLGROUP}{THEAD}{"".join(blocks_html)}</table></div>'
        f'</div>'
    )

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

def parse_overflow_config(config):
    """Liest die OVERFLOW_*-Keys aus config.env und liefert ein dict für die
    Injektion als window.OVERFLOW. Werte werden geklemmt; ungültige → Default."""
    def flag(key, default):
        v = config.get(key, "")
        if v == "":
            return default
        return v.strip().lower() == "true"

    try:
        smin = float(config.get("OVERFLOW_SCALE_MIN", "0.65"))
    except ValueError:
        smin = 0.65
    smin = min(1.0, max(0.3, smin))

    try:
        psec = int(config.get("OVERFLOW_PAGE_SECONDS", "12"))
    except ValueError:
        psec = 12
    psec = max(3, psec)

    return {
        "scale":        flag("OVERFLOW_SCALE", True),
        "scale_min":    round(smin, 4),
        "reduce":       flag("OVERFLOW_REDUCE", True),
        "paginate":     flag("OVERFLOW_PAGINATE", True),
        "page_seconds": psec,
    }


def generate_html(groups_today, groups_tomorrow, today_date, tomorrow_date,
                  teacher_lookup, period_nr, period_start, period_end,
                  show_logo=False, import_time=None, train_enabled=False,
                  today_classes_override=None, tomorrow_classes_override=None,
                  compact_col_width=320,
                  school_name="MS Roda-Roda-Gasse", school_type="Mittelschule",
                  school_location="1210 Wien", show_clock=True,
                  tz_name="Europe/Vienna", theme="dark",
                  today_full_absent=None, tomorrow_full_absent=None,
                  overflow_cfg=None):

    overflow_cfg = overflow_cfg or parse_overflow_config({})
    logo_html = f'<div class="logo"><img src="{esc(LOGO_FILE)}" alt="Logo"></div>\n            ' if show_logo else ''
    train_widget_html = render_train_widget(train_enabled)

    # Schul-Bezeichnungen (config.env) — leere Teile fallen aus der " · "-Kette.
    school_sub_str  = " · ".join(p for p in (school_type, school_location) if p)
    school_foot_str = " · ".join(p for p in (school_name, school_location) if p)
    tz_js    = json.dumps(tz_name)  # sicheres JS-String-Literal für die Uhr-Logik
    theme_js = json.dumps(theme)    # Config-Theme fürs Head-Script

    if import_time:
        import_block = f'<span class="foot-c">Stand Untis: {import_time.strftime("%d.%m.%Y %H:%M")} Uhr</span>'
    else:
        import_block = ''

    now      = now_local()
    date_str = f"{WEEKDAYS[now.weekday()]}, {now.day}. {MONTHS[now.month-1]} {now.year}"
    time_str = now.strftime("%H:%M")
    upd_str  = now.strftime("%H:%M Uhr")

    if period_nr is not None:
        period_block = (
            f'<div class="current-period">'
            f'<span class="period-label">Laufende Stunde</span>'
            f'<span class="period-value"><span class="period-dot"></span>{period_nr}. Stunde</span>'
            f'<span class="period-time">{period_start} – {period_end}</span>'
            f'</div>'
        )
    else:
        period_block = (
            '<div class="current-period">'
            '<span class="period-label">Laufende Stunde</span>'
            '<span class="period-value">—</span>'
            '<span class="period-time">&nbsp;</span>'
            '</div>'
        )

    # Uhr + Datum (optional via SHOW_CLOCK); Divider nur wenn Uhr sichtbar.
    if show_clock:
        clock_html = (
            f'<div class="header-divider"></div>'
            f'<div class="clock">'
            f'<p class="clock-date" id="clock-date">{date_str}</p>'
            f'<p class="clock-time" id="clock-time">{time_str}</p>'
            f'</div>'
        )
    else:
        clock_html = ''

    show_today    = bool(groups_today)
    show_tomorrow = bool(groups_tomorrow) and bool(tomorrow_date)
    both_visible  = show_today and show_tomorrow

    today_section = ""
    if show_today:
        today_absent, today_classes_derived = compute_absent(groups_today, today_full_absent)
        today_classes = today_classes_override if today_classes_override is not None else today_classes_derived
        date_str_today = (
            f"{WEEKDAYS[today_date.weekday()]}, "
            f"{today_date.day}. {MONTHS[today_date.month-1]} {today_date.year}"
        )
        today_title = (
            f'<div class="day-title-bar today">'
            f'<span class="day-title-text">Heute · {date_str_today}</span>'
            f'</div>' if both_visible else ''
        )
        section_cls = "plan-section today-section" if both_visible else "plan-section"
        today_section = (
            f'<div class="{section_cls}">'
            f'{today_title}'
            f'{render_summary_bar(today_absent, today_classes)}'
            f'{build_day_content(groups_today, teacher_lookup, "today")}'
            f'</div>'
        )

    tomorrow_section = ""
    tomorrow_only_label_full = ""
    tomorrow_only_label_short = ""
    if show_tomorrow:
        tom_absent, tom_classes_derived = compute_absent(groups_tomorrow, tomorrow_full_absent)
        tom_classes = tomorrow_classes_override if tomorrow_classes_override is not None else tom_classes_derived
        days_ahead = (tomorrow_date - today_date).days
        date_str_tom = (
            f"{WEEKDAYS[tomorrow_date.weekday()]}, "
            f"{tomorrow_date.day}. {MONTHS[tomorrow_date.month-1]} {tomorrow_date.year}"
        )
        date_str_tom_short = (
            f"{WEEKDAYS_SHORT[tomorrow_date.weekday()]}, "
            f"{tomorrow_date.day}. {MONTHS[tomorrow_date.month-1]} {tomorrow_date.year}"
        )
        if days_ahead == 1:
            day_label = f"Morgen · {date_str_tom}"
            day_label_short = f"Morgen · {date_str_tom_short}"
        else:
            day_label = f"Nächster Schultag · {date_str_tom}"
            day_label_short = f"Nä. Schultag · {date_str_tom_short}"
        # Wenn nur Morgen sichtbar: Headline ins Plan-Tag oben verlegen
        if not show_today:
            tomorrow_only_label_full = day_label
            tomorrow_only_label_short = day_label_short
        title_bar_html = (
            f'<div class="day-title-bar"><span class="day-title-text">{esc(day_label)}</span></div>'
            if show_today else ''
        )
        tomorrow_section = (
            f'<div class="plan-section tomorrow-section">'
            f'{title_bar_html}'
            f'{render_summary_bar(tom_absent, tom_classes)}'
            f'{build_day_content(groups_tomorrow, teacher_lookup, "tomorrow")}'
            f'</div>'
        )

    if not show_today and not show_tomorrow:
        main_content = (
            '<div class="plan-section">'
            f'<div class="empty-state"><p>Kein {esc(PLAN_TITLE)} verfügbar</p></div>'
            '</div>'
        )
    else:
        main_content = today_section + tomorrow_section

    # Plan-Tag im Header: 'Heute' normal, sonst Morgen-Label in blau
    if tomorrow_only_label_full:
        plan_tag_html = (
            f'<span class="plan-tag tomorrow-only">'
            f'<span class="tag-full">{esc(tomorrow_only_label_full)}</span>'
            f'<span class="tag-short">{esc(tomorrow_only_label_short)}</span>'
            f'</span>'
        )
    else:
        plan_tag_html = '<span class="plan-tag">Heute</span>'

    return f"""<!DOCTYPE html>
<html lang="de" data-theme="{esc(theme)}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>{esc(PLAN_TITLE)} – {esc(school_name)}</title>
    <link rel="stylesheet" href="css/style.css">
    <!-- PWA -->
    <link rel="manifest" href="manifest.json">
    <meta name="theme-color" content="#c8102e">
    <meta name="application-name" content="{esc(PLAN_TITLE)}">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="{esc(PLAN_TITLE)}">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="apple-touch-icon" href="{esc(LOGO_FILE)}">
    <script>window.COMPACT_COL_WIDTH = {compact_col_width};</script>
    <script>window.OVERFLOW = {json.dumps(overflow_cfg)};</script>
    <script>
    // Theme-Auflösung: Breit/Schmal folgen der Config, Mobil-Ansicht darf via
    // localStorage überschreiben. Läuft früh im <head> → minimiert Flackern.
    (function () {{
        var CONFIG_THEME = {theme_js};
        var mq = window.matchMedia('(max-width: 600px)');
        function resolveTheme() {{
            var t = CONFIG_THEME;
            if (mq.matches) {{
                try {{
                    var s = localStorage.getItem('theme-override');
                    if (s === 'dark' || s === 'light') t = s;
                }} catch (e) {{}}
            }}
            document.documentElement.setAttribute('data-theme', t);
        }}
        resolveTheme();
        if (mq.addEventListener) mq.addEventListener('change', resolveTheme);
        else if (mq.addListener) mq.addListener(resolveTheme);
    }})();
    </script>
</head>
<body>
<div class="layout">
    <div class="accent-top"></div>
    <header class="header">
        <div class="header-left">
            <button id="theme-toggle" class="theme-toggle" type="button" aria-label="Hell-/Dunkelmodus umschalten"></button>
            {logo_html}<div>
                <p class="school-name">{esc(school_name)}</p>
                <p class="school-sub">{esc(school_sub_str)}</p>
            </div>
        </div>
        {train_widget_html}
        <div class="header-right">
            {period_block}
            {clock_html}
        </div>
    </header>
    <div class="plan-header">
        <span class="plan-label">{esc(PLAN_TITLE)}</span>
        {plan_tag_html}
        <div class="plan-sep"></div>
        <div class="legend">
            <span class="leg sup">Vertretung</span>
            <span class="leg ent">Entfall</span>
            <span class="leg raum">Raumwechsel</span>
            <span class="leg frei">Freistunde</span>
            <span class="leg pause">Pause</span>
        </div>
    </div>
    <main class="table-wrap">
        {main_content}
    </main>
    <footer>
        <span class="foot-l">Letzte Aktualisierung: {upd_str}</span>
        {import_block}
        <span class="foot-r">{esc(school_foot_str)}</span>
    </footer>
</div>
<script>
// ── PWA: Service-Worker registrieren ──
if ('serviceWorker' in navigator) {{
    window.addEventListener('load', function () {{
        navigator.serviceWorker.register('sw.js').catch(function () {{ /* silent */ }});
    }});
}}

(function tick() {{
    var ct = document.getElementById('clock-time');
    var cd = document.getElementById('clock-date');
    if (!ct && !cd) return;  // Uhr per Config deaktiviert
    var now  = new Date();
    var tz   = {tz_js};
    var tOpt = {{hour: '2-digit', minute: '2-digit', hour12: false}};
    var dOpt = {{weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'}};
    if (tz) {{ tOpt.timeZone = tz; dOpt.timeZone = tz; }}
    if (ct) ct.textContent = new Intl.DateTimeFormat('de-DE', tOpt).format(now);
    if (cd) cd.textContent = new Intl.DateTimeFormat('de-DE', dOpt).format(now);
    setTimeout(tick, 1000);
}})();

// Auto-Refresh: 60s soft-reload, alle 5 min Hard-Reload mit Cache-Bust
(function () {{
    var tick = 0;
    setInterval(function () {{
        tick++;
        if (tick % 5 === 0) {{
            // Cache-Bust: erzwingt Neuladen aller Ressourcen
            window.location.href = window.location.pathname + '?cb=' + Date.now();
        }} else {{
            window.location.reload();
        }}
    }}, 60 * 1000);
}})();

// ── Multi-Column Layout-Engine v2 ──
(function () {{
    var MIN_COL_WIDTH = 280;  // für Spaltenzahl-Berechnung
    var MAX_COLS = 4;

    function getBlocks(wrapper) {{
        return Array.prototype.slice.call(
            wrapper.querySelectorAll('tbody[data-block]')
        );
    }}

    function chooseColCount(wrapper, blocks, availablePerCol) {{
        if (availablePerCol <= 0) return 1;
        var total = 0;
        for (var i = 0; i < blocks.length; i++) {{
            total += blocks[i].getBoundingClientRect().height;
        }}
        var byHeight = Math.max(1, Math.ceil(total / availablePerCol));
        var byWidth  = Math.max(1, Math.floor(wrapper.clientWidth / MIN_COL_WIDTH));
        return Math.min(MAX_COLS, byHeight, byWidth);
    }}

    var CANCEL_HEADER_H = 46;  // geschätzte Höhe der eingefügten Überschrift

    function distributeGreedy(blocks, cols, availablePerCol) {{
        var buckets = [];
        for (var i = 0; i < cols; i++) buckets.push([]);

        // Lehrer-Blöcke zuerst, danach die einzelnen Entfall-Zeilen. So bleiben die
        // Entfälle am Ende des Leseflusses, füllen aber jede Spalte bis zum Limit
        // und brechen erst an der echten Spaltengrenze um (statt in starre Chunks).
        // Pro Spalte, in der Entfälle beginnen, wird Platz für die später
        // eingefügte Überschrift reserviert.
        var regular = [];
        var cancels = [];
        for (var j = 0; j < blocks.length; j++) {{
            if (blocks[j].getAttribute('data-block') === 'cancel') {{
                cancels.push(blocks[j]);
            }} else {{
                regular.push(blocks[j]);
            }}
        }}
        var ordered = regular.concat(cancels);

        var currentCol = 0;
        var currentHeight = 0;
        var colHasCancel = false;
        for (var k = 0; k < ordered.length; k++) {{
            var b = ordered[k];
            var isCancel = b.getAttribute('data-block') === 'cancel';
            var h = b.getBoundingClientRect().height;
            var extra = (isCancel && !colHasCancel) ? CANCEL_HEADER_H : 0;
            if (currentHeight + h + extra > availablePerCol
                    && currentCol < cols - 1
                    && buckets[currentCol].length > 0) {{
                currentCol++;
                currentHeight = 0;
                colHasCancel = false;
                extra = isCancel ? CANCEL_HEADER_H : 0;
            }}
            buckets[currentCol].push(b);
            currentHeight += h + extra;
            if (isCancel) colHasCancel = true;
        }}

        return buckets;
    }}

    function makeCancelHeader(ncols, isCont, spaced, isTomorrow) {{
        var tb = document.createElement('tbody');
        tb.className = 'cancel-header-block';
        var tr = document.createElement('tr');
        tr.className = 'cancel-header'
            + (isTomorrow ? ' tomorrow' : '')
            + (isCont ? ' cont' : '')
            + (spaced ? ' spaced' : '');
        var td = document.createElement('td');
        td.colSpan = ncols;
        var span = document.createElement('span');
        span.className = 'ch-label';
        span.textContent = isCont ? 'Entfallende Stunden (Forts.)' : 'Entfallende Stunden';
        td.appendChild(span);
        tr.appendChild(td);
        tb.appendChild(tr);
        return tb;
    }}

    function applyLayout(wrapper) {{
        var blocks = getBlocks(wrapper);
        if (blocks.length === 0) return;

        var tableWrap = wrapper.closest('.table-wrap');
        if (!tableWrap) return;
        var sectionCount = tableWrap.querySelectorAll('.plan-section').length || 1;
        var availablePerCol = Math.floor(tableWrap.clientHeight / sectionCount) - 60;
        if (availablePerCol < 100) availablePerCol = 100;

        // Reset für saubere Messung mit 1-Spalten-Layout
        wrapper.classList.remove('cols-1','cols-2','cols-3','cols-4');
        wrapper.classList.remove('compact-mode');
        wrapper.classList.add('cols-1');

        var cols = chooseColCount(wrapper, blocks, availablePerCol);

        wrapper.classList.remove('cols-1');
        wrapper.classList.add('cols-' + cols);

        var origTable    = wrapper.querySelector('table');
        if (!origTable) return;
        var origColgroup = origTable.querySelector('colgroup');
        var origThead    = origTable.querySelector('thead');
        var ncols = origColgroup ? origColgroup.querySelectorAll('col').length : 8;
        var isTomorrow = !!wrapper.closest('.tomorrow-section');

        var buckets = distributeGreedy(blocks, cols, availablePerCol);

        // Container leeren und N neue Spalten/Tables anlegen. Die "Entfallende
        // Stunden"-Überschrift wird pro Spalte VOR der ersten Entfall-Zeile
        // eingefügt: in der ersten betroffenen Spalte voll, danach als "(Forts.)".
        // Zusätzlicher Abstand (spaced) nur, wenn die Überschrift unter einem
        // anderen Block steht — nicht, wenn sie ganz oben in der Spalte sitzt.
        wrapper.innerHTML = '';
        var cancelHeaderSeen = false;
        for (var c = 0; c < cols; c++) {{
            var colDiv = document.createElement('div');
            colDiv.className = 'col';
            var table = document.createElement('table');
            if (origColgroup) table.appendChild(origColgroup.cloneNode(true));
            if (origThead)    table.appendChild(origThead.cloneNode(true));
            var colCancelSeen = false;
            for (var m = 0; m < buckets[c].length; m++) {{
                var blk = buckets[c][m];
                if (blk.getAttribute('data-block') === 'cancel' && !colCancelSeen) {{
                    colCancelSeen = true;
                    table.appendChild(
                        makeCancelHeader(ncols, cancelHeaderSeen, m > 0, isTomorrow)
                    );
                    cancelHeaderSeen = true;
                }}
                table.appendChild(blk);
            }}
            colDiv.appendChild(table);
            wrapper.appendChild(colDiv);
        }}

        // Compact-Mode prüfen nach Spalten-Build
        var firstCol = wrapper.querySelector('.col');
        if (firstCol && firstCol.clientWidth < (window.COMPACT_COL_WIDTH || 320)) {{
            wrapper.classList.add('compact-mode');
        }}
    }}

    function layoutAll() {{
        var wrappers = document.querySelectorAll('.layout-wrapper');
        for (var i = 0; i < wrappers.length; i++) {{
            applyLayout(wrappers[i]);
        }}
    }}

    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', layoutAll);
    }} else {{
        layoutAll();
    }}

    // Nochmal nach window.load (Fonts/CSS final geladen)
    window.addEventListener('load', function () {{
        setTimeout(layoutAll, 50);
    }});

    var resizeTimer = null;
    window.addEventListener('resize', function () {{
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(layoutAll, 250);
    }});
}})();

// ── Theme-Umschalter (nur in der Mobil-Ansicht sichtbar) ──
(function () {{
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', function () {{
        var cur  = document.documentElement.getAttribute('data-theme');
        var next = cur === 'light' ? 'dark' : 'light';
        try {{ localStorage.setItem('theme-override', next); }} catch (e) {{}}
        document.documentElement.setAttribute('data-theme', next);
    }});
}})();

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

    // Im Mobile-Mode nur den nächsten Zug je Richtung zeigen (sonst alle).
    var mobileMQ = window.matchMedia('(max-width: 600px)');
    var lastData = null;

    function render(data) {{
        if (!data) return;
        document.getElementById('tw-station').textContent = data.station || '';
        var tCell = document.getElementById('tw-towards-row');
        var aCell = document.getElementById('tw-away-row');
        tCell.innerHTML = '';
        aCell.innerHTML = '';
        var limit = mobileMQ.matches ? 1 : Infinity;
        (data.towards || []).slice(0, limit).forEach(function (dep) {{ tCell.appendChild(fmtRow(dep, 'tw-towards')); }});
        (data.away    || []).slice(0, limit).forEach(function (dep) {{ aCell.appendChild(fmtRow(dep, 'tw-away')); }});

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

    function update(data) {{
        lastData = data;
        render(data);
    }}

    // Bei Wechsel mobil ↔ desktop neu rendern (Anzahl Züge ändert sich).
    var onMQ = function () {{ if (lastData) render(lastData); }};
    if (mobileMQ.addEventListener) mobileMQ.addEventListener('change', onMQ);
    else if (mobileMQ.addListener) mobileMQ.addListener(onMQ);

    function load() {{
        fetch('data/trains.json?cb=' + Date.now(), {{cache: 'no-store'}})
            .then(function (r) {{ return r.ok ? r.json() : null; }})
            .then(function (data) {{ if (data) update(data); }})
            .catch(function () {{ /* JSON nicht erreichbar → DOM unverändert */ }});
    }}

    load();
    setInterval(load, 60 * 1000);
}})();
</script>
</body>
</html>"""

# ── Cloudflare Cache-Purge ────────────────────────────
def purge_cloudflare_cache(zone_id, token, host=None):
    """Löscht den Cloudflare-Cache nach dem Generieren der index.html.
       - Wenn `host` gesetzt: nur den angegebenen Hostname purgen (sicher).
       - Sonst: gesamten Zone-Cache leeren (purge_everything).
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache"
    if host:
        payload = json.dumps({"hosts": [host]}).encode()
    else:
        payload = json.dumps({"purge_everything": True}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

# ── PWA-Manifest (aus config.env generiert) ───────────
def write_manifest(school_name, school_location, theme):
    """Erzeugt manifest.json passend zu Schulname, Logo, Plan-Titel und Theme.
    Wird (wie index.html) bei jedem Run neu geschrieben → ist gitignored."""
    ext  = LOGO_FILE.rsplit(".", 1)[-1].lower() if "." in LOGO_FILE else "png"
    mime = {"png": "image/png", "svg": "image/svg+xml", "jpg": "image/jpeg",
            "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
    desc_loc = f", {school_location}" if school_location else ""
    icon = lambda size, purpose: {"src": LOGO_FILE, "sizes": size, "type": mime, "purpose": purpose}
    manifest = {
        "name":              f"{PLAN_TITLE} {school_name}".strip(),
        "short_name":        PLAN_TITLE,
        "description":       f"{PLAN_TITLE} der {school_name}{desc_loc}",
        "start_url":         "./",
        "scope":             "./",
        "display":           "fullscreen",
        "display_override":  ["fullscreen", "standalone"],
        "orientation":       "landscape",
        "background_color":  "#eef0f4" if theme == "light" else "#0c0c11",
        "theme_color":       "#c8102e",
        "lang":              "de",
        "dir":               "ltr",
        "icons": [icon("192x192", "any"), icon("512x512", "any"), icon("512x512", "maskable")],
    }
    (BASE_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

# ── Daten-Dump (lesbare Übersicht + Roh-JSON) ─────────
def write_data_dump(today_substs, tomorrow_substs, today_rows, tomorrow_rows,
                    holidays, import_time, today_date, tomorrow_date):
    """Schreibt zwei Dateien ins data/-Verzeichnis:
       - last_raw.json:     unveränderte Roh-Daten von WebUntis
       - last_overview.html: formatierte Übersicht für Browser
    """
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)

    fetched_at = now_local().strftime("%Y-%m-%d %H:%M:%S %Z")
    untis_stand = import_time.strftime("%Y-%m-%d %H:%M:%S %Z") if import_time else None

    raw = {
        "metadata": {
            "fetched_at": fetched_at,
            "import_time_untis": untis_stand,
            "today_date": today_date.isoformat(),
            "tomorrow_date": tomorrow_date.isoformat() if tomorrow_date else None,
        },
        "today_substitutions_raw":    today_substs,
        "tomorrow_substitutions_raw": tomorrow_substs,
        "holidays":                   holidays,
    }
    (data_dir / "last_raw.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    def row_html(r):
        lehrer = esc(r["kuerzel"])
        if r.get("org_kuerzel"):
            lehrer = f'<s>{esc(r["org_kuerzel"])}</s> &rarr; {esc(r["kuerzel"])}'
        raum = esc(r["raum"])
        if r.get("raum_org"):
            raum = f'<s>{esc(r["raum_org"])}</s> &rarr; {esc(r["raum"])}'
        return (
            f'<tr>'
            f'<td>{esc(r["std"])}</td>'
            f'<td>{lehrer}</td>'
            f'<td>{esc(r["klasse"])}</td>'
            f'<td>{esc(r["fach"])}</td>'
            f'<td>{raum}</td>'
            f'<td>{esc(r["art"])}</td>'
            f'<td>{esc(r["text"])}</td>'
            f'</tr>'
        )

    def day_section(title, rows):
        if not rows:
            return f"<h2>{esc(title)}</h2><p><em>Keine Einträge</em></p>"
        body = "".join(
            row_html(r)
            for r in sorted(rows, key=lambda x: (x["sort_key"], x["kuerzel"]))
        )
        return (
            f'<h2>{esc(title)} <small>({len(rows)} Zeilen)</small></h2>'
            f'<table><thead><tr>'
            f'<th>Std</th><th>Lehrer</th><th>Klasse</th>'
            f'<th>Fach</th><th>Raum</th><th>Art</th><th>Text</th>'
            f'</tr></thead><tbody>{body}</tbody></table>'
        )

    html_out = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><title>Supplierplan — API-Dump</title>
<style>
body {{ font-family: -apple-system, Segoe UI, sans-serif; margin: 24px; background: #f5f5f7; color: #222; }}
h1   {{ font-size: 22px; margin-bottom: 8px; }}
h2   {{ font-size: 18px; margin-top: 28px; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 8px; font-size: 13px; background: #fff; }}
th, td {{ padding: 6px 10px; border-bottom: 1px solid #e2e2e6; text-align: left; vertical-align: top; }}
th    {{ background: #e8e8ed; font-weight: 600; }}
tr:hover td {{ background: #fafafd; }}
s     {{ color: #888; }}
.meta {{ background: #fff; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; box-shadow: 0 1px 2px rgba(0,0,0,.05); }}
.meta p {{ margin: 4px 0; font-size: 14px; }}
.links a {{ color: #2a66d6; text-decoration: none; margin-right: 14px; font-size: 13px; }}
.links a:hover {{ text-decoration: underline; }}
</style></head>
<body>
<h1>Supplierplan — API-Daten-Dump</h1>
<div class="meta">
  <p><strong>Abruf:</strong> {esc(fetched_at)}</p>
  <p><strong>Untis Stand:</strong> {esc(untis_stand or "—")}</p>
  <p><strong>Heute:</strong> {esc(today_date.isoformat())}</p>
  <p><strong>Nächster Schultag:</strong> {esc(tomorrow_date.isoformat() if tomorrow_date else "—")}</p>
  <p class="links"><a href="last_raw.json">→ Roh-JSON ansehen</a><a href="../index.html">→ zurück zur Anzeige</a></p>
</div>
{day_section("Heute (verarbeitete Zeilen)", today_rows)}
{day_section("Nächster Schultag (verarbeitete Zeilen)", tomorrow_rows)}
</body></html>"""

    (data_dir / "last_overview.html").write_text(html_out, encoding="utf-8")

# ── Main ──────────────────────────────────────────────
def main():
    global PLAN_TITLE, LOGO_FILE
    config = load_config()
    tz_name = config.get("TIMEZONE", "").strip() or "Europe/Vienna"
    set_timezone(tz_name)

    # Schul-spezifische Stellschrauben aus config.env (siehe config.env.example)
    configure_skip_teachers(config.get("SKIP_TEACHERS", "Z Entfall"))
    configure_text_badges(config.get("TEXT_BADGES", "b,ub,MA"))
    PLAN_TITLE = config.get("PLAN_TITLE", "Supplierplan").strip() or "Supplierplan"
    LOGO_FILE  = config.get("LOGO_FILE", "logo.png").strip() or "logo.png"
    try:
        department_id = int(config.get("UNTIS_DEPARTMENT_ID", "0"))
    except ValueError:
        department_id = 0

    untis  = WebUntis(
        url       = config["UNTIS_URL"],
        school_id = config.get("UNTIS_SCHOOL_ID", "s921092"),
        user      = config["UNTIS_USER"],
        password  = config["UNTIS_PASSWORD"],
    )

    try:
        print("Einloggen ...", flush=True)
        untis.login()

        def _optional(label, fn, fallback):
            """Nicht-essentieller API-Call: fehlt das Recht (z.B. API -8509) oder
            schlägt er fehl, wird gewarnt und der Fallback genutzt, statt das ganze
            Board crashen zu lassen. Vertretungen + Zeitraster bleiben Pflicht."""
            try:
                return fn()
            except Exception as e:
                print(f"  ⚠️  {label}: {e} – läuft eingeschränkt weiter", flush=True)
                return fallback

        grid_raw       = untis.get_timegrid()
        teachers       = _optional("getTeachers (Stammdaten Lehrkraft)", untis.get_teachers, [])
        klassen_raw    = _optional("getKlassen (Stammdaten Klasse)", untis.get_klassen, [])
        holidays_raw   = _optional("getHolidays (Stammdaten Ferien)", untis.get_holidays, [])
        import_time    = _optional("getLatestImportTime", untis.get_latest_import_time, None)
        timegrid       = build_timegrid(grid_raw)
        break_lookup   = build_break_lookup(grid_raw)
        teacher_lookup = build_teacher_lookup(teachers)
        class_id_lk    = build_class_id_lookup(klassen_raw)
        holiday_set    = parse_holidays(holidays_raw)
        # Kürzel → Lehrer-ID für die weekly/data-Abfrage (komplett vs. teil-abwesend)
        kuerzel_to_id  = {t.get("name", "").strip(): t["id"]
                          for t in (teachers or []) if t.get("id") and t.get("name")}

        now_t   = now_hhmm()
        today   = today_local()
        today_int = int(today.strftime("%Y%m%d"))

        # Heute: vergangene Stunden herausfiltern
        print(f"Hole Heute ({today_int}) ...", flush=True)
        today_substs = untis.get_substitutions(today_int, department_id=department_id)
        today_rows   = process_substitutions(today_substs, timegrid, break_lookup, day="today")
        today_rows   = [r for r in today_rows if r["end_time"] >= now_t]
        groups_today = group_by_teacher(today_rows)

        # Echte Klassen-Abwesenheits-Liste aus weekly/data (statt aus cancel-Einträgen abgeleitet)
        try:
            today_abs_classes_raw = untis.get_weekly_class_absences(today)
        except Exception as e:
            print(f"Klassen-Abwesenheits-API Fehler (heute): {e}", flush=True)
            today_abs_classes_raw = {}
        today_absent_classes_override = class_absences_to_list(today_abs_classes_raw, class_id_lk, timegrid)

        # Komplett abwesende Lehrer (weekly/data) → zeigen nur das Kürzel ohne Std-Range
        today_full_absent = determine_full_absent(untis, groups_today, kuerzel_to_id, today)

        # Morgen: ab konfigurierter Uhrzeit ODER wenn heute schon leer ist
        threshold_str = config.get("SHOW_TOMORROW_AFTER", "14:00")
        th, tm     = map(int, threshold_str.split(":"))
        threshold  = th * 100 + tm
        show_tomorrow = now_t >= threshold or not groups_today

        groups_tomorrow = {}
        tomorrow_date   = None
        tom_substs      = []
        tom_rows        = []
        tomorrow_absent_classes_override = []
        tomorrow_full_absent = set()

        if show_tomorrow:
            tomorrow      = next_school_day(today, holiday_set)
            tomorrow_int  = int(tomorrow.strftime("%Y%m%d"))
            tomorrow_date = tomorrow
            print(f"Hole nächsten Schultag ({tomorrow_int}) ...", flush=True)
            tom_substs    = untis.get_substitutions(tomorrow_int, department_id=department_id)
            tom_rows      = process_substitutions(tom_substs, timegrid, break_lookup, day="tomorrow")
            groups_tomorrow = group_by_teacher(tom_rows)

            try:
                tom_abs_classes_raw = untis.get_weekly_class_absences(tomorrow)
            except Exception as e:
                print(f"Klassen-Abwesenheits-API Fehler (morgen): {e}", flush=True)
                tom_abs_classes_raw = {}
            tomorrow_absent_classes_override = class_absences_to_list(tom_abs_classes_raw, class_id_lk, timegrid)

            tomorrow_full_absent = determine_full_absent(untis, groups_tomorrow, kuerzel_to_id, tomorrow)

        period_nr, p_start, p_end = find_current_period(timegrid)

        today_count   = sum(len(v) for v in groups_today.values())
        tomorrow_count = sum(len(v) for v in groups_tomorrow.values())
        print(f"Heute: {today_count} Zeilen | Morgen: {tomorrow_count} Zeilen", flush=True)

        show_logo = config.get("SHOW_LOGO", "false").lower() == "true"
        train_enabled = (
            config.get("TRAIN_STATION", "").strip()
            and config.get("TRAIN_DISABLED", "").strip().lower() != "true"
        )
        try:
            compact_col_width = max(0, int(config.get("COMPACT_COL_WIDTH_PX", "320")))
        except ValueError:
            compact_col_width = 320

        school_name     = config.get("SCHOOL_NAME", "MS Roda-Roda-Gasse").strip() or "MS Roda-Roda-Gasse"
        school_type     = config.get("SCHOOL_TYPE", "Mittelschule").strip()
        school_location = config.get("SCHOOL_LOCATION", "1210 Wien").strip()
        show_clock      = config.get("SHOW_CLOCK", "true").strip().lower() != "false"
        theme           = config.get("THEME", "dark").strip().lower()
        if theme not in ("dark", "light"):
            theme = "dark"

        overflow_cfg = parse_overflow_config(config)
        html = generate_html(
            groups_today, groups_tomorrow, today, tomorrow_date,
            teacher_lookup, period_nr, p_start, p_end,
            show_logo=show_logo,
            import_time=import_time,
            train_enabled=bool(train_enabled),
            today_classes_override=today_absent_classes_override,
            tomorrow_classes_override=tomorrow_absent_classes_override,
            compact_col_width=compact_col_width,
            school_name=school_name,
            school_type=school_type,
            school_location=school_location,
            show_clock=show_clock,
            tz_name=tz_name,
            theme=theme,
            today_full_absent=today_full_absent,
            tomorrow_full_absent=tomorrow_full_absent,
            overflow_cfg=overflow_cfg,
        )
        out = BASE_DIR / "index.html"
        out.write_text(html, encoding="utf-8")
        print(f"Fertig -> {out}", flush=True)

        # PWA-Manifest passend zu Schulname/Logo/Theme schreiben
        write_manifest(school_name, school_location, theme)

        # Lesbare Datenübersicht in data/ ablegen
        write_data_dump(
            today_substs, tom_substs,
            today_rows, tom_rows,
            holidays_raw, import_time,
            today, tomorrow_date,
        )
        print(f"Daten-Dump -> {BASE_DIR / 'data'}", flush=True)

        # Cloudflare Cache-Purge (optional, nur wenn konfiguriert)
        cf_zone  = config.get("CLOUDFLARE_ZONE_ID", "").strip()
        cf_token = config.get("CLOUDFLARE_API_TOKEN", "").strip()
        cf_host  = config.get("CLOUDFLARE_HOST", "").strip() or None
        if cf_zone and cf_token:
            try:
                result = purge_cloudflare_cache(cf_zone, cf_token, host=cf_host)
                if result.get("success"):
                    target = cf_host or "(alle Hosts)"
                    print(f"Cloudflare Cache geleert: {target}", flush=True)
                else:
                    print(f"Cloudflare Purge fehlgeschlagen: {result.get('errors')}", flush=True)
            except Exception as e:
                print(f"Cloudflare Purge Fehler: {e}", flush=True)

    finally:
        untis.logout()

if __name__ == "__main__":
    main()
