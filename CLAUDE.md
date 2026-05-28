# Projekt: Supplierplan-Anzeige – VS Roda-Roda-Gasse Wien

## Projektübersicht
Selbst gehostete Webanzeige für den Supplierplan unserer Schule (MS Roda-Roda-Gasse,
1210 Wien) als Ersatz für die WebUntis-Monitor-Ansicht. Läuft auf einem dedizierten
PC im Schulnetzwerk, Anzeige auf Monitor (kein Touch).

## Status: Phase 2 / 3 aktiv
- Phase 1 (Mockup, Server-Wahl) ✅ erledigt
- Phase 2 (WebUntis API erkunden) ✅ erledigt (`scripts/discover_api.py`)
- Phase 3 (Backend, Auto-Update) ✅ läuft (Cron + `fetch_untis.py`)

---

## Architektur

```
Cron (Server-LXC) → scripts/fetch_untis.py
       │
       ├─→ Untis JSON-RPC API (Login als "Monitor")
       │
       ├─→ index.html        (Haupt-Anzeige)
       └─→ data/
             ├─ last_overview.html  (lesbare Übersicht für Browser)
             └─ last_raw.json       (komplette Roh-API-Daten)

Browser (Monitor-PC) → http://server:8080/index.html
       Auto-Refresh: 60s soft / alle 5 min hard (Cache-Bust)
```

### Technischer Stack
- **Frontend:** statisches HTML5 + CSS3, minimal JS (Uhr + Refresh-Loop)
- **Backend:** Python 3.9+ (stdlib only), `scripts/fetch_untis.py`
- **Datenquelle:** WebUntis JSON-RPC API
- **Webserver:** `python3 -m http.server 8080` als systemd-Dienst auf Proxmox LXC
- **Hosting:** LXC `192.168.10.134`, erreichbar via Cloudflare Tunnel
- **Deployment:** `rsync` von WSL auf den LXC, danach Cron übernimmt

### Dateistruktur
```
supplierplan/
├── index.html                    # Wird vom Script erzeugt (gitignored)
├── config.env                    # WebUntis-Login + Schwellen (gitignored)
├── config.env.example            # Vorlage ohne Geheimnisse
├── css/style.css                 # Komplettes Styling
├── fonts/                        # Roboto + Roboto Condensed (lokal, kein CDN)
├── logo.png                      # Schullogo
├── scripts/
│   ├── fetch_untis.py            # Haupt-Script (Cron)
│   ├── discover_api.py           # Erkundungs-Script (nicht produktiv)
│   ├── diagnose_api.py           # Diagnose-Helper (nicht produktiv)
│   ├── explore_rest.py           # REST-Exploration (Archiv)
│   └── api_dump/                 # Discovery-Outputs (gitignored)
└── data/                         # Wird vom Script bei jedem Run überschrieben (gitignored)
    ├── last_overview.html        # Lesbare API-Daten-Übersicht
    └── last_raw.json             # Roh-Antworten von WebUntis
```

---

## WebUntis API – was wir nutzen

Server: `https://s921092.webuntis.com`, Schul-ID `s921092`, User `Monitor` (Admin).

### Aktiv genutzte JSON-RPC Methoden
| Methode | Zweck |
|---|---|
| `authenticate` / `logout` | Session-Login mit Cookie |
| `getTeachers` | Lehrer-Lookup (Vor- und Nachname) |
| `getKlassen` | (verfügbar, derzeit nicht im Hauptscript) |
| `getSubjects` | (verfügbar, derzeit nicht genutzt) |
| `getRooms` | (verfügbar, derzeit nicht genutzt) |
| `getHolidays` | Ferien/Feiertage für "nächster Schultag"-Logik |
| `getTimegridUnits` | Stundenraster (Uhrzeiten der Stunden 1–8) |
| `getLatestImportTime` | Untis-eigener Zeitstempel der letzten Änderung |
| `getSubstitutions(startDate, endDate, departmentId)` | **Hauptdaten: Supplierplan** |
| `getStatusData` | (verfügbar: Untis-Farben für Stunden-Arten — derzeit nicht genutzt) |

