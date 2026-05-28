# Projekt: Supplierplan-Anzeige – MS Roda-Roda-Gasse Wien

## Projektübersicht
Selbst gehostete Webanzeige für den Supplierplan unserer Schule (MS Roda-Roda-Gasse,
1210 Wien) als Ersatz für die WebUntis-Monitor-Ansicht. Läuft auf einem dedizierten
PC im Schulnetzwerk, Anzeige auf Monitor (kein Touch).

## Status: Phase 3 läuft, in Iterations-Feinschliff
- Phase 1 (Mockup, Server-Wahl) ✅ erledigt
- Phase 2 (WebUntis API erkundet) ✅ erledigt (`scripts/discover_api.py`)
- Phase 3 (Backend, Auto-Update, Filter-Logik, Layout) ✅ produktiv, läuft auf LXC

---

## Architektur

```
Cron (Server-LXC) → scripts/fetch_untis.py
       │
       ├─→ Untis JSON-RPC API (Login als Service-Account "Monitor")
       │
       ├─→ index.html         (Haupt-Anzeige für Monitor)
       └─→ data/
             ├─ last_overview.html  (lesbare Übersicht für Browser)
             └─ last_raw.json       (komplette Roh-API-Daten)

Cloudflare Tunnel → Webserver (python3 -m http.server 8080)
       │
       └─→ Browser am Monitor-PC
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
│   ├── discover_api.py           # API-Erkundungs-Script (nicht produktiv)
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
| `getTeachers` | Lehrer-Lookup (Kürzel → Vor-/Nachname) |
| `getHolidays` | Ferien/Feiertage für „nächster Schultag"-Logik |
| `getTimegridUnits` | Stundenraster (Uhrzeiten der Stunden 0–10) |
| `getLatestImportTime` | Untis-eigener Zeitstempel der letzten Änderung |
| `getSubstitutions(startDate, endDate, departmentId)` | **Hauptdaten: Supplierplan** |

### Verarbeitete Felder aus `getSubstitutions`
- `type` → `subst`, `cancel`, `roomchange`, `free` (ART_MAP in `fetch_untis.py`)
- `startTime`, `endTime` → Stundennummer aus Timegrid
- `kl[].name` → Klasse(n), dedupliziert
- `te[].name, .orgid, .orgname` → Lehrer + Vertretung (alter Lehrer durchgestrichen)
- `su[].name` → Fach (auch ohne Klasse, z.B. `TO (SIB)`)
- `ro[].name, .orgid, .orgname` → Raum + Raumwechsel (alter Raum durchgestrichen)
- `txt` → Bemerkungstext; Badges nur für `b`, `ub`, `MA` (Rest als reiner Text)
- `lstype == "bs"` → Pausenaufsicht (eigene Darstellung)

### Pseudo-Lehrer der Schule (in Untis-Stammdaten)
- **`Z Entfall`** (longName "Bester Lehrer", id 127) → in `SKIP_NAMES`, wird wie `---` behandelt
- **`Mr. X`** (longName "Lückenfüler", in `getTeachers`) → aktuell **NICHT** in SKIP_NAMES.
  Wenn er irgendwann in Substitutionen auftaucht, würde er als echter Lehrer angezeigt.
  Verhalten unklar — siehe TODOs.

### Filter-Logik (`process_substitutions`)

Zwei Filter-Stufen sorgen dafür, dass nur echte Änderungen angezeigt werden:

**Filter A — Substitution-Ebene** (`_is_meaningful_subst`):
Stunde wird nur verarbeitet wenn mindestens eines zutrifft:
- `type` ist `cancel` oder `free`
- Mindestens ein `te[]`-Eintrag hat `orgid` (= jemand fehlt/vertritt)
- Mindestens ein `ro[]`-Eintrag hat `orgid` (= Raumwechsel)

→ Reguläre Stunden ohne Vertretung (z.B. Co-Lehrer-Erwähnungen in Pausenaufsichten ohne
  jeden orgid) werden komplett übersprungen.

**Filter B — Lehrer-Ebene**:
Wenn ein expliziter Vertreter (`orgid` + Name nicht in `SKIP_NAMES`) im te[] steht,
werden andere Lehrer ohne `orgid` als Co-Lehrer übersprungen.

→ Eliminiert: Ala (Co-Lehrer bei BUS-Teamteaching), MaM/WoF-Duplikate
  (Vertreter steht doppelt mit und ohne orgid).

### Heuristiken (siehe `process_substitutions`)

**`---` / `Z Entfall` als Vorgänger-Marker** (`absent_via_dash`):
Pattern `te=[---/SaF, BuL]` (SaF fehlt, BuL ist da). Für Lehrer ohne orgid wird
`orgname` aus dem `---`-Eintrag als `org_kuerzel` übernommen → Anzeige `SaF→BuL`.

**FDKM-artiger Sonderfall (Entfall ohne Vertretung)**:
Wenn `te[]` nur `---`/`Z Entfall`-Marker enthält (kein echter Lehrer-Eintrag),
wird **eine virtuelle Zeile pro abwesendem Lehrer** erzeugt:
- `kuerzel` = abwesender Lehrer
- `art` = `cancel`
- `kuerzel_absent` = True (für Render-Logik: nur durchgestrichener Name, kein Pfeil)

→ FDKM Std 0 für NeS, Pausenaufsicht-Entfälle (GrM, WöR Std 8/9), etc.

**Trenner Pfeil ↔ Bindestrich**:
- `→` bei echter Vertretung (orgid vorhanden)
- ` - ` bei `txt = "Vtr. ohne Lehrer"` (kein echter Vertreter, Lehrer ist nur Klassen-Stammlehrer)

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
- **Solo-Morgen (heute leer):**
  Das Datum-Label wandert nach oben ins `plan-tag` (in hellblau `#6aacf0`),
  die `day-title-bar` über der Tabelle entfällt.

