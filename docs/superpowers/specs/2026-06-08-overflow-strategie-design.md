# Design: Überlauf-Strategie für den Supplierplan-Monitor

**Datum:** 2026-06-08
**Status:** abgesegnet (Brainstorming), bereit für Implementierungsplan

## Problem

Der Supplierplan läuft auf einem festen Monitor ohne Scroll. An sehr vollen Tagen
(Projekttage, ganze Klassen abwesend, Schullandwochen) passt der Inhalt selbst bei
4 Spalten + Compact-Mode nicht mehr auf den Bildschirm und wird unten **abgeschnitten**.
Ziel: nichts wird je abgeschnitten, an normalen Tagen ändert sich nichts.

## Lösung im Überblick

Eine **gestufte Überlauf-Pipeline**, die client-seitig an die bestehende
JS-Layout-Engine (`applyLayout` in `scripts/fetch_untis.py`) angehängt wird. Nach der
normalen 1–4-Spalten-Verteilung wird gemessen, ob der Inhalt passt; falls nicht,
greifen nacheinander drei Stufen, bis es passt:

1. **Skalieren** (board-weit verkleinern bis Mindestgröße)
2. **Reduzieren** (Text-Spalte aus → Entfall-Sektion kompakt)
3. **Blättern** (überlaufende Sektion rotiert seitenweise)

Jede Stufe ist **unabhängig in `config.env` aktivierbar**. Reihenfolge fix:
Skalieren → Reduzieren → Blättern. Jede Stufe misst nach ihrer Anwendung neu.

**Harte Vorgabe:** Die „Morgen"-Sektion bleibt in **jeder** Stufe sichtbar — sie
wird nie weggelassen und nie auf eine Wartet-Seite verschoben.

## Konfiguration (`config.env`)

Alle Werte werden — wie `COMPACT_COL_WIDTH` — als `window.*`-Variablen ins generierte
HTML injiziert. Defaults so gewählt, dass „nie abgeschnitten" out-of-the-box gilt.

| Key | Default | Wirkung |
|---|---|---|
| `OVERFLOW_SCALE` | `true` | Stufe 1 (Skalieren) erlaubt |
| `OVERFLOW_SCALE_MIN` | `0.65` | kleinster Skalierungsfaktor (0.65 = 65 %); darunter wird nicht weiter verkleinert |
| `OVERFLOW_REDUCE` | `true` | Stufe 2 (Reduzieren) erlaubt |
| `OVERFLOW_PAGINATE` | `true` | Stufe 3 (Blättern) erlaubt |
| `OVERFLOW_PAGE_SECONDS` | `12` | Sekunden pro Seite beim Blättern |

`OVERFLOW_SCALE_MIN` wird auf den Bereich `[0.3, 1.0]` geklemmt; ungültige Werte →
Default. `OVERFLOW_PAGE_SECONDS` wird auf `>= 3` geklemmt.

## Mechanik

### Überlauf-Erkennung

Nach der bestehenden Spaltenverteilung (`distributeGreedy` bei bis zu `MAX_COLS=4`)
misst die Engine pro Sektion die Höhe der **höchsten Spalte** und vergleicht sie mit
`availablePerCol`. Übersteigt sie diese, gilt die Sektion als übergelaufen und die
Pipeline startet. Nach jeder Stufe wird neu gemessen; die Pipeline stoppt, sobald
keine Sektion mehr überläuft oder alle aktiven Stufen ausgereizt sind.

### Stufe 1 — Skalieren

- **Board-weiter** Faktor (ein Wert für Heute *und* Morgen, damit beide optisch
  gleich groß bleiben), getrieben von der volleren Sektion.
- Start bei `1.0`, schrittweise Verkleinerung (Schrittweite `0.05`) bis es passt oder
  `OVERFLOW_SCALE_MIN` erreicht ist.
- Technisch über **Schrift-/Zeilen-Skalierung** (echtes Reflow), nicht über
  `transform: scale` (das ließe die reservierte Box-Höhe unverändert). Nach jedem
  Skalierungsschritt wird die Spaltenverteilung neu gerechnet, weil sich Blockhöhen
  ändern.

### Stufe 2 — Reduzieren

Nur wenn bei `OVERFLOW_SCALE_MIN` noch Überlauf besteht **und** `OVERFLOW_REDUCE=true`.
Zwei Teilschritte, je mit Neu-Messung:

1. **Text-Spalte ausblenden** — Bemerkungs-Spalte (`c-text`) inkl. Header und
   `colgroup`-Eintrag auf `display:none`. Geringster Informationsverlust.
