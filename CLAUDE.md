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

### Zug-Widget (separater Datenfluss)

```
Cron jede Minute → scripts/fetch_trains.py
    → urllib POST → ÖBB HAFAS mgate.exe (Direct JSON-API, stdlib only)
    → data/trains.json (atomar geschrieben, alte Datei bleibt bei Fehler)

Browser fetched data/trains.json alle 60s und befüllt #train-widget im Header.
```

Konfiguration in `config.env` über `TRAIN_*`-Variablen. Wenn `TRAIN_STATION` leer oder
`TRAIN_DISABLED=true`, wird das Widget nicht ins HTML eingebaut.

**Weitere Layout-Variablen:**
- `COMPACT_COL_WIDTH_PX` (Default 320): Schwelle für Badge-Rundung + Aufs.-Kürzung
- `MAX_COLUMNS` (Default 4, geklemmt 1–4): Obergrenze der Spaltenanzahl im
  Multi-Column-Layout. Wird als `window.MAX_COLUMNS` injiziert und in der JS-Engine
  als `MAX_COLS` verwendet (greift in `maxColsByWidth`, `chooseColCount`,
  `paginateColumns`).
- **Überlauf-Strategie** (`OVERFLOW_*`): greift, wenn der Plan zu voll für den
  Bildschirm ist — gestuft **Skalieren → Reduzieren → Blättern**, jede Stufe einzeln
  schaltbar. `OVERFLOW_SCALE`/`OVERFLOW_SCALE_MIN` (Default true / 0.65, board-weiter
  Faktor), `OVERFLOW_REDUCE` (Text-Spalte aus, dann Entfall-Sektion kompakt),
  `OVERFLOW_PAGINATE` + `OVERFLOW_PAGE_SECONDS` (Default 12). „Morgen" bleibt in jeder
  Stufe sichtbar. Logik im JS-`applyLayout`/`layoutAll`, testbarer Mirror in
  `_layout_logic.py` (`fit_scale`, `distribute_uncapped`, `paginate_columns`),
  Parsing in `parse_overflow_config`, Config via `window.OVERFLOW` injiziert.
- `SCHOOL_NAME` / `SCHOOL_TYPE` / `SCHOOL_LOCATION`: Schul-Bezeichnung im Header,
  Footer und Browser-Titel. Sub-Zeile = `TYPE · LOCATION`, Footer = `NAME · LOCATION`
  (leere Teile fallen aus der `·`-Kette). Defaults = MS Roda-Roda-Gasse-Werte.