### Layout (CSS)
- **Heute leer + Morgen vorhanden:** Heute-Section wird komplett ausgeblendet
- **Beide sichtbar:** Heute = `flex: 0 1 auto` (Content-Größe),
  Morgen = `flex: 1 1 auto` (nimmt restlichen Platz)
  → Wenn heute schrumpft (Stunden vergehen), rutscht Morgen automatisch hoch
- **Tag-Headlines:**
  - Heute: rote Akzentlinie (`.day-title-bar.today`)
  - Morgen: blaue Akzentlinie

### Lehrer-Gruppierung
- Eine Tabellenzeile pro Vertretungs-Eintrag, gruppiert nach **aktuellem Lehrer-Kürzel**
- Pro Gruppe ein Header `<KÜRZEL> Vor- und Nachname` (16px, kontrastreich)
- Bei langen Tagen: 2-spaltige Aufteilung (Threshold: 30 Zeilen)

### Entfallende-Stunden-Sektion (eigene Gruppe am Ende)
Alle Zeilen mit `art=cancel` werden **aus den Lehrer-Gruppen ausgelagert** und am
Ende des Tages in einer eigenen Sektion mit Überschrift `Entfallende Stunden`
gesammelt. Vorteil: ein Lehrer, der nur Entfälle hatte (z.B. NeS für FDKM),
bekommt keine eigene Gruppen-Headline mehr — die Information steht kompakt
in der Cancel-Sektion mit dem Kürzel in der Lehrer-Spalte (durchgestrichen).

### Abwesenheits-Leisten (oben in jeder Section)

Quellen für „Abwesende Lehrer":
- `te[].orgname` mit `orgid` → der vertretene Lehrer ist abwesend
- `kuerzel_absent=True` → FDKM-artige Sonderfälle
- `art="cancel"` → bei Entfall ist der Lehrer abwesend
- Die `---`-Heuristik propagiert `orgname` auch auf Co-Lehrer-Zeilen

