# Layout-Browser-Fixtures

Reproduzierbarer Anker für den **manuellen** Browser-Check des Layout-Refactors
(ADR `docs/adr/0002-layout-engine-extracted-and-tested.md`). Der Driver in
`js/layout.js` misst echte DOM-Höhen — das kann keine headless-Umgebung ohne
Layout-Engine prüfen (jsdom liefert `getBoundingClientRect()==0`). Die reine
Mathematik ist per Node getestet (`tests/js/`); diese drei Seiten decken das ab,
was nur ein echter Browser zeigt.

## Erzeugen

```
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe \
    tests/fixtures/layout/gen.py
```

Schreibt `normal.html`, `overflow.html`, `cancel_heavy.html` in dieses Verzeichnis
(deterministisch: fester Zeitpunkt). Die HTML-Dateien selbst sind **nicht**
eingecheckt — nur der Generator; erzeuge sie bei Bedarf frisch.

## Prüfen

Jede Datei **aus dem Projekt-Root serviert** im Browser öffnen, damit
`js/layout-core.js` + `js/layout.js` (und `css/`) auflösen, z.B.:

```
python3 -m http.server 8080      # im Projekt-Root
# dann: http://localhost:8080/tests/fixtures/layout/overflow.html
```

| Datei | Erwartetes Verhalten |
|---|---|
| `normal.html` | Sauberes 2–4-Spalten-Layout, nichts abgeschnitten, keine Konsolenfehler. |
| `overflow.html` | Überlauf-Pipeline greift gestuft: erst **Skalieren**, dann **Reduzieren** (Text-Spalte weg, Entfall kompakt), dann **Blättern** mit Seiten-Indikator. „Morgen" bleibt in jeder Stufe sichtbar. |
| `cancel_heavy.html` | Große „Entfallende Stunden"-Sektion fließt über echte Spaltengrenzen; **genau eine** Überschrift je Spalte, Folge-Spalten „… (Forts.)" (dezent), keine überlaufende Spalte. |

Diagnose: dieselbe URL mit `?ovdebug=1` blendet unten links ein Overlay ein, das
je Sektion die gegriffene Überlauf-Stufe und die gemessenen Höhen zeigt.

Fenster schmäler ziehen (Resize, 250 ms debounced) und auf < 600 px (Mobil-Ansicht)
gehen, um Re-Layout und Kompakt-Modus zu prüfen.