- `SHOW_CLOCK` (Default true): `false` blendet Datum + Uhrzeit + Trennlinie aus.
- `PLAN_TITLE` (Default „Supplierplan"): Titel in Browser-Tab, Sub-Header-Label,
  Leer-Meldungen und PWA-Manifest. Für andere Schulen z.B. „Vertretungsplan".
- `LOGO_FILE` (Default `logo.png`): Logo-Dateiname im Projekt-Root (PNG/SVG/JPG/WebP).
- `SKIP_TEACHERS` (Default „Z Entfall"): schul-eigene Pseudo-Lehrer, die wie `---`
  ignoriert werden (Komma-Liste). `---`/Leer sind strukturell immer dabei. Wird in
  `main()` via `configure_skip_teachers()` in `SKIP_NAMES` gemischt.
- `TEXT_BADGES` (Default `b,ub,MA`): Bemerkungs-Codes, die als Badge gerendert werden.
  Bekannte (b/ub/MA) behalten ihre Farbe, neue bekommen neutrales `.text-badge`.
- `UNTIS_DEPARTMENT_ID` (Default 0): Abteilungs-Filter für `getSubstitutions`.
- `THEME` (`dark` Default / `light`): Farbschema für den gesamten Supplierplan.
  Setzt `data-theme` auf `<html>`; CSS-Variablen für Light unter
  `:root[data-theme="light"]`. In der **Mobil-Ansicht** überschreibt ein kleiner
  Schalter oben links (`#theme-toggle`) das Theme pro Gerät (localStorage
  `theme-override`); Breit/Schmal folgen nur der Config. Theme-Auflösung läuft als
  Inline-Script früh im `<head>` (reaktiv via `matchMedia`, minimiert Flackern).
- `TIMEZONE` (Default `Europe/Vienna`): IANA-Zeitzone für „heute/morgen"-Logik **und**
  die clientseitige Uhr (JS nutzt `Intl.DateTimeFormat` mit `timeZone`).

**Viewport-Stufen (Media Queries, unabhängig vom spaltenbreiten-basierten
`compact-mode` der Tabelle):**
- **Breit-Ansicht** (`> 830px`): alles sichtbar (Logo, Schul-Text, Train-Widget,
  laufende Stunde, Uhr, Legende)
- **Schmal-Ansicht** (`≤ 830px`): Schul-Text (Name + Sub), ganze Uhr (Datum + Zeit
  + Trennlinie) **und** Legende ausgeblendet; Logo + laufende Stunde + Train-Widget bleiben
- **Mobil-Ansicht** (`≤ 600px`): zusätzlich Logo weg, Train-Widget zeigt nur den
  **nächsten** Zug je Richtung (JS-`slice` via `matchMedia`, Re-Render bei Resize),
  Plan-Tag-Kurzform, scrollbar

**Keine externe Dependency** — `fetch_trains.py` nutzt nur stdlib (`urllib.request`,
`json`, `datetime`). pyhafas hatte kein OEBBProfile, daher direkter Aufruf gegen
`https://fahrplan.oebb.at/bin/mgate.exe` (das was die ÖBB-App selbst verwendet).

### Technischer Stack
- **Frontend:** statisches HTML5 + CSS3, minimal JS (Uhr + Refresh-Loop)
- **Backend:** Python 3.9+ (stdlib only), `scripts/fetch_untis.py`
- **Datenquelle:** WebUntis JSON-RPC API
- **Webserver:** `python3 -m http.server 8080` als systemd-Dienst auf Proxmox LXC
- **Hosting:** LXC `192.168.10.134`, erreichbar via Cloudflare Tunnel
- **Deployment:** `rsync` von WSL auf den LXC, danach Cron übernimmt

### Lokaler Betrieb (Windows-Tray-App, Alternative zum LXC/Cron)
`tray/` ist eine Windows-Tray-App (PyInstaller-`.exe`), die `fetch_untis.py`/
`fetch_trains.py` `main()` auf Timern aufruft und einen gehärteten lokalen Webserver
betreibt (`web/` als einziges ausgeliefertes Verzeichnis, im LAN erreichbar).
Ausgaben werden über `SUPPLIERPLAN_CONFIG`/`SUPPLIERPLAN_WEBROOT`/`SUPPLIERPLAN_DATA`
in ein beschreibbares Datenverzeichnis gelenkt (neben der `.exe` oder
`%LOCALAPPDATA%\Supplierplan`, via `tray/paths.resolve_data_dir`). Konfiguration über
ein tkinter-Fenster → `config.env`. Cloudflare optional. Grün/rot-Tray-Icon,
Autostart via HKCU-Run. Testbare Logik in `tray/{paths,config_io,autostart,server}.py`;
GUI/Tray manuell geprüft. Spec/Plan: `docs/superpowers/{specs,plans}/2026-06-08-tray-app*`.

### Dateistruktur
```
supplierplan/
├── index.html                    # Wird vom Script erzeugt (gitignored)
├── manifest.json                 # PWA-Manifest, vom Script aus config.env erzeugt (gitignored)
├── config.env                    # WebUntis-Login + Schwellen (gitignored)
├── config.env.example            # Vorlage ohne Geheimnisse
├── css/style.css                 # Komplettes Styling
├── fonts/                        # Roboto + Roboto Condensed (lokal, kein CDN)
├── logo.png                      # Schullogo (Dateiname via LOGO_FILE)
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
- **`Z Entfall`** (longName "Bester Lehrer", id 127) → via `SKIP_TEACHERS` (config.env,
  Default „Z Entfall") in `SKIP_NAMES`, wird wie `---` behandelt. Andere Schulen tragen
  hier ihre eigenen Pseudo-Lehrer ein — kein Code-Edit nötig.
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
Für **jeden** via `---`/`Z Entfall`-Marker abwesenden Lehrer (`absent_via_dash`),
der nicht ohnehin schon real vertreten wird (`covered_orgs`), wird **eine virtuelle
Zeile** erzeugt:
- `kuerzel` = abwesender Lehrer
- `art` = `cancel`
- `kuerzel_absent` = True (für Render-Logik: nur durchgestrichener Name, kein Pfeil)

→ FDKM Std 0 für NeS, Pausenaufsicht-Entfälle (GrM, WöR Std 8/9), etc.

⚠️ Greift auch in **gemischten Einträgen**, in denen ein echter Vertreter für
einen *anderen* Lehrer steht (z.B. Pausenaufsicht `te=[LaI, SeM<-FaM, Z Entfall<-BrH]`:
SeM vertritt FaM, BrH entfällt). Früher unterdrückte ein `not real_teacher_names`-Guard
diese cancel-Zeilen → Aufsichten abwesender Lehrer gingen bei Projekttagen verloren.
`covered_orgs` (alle real vertretenen `orgname`) verhindert dabei doppelte/falsche
Entfälle für tatsächlich gedeckte Lehrer.

**Aufsicht-`type`:** Eine Pausenaufsicht (`lstype="bs"`) behält `cancel`/`free` als
Art (→ Sektion „Entfallende Stunden", Lehrer gilt als abwesend); nur eine real
stattfindende Aufsichts-Vertretung wird zu `pause`.

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

### Multi-Column-Layout (Browser-seitig)

Die Supplierliste wird server-seitig als **flache Tabelle** ausgegeben: ein
`<tbody data-block="teacher">` pro Lehrer und **je Entfall-Zeile ein eigenes**
`<tbody data-block="cancel">` (ohne Überschrift). Eine JavaScript-Layout-Engine
im Browser misst nach DOMContentLoaded den verfügbaren Platz und verteilt die
Blöcke per first-fit-min auf 1–4 Spalten. Setzt am `.layout-wrapper`-Container
die Klasse `.cols-N` (1, 2, 3 oder 4).

Ab `.cols-3` schaltet CSS die Art-Badges (Vertr./Entfall/…) auf runde
Einbuchstaben-Form (V/E/R/F/P) um.

**Cancel-Sektion („Entfallende Stunden"):** Die einzelnen `cancel`-Zeilen fließen
**nach** allen Lehrer-Blöcken in den Greedy-Fill (`distributeGreedy`) und brechen
damit an den **echten Spaltengrenzen** um (kein starres Chunking mehr). Die
Überschrift erzeugt die Engine selbst (`makeCancelHeader`) — **pro Spalte einmal**,
direkt vor der ersten Entfall-Zeile dieser Spalte:
- erste betroffene Spalte → „Entfallende Stunden", weitere → „… (Forts.)" (`.cont`, dezenter)
- zusätzlicher Freiraum + Trennlinie oben (`.spaced`) nur, wenn die Überschrift
  **unter** einem anderen Block in derselben Spalte sitzt — nicht, wenn sie ganz
  oben in einer Spalte steht.
Pro Spalte mit Entfällen reserviert der Greedy-Fill `CANCEL_HEADER_H` px für die
später eingefügte Überschrift. So verteilen sich auch sehr viele Entfälle (z.B.
Projekttage mit ganzen abwesenden Klassen) sauber über die Spalten, statt eine
Spalte zu überlaufen.

Re-Layout bei Browser-Resize (250 ms debounced) und bei jedem Page-Reload
(60 s Auto-Refresh greift wie bisher).

**Verteilung:** Block-Reihenfolge + Greedy-Fit. Lehrer in alphabetischer Reihenfolge,
aktuelle Spalte füllen bis Höhe-Limit, dann nächste Spalte. Lesefluss oben-links →
unten-links → oben-rechts → unten-rechts.

**Compact-Mode** (Badges rund, „Aufsicht" → „Aufs.", Raum-Spalte breiter) wird
breite-basiert getriggert: wenn die tatsächliche Spaltenbreite kleiner ist als
`COMPACT_COL_WIDTH_PX` (Default 320, konfigurierbar in `config.env`). Greift damit
sowohl bei 3–4 Spalten am Desktop als auch in der Mobil-Ansicht.

**Mobil-Ansicht** (`@media (max-width: 600px)`): Logo, Schul-Text, Uhr, Datum,
Legende werden ausgeblendet. Train-Widget rückt an den linken Rand und zeigt nur
den nächsten Zug je Richtung, Plan-Tag zeigt Wochentag-Kurzform („Mo" statt „Montag").
Siehe auch die Viewport-Stufen Breit/Schmal/Mobil weiter unten.

### Tabellenspalten (datengetrieben)
- Die Spalten sind in **einer** Liste `COLUMNS` definiert (Tupel
  `(key, header, css_class, cell_fn)`). `COLGROUP`, `THEAD` und jede Datenzeile
  (`render_row`) werden daraus generiert → **Reihenfolge ändern = Liste umsortieren**,
  eine Stelle. `colspan` der Section-Header nutzt `NCOLS = len(COLUMNS)`.
- Spaltenbreiten bleiben im CSS (`col.c-*` + `.compact-mode`-Overrides, klassenbasiert)
  und greifen damit unabhängig von der Reihenfolge.
- Aktuelle Reihenfolge: `(Stripe) · Std · Fach · Klasse · Lehrer · Art · Raum · Text`.
- ⚠️ XSS: jede Zell-Funktion escaped ihre API-Werte selbst (`esc()`).

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

**Stundenangabe komplett vs. teil-abwesend** (`period_range` + `determine_full_absent`):
- **Komplett abwesend → nur Kürzel** (keine Stundenangabe). Schul-Konvention.
- **Teil-abwesend → Range `min–max`** der Fehl-Stunden (z.B. `WöR (5–9)`),
  einzelne Stunde → die Zahl (z.B. `SaI (6)`).

Ob „komplett" oder „teil" kommt **datengetrieben aus `weekly/data`**, nicht aus einer
Heuristik: `determine_full_absent()` ruft pro abwesendem Lehrer
`get_teacher_present_periods(teacher_id, date)` auf (REST
`weekly/data?elementType=2&elementId=<id>`). Hat der Lehrer an dem Tag **keine**
Stunde mit `cellState ∈ {STANDARD, BREAKSUPERVISION}` (= echter Unterricht /
Pausenaufsicht), gilt er als komplett abwesend → nur Kürzel. Hat er welche
(z.B. eine nicht entfallene Stunde, oder eine Aufsicht) → teil-abwesend → Range.

⚠️ **Warum nicht aus dem Supplierplan ableitbar:** dort sind nur Stunden **mit
Änderung** sichtbar, nicht der ganze Tag — ob `1–5` der volle Tag oder nur der
Vormittag ist, steht da nicht drin. Daher der separate `weekly/data`-Call.

⚠️ **`cellState`, nicht `state`:** Das `state`-Feld am Lehrer-Element ist unbrauchbar
(steht auch bei entfallenen Stunden auf `REGULAR`). Maßgeblich ist `cellState` der
Periode: `STANDARD` / `CANCEL` / `SUBSTITUTION` / `BREAKSUPERVISION`.

⚠️ **`elementId=0` ist ein Phantom** (liefert beliebige/falsche Tage) — immer die
**echte Lehrer-ID** verwenden. `get_weekly_class_absences` nutzt noch `elementId=0`
und liefert daher vermutlich Müll — beim nächsten Anfassen auf echte Klassen-IDs
umstellen (TODO).

**Kosten:** ein REST-Call pro abwesendem Lehrer je angezeigtem Tag. Bei API-Fehler
oder unbekannter ID fällt der Lehrer auf die Range-Anzeige zurück (sicher).

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

`fetch_untis.py` nutzt die Zeitzone aus `config.env` (`TIMEZONE`, Default `Europe/Vienna`)
via `set_timezone()` → `ZoneInfo`.
- **Linux/Server (LXC):** funktioniert wenn `tzdata`-Paket installiert ist (Standard auf Debian)
- **Windows:** braucht `pip install tzdata`. Falls nicht installiert → Fallback auf System-TZ
- Alle Aufrufe von `datetime.now()` / `date.today()` gehen über `now_local()` / `today_local()`

⚠️ **Wenn der Server in UTC läuft und `tzdata` fehlt**, ist die „Heute"-Berechnung ab
22:00 falsch. Im Zweifel `apt install tzdata` auf dem LXC ausführen.

---

## Cron-Setup auf dem LXC

```cron
SUPPLIERPLAN_CONFIG=/etc/supplierplan/config.env
*/5  * * * *  cd /var/www/supplierplan && python3 scripts/fetch_untis.py  >> /var/log/supplierplan-untis.log 2>&1
*    * * * *  cd /var/www/supplierplan && python3 scripts/fetch_trains.py >> /var/log/supplierplan-trains.log 2>&1
```

Voraussetzungen: nur Python 3.9+ (stdlib reicht, keine externen Packages mehr).

⚠️ **`config.env` gehört NICHT in den Webroot** (`python3 -m http.server` liefert sonst
Passwort + Cloudflare-Token aus). Sie liegt unter `/etc/supplierplan/config.env`
(außerhalb von `/var/www/supplierplan`), und die Scripts finden sie über
`SUPPLIERPLAN_CONFIG` (siehe `resolve_config_path()`). Ohne die Variable fällt der
Pfad auf den Projekt-Root zurück — das ist nur für lokale Entwicklung gedacht.

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
      --exclude='config.env' \
      /mnt/c/Users/Admin/Onedrive/Programming/Claude/Supplier/ \
      root@192.168.10.134:/var/www/supplierplan/
```
⚠️ `--exclude='config.env'` ist **Sicherheits-relevant**: die Datei darf nicht in den
ausgelieferten Webroot. Auf dem Server liegt sie unter `/etc/supplierplan/config.env`
(einmalig dorthin kopieren, `chmod 600`). Wird über `SUPPLIERPLAN_CONFIG` gefunden.

SSH-Auth läuft nur im echten Terminal (kein ssh-askpass in WSL).
Im Claude Code Prompt mit `!`-Präfix ausführen, dann landet Output direkt im Chat.

### Python-Setup
- WSL hat kein Python: nutzen wir `/mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe`
- Für UTF-8-Output unter Windows: `PYTHONIOENCODING=utf-8` voranstellen, sonst CP1252-Fehler

---

## Verfügbar aber noch nicht genutzt — Ideen für später
- **`weekly/data` REST für Klassen** (`elementType=1`): könnte die „Abwesende
  Klassen"-Liste sauber liefern (aktuell `get_weekly_class_absences` mit kaputtem
  `elementId=0`). Pro Klasse ein Call. (Für Lehrer ist `weekly/data` bereits
  produktiv im Einsatz, siehe „Stundenangabe komplett vs. teil-abwesend".)
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
3. ~~**`weekly/data`-Migration** für „Abwesende Lehrer"~~ ✅ erledigt: komplett vs.
   teil-abwesend kommt jetzt aus `weekly/data` (`determine_full_absent`,
   `get_teacher_present_periods`). Offen bleibt nur die Klassen-Liste
   (`get_weekly_class_absences` nutzt noch `elementId=0` → kaputt).
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