**Heuristik für Stundenangabe** (`period_range`):
1. Einzelne Stunde → nur die Zahl (z.B. `DuS (2)`)
2. Lückenhaft → Range `min–max` (z.B. `SeA (3–8)` wenn 3,4,6,8)
3. Lückenlos + reicht bis globalen Tagesende (höchste abwesende Stunde aller Lehrer):
   - Wenn `min ≤ 1` → nur Kürzel ohne Suffix (= Ganzer Tag)
   - Wenn `min > 1` → `ab X` (z.B. `WöR (ab 6)`)

„Globaler Tagesende" ist die höchste Stunde über alle abwesenden Lehrer dieses Tages
— dynamisch, nicht aus dem Timegrid.

---

## Refresh-Verhalten

Im generierten `index.html`:
- `<meta http-equiv="refresh" content="300">` als JS-Disable-Fallback
- **JavaScript:**
  - Jede Sekunde: Uhr-Update im Header (`tick()`)
  - Jede 60 Sekunden: `location.reload()` (soft reload)
  - Alle 5 Minuten (jeder 5. Tick): Hard-Reload mit Cache-Bust:
    `?cb=<timestamp>` → Browser ignoriert Cache, lädt CSS/Bilder neu
- HTTP-Header `Cache-Control: no-cache, no-store, must-revalidate`

### Cloudflare Auto-Purge (eingebaut)
`fetch_untis.py` ruft nach jedem erfolgreichen Schreiben der `index.html`
optional die Cloudflare-API auf, um den Cache zu leeren — sobald in `config.env`
gesetzt:
```
CLOUDFLARE_ZONE_ID=...      # Dashboard → Domain → API → Zone ID
CLOUDFLARE_API_TOKEN=...    # My Profile → API Tokens, Permission: Zone:Cache Purge
CLOUDFLARE_HOST=...         # optional: nur diesen Hostname purgen (sicher)
```
Wenn `CLOUDFLARE_HOST` leer ist, wird die **ganze Zone** gepurged
(`purge_everything: true`). Mit `CLOUDFLARE_HOST=supplierplan.example.tld`
nur die eine Subdomain.

### ⚠️ Manueller Cache-Purge (falls Token nicht konfiguriert)
1. Cloudflare Dashboard → Caching → Configuration → *Purge Everything*
2. Im Browser zusätzlich `Ctrl+Shift+R` (Hard-Reload)
3. Falls Page Rule "Cache Everything" gesetzt → auf *Standard* oder *Bypass* ändern
4. Test mit `?nocache=<random>` umgeht beide Caches

---

## Zeitzone

`fetch_untis.py` versucht `ZoneInfo("Europe/Vienna")` zu nutzen.
- **Linux/Server (LXC):** funktioniert wenn `tzdata`-Paket installiert ist (Standard auf Debian)
- **Windows:** braucht `pip install tzdata`. Falls nicht installiert → Fallback auf System-TZ
- Alle Aufrufe von `datetime.now()` / `date.today()` gehen über `now_local()` / `today_local()`

⚠️ **Wenn der Server in UTC läuft und `tzdata` fehlt**, ist die „Heute"-Berechnung ab
22:00 falsch. Im Zweifel `apt install tzdata` auf dem LXC ausführen.

---

## Konventionen & Sicherheit

### XSS-Schutz (IMMER einhalten)
- **Alle Werte aus der WebUntis API** müssen mit `esc()` (= `html.escape()`) escaped werden,
  bevor sie in HTML eingefügt werden — auch Fallback-Werte ("—") und neue Felder.
- Bei jeder Änderung am Render-Code prüfen: fließen unescaped API-Daten ins HTML?