2. **Entfall-Sektion kompakt** — statt voller Tabellenzeilen eine dichte Liste
   (Kürzel + Stunde) für die „Entfallende Stunden".

„Morgen" wird nie entfernt. Beide Schritte greifen erst, wenn der vorherige nicht
gereicht hat.

### Stufe 3 — Blättern

Nur wenn nach Min-Skalierung + Reduktion noch Überlauf besteht **und**
`OVERFLOW_PAGINATE=true`.

- **Pro überlaufender Sektion**: Die Spalten, die in `availablePerCol` passen, bleiben
  stehen; die restlichen Blöcke werden auf weitere **Seiten** verteilt. Die Seiten
  rotieren alle `OVERFLOW_PAGE_SECONDS`.
- **Seitenindikator** in der Sektions-Headline (z. B. „Heute 1/2" + Punkte/Fortschritt).
- Beide Sektionen blättern **unabhängig**; eine nicht überlaufende Sektion steht still.
- Beide Tage bleiben durchgehend gleichzeitig auf dem Schirm (keine „Morgen"-Wartezeit).
- Garantie „nie abgeschnitten": Jede Seite enthält nur Blöcke, die zusammen passen.

### Interaktion mit dem Refresh

Der bestehende 60-s-Soft-Reload und der 5-Minuten-Hard-Reload laufen unverändert
weiter (Datenaktualität). Nach einem Reload wird die Pipeline neu durchlaufen und die
Rotation startet bei Seite 1. Der Rotations-Timer ist unabhängig vom Reload-Timer.

## Edge-Cases

- **Normaler Tag (kein Überlauf):** Faktor 1.0, keine Reduktion, kein Blättern →
  **exakt das heutige Verhalten**.
- **Mobil (`≤ 600px`):** bleibt beim aktuellen Scroll-Verhalten; die Überlauf-Pipeline
  ist nur im Monitor-/Desktop-Modus aktiv.
- **Alle Stufen aus + Überlauf:** Inhalt kann abgeschnitten werden — bewusste
  Nutzerentscheidung. Mit den Defaults (alle an) garantiert Blättern „nie abgeschnitten".
- **Resize:** die gesamte Pipeline läuft (250 ms debounced) neu, wie bisher.
- **Extremfall** (selbst eine Spalte passt bei Min-Skalierung kaum): Blättern legt pro
  Seite nur, was passt — Abschneiden bleibt ausgeschlossen.

## Architektur / betroffene Stellen

- `scripts/fetch_untis.py`
  - JS-Layout-Engine: Überlauf-Check + Stufen-Pipeline in/nach `applyLayout`,
    Skalierung, Reduktions-Klassen, Pagination-Rotation + Indikator.
  - Config-Einlesen in `main()` + Injektion als `window.*` (analog `COMPACT_COL_WIDTH`).
  - Kompakte Entfall-Liste als alternative Render-Variante.
- `css/style.css`
  - skalierbare Schrift-/Zeilen-Größen, `.reduce-text`/`.reduce-cancel`-Klassen,
    Seitenindikator-Styling.
- `config.env.example` + `CLAUDE.md` + `README.md`: neue Keys dokumentieren.
- `scripts/_layout_logic.py` + `tests/`: testbarer Logik-Mirror + Unit-Tests.

## Testing

- **Unit (Python-Mirror in `_layout_logic.py`):** Eine reine Funktion bekommt
  Block-Höhen, verfügbare Höhe, aktive Stufen und Min-Faktor und liefert das Ergebnis
  (resultierender Faktor / Reduktions-Flags / Seiten-Buckets). Tests analog
  `tests/test_layout.py`:
  - kein Überlauf → Faktor 1.0, keine Reduktion, 1 Seite
  - leichter Überlauf → skaliert, keine Reduktion
  - Überlauf bei Min-Faktor → Reduktions-Flags gesetzt
  - weiterhin Überlauf → mehrere Seiten-Buckets, korrekte Block-Zuordnung
  - einzelne Stufen deaktiviert → werden übersprungen
- **Manuell:** künstlich überfüllter Tag am Monitor; prüfen, dass nichts abschneidet,
  Morgen immer sichtbar ist und der Indikator stimmt.

## Bewusst nicht enthalten (YAGNI)

- Keine pro-Sektion unterschiedlichen Skalierungsfaktoren (board-weit reicht).
- Keine konfigurierbare Reduktions-Reihenfolge (fix: Text → Entfall-kompakt).
- Keine vertikale Lauftext-/Marquee-Variante.
