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
    now_t = datetime.now().hour * 100 + datetime.now().minute
    for start, (nr, s, e) in sorted(timegrid.items()):
        if s <= now_t <= e:
            return nr, fmt_time(s), fmt_time(e)
    return None, None, None

def now_hhmm():
    n = datetime.now()
    return n.hour * 100 + n.minute

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
def process_substitutions(substs, timegrid, break_lookup, day="today"):
    rows = []
    for s in substs:
        start  = s.get("startTime", 0)
        end    = s.get("endTime", 0)
        lstype = s.get("lstype", "")
        art    = s.get("type", "subst")
        txt    = s.get("txt", "")

        is_break = lstype == "bs"

        if is_break:
            std_display = break_lookup.get(start, fmt_time(start))
            klasse = "—"
            fach   = "Aufsicht"
            raum   = " · ".join(
                r["name"] for r in s.get("ro", [])
                if r.get("name") and r["name"] not in ("---", "")
            ) or "—"
            art_out = "pause"
        else:
            if not s.get("kl"):
                continue
            info = timegrid.get(start)
            std_display = str(info[0]) if info else "?"
            klasse = " · ".join(k["name"] for k in s.get("kl", []))
            fach   = " · ".join(f["name"] for f in s.get("su", [])) or "—"
            raum   = " · ".join(
                r["name"] for r in s.get("ro", [])
                if r.get("name") and r["name"] not in ("---", "")
            ) or "—"
            art_out = art

        for t in s.get("te", []):
            kuerzel = t.get("name", "").strip()
            if kuerzel in SKIP_NAMES:
                continue
            orgname = t.get("orgname", "").strip()
            lehrer  = f"{orgname} → {kuerzel}" if (t.get("orgid") and orgname) else kuerzel

            rows.append({
                "kuerzel":  kuerzel,
                "std":      std_display,
                "sort_key": start,
                "end_time": end,
                "day":      day,
                "fach":     fach,
                "klasse":   klasse,
                "lehrer":   lehrer,
                "art":      art_out,
                "raum":     raum,
                "text":     txt,
            })
    return rows

