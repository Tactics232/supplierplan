#!/usr/bin/env python3
"""
explore_rest.py – Erkundet die WebUntis REST API mit bestehenden Credentials.
Nur zum Testen – nicht für Produktion.
"""

import json
import urllib.request
import urllib.parse
import http.cookiejar
from pathlib import Path
from datetime import date

BASE_DIR    = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config.env"

def load_config():
    config = {}
    with open(CONFIG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                config[key.strip()] = val.strip()
    return config

def main():
    config   = load_config()
    base_url = config["UNTIS_URL"].rstrip("/")
    school   = config.get("UNTIS_SCHOOL_ID", "s921092")
    user     = config["UNTIS_USER"]
    password = config["UNTIS_PASSWORD"]

    jar    = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar)
    )

    # ── 1. Login via JSON-RPC (setzt Session-Cookie) ──────
    print("=== Login via JSON-RPC ===")
    rpc_url = f"{base_url}/WebUntis/jsonrpc.do?school={urllib.parse.quote(school)}"
    payload = json.dumps({
        "jsonrpc": "2.0", "id": "1", "method": "authenticate",
        "params": {"user": user, "password": password, "client": "explore"}
    }).encode()
    req = urllib.request.Request(
        rpc_url, data=payload,
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req, timeout=15) as resp:
        result = json.loads(resp.read())
    print("Login:", result.get("result", result.get("error")))
    print("Cookies:", [(c.name, c.value[:20]+"…") for c in jar])

    # ── 2. REST Endpoints ausprobieren ────────────────────
    today     = date.today()
    today_str = today.strftime("%Y-%m-%d")
    school_year_start = f"{today.year}-09-01" if today.month >= 9 else f"{today.year-1}-09-01"

    endpoints = [
        f"/WebUntis/api/public/timetable/weekly/data?elementType=1&elementId=1&date={today_str}&formatId=1",
        f"/WebUntis/api/substitutions/v1/substitutions?schoolyearId=1&departmentId=0&startDate={today_str}&endDate={today_str}",
        f"/WebUntis/api/classreg/absences/students?startDate={today_str}&endDate={today_str}",
        f"/WebUntis/api/classreg/absences/teachers?startDate={today_str}&endDate={today_str}",
        f"/WebUntis/api/absences/student?startDate={today_str}&endDate={today_str}",
        f"/WebUntis/api/teachers/absent?startDate={today_str}&endDate={today_str}",
        f"/WebUntis/api/schoolyears",
        f"/WebUntis/api/timetable/weekly/config",
        f"/WebUntis/api/daytimetable?date={today_str}",
    ]

    for path in endpoints:
        url = base_url + path
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with opener.open(req, timeout=15) as resp:
                status = resp.status
                body   = resp.read().decode(errors="replace")
                try:
                    data = json.loads(body)
                    preview = json.dumps(data, ensure_ascii=False)[:200]
                except Exception:
                    preview = body[:200]
        except urllib.error.HTTPError as e:
            status  = e.code
            preview = e.reason
        except Exception as e:
            status  = "ERR"
            preview = str(e)

        print(f"\n{'='*60}")
        print(f"GET {path[:70]}")
        print(f"Status: {status}")
        print(f"Response: {preview}")

    # ── 3. Logout ─────────────────────────────────────────
    try:
        logout_payload = json.dumps({
            "jsonrpc": "2.0", "id": "1", "method": "logout", "params": {}
        }).encode()
        req = urllib.request.Request(
            rpc_url, data=logout_payload,
            headers={"Content-Type": "application/json"}
        )
        opener.open(req, timeout=15)
    except Exception:
        pass
    print("\n=== Fertig ===")

if __name__ == "__main__":
    main()
