#!/usr/bin/env python3
"""
fetch_untis.py – WebUntis Supplierplan Fetcher
Holt den heutigen (und ggf. morgigen) Supplierplan und generiert index.html
"""

import html as _html
import json
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
    """Aktuelle Wien-Zeit (oder System-Zeit falls ZoneInfo nicht verfügbar)."""
    return datetime.now(TZ) if TZ else datetime.now()

def today_local():
    return now_local().date()


def esc(s):
    """HTML-escape a value from external data sources."""
    return _html.escape(str(s)) if s is not None else ""

BASE_DIR    = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config.env"

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

# ── WebUntis JSON-RPC Client ──────────────────────────
class WebUntis:
    def __init__(self, url, school_id, user, password):
        self.endpoint = url.rstrip("/") + "/WebUntis/jsonrpc.do"
        self.school_id = school_id
        self.user = user
        self.password = password
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

    def get_substitutions(self, date_int):
        return self._rpc("getSubstitutions", {
            "startDate": date_int, "endDate": date_int, "departmentId": 0
        })

    def get_timegrid(self):
        return self._rpc("getTimegridUnits")

    def get_teachers(self):
        return self._rpc("getTeachers")

    def get_holidays(self):
        return self._rpc("getHolidays")

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
SKIP_NAMES = {"---", "Z Entfall", ""}

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
            art_out = "pause"
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

        # Sonderfall FDKM-artig: te[] enthält NUR '---'-Marker, kein echter Lehrer
        # → eine Zeile pro abwesendem Lehrer erzeugen (Entfall ohne Vertretung)
        if not real_teacher_names and absent_via_dash:
            for absent_name in absent_via_dash:
                if absent_name in seen_kuerzel:
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

def compute_absent(groups):
    absent_periods  = {}
    classes_periods = {}
    for rows in groups.values():
        for r in rows:
            if r.get("org_kuerzel"):
                org = r["org_kuerzel"]
                for o in org.split(" · "):
                    o = o.strip()
                    if o:
                        absent_periods.setdefault(o, set()).add(r.get("std", ""))
            elif r.get("kuerzel_absent"):
                # FDKM-Fall: Lehrer in 'kuerzel' ist selbst abwesend (kein Vertreter)
                absent_periods.setdefault(r["kuerzel"], set()).add(r.get("std", ""))
            if r.get("art") in ("cancel", "free"):
                klasse = r.get("klasse", "")
                if klasse and klasse != "—":
                    for k in klasse.split(" · "):
                        k = k.strip()
                        if k:
                            classes_periods.setdefault(k, set()).add(r.get("std", ""))

    def period_range(stds):
        nums = sorted({int(s) for s in stds if str(s).lstrip("-").isdigit()})
        if not nums:
            return ""
        if len(nums) == 1:
            return str(nums[0])
        return f"{nums[0]}–{nums[-1]}"

    absent  = [(k, period_range(v)) for k, v in sorted(absent_periods.items())]
    classes = [(k, period_range(v)) for k, v in sorted(classes_periods.items())]
    return absent, classes

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
ART_MAP = {
    "subst":      ("s-sup",   "b-sup",   "Vertr."),
    "cancel":     ("s-ent",   "b-ent",   "Entfall"),
    "roomchange": ("s-raum",  "b-raum",  "Raum"),
    "free":       ("s-frei",  "b-frei",  "Freistunde"),
    "pause":      ("s-pause", "b-pause", "Pause"),
}

WEEKDAYS = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
MONTHS   = ["Januar","Februar","März","April","Mai","Juni",
            "Juli","August","September","Oktober","November","Dezember"]

TEXT_BADGES   = {"b": "tb-b", "ub": "tb-ub", "MA": "tb-ma"}
_TEXT_PATTERN = re.compile(r'\b(ub|MA|b)\b')

