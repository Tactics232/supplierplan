# Supplierplan-Anzeige

Selbstgehostete Live-Webanzeige für den Supplierplan einer Wiener Schule.
Ersetzt die unübersichtliche WebUntis-Monitor-Ansicht durch ein eigenes, dunkles,
auf große Bildschirme optimiertes Layout. Läuft auf einem Proxmox-LXC, wird im
Schulgebäude auf einem Monitor im Fullscreen Hochkant angezeigt.

---

## Features

- **Echtzeit-Supplierplan** mit WebUntis-JSON-RPC-API
  - Heutige Vertretungen + nächster Schultag (Wochenenden & Ferien werden übersprungen)
  - Automatisches Filtern echter Vertretungen (Co-Lehrer & doppelte Einträge raus)
  - Eigene Cancel-Sektion am Tagesende
- **Abwesende Lehrer & Klassen** prominent im Header
  - Lehrer aus Substitutionen abgeleitet
  - Klassen aus echter WebUntis-Abwesenheitsliste (`weekly/data`-API)
  - „ab X", „Ganzer Tag" oder Range pro Person
- **Echtzeit-Zuganzeige** im Header (optional)
  - ÖBB HAFAS `mgate.exe`-Direct-Call (stdlib only, keine externen Deps)
  - Anzahl der Züge über config.env pro Richtung einstellbar(Wien Innenstadt / weg), 60s Auto-Refresh
  - Verspätungs-Anzeige, Linienfilter (z.B. nur S-Bahnen)
- **PWA-fähig** für Smart-TV-Vollbild-Installation
- **Selbst-aktualisierend** im Browser
  - 60s Soft-Reload, alle 5 min Hard-Reload mit Cache-Bust
  - Cloudflare Cache-Purge nach jedem Cron-Run (optional)
- **Robuste UI-Logik**
  - Heute leer → automatisch auf Morgen wechseln
  - Solo-Morgen → Datum wandert ins Plan-Tag oben
  - Dynamisches Layout (Morgen rückt hoch wenn Heute schrumpft)

---

## Tech-Stack

| Layer | Wahl | Begründung |
|---|---|---|
| Frontend | Statisches HTML5 + CSS3 + Vanilla JS | Kein Build-Step, lädt sofort, läuft überall |
| Backend | Python 3.9+ (**stdlib only**) | Keine externen Dependencies, einfaches Deployment |
| Datenquellen | WebUntis JSON-RPC + ÖBB HAFAS mgate.exe | Beide direkt via `urllib`, kein Wrapper-Lib |
| Webserver | `python3 -m http.server` als systemd-Service | Minimaler Footprint, reicht für statische Files |
| Hosting | Proxmox-LXC + Cloudflare Tunnel | Interne IP, von außen via HTTPS erreichbar |
| Deployment | `rsync` von Entwickler-Workstation | Schnell, idempotent, kein CI-Setup nötig |

---

## Projektstruktur

```
supplierplan/
├── index.html                     # Generiert vom Cron (gitignored)
├── manifest.json                  # PWA-Manifest
├── sw.js                          # Service-Worker für Offline + Cache
├── config.env                     # Geheimnisse (gitignored)
├── config.env.example             # Vorlage ohne Werte
├── css/
│   └── style.css                  # Komplettes Styling, eigene Custom Properties
├── fonts/                         # Roboto + Roboto Condensed (lokal, kein CDN)
├── logo.png                       # Schullogo / PWA-Icon
├── scripts/
│   ├── fetch_untis.py             # Hauptscript: holt Supplierplan, baut index.html
│   ├── fetch_trains.py            # Cron-Skript: schreibt data/trains.json
│   ├── discover_api.py            # Einmaliges API-Discovery-Tool
│   └── diagnose_api.py            # Diagnose-Helper für die WebUntis-API
├── tests/
│   └── test_fetch_trains.py       # 22 unittest-Tests für Pure-Logic
├── data/                          # Laufzeit-Output (gitignored)
│   ├── trains.json                # Aktueller Zugplan (atomar geschrieben)
│   ├── last_raw.json              # Roh-API-Daten zur Diagnose
│   └── last_overview.html         # Lesbare API-Übersicht für Browser
└── docs/superpowers/
    ├── specs/2026-05-28-zuganzeige-design.md
    └── plans/2026-05-28-train-widget.md
```

---

## Setup

### 1. Repository klonen

