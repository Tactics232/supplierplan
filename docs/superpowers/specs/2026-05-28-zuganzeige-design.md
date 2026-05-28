# Design: Echtzeit-Zuganzeige im Supplierplan-Header

**Status:** Draft, awaiting user approval
**Branch:** `feature/train-widget`
**Datum:** 2026-05-28

## Ziel
Ein Widget im Header der Supplierplan-Anzeige, das die zwei nächsten relevanten Züge
einer konfigurierten Wiener Bahnhaltestelle zeigt — getrennt nach „Richtung Wien"
(grüner Indikator) und „weg von Wien" (roter Indikator). Aktualisierung alle 60 Sekunden.

## Nicht-Ziele
- Vollwertige Fahrplanauskunft (mehrere Züge, Routing, Umstiege) — nur zwei Zeilen
- Mehrere Haltestellen gleichzeitig
- Mobile-Optimierung (Anzeige läuft auf festem Monitor)

## Architektur

```
┌──────────────────────────────────────────────────────────────┐
│ Cron jede Minute → scripts/fetch_trains.py                    │
│   ├─→ pyhafas.HafasClient(ÖBBProfile()).departures(station)  │
│   ├─→ Filtere & sortiere: ein nächster pro Richtung           │
│   ├─→ Bei Erfolg: data/trains.json überschreiben              │
│   └─→ Bei Fehler: alte data/trains.json bleibt — nicht touch  │
│                                                                │
│ Cron jede 5 min → scripts/fetch_untis.py (unverändert)        │
│   └─→ generiert index.html mit eingebettetem Widget-Stub       │
│                                                                │
│ Browser am Monitor:                                            │
│   ├─→ index.html (60s reload, wie bisher)                     │
│   └─→ Inline-JS holt alle 60s data/trains.json                │
│       und befüllt das Widget im Header                         │
└──────────────────────────────────────────────────────────────┘
```

### Trennung der Concerns
- `fetch_trains.py` weiß nichts von Untis, generiert kein HTML — schreibt nur JSON
- `fetch_untis.py` weiß nichts von Zügen — rendert nur einen leeren Widget-Container
- Browser-JS lädt JSON und befüllt das Widget — unabhängig vom HTML-Reload-Zyklus

## Komponenten

### 1. `scripts/fetch_trains.py` (neu)
- **Input:** Konfigurations-Werte aus `config.env`
- **Verarbeitung:**
  1. `pyhafas.HafasClient(ÖBBProfile())`
  2. `client.locations(TRAIN_STATION)` → erste Treffer-Station
  3. `client.departures(station_id, when=now, max_journeys=20)`
  4. Pro Departure: prüfen ob Endbahnhof in `TRAIN_DIR_TOWARDS` matched (substring, case-insensitive)
  5. Aufteilen in zwei Listen `towards` / `away`, je nach `TRAIN_PER_DIRECTION` viele behalten
  6. Bei Erfolg: `data/trains.json` schreiben
  7. Bei Exception (Network, Parse, …): log + exit ohne JSON-Update (alte Datei bleibt)
- **Sicherheits-Regel:** Alle Untis-API-Texte werden in `fetch_untis.py` mit `esc()` escaped.
  pyhafas-Outputs werden NIE direkt in HTML eingebettet — der Browser parsed das JSON
  und setzt es via `textContent` ins DOM. (Keine XSS-Lücke.)

### 2. `data/trains.json` (neu — bereits gitignored über `data/`-Eintrag)
Format:
```json
{
  "station": "Wien Hütteldorf Bahnhof",
  "fetched_at": "2026-05-28T14:23:00+02:00",
  "towards": [
    {
      "line": "S50",
      "destination": "Wien Hauptbahnhof",
      "planned": "14:23",
      "actual": "14:23",
      "delay_minutes": 0,
      "platform": "1"
    }
  ],
  "away": [
    {
      "line": "S50",
      "destination": "St. Pölten Hbf",
      "planned": "14:29",
      "actual": "14:31",
      "delay_minutes": 2,
      "platform": "2"
    }
  ]
}
```

### 3. Widget im HTML (`fetch_untis.py` minimaler Patch)
- Neuer Container `<div id="train-widget">` zwischen `.header-left` und `.header-right`
- Inline-CSS (Erweiterung in `css/style.css`): fixe Breite ~340px, gleiche Höhe wie Header
- Inline-JS zusätzlich zum bestehenden Clock-Ticker: alle 60s `fetch('data/trains.json')` +
  DOM-Update der Widget-Zellen

### 4. `config.env` Erweiterung (siehe Section 3 im Brainstorming)

## Visuelles Layout (Widget)