def render_text(txt):
    if not txt:
        return txt
    txt_escaped = esc(txt)
    def _replace(m):
        code = m.group(0)
        cls  = TEXT_BADGES.get(code, "")
        return f'<span class="text-badge {cls}">{code}</span>' if cls else esc(code)
    return _TEXT_PATTERN.sub(_replace, txt_escaped)

def render_teacher_header(kuerzel, teacher_lookup, day="today"):
    info     = teacher_lookup.get(kuerzel, {})
    nachname = info.get("nachname", kuerzel)
    vorname  = info.get("vorname", "")
    name_str = f"{nachname} {vorname}".strip()
    day_cls  = " tomorrow" if day == "tomorrow" else ""
    return (
        f'<tr class="teacher-header{day_cls}">'
        f'<td colspan="8">'
        f'<span class="th-kuerzel">{esc(kuerzel)}</span>'
        f'<span class="th-name">{esc(name_str)}</span>'
        f'</td></tr>'
    )

def render_day_separator(d):
    label = f"Morgen · {WEEKDAYS[d.weekday()]}, {d.day}. {MONTHS[d.month-1]} {d.year}"
    return f'<tr class="day-separator"><td colspan="8">{label}</td></tr>'

def render_row(r):
    row_cls, badge_cls, label = ART_MAP.get(r["art"], ("s-sup", "b-sup", r["art"]))
    day_cls = " tomorrow" if r.get("day") == "tomorrow" else ""
    org = r.get("org_kuerzel", "")
    if org:
        # Bei "Vtr. ohne Lehrer": Bindestrich statt Pfeil (kein echter Vertreter)
        is_vtr_ohne = (r.get("text") or "").strip().lower().startswith("vtr. ohne lehrer")
        sep = " - " if is_vtr_ohne else "&rarr;"
        lehrer_html = (
            f'<s class="lehr-absent">{esc(org)}</s>'
            f'<span class="lehr-arrow">{sep}</span>'
            f'{esc(r["kuerzel"])}'
        )
    elif r.get("kuerzel_absent"):
        # Entfall ohne Vertretung: nur der abwesende Lehrer, durchgestrichen
        lehrer_html = f'<s class="lehr-absent">{esc(r["kuerzel"])}</s>'
    else:
        lehrer_html = esc(r["kuerzel"])
    raum_org = r.get("raum_org", "")
    if raum_org:
        raum_html = (
            f'<s class="room-absent">{esc(raum_org)}</s>'
            f'<span class="lehr-arrow">&rarr;</span>'
            f'{esc(r["raum"])}'
        )
    else:
        raum_html = esc(r["raum"])
    return (
        f'<tr class="{row_cls}{day_cls}">'
        f'<td class="c-kuerzel"></td>'
        f'<td class="c-std">{esc(r["std"])}</td>'
        f'<td class="c-fach">{esc(r["fach"])}</td>'
        f'<td class="c-klasse">{esc(r["klasse"])}</td>'
        f'<td class="c-lehrer">{lehrer_html}</td>'
        f'<td class="c-art"><span class="badge {badge_cls}">{esc(label)}</span></td>'
        f'<td class="c-raum">{raum_html}</td>'
        f'<td class="c-text">{render_text(r["text"])}</td>'
        f'</tr>'
    )

COLGROUP = """<colgroup>
                <col class="c-kuerzel"><col class="c-std"><col class="c-fach">
                <col class="c-klasse"><col class="c-lehrer"><col class="c-art">
                <col class="c-raum"><col class="c-text">
            </colgroup>"""
THEAD = """<thead><tr>
                <th class="c-kuerzel"></th>
                <th class="c-std">Std.</th>
                <th class="c-fach">Fach</th>
                <th class="c-klasse">Klasse(n)</th>
                <th class="c-lehrer">(Lehrer)</th>
                <th class="c-art">Art</th>
                <th class="c-raum">Raum</th>
                <th class="c-text">Text</th>
            </tr></thead>"""

TWO_COL_THRESHOLD = 30