```bash
git clone https://github.com/Tactics232/supplierplan.git
cd supplierplan
```

### 2. Konfiguration

```bash
cp config.env.example config.env
```

Dann `config.env` mit deinen Werten füllen — siehe **Konfiguration** unten.

### 3. Lokal testen

```bash
python3 scripts/fetch_untis.py     # erzeugt index.html
python3 -m http.server 8080        # statischer Webserver
```

Browser: `http://localhost:8080/`

### 4. Deployment auf LXC (Production)

```bash
rsync -avz --exclude='.claude' --exclude='.git' --exclude='data/' \
      --exclude='config.env' \
      ./ root@<lxc-ip>:/var/www/supplierplan/
```

> ⚠️ **`config.env` wird bewusst NICHT mitkopiert.** Der statische Webserver würde
> jede Datei im Verzeichnis ausliefern — also auch Passwort und Token. Lege die
> Datei stattdessen außerhalb des Webroots ab und schütze sie:
> ```bash
> mkdir -p /etc/supplierplan
> # config.env einmalig nach /etc/supplierplan/config.env kopieren, dann:
> chmod 600 /etc/supplierplan/config.env
> ```
> Die Scripts finden sie über die Umgebungsvariable `SUPPLIERPLAN_CONFIG`
> (siehe Cron unten). Ohne die Variable greift der Fallback auf den Projekt-Root —
> nur für lokale Entwicklung gedacht.

Auf dem LXC einmal:

```bash
# Webserver als systemd-Service
sudo tee /etc/systemd/system/supplierplan.service <<'EOF'
[Unit]
Description=Supplierplan-Webserver
After=network.target

[Service]
WorkingDirectory=/var/www/supplierplan
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now supplierplan

# Cron einrichten
crontab -e
```

Crontab:
```cron
SUPPLIERPLAN_CONFIG=/etc/supplierplan/config.env
*/5 * * * *  cd /var/www/supplierplan && /usr/bin/python3 scripts/fetch_untis.py  >> /var/log/supplierplan-untis.log 2>&1
*   * * * *  cd /var/www/supplierplan && /usr/bin/python3 scripts/fetch_trains.py >> /var/log/supplierplan-trains.log 2>&1
```

Die erste Zeile setzt `SUPPLIERPLAN_CONFIG` für beide Jobs, damit sie die
`config.env` außerhalb des Webroots lesen.

---

## Konfiguration (`config.env`)