### Credentials
- `config.env` enthält WebUntis-Passwort und Cloudflare-Token → niemals committen
- Steht in `.gitignore`, daneben `config.env.example` als Vorlage
- ⚠️ **Claude öffnet `config.env` NICHT** (kein `Read`, kein `cat`, kein `grep`).
  Geheimnisse bleiben unter dem Radar des Assistenten.
  - Wenn neue Variablen dokumentiert werden müssen → nur `config.env.example` editieren
  - Wenn der User eine Variable ändern soll → ihm den Schlüssel + erwarteten Wert
    nennen, er trägt selbst ein. Niemals Werte aus `config.env` zitieren oder vorschlagen
    sie an einer anderen Stelle einzusetzen.
  - Ausnahme: der User bittet explizit darum, eine konkrete Zeile zu prüfen oder zu
    ändern — dann gezielt mit `Edit` (alte → neue Zeichenkette), nicht mit `Read`.

### HTTP
- Alle Untis-Requests haben `timeout=15` Sekunden
- Login-Cookie via `http.cookiejar`, Logout am Ende garantiert

### Git-Workflow
- Commits immer mit `git commit -m "kurze Nachricht"` (kein Heredoc, keine WSL-Eigenheiten)
- Nach jedem Commit: `git push`

### Deployment auf den LXC
```
rsync -avz --exclude='.claude' --exclude='Screenshot*' --exclude='.git' \
      /mnt/c/Users/Admin/Onedrive/Programming/Claude/Supplier/ \
      root@192.168.10.134:/var/www/supplierplan/
```
SSH-Auth läuft nur im echten Terminal (kein ssh-askpass in WSL).
Im Claude Code Prompt mit `!`-Präfix ausführen, dann landet Output direkt im Chat.

### Python-Setup
- WSL hat kein Python: nutzen wir `/mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe`
- Für UTF-8-Output unter Windows: `PYTHONIOENCODING=utf-8` voranstellen, sonst CP1252-Fehler

---

## Verfügbar aber noch nicht genutzt — Ideen für später
- **`weekly/data` REST** (`elementType=2`): Wochenstundenplan ALLER Lehrer mit
  `state: ABSENT`/`REGULAR` pro Stunde → präzisere Quelle für „Abwesende Lehrer".
  Würde u.a. die Heuristik mit dem globalen Tagesende ersetzen können.
- `getStatusData`: Original-Untis-Farben (`lstypes`, `codes`)
- `getKlassen.longName`: `DFK` → `Deutsch Förderklasse`
- `getSubjects.foreColor/backColor`: Fach-spezifische Farben
- `getExams`: aktuell leer, könnte aber Prüfungen abbilden

---

## Offene Punkte / TODOs

1. **`Mr. X` als Pseudo-Lehrer** (longName "Lückenfüler") in `SKIP_NAMES` aufnehmen?
   Aktuell nicht — wartet auf User-Entscheidung, weil unklar ob er „Vertretung noch offen"
   oder „Entfall" bedeutet.
2. **Bedeutung unklar:** `txt='a'` (4× im Dump), `txt='t'` (2× im Dump). Werden aktuell
   einfach als Text durchgereicht. Bei Bedarf Badges definieren.
3. **`weekly/data`-Migration** für die „Abwesende Lehrer"-Liste (siehe oben).
   Aktuelle Heuristik ist gut, aber `weekly/data` wäre noch genauer (z.B. wenn ein
   Lehrer fehlt aber gar nicht im Supplierplan auftaucht).
4. **Sonder-Modi für `lstype`:** `ex` (Prüfung), `oh` (Sprechstunde), `sb` (Standby)
   sind im Code nicht behandelt — Verhalten unklar bis sie auftauchen.
5. ~~Automatisches Cloudflare Cache-Purge~~ ✅ implementiert (siehe oben).
   Token + Zone-ID nur noch in `config.env` eintragen.

---

## Schnell-Referenzen

- Lokal testen:
  `PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py`
- Daten-Übersicht öffnen: `data/last_overview.html` im Browser
- API-Discovery erneut: `python scripts/discover_api.py` → schreibt nach `scripts/api_dump/`
- Server-Datei prüfen:
  `ssh root@192.168.10.134 'ls -la /var/www/supplierplan/index.html'`
- WebUntis API-Doku (PDF): https://untis-sr.ch/wp-content/uploads/2019/11/2018-09-20-WebUntis_JSON-RPC_API.pdf