def build_day_content(groups, teacher_lookup, day):
    if not groups:
        msg = "Kein Supplierplan für heute" if day == "today" else "Kein Supplierplan für morgen"
        return f'<div class="empty-state"><p>{msg}</p></div>'
    chunks = []
    for kuerzel, rows in groups.items():
        h = render_teacher_header(kuerzel, teacher_lookup, day)
        h += "".join(render_row(r) for r in rows)
        chunks.append((h, 1 + len(rows)))
    total = sum(w for _, w in chunks)
    if total > TWO_COL_THRESHOLD:
        left_html, right_html = split_chunks(chunks)
        return (
            f'<div class="columns">'
            f'<div class="col"><table>{COLGROUP}{THEAD}<tbody>{left_html}</tbody></table></div>'
            f'<div class="col"><table>{COLGROUP}{THEAD}<tbody>{right_html}</tbody></table></div>'
            f'</div>'
        )
    else:
        all_html = "".join(h for h, _ in chunks)
        return (
            f'<div class="columns single">'
            f'<div class="col"><table>{COLGROUP}{THEAD}<tbody>{all_html}</tbody></table></div>'
            f'</div>'
        )

def split_chunks(chunks):
    total = sum(w for _, w in chunks)
    half  = total / 2
    left, right = [], []
    count = 0
    for html, weight in chunks:
        if count < half:
            left.append(html)
        else:
            right.append(html)
        count += weight
    return "".join(left), "".join(right)

def generate_html(groups_today, groups_tomorrow, today_date, tomorrow_date,
                  teacher_lookup, period_nr, period_start, period_end,
                  show_logo=False, import_time=None):

    logo_html = '<div class="logo"><img src="logo.png" alt="Logo"></div>\n            ' if show_logo else ''

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

    show_today    = bool(groups_today)
    show_tomorrow = bool(groups_tomorrow) and bool(tomorrow_date)
    both_visible  = show_today and show_tomorrow

    today_section = ""
    if show_today:
        today_absent, today_classes = compute_absent(groups_today)
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
    if show_tomorrow:
        tom_absent, tom_classes = compute_absent(groups_tomorrow)
        days_ahead = (tomorrow_date - today_date).days
        date_str_tom = (
            f"{WEEKDAYS[tomorrow_date.weekday()]}, "
            f"{tomorrow_date.day}. {MONTHS[tomorrow_date.month-1]} {tomorrow_date.year}"
        )
        if days_ahead == 1:
            day_label = f"Morgen · {date_str_tom}"
        else:
            day_label = f"Nächster Schultag · {date_str_tom}"
        tomorrow_section = (
            f'<div class="plan-section tomorrow-section">'
            f'<div class="day-title-bar"><span class="day-title-text">{day_label}</span></div>'
            f'{render_summary_bar(tom_absent, tom_classes)}'
            f'{build_day_content(groups_tomorrow, teacher_lookup, "tomorrow")}'
            f'</div>'
        )

    if not show_today and not show_tomorrow:
        main_content = (
            '<div class="plan-section">'
            '<div class="empty-state"><p>Kein Supplierplan verfügbar</p></div>'
            '</div>'
        )
    else:
        main_content = today_section + tomorrow_section

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>Supplierplan – MS Roda-Roda-Gasse</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
<div class="layout">
    <div class="accent-top"></div>
    <header class="header">
        <div class="header-left">
            {logo_html}<div>
                <p class="school-name">MS Roda-Roda-Gasse</p>
                <p class="school-sub">Mittelschule · 1210 Wien</p>
            </div>
        </div>
        <div class="header-right">
            {period_block}
            <div class="header-divider"></div>
            <div class="clock">
                <p class="clock-date" id="clock-date">{date_str}</p>
                <p class="clock-time" id="clock-time">{time_str}</p>
            </div>
        </div>
    </header>
    <div class="plan-header">
        <span class="plan-label">Supplierplan</span>
        <span class="plan-tag">Heute</span>
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
        <span class="foot-r">MS Roda-Roda-Gasse · 1210 Wien</span>
    </footer>