| Variable | Pflicht? | Beispiel | Beschreibung |
|---|---|---|---|
| `UNTIS_URL` | ✅ | `https://s123456.webuntis.com` | WebUntis-Instanz der Schule |
| `UNTIS_SCHOOL_ID` | ✅ | `s123456` | Schul-Subdomain-ID |
| `UNTIS_USER` | ✅ | `Monitor` | Service-Account-User (mit Lese-Rechten) |
| `UNTIS_PASSWORD` | ✅ | `…` | Passwort zum User |
| `SHOW_TOMORROW_AFTER` | – | `12:30` | Ab welcher Uhrzeit der nächste Schultag angezeigt wird |
| `UNTIS_DEPARTMENT_ID` | – | `0` | Abteilungs-Filter (0 = alle) |
| **Schul-Bezeichnung & Aussehen** | | | |
| `SCHOOL_NAME` | – | `MS Roda-Roda-Gasse` | Überschrift, Footer, Browser-Titel |
| `SCHOOL_TYPE` | – | `Mittelschule` | Sub-Zeile (1. Teil) |
| `SCHOOL_LOCATION` | – | `1210 Wien` | Sub-Zeile (2. Teil) + Footer |
| `PLAN_TITLE` | – | `Supplierplan` | Plan-Titel (z.B. „Vertretungsplan") |
| `SHOW_LOGO` | – | `false` | Logo im Header rendern |
| `LOGO_FILE` | – | `logo.png` | Logo-Dateiname (PNG/SVG/JPG/WebP) |
| `THEME` | – | `dark` | `dark` oder `light` (Mobil per Schalter überschreibbar) |
| `SHOW_CLOCK` | – | `true` | Datum + Uhr im Header anzeigen |
| `TIMEZONE` | – | `Europe/Vienna` | IANA-Zeitzone (heute/morgen + Uhr) |
| `COMPACT_COL_WIDTH_PX` | – | `320` | Schwelle für Compact-Mode (Badges rund, „Aufs.") |
| `OVERFLOW_SCALE` | – | `true` | Bei Überlauf alles verkleinern (Stufe 1) |
| `OVERFLOW_SCALE_MIN` | – | `0.65` | kleinster Skalierungsfaktor (0.3–1.0) |
| `OVERFLOW_REDUCE` | – | `true` | Bei Überlauf Text-Spalte aus / Entfall kompakt (Stufe 2) |
| `OVERFLOW_PAGINATE` | – | `true` | Bei Überlauf seitenweise blättern (Stufe 3) |
| `OVERFLOW_PAGE_SECONDS` | – | `12` | Sekunden pro Seite beim Blättern |
| **WebUntis-Feinjustierung** | | | |
| `SKIP_TEACHERS` | – | `Z Entfall` | Schul-eigene Pseudo-Lehrer (wie `---` ignorieren) |
| `TEXT_BADGES` | – | `b,ub,MA` | Bemerkungs-Codes, die als Badge erscheinen |
| **Cloudflare Cache-Purge** (optional) | | | |
| `CLOUDFLARE_ZONE_ID` | – | – | Aus dem Cloudflare-Dashboard |
| `CLOUDFLARE_API_TOKEN` | – | – | Permission: *Zone:Cache Purge* |
| `CLOUDFLARE_HOST` | – | `supp.example.tld` | Nur diese Subdomain purgen (sicher) |
| **Zug-Widget** (optional) | | | |
| `TRAIN_STATION` | – | `Wien Hütteldorf` | Stationsname (HAFAS-Suche) |
| `TRAIN_DIR_TOWARDS` | – | `Wien Hbf,Wien Westbf,…` | Substrings für „Richtung Wien" |
| `TRAIN_PER_DIRECTION` | – | `1` | Anzahl Züge je Richtung |
| `TRAIN_DISABLED` | – | `false` | Widget komplett ausschalten |
| `TRAIN_PRODUCTS` | – | `S` | Komma-getrennte Linien-Präfixe (leer = alle) |

---

## Für andere Schulen einrichten

Das Projekt ist mandantenfähig: **eine neue Schule braucht nur eine eigene
`config.env` und ein Logo — kein Code-Edit.** Alle schul-spezifischen Stellen
(Pseudo-Lehrer, Abteilung, Logo, Bemerkungs-Codes, Plan-Titel, Branding, Theme,
Zeitzone) sind Config-Keys (siehe Tabelle oben).

1. **Klonen** und `config.env` aus `config.env.example` anlegen.
2. **WebUntis-Zugang** eintragen: `UNTIS_URL`, `UNTIS_SCHOOL_ID`, `UNTIS_USER`,
   `UNTIS_PASSWORD` (am besten ein dedizierter Lese-Service-Account).
3. **Branding**: `SCHOOL_NAME`, `SCHOOL_TYPE`, `SCHOOL_LOCATION`, `PLAN_TITLE`
   setzen; eigenes Logo als Datei ablegen und `LOGO_FILE` + `SHOW_LOGO=true` setzen.
4. **Region**: `TIMEZONE` anpassen. Train-Widget ist ÖBB-spezifisch → für Schulen
   außerhalb Österreichs `TRAIN_DISABLED=true`.
5. **WebUntis-Eigenheiten**: ggf. eigene Pseudo-Lehrer in `SKIP_TEACHERS` und
   Bemerkungs-Codes in `TEXT_BADGES` eintragen; bei Abteilungsbetrieb
   `UNTIS_DEPARTMENT_ID`.
6. **Cron** einrichten (siehe Deployment) — `index.html` **und** `manifest.json`
   werden bei jedem Run aus der Config generiert.

> Hinweis: `index.html` und `manifest.json` sind generierte Artefakte (gitignored).
> Spaltenreihenfolge der Tabelle ist in `scripts/fetch_untis.py` über die zentrale
> `COLUMNS`-Liste definiert (eine Stelle umsortieren).

---

## Architektur

```
┌──────────────────────────────────────────────────────────────────┐
│ Proxmox-LXC                                                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Cron */5 min  → scripts/fetch_untis.py                    │    │
│  │   ├─→ WebUntis JSON-RPC (Login als Service-Account)       │    │
│  │   ├─→ weekly/data (Klassen-Abwesenheiten)                 │    │
│  │   ├─→ index.html  (Haupt-Anzeige)                         │    │
│  │   └─→ data/last_overview.html + last_raw.json             │    │
│  │                                                           │    │
│  │ Cron */1 min  → scripts/fetch_trains.py                   │    │
│  │   ├─→ urllib → ÖBB HAFAS mgate.exe (Direct, stdlib only)  │    │
│  │   └─→ data/trains.json  (atomar geschrieben)              │    │
│  │                                                           │    │
│  │ systemd       → python3 -m http.server 8080               │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
              │ via Cloudflare Tunnel
              ▼
┌────────────────────────┐    ┌───────────────────────────┐
│ Browser am Schulmonitor │   │ Smart-TV (PWA installiert) │
│  Auto-Refresh 60s soft  │   │  Display: fullscreen       │
│  Alle 5 min: Cache-Bust │   │  via manifest.json         │
└────────────────────────┘    └───────────────────────────┘
```

### Datenfluss-Highlights

- **Atomares JSON-Schreiben** (`os.replace`) — der Browser sieht nie eine halbe Datei
- **`weekly/data?elementId=0`** liefert in einem Call alle ABSENT-Markierungen einer Woche
- **XSS-sicher**: Werte aus externen APIs landen via `textContent` im DOM, niemals via `innerHTML`
- **Service-Worker** cached statische Assets (CSS, Fonts, Logo), für `index.html` und `data/*.json` gilt Network-First

---

## Tests

```bash
python3 -m unittest discover tests -v
```

22 Tests für die Pure-Logic-Funktionen in `fetch_trains.py`:
- `classify_direction` (Wien-Whitelist-Match)
- `extract_departure` (HAFAS-Leg → JSON-Dict)
- `split_by_direction` (towards/away, Limit, Cancelled-Skip)
- `atomic_write_json` (Race-Safety, Overwrite)
- `load_config` (.env-Parser)
- `filter_by_product_prefix` (Linien-Filter)

---

## PWA-Installation auf dem Smart-TV

1. Im TV-Browser die URL aufrufen
2. Browser-Menü → *Zum Startbildschirm hinzufügen* / *Als App installieren*
3. App-Icon erscheint → starten → läuft Fullscreen, ohne Adressleiste

Voraussetzung: Aufruf via HTTPS (Cloudflare Tunnel reicht).

---

## Sicherheitsregeln (für Beiträge)

- **`config.env` ist gitignored** und enthält Geheimnisse — niemals committen
- **Alle externen API-Werte werden mit `esc()` (= `html.escape`) escaped** bevor sie in HTML fließen
- HTTP-Requests haben Timeout (`timeout=15`)
- Login-Cookie wird nach jedem Lauf invalidiert

---

## Lizenz

Privates Schulprojekt, kein offizielles Release. Code-Reuse für ähnliche
Schulanzeigen ist willkommen — aber: keine Garantien, eigenes Risiko.

---

## Windows-App (Schul-PC)

Die Tray-App (`tray/`) betreibt Holen + lokalen Webserver direkt auf dem Schul-PC;
die Seite ist im LAN unter `http://<PC-IP>:<SERVER_PORT>` erreichbar. Cloudflare ist
optional (Felder leer lassen = nicht extern erreichbar).

### Build (auf dem Entwickler-PC, Python nötig)
```
pip install pyinstaller pystray pillow
python tray/build.py
```
Ergebnis: `dist/Supplierplan/` (portabel) und – falls Inno Setup installiert –
`dist/Supplierplan-Setup.exe`.

### Installation (Schul-PC, kein Python nötig)
- Portabel: Ordner `dist/Supplierplan/` kopieren, `Supplierplan.exe` starten.
- Oder `Supplierplan-Setup.exe` ausführen.
- Tray-Icon → „Einstellungen…" ausfüllen → „Start" (Icon wird grün).
- „Mit Windows starten" anhaken.

Daten/Config liegen im beschreibbaren Datenverzeichnis (portabel: neben der `.exe`;
installiert: `%LOCALAPPDATA%\Supplierplan`). `config.env` liegt außerhalb des
ausgelieferten `web/` und ist nicht über die URL abrufbar.

---

## Hintergrund

Entstanden als Ersatz für die schwer lesbare WebUntis-Monitor-Anzeige der. Die offizielle
Dieses Projekt sortiert nach Lehrer, gruppiert Cancels
am Tagesende, zeigt Abwesenheits-Stunden präzise (z.B. „ab 6", „Ganzer Tag")
und ergänzt eine Live-Zuganzeige für die nahegelegene Bahnstation.
