# Projekt: Supplierplan-Anzeige - VS Roda-Roda-Gasse Wien

## Projektübersicht
Ich baue eine selbst gehostete Webanzeige für den Supplierplan unserer Schule 
(Mittelschule Roda-Roda-Gasse, 1210 Wien) als Ersatz für die unübersichtliche 
WebUntis Monitor-Ansicht. Die Seite läuft auf einem dedizierten PC im 
Schulnetzwerk und wird auf einem Monitor (kein Touch) angezeigt.

## Technischer Stack
- **Frontend:** Reines HTML5 + CSS3 (KEIN JavaScript erforderlich)
- **Server:** [NOCH ZU ENTSCHEIDEN - siehe unten]
- **Datenquelle:** WebUntis API (Untis)
- **Hosting:** Interner Schulserver, läuft dauerhaft
- **Betriebssystem Server-PC:** Windows (Laptop, läuft dauerhaft)

## Server-Entscheidung (wichtig!)
Ich brauche zuerst eine Empfehlung welchen einfachen Webserver ich nutzen soll.
Anforderungen:
- Einfache Installation auf Windows
- Statische HTML-Dateien ausliefern
- Später eventuell kleine API-Abfragen (WebUntis) integrieren
- Muss zuverlässig dauerhaft laufen (Autostart)
- Möglichst wenig Wartungsaufwand
Optionen zur Bewertung: nginx, Apache, Python http.server, Node.js/Express, 
Caddy, Live Server (VS Code)

## WebUntis API - Was müssen wir herausfinden?
Folgende Daten brauchen wir vom Supplierplan:
- [ ] Welche Stunden fallen aus?
- [ ] Welche Lehrer supplieren?
- [ ] In welchem Raum findet die Stunde statt?
- [ ] Klasse/Gruppe betroffener Schüler
- [ ] Uhrzeit / Stundennummer
- [ ] Status (Supplierung, Entfall, Raumänderung)

WebUntis API Dokumentation: https://untis-sr.ch/wp-content/uploads/2019/11/2018-09-20-WebUntis_JSON-RPC_API.pdf
Unsere WebUntis Instanz: https://s921092.webuntis.com
Schule in WebUntis: [SCHULNAME wie in WebUntis eingetragen]

## Design-Anforderungen
- **Schule:** MS Roda-Roda-Gasse, 1210 Wien
- **Logo:** Logo der Schule soll eingebunden werden (Datei: logo.png)
- **Farben:** [Schulfarben - bitte recherchieren oder vorgeben]
- **Schriftgröße:** Groß und gut lesbar (Monitor-Abstand ca. 2-3 Meter)
- **Layout:** Übersichtliche Tabelle, ganzer Bildschirm genutzt
- **Kein JavaScript** - rein statisches HTML/CSS
- **Kein Scrolling** - alles auf einen Blick sichtbar
- **Kontrast:** Hoch, auch bei Tageslicht lesbar

## Gewünschte Anzeigeelemente
1. Schullogo + Schulname oben
2. Aktuelles Datum + Uhrzeit (CSS only, oder server-seitig gerendert)
3. Haupttabelle Supplierplan mit Spalten:
   - Stunde (Nr. + Uhrzeit)
   - Klasse
   - Fach
   - Vertretungslehrer
   - Raum
   - Bemerkung/Status
4. Farbliche Kennzeichnung nach Status:
   - Supplierung = [Farbe]
   - Entfall = [Farbe]
   - Raumänderung = [Farbe]
5. Footer mit letzter Aktualisierungszeit

## Projektphasen
### Phase 1 (JETZT):
- Server-Tool auswählen und Installationsanleitung
- Statisches HTML/CSS Mockup der Anzeigeseite
- Testdaten (hardcoded) zur Layout-Kontrolle

### Phase 2:
- WebUntis API erkunden und testen
- Herausfinden welche Daten wir bekommen können
- Authentifizierung klären

### Phase 3:
- Backend-Script das WebUntis Daten abruft
- HTML automatisch generieren oder Template befüllen
- Automatische Aktualisierung einrichten (Cron/Task Scheduler)

## Dateistruktur (geplant)

```
supplierplan/
├── index.html          # Hauptanzeige
├── css/
│   └── style.css       # Styles
├── assets/
│   └── logo.png        # Schullogo
├── data/
│   └── plan.json       # Von API generierte Daten (Phase 2)
└── scripts/
    └── fetch_untis.py  # API-Abfrage Script (Phase 2)
```

## Meine Umgebung
- Ich arbeite mit Claude Code auf einem separaten Entwicklungs-PC
- Server-PC läuft dauerhaft in der Schule
- Deployment: Dateien werden manuell oder per Script übertragen
- Netzwerk: Internes Schulnetzwerk
