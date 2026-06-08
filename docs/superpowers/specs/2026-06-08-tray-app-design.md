# Design: Windows-Tray-App für den Schul-PC

**Datum:** 2026-06-08
**Status:** abgesegnet (Brainstorming), bereit für Implementierungsplan

## Problem / Ziel

Der Supplierplan soll **lokal auf dem Schul-PC** laufen, nicht mehr zwingend über
den Proxmox-LXC + Cloudflare. Eine Windows-Hintergrund-Anwendung (Tray/Taskleiste)
holt die Daten selbst, betreibt den Webserver im lokalen Netzwerk und macht die
Konfiguration über eine Fensteroberfläche bedienbar. Cloudflare (externe
Erreichbarkeit) wird optional und per Schalter zuschaltbar.

**Kernanforderungen (vom User):**
- Läuft im Hintergrund / in der Taskleiste (System-Tray).
- Option „mit Windows starten" (an/aus).
- Zwei Tray-Symbole: **roter Kreis = läuft nicht**, **grüner Kreis = läuft**.
- Konfigurations-Fenster, das in `config.env` schreibt.
- Auslieferung als **eigenständige `.exe`** (auf dem Schul-PC ist kein Python nötig).

## Architektur-Entscheidungen (aus dem Brainstorming)

1. **PC ist das Backend:** die App holt die Untis-/Zug-Daten lokal (ruft die
   bestehende Logik) und betreibt den HTTP-Server, der die Seite **im LAN**
   bereitstellt. Standardmäßig **nicht** von außen erreichbar.
2. **Nur Backend:** die App steuert KEINE Anzeige (kein Vollbild-Browser); das
   Anzeigen übernimmt ein Browser/Gerät separat über die LAN-URL.
3. **Cloudflare optional:** per Häkchen + Feldern zuschaltbar (sonst kein Purge,
   keine externe Auslieferung).
4. **Eigenständige `.exe`** via PyInstaller; Python nur auf dem Dev-PC zum Bauen.
5. **Config-GUI: alle Einstellungen**, in Reitern gruppiert.
6. **Reuse statt Neubau:** die App importiert `fetch_untis.py`/`fetch_trains.py`
   und ruft deren `main()` auf Timern auf. Die Fetch-/Render-Logik bleibt unverändert.

## Komponenten & Ordnerlayout

**Programm-Teil** (read-only, neben der `.exe` bzw. unter `Programme` bei Installation):
```
<Programmordner>/
├── Supplierplan.exe        # Tray-App (Python + Abhängigkeiten gebündelt)
└── assets/                 # mitgelieferte Vorlagen: css/ fonts/ logo.png sw.js manifest-Vorlage
```

**Beschreibbares Datenverzeichnis** (zur Laufzeit, siehe unten):
```
<Datenverzeichnis>/
├── config.env              # von der GUI geschrieben — NICHT im Web-Root
├── web/                    # einziges ausgeliefertes Verzeichnis
│   ├── index.html          # von fetch_untis.py erzeugt
│   ├── css/  fonts/  logo.png  manifest.json  sw.js   (beim Erststart aus assets/ kopiert)
└── data/                   # last_raw.json, trains.json, app.log — NICHT ausgeliefert
```

**Datenverzeichnis-Auflösung** (`resolve_data_dir()`): bevorzugt **neben der `.exe`**
(portabler Ordner, wenn dort schreibbar); ist das nicht beschreibbar (Installation
unter `C:\Program Files\…`), dann **`%LOCALAPPDATA%\Supplierplan\`**. Beim Erststart
werden `web/`, `data/` angelegt, die statischen Assets aus `assets/` nach `web/`
kopiert und `config.env` aus der Vorlage erzeugt. `SUPPLIERPLAN_CONFIG` und
`SUPPLIERPLAN_WEBROOT` zeigen auf dieses Datenverzeichnis.

**Sicherheit:** Der HTTP-Server liefert ausschließlich `web/` aus. `config.env`
(Passwort, Cloudflare-Token) liegt außerhalb des Web-Roots und ist damit nicht
abrufbar (konsequent zum Security-Review). Zusätzlich ein gehärteter Request-Handler
(kein Directory-Listing; `.env`/Dotfiles/Pfad-Traversal blockiert).

## Technischer Stack

- **Tray-Icon:** `pystray` + `Pillow` (rotes/grünes Kreis-Icon zur Laufzeit gezeichnet).
- **Config-GUI:** `tkinter` (stdlib).
- **Dienst:** Hintergrund-Threads (Timer für Untis/Zug) + `http.server`-Thread.
- **Bundling:** PyInstaller (one-folder oder one-file).
- **Autostart:** Registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
  (kein Admin nötig), Eintrag wird per Checkbox gesetzt/entfernt.

Neue Laufzeit-Abhängigkeiten (`pystray`, `Pillow`) betreffen **nur die Tray-App**;
die Kern-Scripts bleiben stdlib-only.

## Tray-Verhalten

- **Icon-Zustände:** grün = Dienst läuft, rot = gestoppt (oder Fehler/keine Config).
  Tooltip: Kurzstatus (z. B. „Läuft · letzte Aktualisierung 14:05", „Gestoppt",
  „Fehler: WebUntis-Login").
- **Rechtsklick-Menü:**
  - **Start / Stopp** — schaltet den Hintergrund-Dienst, Icon wechselt.
  - **Einstellungen…** — öffnet das Config-Fenster.
  - **Im Browser öffnen** — öffnet `http://localhost:<port>`.
  - **Mit Windows starten** — Häkchen, schreibt/entfernt den Registry-Run-Eintrag.
  - **Beenden** — stoppt Dienst + App.
