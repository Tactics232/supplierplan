#!/usr/bin/env python3
"""
discover_api.py – Systematische Erkundung aller WebUntis-API-Endpunkte
                  mit unseren Admin-Credentials.

Testet alle bekannten JSON-RPC Methoden + relevante REST Endpoints,
speichert jede Antwort als JSON-Datei und gibt eine Übersicht aus.
"""

import json
import sys
import io
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from pathlib import Path
from datetime import date, timedelta

BASE_DIR    = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config.env"
OUT_DIR     = BASE_DIR / "scripts" / "api_dump"
OUT_DIR.mkdir(exist_ok=True)


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def load_config():
    config = {}
    with open(CONFIG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                config[key.strip()] = val.strip()
    return config


class WebUntis:
    def __init__(self, url, school_id, user, password):
        self.endpoint  = url.rstrip("/") + "/WebUntis/jsonrpc.do"
        self.base_url  = url.rstrip("/")
        self.school_id = school_id
        self.user      = user
        self.password  = password
        self.jar       = http.cookiejar.CookieJar()
        self.opener    = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.session_token = None

    def rpc(self, method, params=None):
        payload = json.dumps({
            "jsonrpc": "2.0", "id": "1",
            "method": method, "params": params or {}
        }).encode()
        url = f"{self.endpoint}?school={urllib.parse.quote(self.school_id)}"
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            with self.opener.open(req, timeout=15) as resp:
                data = json.loads(resp.read())
            if "error" in data:
                return {"_error": data["error"]}
            return {"_ok": data.get("result")}
        except Exception as e:
            return {"_exc": str(e)}

    def rest(self, path):
        url = self.base_url + path
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with self.opener.open(req, timeout=15) as resp:
                body = resp.read().decode(errors="replace")
                try:
                    return {"_status": resp.status, "_ok": json.loads(body)}
                except Exception:
                    return {"_status": resp.status, "_raw": body[:500]}
        except urllib.error.HTTPError as e:
            return {"_status": e.code, "_error": e.reason}
        except Exception as e:
            return {"_exc": str(e)}

    def login(self):
        res = self.rpc("authenticate", {
            "user": self.user, "password": self.password, "client": "discover"
        })
        if "_ok" in res and res["_ok"]:
            self.session_token = res["_ok"].get("sessionId")
        return res

    def logout(self):
        try:
            self.rpc("logout")
        except Exception:
            pass


def short(data, n=300):
    if data is None:
        return "None"
    if isinstance(data, (dict, list)):
        s = json.dumps(data, ensure_ascii=False)
    else:
        s = str(data)
    return s[:n] + ("…" if len(s) > n else "")


def save(name, data):
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def summarize(name, res):
    if "_ok" in res:
        body = res["_ok"]
        if isinstance(body, list):
            count = len(body)
            sample_keys = list(body[0].keys()) if body and isinstance(body[0], dict) else []
            return f"OK  ({count} Einträge)  Felder: {sample_keys}"
        elif isinstance(body, dict):
            return f"OK  Felder: {list(body.keys())}"
        else:
            return f"OK  {short(body, 80)}"
    if "_error" in res:
        err = res["_error"]
        if isinstance(err, dict):
            return f"FEHLER  [{err.get('code')}] {err.get('message')}"
        return f"FEHLER  {err}"
    if "_status" in res:
        return f"HTTP {res['_status']}  {short(res.get('_ok') or res.get('_raw') or res.get('_error'), 100)}"
    if "_exc" in res:
        return f"EXC  {res['_exc']}"
    return short(res, 100)


def section(title):
    print(f"\n{'='*78}")
    print(f"  {title}")
    print(f"{'='*78}")


def main():
    config = load_config()
    untis  = WebUntis(
        url       = config["UNTIS_URL"],
        school_id = config.get("UNTIS_SCHOOL_ID", "s921092"),
        user      = config["UNTIS_USER"],
        password  = config["UNTIS_PASSWORD"],
    )

    section("LOGIN")
    login_res = untis.login()
    print(summarize("authenticate", login_res))
    save("00_authenticate", login_res)

    # Datumsberechnung – nächster Werktag
    today = date.today()
    while today.weekday() >= 5:
        today += timedelta(days=1)
    today_int = int(today.strftime("%Y%m%d"))

    week_end  = today + timedelta(days=6)
    week_end_int = int(week_end.strftime("%Y%m%d"))

    try:
        # ── JSON-RPC Methoden ohne Parameter ──────────────────
        section("JSON-RPC: Stammdaten (ohne Parameter)")
        plain_methods = [
            "getTeachers",
            "getStudents",
            "getKlassen",
            "getSubjects",
            "getRooms",
            "getDepartments",
            "getHolidays",
            "getTimegridUnits",
            "getStatusData",
            "getCurrentSchoolyear",
            "getSchoolyears",
            "getLatestImportTime",
            "getExamTypes",
            "getPersonId",
        ]
        for m in plain_methods:
            res = untis.rpc(m)
            print(f"  {m:30s} → {summarize(m, res)}")
            save(f"01_{m}", res)

        # ── JSON-RPC Methoden mit Datums-Parametern ───────────
        section(f"JSON-RPC: Datumsabhängig ({today_int} – {week_end_int})")
        param_methods = [
            ("getSubstitutions",   {"startDate": today_int, "endDate": today_int, "departmentId": 0}),
            ("getSubstitutions",   {"startDate": today_int, "endDate": week_end_int, "departmentId": 0}),
            ("getClassregEvents",  {"startDate": today_int, "endDate": today_int}),
            ("getClassregEvents",  {"startDate": today_int, "endDate": week_end_int}),
            ("getExams",           {"startDate": today_int, "endDate": week_end_int, "examTypeId": 0}),
        ]
        for m, params in param_methods:
            res = untis.rpc(m, params)
            label = f"{m}({list(params.keys())})"
            print(f"  {label:50s} → {summarize(m, res)}")
            tag = "_range" if params.get("endDate") != params.get("startDate") else "_today"
            save(f"02_{m}{tag}", res)

        # ── Timetable Beispiel: erstes Lehrer-Kürzel ─────────
        section("JSON-RPC: Stundenplan-Tests")
        teachers_res = untis.rpc("getTeachers")
        teachers = teachers_res.get("_ok") or []
        if teachers:
            first = teachers[0]
            tid = first.get("id")
            print(f"  Beispiel-Lehrer: id={tid} kürzel={first.get('name')}")
            res = untis.rpc("getTimetable", {
                "id": tid, "type": 2,  # 2 = Lehrer
                "startDate": today_int, "endDate": today_int
            })
            print(f"  getTimetable(teacher={tid}, heute)        → {summarize('getTimetable', res)}")
            save("03_getTimetable_teacher", res)

        klassen_res = untis.rpc("getKlassen")
        klassen = klassen_res.get("_ok") or []
        if klassen:
            first = klassen[0]
            kid = first.get("id")
            print(f"  Beispiel-Klasse: id={kid} name={first.get('name')}")
            res = untis.rpc("getTimetable", {
                "id": kid, "type": 1,  # 1 = Klasse
                "startDate": today_int, "endDate": today_int
            })
            print(f"  getTimetable(klasse={kid}, heute)         → {summarize('getTimetable', res)}")
            save("03_getTimetable_klasse", res)

        # ── REST API: Abwesenheiten ───────────────────────────
        section("REST: Abwesenheiten & weitere Endpoints")
        rest_endpoints = [
            f"/WebUntis/api/classreg/absences/teachers?startDate={today_int}&endDate={today_int}",
            f"/WebUntis/api/classreg/absences/teachers?startDate={today_int}&endDate={week_end_int}",
            f"/WebUntis/api/classreg/absences/students?startDate={today_int}&endDate={today_int}",
            f"/WebUntis/api/classreg/absences?startDate={today_int}&endDate={today_int}",
            f"/WebUntis/api/public/timetable/weekly/data?elementType=2&date={today.strftime('%Y-%m-%d')}",
            f"/WebUntis/api/public/timetable/weekly/data?elementType=1&date={today.strftime('%Y-%m-%d')}",
            f"/WebUntis/api/public/news/newsWidgetData?date={today.strftime('%Y-%m-%d')}",
            f"/WebUntis/api/dailyschedule?date={today.strftime('%Y-%m-%d')}",
            "/WebUntis/api/rest/view/v1/timetable/entries",
            f"/WebUntis/api/rest/view/v1/timetable/entries?start={today.strftime('%Y-%m-%d')}&end={today.strftime('%Y-%m-%d')}",
        ]
        for path in rest_endpoints:
            res = untis.rest(path)
            label = path.split("?")[0].split("/")[-1]
            print(f"  {path[-65:]:65s} → {summarize(label, res)}")
            safe = path.replace("/", "_").replace("?", "_").replace("=", "-").replace("&", "+")[:80]
            save(f"10_REST_{safe}", res)

    finally:
        untis.logout()

    section("FERTIG")
    print(f"  Alle Antworten gespeichert in: {OUT_DIR}")


if __name__ == "__main__":
    main()