### Verarbeitete Felder aus `getSubstitutions`
- `type` → `subst`, `cancel`, `roomchange`, `free` (ART_MAP in `fetch_untis.py`)
- `startTime`, `endTime` → Stundennummer aus Timegrid
- `kl[].name` → Klasse(n)
- `te[].name, .orgid, .orgname` → Lehrer + Vertretung (alter Lehrer durchgestrichen)
- `su[].name` → Fach (auch ohne Klasse, z.B. `TO (SIB)`)
- `ro[].name, .orgid, .orgname` → Raum + Raumwechsel (alter Raum durchgestrichen)
- `txt` → Bemerkungstext; Badges nur für `b`, `ub`, `MA` (Rest als reiner Text)
- `lstype == "bs"` → Pausenaufsicht (eigene Darstellung)

### Bekannte API-Quirks
- Einträge **ohne `kl[]`** (z.B. `TO (SIB)`, Sonderdienste) werden trotzdem angezeigt
  → Klasse zeigt `—`
- `lstype` fehlt bei regulären Unterrichtsstunden (= nicht-Pause) — Default-Verhalten
- `te[]` kann doppelte Einträge enthalten (mit und ohne `orgid`) → führt aktuell zu
  doppelten Zeilen, weiteres Refactoring nötig
- REST-Endpoint `/api/classreg/absences/teachers` → HTTP 500 mit Session-Cookie.
  Workaround: `getSubstitutions` + ggf. `/api/public/timetable/weekly/data` (siehe unten).

### Verfügbar aber noch nicht genutzt — Ideen für später
- `weekly/data` REST (elementType=2): Wochenstundenplan ALLER Lehrer mit
  `state: ABSENT`/`REGULAR` pro Stunde → bessere Quelle für "Abwesende Lehrer"
- `getStatusData`: Original-Untis-Farben (`lstypes`, `codes`)
- `getKlassen.longName`: `DFK` → `Deutsch Förderklasse`
- `getSubjects.foreColor/backColor`: Fach-spezifische Farben
- `getExams`: aktuell leer, könnte aber Prüfungen abbilden

---

## Anzeige-Logik (`scripts/fetch_untis.py`)

### Heute vs. nächster Schultag
- **Heute:** vergangene Stunden werden via `end_time >= now_t` ausgefiltert
- **Nächster Schultag:**
  - überspringt Wochenenden **und** Ferien (`parse_holidays` aus `getHolidays`)
  - wird angezeigt ab `SHOW_TOMORROW_AFTER` (config.env, aktuell `12:30`)
  - **wird auch angezeigt** wenn heute leer ist, egal ob Schwelle erreicht
- **Label:**
  - 1 Tag in der Zukunft → `Morgen · Freitag, 29. Mai 2026`
  - mehrere Tage → `Nächster Schultag · Montag, 1. Juni 2026`

### Layout (CSS)
- **Heute leer + Morgen vorhanden:** Heute-Section wird komplett ausgeblendet
- **Beide sichtbar:** Heute = `flex: 0 1 auto` (Content-Größe),
  Morgen = `flex: 1 1 auto` (nimmt restlichen Platz)
  → Wenn heute schrumpft (Stunden vergehen), rutscht Morgen automatisch hoch
- **Tag-Headlines:**
  - Heute: rote Akzentlinie (`.day-title-bar.today`)
  - Morgen: blaue Akzentlinie

### Lehrer-Gruppierung
- Eine Tabellenzeile pro Vertretungs-Eintrag, aber gruppiert nach **Lehrer-Kürzel**
- Pro Gruppe ein Header `<KÜRZEL> Vor- und Nachname` (16px, kontrastreich)
- Bei langen Tagen: 2-spaltige Aufteilung (Threshold: 30 Zeilen)

### Abwesenheits-Leisten (oben in jeder Section)
- **Abwesende Lehrer:** abgeleitet aus `te[].orgname/orgid` im Supplierplan
- **Abwesende Klassen:** abgeleitet aus `type=cancel|free`-Einträgen
- ⚠️ Limitation: Wenn ein Lehrer fehlt aber keine Vertretung im Supplierplan steht,
  taucht er nicht auf. Saubere Lösung wäre `weekly/data` (siehe TODOs).

---