```
┌─ Wien Hütteldorf ──────────────────────┐
│ 🟢 → S50  14:23  Wien Hbf              │
│ 🔴 → S50  14:31  St. Pölten Hbf  +2    │
│            Stand: vor 0 min            │
└────────────────────────────────────────┘
```

- **Richtungs-Indikator:** Grüner Punkt (`towards`) / Roter Punkt (`away`), 8px ø
- **Zug-Pikto-SVG:** ein einheitliches Zug-Icon (16px), folgend dem Richtungs-Pfeil:
  - `towards` → Pfeil zeigt nach rechts (→)
  - `away` → Pfeil zeigt nach links (←)
- **Verspätung `+N`** in Orange (`#d99228`), nur wenn `delay_minutes > 0`
- **Stand-Label:** `(now - fetched_at)` in Minuten — Anzeige nur wenn > 0,
  ab > 5 Minuten in Orange als visueller Warnhinweis

### Fehler-Verhalten
- **JSON noch nie geschrieben** → Widget zeigt „— Zugdaten werden geladen —" (kein Layout-Hüpfen)
- **JSON veraltet (> 5 min)** → Widget zeigt letzte Daten, Stand-Label in Orange
- **Fetch im Browser fehlschlägt** → DOM bleibt unverändert (zeigt letzten Stand)
- **`TRAIN_DISABLED=true`** → Widget wird gar nicht ins HTML eingefügt
- **Beim Schreiben Race-Free:** `fetch_trains.py` schreibt erst `data/trains.json.tmp`,
  dann `os.replace()` — atomarer Wechsel, der Browser sieht nie eine halbe Datei

## Konfiguration (`config.env`)

| Variable | Beispiel | Beschreibung |
|---|---|---|
| `TRAIN_STATION` | `Wien Hütteldorf` | Stationsname für pyhafas-Suche |
| `TRAIN_DIR_TOWARDS` | `Hbf,Westbf,Praterstern,Heiligenstadt,Floridsdorf,Meidling,Mitte` | Substrings, die als „Richtung Wien" zählen (case-insensitive) |
| `TRAIN_PER_DIRECTION` | `1` | Anzahl Züge je Richtung |
| `TRAIN_DISABLED` | `false` | Widget komplett ausschalten |

## Dependencies & Setup

### Neu: `pyhafas`
- Erste externe Python-Dependency in diesem Projekt
- Installation auf dem LXC: `pip3 install pyhafas`
- `requirements.txt` wird angelegt mit fixierten Versionen

### Cron-Setup auf dem LXC (nicht Teil dieses Branches, manuelle Schritte dokumentieren)
```cron
*/5  * * * *  cd /var/www/supplierplan && python3 scripts/fetch_untis.py  >> /var/log/supplierplan-untis.log 2>&1
* * * * *  cd /var/www/supplierplan && python3 scripts/fetch_trains.py >> /var/log/supplierplan-trains.log 2>&1
```

## Testing-Plan
1. **Unit-artig:** Eingabe-JSON aus pyhafas-Mock → erwartete Aufteilung
2. **Smoke-Test:** Skript einmal lokal ausführen, JSON-Output prüfen
3. **End-to-End:** im Browser `index.html` öffnen, prüfen ob JS die JSON lädt und Widget befüllt
4. **Fehler-Pfad:** `data/trains.json` löschen → Browser zeigt Lade-Platzhalter
5. **Verspätungs-Test:** JSON manuell mit `delay_minutes: 5` editieren → orange Markierung

## Risiken & Abwägungen
- **Stationsname-Auflösung mehrdeutig** — `pyhafas.locations()` gibt mehrere Treffer.
  Mitigation: ersten Treffer nehmen; im Log loggen welche Station tatsächlich gewählt wurde
- **`TRAIN_DIR_TOWARDS` Substring-Matching zu greedy** — z.B. „Wien" matcht alles.
  Mitigation: Default-Liste verwendet eindeutige Bahnhofsnamen-Fragmente
- **pyhafas-Maintainer-Risiko** — wenn das Paket nicht gepflegt wird und ÖBB ihr HAFAS umbaut,
  müssen wir auf ÖBB-Legacy-XML migrieren (Plan B im Hinterkopf)
- **JSON-Datei-Race** — Cron schreibt, Browser liest. Schreibvorgang: erst `trains.json.tmp`,
  dann atomares `os.replace`. So liest der Browser nie eine halbgeschriebene Datei.

## Out-of-Scope (für später)
- Anzeige von mehr als 2 Zügen (z.B. nächste 3 pro Richtung)
- Gleis-Anzeige (in Daten enthalten, nicht visualisiert)
- Cloudflare-Cache-Purge für `trains.json` — nicht nötig, da Browser direkt fetched mit `cache: no-cache`
- Anzeige der Plan-vs-Real-Differenz textlich („14:21+2" statt „14:23"+„+2")