</div>
<script>
(function tick() {{
    var n = new Date();
    var days = ['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag'];
    var months = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
    document.getElementById('clock-time').textContent =
        String(n.getHours()).padStart(2,'0') + ':' + String(n.getMinutes()).padStart(2,'0');
    document.getElementById('clock-date').textContent =
        days[n.getDay()] + ', ' + n.getDate() + '. ' + months[n.getMonth()] + ' ' + n.getFullYear();
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
</script>
</body>
</html>"""

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
    config = load_config()
    untis  = WebUntis(
        url       = config["UNTIS_URL"],
        school_id = config.get("UNTIS_SCHOOL_ID", "s921092"),
        user      = config["UNTIS_USER"],
        password  = config["UNTIS_PASSWORD"],
    )

    try:
        print("Einloggen ...", flush=True)
        untis.login()

        grid_raw       = untis.get_timegrid()
        teachers       = untis.get_teachers()
        holidays_raw   = untis.get_holidays()
        import_time    = untis.get_latest_import_time()
        timegrid       = build_timegrid(grid_raw)
        break_lookup   = build_break_lookup(grid_raw)
        teacher_lookup = build_teacher_lookup(teachers)
        holiday_set    = parse_holidays(holidays_raw)

        now_t   = now_hhmm()
        today   = today_local()
        today_int = int(today.strftime("%Y%m%d"))

        # Heute: vergangene Stunden herausfiltern
        print(f"Hole Heute ({today_int}) ...", flush=True)
        today_substs = untis.get_substitutions(today_int)
        today_rows   = process_substitutions(today_substs, timegrid, break_lookup, day="today")
        today_rows   = [r for r in today_rows if r["end_time"] >= now_t]
        groups_today = group_by_teacher(today_rows)

        # Morgen: ab konfigurierter Uhrzeit ODER wenn heute schon leer ist
        threshold_str = config.get("SHOW_TOMORROW_AFTER", "14:00")
        th, tm     = map(int, threshold_str.split(":"))
        threshold  = th * 100 + tm
        show_tomorrow = now_t >= threshold or not groups_today

        groups_tomorrow = {}
        tomorrow_date   = None
        tom_substs      = []
        tom_rows        = []

        if show_tomorrow:
            tomorrow      = next_school_day(today, holiday_set)
            tomorrow_int  = int(tomorrow.strftime("%Y%m%d"))
            tomorrow_date = tomorrow
            print(f"Hole nächsten Schultag ({tomorrow_int}) ...", flush=True)
            tom_substs    = untis.get_substitutions(tomorrow_int)
            tom_rows      = process_substitutions(tom_substs, timegrid, break_lookup, day="tomorrow")
            groups_tomorrow = group_by_teacher(tom_rows)

        period_nr, p_start, p_end = find_current_period(timegrid)

        today_count   = sum(len(v) for v in groups_today.values())
        tomorrow_count = sum(len(v) for v in groups_tomorrow.values())
        print(f"Heute: {today_count} Zeilen | Morgen: {tomorrow_count} Zeilen", flush=True)

        show_logo = config.get("SHOW_LOGO", "false").lower() == "true"
        html = generate_html(
            groups_today, groups_tomorrow, today, tomorrow_date,
            teacher_lookup, period_nr, p_start, p_end,
            show_logo=show_logo,
            import_time=import_time,
        )
        out = BASE_DIR / "index.html"
        out.write_text(html, encoding="utf-8")
        print(f"Fertig -> {out}", flush=True)

        # Lesbare Datenübersicht in data/ ablegen
        write_data_dump(
            today_substs, tom_substs,
            today_rows, tom_rows,
            holidays_raw, import_time,
            today, tomorrow_date,
        )
        print(f"Daten-Dump -> {BASE_DIR / 'data'}", flush=True)

    finally:
        untis.logout()

if __name__ == "__main__":
    main()