## Refresh-Verhalten

Im generierten `index.html`:
- `<meta http-equiv="refresh" content="300">` als JS-Disable-Fallback
- **JavaScript:**
  - Jede Sekunde: Uhr-Update im Header (`tick()`)
  - Jede 60 Sekunden: `location.reload()` (soft reload)
  - Alle 5 Minuten (jeder 5. Tick): Hard-Reload mit Cache-Bust:
    `?cb=<timestamp>` → Browser ignoriert Cache, lädt CSS/Bilder neu
- HTTP-Header `Cache-Control: no-cache` verhindert Browser-Caching

---

## Zeitzone

`fetch_untis.py` versucht `ZoneInfo("Europe/Vienna")` zu nutzen.
- **Linux/Server (LXC):** funktioniert wenn `tzdata`-Paket installiert ist (Standard auf Debian/Ubuntu)
- **Windows:** braucht `pip install tzdata`. Falls nicht installiert → Fallback auf System-TZ
- Alle Aufrufe von `datetime.now()` / `date.today()` gehen über `now_local()` / `today_local()`

⚠️ **Wenn der Server in UTC läuft und `tzdata` fehlt**, ist die "Heute"-Berechnung ab
22:00 falsch. Im Zweifel `apt install tzdata` auf dem LXC ausführen.

---

## Konventionen & Sicherheit

### XSS-Schutz (IMMER einhalten)
- **Alle Werte aus der WebUntis API** müssen mit `esc()` (= `html.escape()`) escaped werden,
  bevor sie in HTML eingefügt werden — auch Fallback-Werte ("—") und neue Felder.
- Bei jeder Änderung am Render-Code prüfen: fließen unescaped API-Daten ins HTML?

### Credentials
- `config.env` enthält WebUntis-Passwort → niemals committen
- Steht in `.gitignore`, daneben `config.env.example` als Vorlage

### HTTP
- Alle Untis-Requests haben `timeout=15` Sekunden
- Login-Cookie via `http.cookiejar`, Logout am Ende garantiert

### Git-Workflow
- Commits immer mit `git commit -m "kurze Nachricht"` (kein Heredoc, keine WSL-Eigenheiten)
- Nach jedem Commit: `git push`
- Nach jedem Deployment:
  ```
  rsync -avz --exclude='.claude' --exclude='Screenshot*' \
        /mnt/c/Users/Admin/Onedrive/Programming/Claude/Supplier/ \
        root@192.168.10.134:/var/www/supplierplan/
  ```

### Python-Setup
- WSL hat kein Python: nutzen wir `/mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe`
- Für UTF-8-Output unter Windows: `PYTHONIOENCODING=utf-8` voranstellen, sonst CP1252-Fehler

---

## Offene Punkte / TODOs für nächste Session

1. **Doppelte Lehrer-Zeilen** bei `te[]` mit redundanten Einträgen (mit und ohne `orgid`)
   → Deduplizieren in `process_substitutions`.
2. **"Vtr. ohne Lehrer"** (`txt`-Wert): aktuell nur als grauer Text — sinnvoll mit
   Badge/Warnung hervorheben?
3. **Bedeutung unklar:** `txt='a'` (4× im Dump), `txt='t'` (2× im Dump) — User fragen.
4. **`weekly/data`-Migration** für "Abwesende Lehrer"-Liste (siehe oben).
5. **Sonder-Modi für `lstype`:** `ex` (Prüfung), `oh` (Sprechstunde), `sb` (Standby)
   sind im Code nicht behandelt — Verhalten unklar bis sie auftauchen.
6. **Refresh-Intervall** (60s) ggf. anpassen wenn der Cron schneller läuft als
   das Browser-Polling.

---

## Schnell-Referenzen

- Lokal testen: `PYTHONIOENCODING=utf-8 python scripts/fetch_untis.py`
- Daten-Übersicht öffnen: `data/last_overview.html` im Browser
- API-Discovery erneut: `python scripts/discover_api.py` → schreibt nach `scripts/api_dump/`
- WebUntis API-Doku (PDF): https://untis-sr.ch/wp-content/uploads/2019/11/2018-09-20-WebUntis_JSON-RPC_API.pdf