- **Doppelklick** aufs Icon öffnet die Einstellungen.
- **Einzel-Instanz:** ein zweiter Start fokussiert die laufende Instanz (kein
  doppelter Server). Umsetzung über ein Lock (z. B. benannte Mutex/Lock-Datei/Port).

## Config-Fenster (tkinter, Reiter)

Reiter: **WebUntis · Schule · Züge · Anzeige · Überlauf · Cloudflare · Server**.
Felder bilden die `config.env`-Schlüssel ab. „Speichern" schreibt `config.env`
(vorhandene Kommentare/Struktur bleiben erhalten; nur Werte werden aktualisiert).

- **WebUntis:** `UNTIS_URL`, `UNTIS_SCHOOL_ID`, `UNTIS_USER`, `UNTIS_PASSWORD`
  (maskiert), `UNTIS_DEPARTMENT_ID`, `SKIP_TEACHERS`. **„Verbindung testen"**-Button:
  probeweiser Login → grün/rot-Rückmeldung.
- **Schule:** `SCHOOL_NAME`, `SCHOOL_TYPE`, `SCHOOL_LOCATION`, `PLAN_TITLE`,
  `LOGO_FILE`, `SHOW_TOMORROW_AFTER`, `TIMEZONE`.
- **Züge:** `TRAIN_STATION`, `TRAIN_DIR_TOWARDS`, `TRAIN_PER_DIRECTION`,
  `TRAIN_PRODUCTS`, `TRAIN_DISABLED`.
- **Anzeige:** `THEME`, `SHOW_CLOCK`, `SHOW_LOGO`, `COMPACT_COL_WIDTH_PX`, `TEXT_BADGES`.
- **Überlauf:** `OVERFLOW_SCALE`, `OVERFLOW_SCALE_MIN`, `OVERFLOW_REDUCE`,
  `OVERFLOW_PAGINATE`, `OVERFLOW_PAGE_SECONDS`.
- **Cloudflare:** Häkchen **„Extern erreichbar machen"**; wenn aus, bleiben
  `CLOUDFLARE_ZONE_ID`/`CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_HOST` leer und es wird
  nichts gepurged.
- **Server:** Port (Default 8080), Untis-Intervall (Default 300 s),
  Zug-Intervall (Default 60 s). (Neue App-Keys, siehe unten.)
- Nach „Speichern" greift die Config beim nächsten Fetch; Button „Jetzt
  aktualisieren" stößt einen sofortigen Lauf an.

## Dienst-Logik

- **Timer-Threads:** Untis-Fetch (Default 300 s) und Zug-Fetch (Default 60 s) rufen
  die bestehenden `main()`-Funktionen auf. `os.environ['SUPPLIERPLAN_CONFIG']` zeigt
  auf die lokale `config.env`. Ausgabe nach `web/` (index.html) bzw. `data/`.
  - Dafür muss konfigurierbar sein, dass `fetch_untis.py`/`fetch_trains.py` ihre
    Ausgabe nach `web/` schreiben statt in den Projekt-Root. Umsetzung über eine
    Umgebungsvariable `SUPPLIERPLAN_WEBROOT` (Default = bisheriges Verhalten;
    abwärtskompatibel, analog zu `SUPPLIERPLAN_CONFIG`).
- **HTTP-Server-Thread:** liefert `web/` im LAN aus (`0.0.0.0:<port>`), gehärteter
  Handler (kein Listing, `.env`/Dotfiles/Traversal blockiert).
- **Start/Stopp:** startet/beendet Threads sauber (Server-`shutdown()`, Timer-Cancel).
- **Fehlerresilienz:** Fehlerhafte Läufe (z. B. WebUntis-Login) crashen die App nicht;
  Status → Tooltip + `data/app.log`. Icon zeigt Fehlerzustand (rot/markiert).
- **Erststart ohne gültige Config:** Icon rot + Hinweis „Bitte Einstellungen ausfüllen".

## Neue/erweiterte Config-Schlüssel