def group_by_teacher(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r["kuerzel"]].append(r)
    for key in groups:
        groups[key].sort(key=lambda r: r["sort_key"])
    return dict(sorted(groups.items()))

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
    day_cls     = " tomorrow" if r.get("day") == "tomorrow" else ""
    # esc() first, then replace the → character (html.escape does not touch it)
    lehrer_html = esc(r["lehrer"]).replace("→", '<span class="lehr-arrow">&rarr;</span>')
    return (
        f'<tr class="{row_cls}{day_cls}">'
        f'<td class="c-kuerzel"></td>'
        f'<td class="c-std">{esc(r["std"])}</td>'
        f'<td class="c-fach">{esc(r["fach"])}</td>'
        f'<td class="c-klasse">{esc(r["klasse"])}</td>'
        f'<td class="c-lehrer">{lehrer_html}</td>'
        f'<td class="c-art"><span class="badge {badge_cls}">{label}</span></td>'
        f'<td class="c-raum">{esc(r["raum"])}</td>'
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

def build_chunks(groups_today, groups_tomorrow, tomorrow_date, teacher_lookup):
    """Gibt Liste von (html, gewicht) Tupeln zurück für die Zwei-Spalten-Aufteilung."""
    chunks = []

    for kuerzel, rows in groups_today.items():
        html = render_teacher_header(kuerzel, teacher_lookup, "today")
        html += "".join(render_row(r) for r in rows)
        chunks.append((html, 1 + len(rows)))

    if groups_tomorrow and tomorrow_date:
        chunks.append((render_day_separator(tomorrow_date), 2))
        for kuerzel, rows in groups_tomorrow.items():
            html = render_teacher_header(kuerzel, teacher_lookup, "tomorrow")
            html += "".join(render_row(r) for r in rows)
            chunks.append((html, 1 + len(rows)))

    return chunks

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

def generate_html(groups_today, groups_tomorrow, tomorrow_date,
                  teacher_lookup, period_nr, period_start, period_end, show_logo=False):

    logo_html = '<div class="logo"><img src="logo.png" alt="Logo"></div>\n            ' if show_logo else ''

    now      = datetime.now()
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

    chunks = build_chunks(groups_today, groups_tomorrow, tomorrow_date, teacher_lookup)

    TWO_COL_THRESHOLD = 30  # ab dieser Zeilenzahl zwei Spalten

    if chunks:
        total_weight = sum(w for _, w in chunks)
        if total_weight > TWO_COL_THRESHOLD:
            left_html, right_html = split_chunks(chunks)
            main_content = (
                f'<div class="columns">'
                f'<div class="col"><table>{COLGROUP}{THEAD}<tbody>{left_html}</tbody></table></div>'
                f'<div class="col"><table>{COLGROUP}{THEAD}<tbody>{right_html}</tbody></table></div>'
                f'</div>'
            )
        else:
            all_html = "".join(h for h, _ in chunks)
            main_content = (
                f'<div class="columns single">'
                f'<div class="col"><table>{COLGROUP}{THEAD}<tbody>{all_html}</tbody></table></div>'
                f'</div>'
            )
    else:
        main_content = '<div class="empty-state"><p>Kein Supplierplan für heute</p></div>'

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
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
</script>
</body>
</html>"""

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
        timegrid       = build_timegrid(grid_raw)
        break_lookup   = build_break_lookup(grid_raw)
        teacher_lookup = build_teacher_lookup(teachers)

        now_t   = now_hhmm()
        today   = date.today()
        today_int = int(today.strftime("%Y%m%d"))

        # Heute: vergangene Stunden herausfiltern
        print(f"Hole Heute ({today_int}) ...", flush=True)
        today_substs = untis.get_substitutions(today_int)
        today_rows   = process_substitutions(today_substs, timegrid, break_lookup, day="today")
        today_rows   = [r for r in today_rows if r["end_time"] >= now_t]
        groups_today = group_by_teacher(today_rows)

        # Morgen: ab konfigurierter Uhrzeit laden
        threshold_str = config.get("SHOW_TOMORROW_AFTER", "14:00")
        th, tm     = map(int, threshold_str.split(":"))
        threshold  = th * 100 + tm
        show_tomorrow = now_t >= threshold

        groups_tomorrow = {}
        tomorrow_date   = None

        if show_tomorrow:
            tomorrow = today + timedelta(days=1)
            while tomorrow.weekday() >= 5:   # Wochenende überspringen
                tomorrow += timedelta(days=1)
            tomorrow_int  = int(tomorrow.strftime("%Y%m%d"))
            tomorrow_date = tomorrow
            print(f"Hole Morgen ({tomorrow_int}) ...", flush=True)
            tom_substs    = untis.get_substitutions(tomorrow_int)
            tom_rows      = process_substitutions(tom_substs, timegrid, break_lookup, day="tomorrow")
            groups_tomorrow = group_by_teacher(tom_rows)

        period_nr, p_start, p_end = find_current_period(timegrid)

        today_count   = sum(len(v) for v in groups_today.values())
        tomorrow_count = sum(len(v) for v in groups_tomorrow.values())
        print(f"Heute: {today_count} Zeilen | Morgen: {tomorrow_count} Zeilen", flush=True)

        show_logo = config.get("SHOW_LOGO", "false").lower() == "true"
        html = generate_html(
            groups_today, groups_tomorrow, tomorrow_date,
            teacher_lookup, period_nr, p_start, p_end,
            show_logo=show_logo,
        )
        out = BASE_DIR / "index.html"
        out.write_text(html, encoding="utf-8")
        print(f"Fertig -> {out}", flush=True)

    finally:
        untis.logout()

if __name__ == "__main__":
    main()
