#!/usr/bin/env python3
"""
diagnose_api.py – Zeigt ALLE Rohdaten von getSubstitutions ungefiltert an.
Hilft zu verstehen, warum manche Einträge (z.B. TO (SIB)) fehlen.
"""

import json
import urllib.request
import urllib.parse
import http.cookiejar
from pathlib import Path
from datetime import date, timedelta
from collections import Counter

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

class WebUntis:
    def __init__(self, url, school_id, user, password):
        self.endpoint = url.rstrip("/") + "/WebUntis/jsonrpc.do"
        self.base_url = url.rstrip("/")
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
            return json.loads(resp.read()).get("result")

    def login(self):
        self._rpc("authenticate", {
            "user": self.user, "password": self.password, "client": "diagnose"
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

    def rest_get(self, path):
        url = self.base_url + path
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with self.opener.open(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, e.reason
        except Exception as e:
            return "ERR", str(e)

def analyse(substs, label):
    print(f"\n{'='*70}")
    print(f"  ANALYSE: {label}  ({len(substs)} Einträge gesamt)")
    print(f"{'='*70}")

    # Kategorien sammeln
    lstype_counter = Counter()
    type_counter   = Counter()
    no_kl = []
    no_te = []
    with_kl_no_te = []

    for s in substs:
        lstype = s.get("lstype", "")
        art    = s.get("type", "")
        lstype_counter[lstype or "(leer)"] += 1
        type_counter[art or "(leer)"] += 1

        if not s.get("kl"):
            no_kl.append(s)
        if not s.get("te"):
            no_te.append(s)
        if s.get("kl") and not s.get("te"):
            with_kl_no_te.append(s)

    print(f"\n--- lstype (Stunden-Art) ---")
    for k, v in lstype_counter.most_common():
        print(f"  {k!r:20s}  {v}x")

    print(f"\n--- type (Vertretungs-Typ) ---")
    for k, v in type_counter.most_common():
        print(f"  {k!r:20s}  {v}x")

    # Gefilterte Einträge: kein kl → wird von fetch_untis.py übersprungen
    print(f"\n--- Einträge OHNE Klasse (kl=[]) = werden gefiltert ---")
    print(f"  Anzahl: {len(no_kl)}")
    for s in no_kl[:10]:
        te_names = [t.get("name","?") for t in s.get("te",[])]
        su_names = [f.get("name","?") for f in s.get("su",[])]
        ro_names = [r.get("name","?") for r in s.get("ro",[])]
        print(f"  lstype={s.get('lstype','')!r:8s} type={s.get('type','')!r:12s} "
              f"te={te_names} su={su_names} ro={ro_names} "
              f"start={s.get('startTime')} txt={s.get('txt','')!r}")

    # Einträge MIT Klasse aber OHNE Lehrer → erzeugen keine Zeile
    print(f"\n--- Einträge MIT Klasse, OHNE Lehrer (te=[]) = keine Zeile ---")
    print(f"  Anzahl: {len(with_kl_no_te)}")
    for s in with_kl_no_te[:10]:
        kl_names = [k.get("name","?") for k in s.get("kl",[])]
        su_names = [f.get("name","?") for f in s.get("su",[])]
        ro_names = [r.get("name","?") for r in s.get("ro",[])]
        print(f"  lstype={s.get('lstype','')!r:8s} type={s.get('type','')!r:12s} "
              f"kl={kl_names} su={su_names} ro={ro_names} "
              f"start={s.get('startTime')} txt={s.get('txt','')!r}")

    # Alle te-Kürzel mit SKIP_NAMES
    SKIP_NAMES = {"---", "Z Entfall", ""}
    skip_filtered = []
    for s in substs:
        for t in s.get("te", []):
            if t.get("name", "").strip() in SKIP_NAMES:
                skip_filtered.append((s, t))
    print(f"\n--- Lehrer-Einträge die durch SKIP_NAMES gefiltert werden ---")
    print(f"  Anzahl: {len(skip_filtered)}")
    for s, t in skip_filtered[:10]:
        kl_names = [k.get("name","?") for k in s.get("kl",[])]
        su_names = [f.get("name","?") for f in s.get("su",[])]
        print(f"  name={t.get('name','')!r} orgname={t.get('orgname','')!r} "
              f"kl={kl_names} su={su_names} lstype={s.get('lstype','')!r} type={s.get('type','')!r}")

    # Vollständige Rohdaten der ersten 5 Einträge
    print(f"\n--- Erste 5 Einträge RAW ---")
    for i, s in enumerate(substs[:5]):
        print(f"\n  [{i}] {json.dumps(s, ensure_ascii=False)}")


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

        today     = date.today()
        today_int = int(today.strftime("%Y%m%d"))

        # Nächsten Werktag bestimmen (falls heute Wochenende)
        check_day = today
        while check_day.weekday() >= 5:
            check_day += timedelta(days=1)
        check_int = int(check_day.strftime("%Y%m%d"))

        # Morgen (nächsten Werktag)
        tomorrow = check_day + timedelta(days=1)
        while tomorrow.weekday() >= 5:
            tomorrow += timedelta(days=1)
        tomorrow_int = int(tomorrow.strftime("%Y%m%d"))

        print(f"Hole Heute ({check_int}) ...")
        today_substs = untis.get_substitutions(check_int)
        if today_substs:
            analyse(today_substs, f"Heute {check_day.strftime('%d.%m.%Y')}")
            # Rohdaten speichern
            out = BASE_DIR / "scripts" / "debug_today.json"
            out.write_text(json.dumps(today_substs, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\n  → Vollständige Daten gespeichert: {out}")
        else:
            print("  Keine Daten für heute.")

        print(f"\nHole Morgen ({tomorrow_int}) ...")
        tom_substs = untis.get_substitutions(tomorrow_int)
        if tom_substs:
            analyse(tom_substs, f"Morgen {tomorrow.strftime('%d.%m.%Y')}")
            out = BASE_DIR / "scripts" / "debug_tomorrow.json"
            out.write_text(json.dumps(tom_substs, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\n  → Vollständige Daten gespeichert: {out}")
        else:
            print("  Keine Daten für morgen.")

        # REST API: Abwesenheiten testen
        print(f"\n{'='*70}")
        print("  REST API: Teacher Absences")
        print(f"{'='*70}")
        for path in [
            f"/WebUntis/api/classreg/absences/teachers?startDate={check_int}&endDate={check_int}",
            f"/WebUntis/api/classreg/absences/teachers?startDate={tomorrow_int}&endDate={tomorrow_int}",
        ]:
            status, data = untis.rest_get(path)
            preview = json.dumps(data, ensure_ascii=False)[:300] if isinstance(data, (dict,list)) else str(data)
            print(f"\n  GET {path[-60:]}")
            print(f"  Status: {status}")
            print(f"  Response: {preview}")

    finally:
        untis.logout()
        print("\n=== Fertig ===")

if __name__ == "__main__":
    main()