In `config.env.example` ergänzen (own-line comments):
- `SERVER_PORT` (Default 8080)
- `UNTIS_INTERVAL_SECONDS` (Default 300)
- `TRAIN_INTERVAL_SECONDS` (Default 60)

Die Scripts erhalten zudem `SUPPLIERPLAN_WEBROOT`-Support (Pfad-Resolver analog
`SUPPLIERPLAN_CONFIG`), damit `index.html`/Assets nach `web/` geschrieben/erwartet
werden. Ohne die Variable bleibt das bisherige Verhalten (Projekt-Root) — die
Cron/LXC-Variante funktioniert unverändert weiter.

## Bauen & Auslieferung

Zwei Artefakte (aus demselben PyInstaller-Build):

1. **Portabler Ordner** — PyInstaller (one-folder): `Supplierplan.exe` + `assets/`.
   Auf einen Stick/Ordner kopieren, starten, fertig (Daten landen neben der `.exe`,
   falls schreibbar).
2. **Setup-Installer** (`Supplierplan-Setup.exe`) — **Inno Setup** (`tray/installer.iss`)
   verpackt den PyInstaller-Output: installiert nach `Programme`, legt
   Startmenü-Eintrag + Deinstaller an, optional Autostart-Häkchen schon im Setup.
   Datenverzeichnis dann automatisch `%LOCALAPPDATA%\Supplierplan` (siehe Auflösung).

- **Build-Skript** (`tray/build.py`) ruft PyInstaller mit den Daten (`scripts/` als
  importierbares Paket, `css/`, `fonts/`, `logo.png`, `sw.js`, `manifest`-Vorlage,
  `config.env.example`) und erzeugt den one-folder-Output; ein zweiter Schritt ruft
  den Inno-Setup-Compiler (`ISCC.exe`) auf `tray/installer.iss` auf.
- Beim ersten Start legt die App das Datenverzeichnis an (siehe oben).
- **README-Abschnitt** „Build der Windows-App" (Dev-PC: `pip install pyinstaller
  pystray pillow`; Inno Setup installiert für den Installer-Schritt; dann
  `build.py`). Plus „Installation am Schul-PC": entweder portablen Ordner kopieren
  **oder** `Supplierplan-Setup.exe` ausführen; danach Einstellungen ausfüllen und
  „Mit Windows starten" anhaken.

## Testing

- **Unit (unittest, headless)** — reine, GUI-freie Logik:
  - `write_config_env(values, path)` — Dict → `config.env`; vorhandene Werte
    aktualisieren, Kommentare erhalten, keine Inline-Kommentar-Fallen, korrektes
    Quoting; Test inkl. Passwort/Sonderzeichen.
  - `read_config_env(path)` — Datei → Dict (Inline-Kommentar-tolerant, konsistent
    zu `parse_overflow_config`).
  - Autostart-Logik (`enable_autostart`/`disable_autostart`/`is_autostart`) gegen
    eine gemockte Registry-Schnittstelle.
  - Validierung Port/Intervalle (Default/Klemmung bei Unsinn).
  - Pfad-Resolver `SUPPLIERPLAN_WEBROOT` in `fetch_untis.py`.
  - `resolve_data_dir()` — wählt neben-der-exe (wenn schreibbar) vs.
    `%LOCALAPPDATA%\Supplierplan` (gemockt: Schreibbarkeit/Umgebung).
- **Manuell:** Tray-Icon (rot/grün), Menü, GUI-Speichern, „Verbindung testen",
  Autostart-Haken, LAN-Abruf von einem zweiten Gerät, `config.env` nicht abrufbar.
- Bestehende `tests/` bleiben grün; neue Tests unter `tests/test_tray_config.py`.

## Bewusst nicht enthalten (YAGNI)

- Keine Anzeige-/Browser-Steuerung (nur Backend).
- Keine Mehrsprachigkeit der GUI (deutsch).
- Kein Auto-Update der App.

## Betroffene/neue Dateien (grob)

- **Neu:** `tray/app.py` (Tray + Dienst-Orchestrierung), `tray/config_io.py`
  (read/write config.env — testbar), `tray/autostart.py` (Registry — testbar),
  `tray/paths.py` (`resolve_data_dir()` — testbar), `tray/gui.py` (tkinter-Fenster),
  `tray/server.py` (gehärteter HTTP-Handler), `tray/build.py` (PyInstaller),
  `tray/installer.iss` (Inno-Setup-Skript), `tests/test_tray_config.py`.
- **Geändert:** `scripts/fetch_untis.py` (+`SUPPLIERPLAN_WEBROOT`-Resolver),
  ggf. `scripts/fetch_trains.py`, `config.env.example` (+`SERVER_PORT`,
  `*_INTERVAL_SECONDS`), `README.md`/`CLAUDE.md` (Build/Install + neue Architektur).
