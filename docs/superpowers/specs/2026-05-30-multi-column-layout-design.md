# Design: Adaptives Multi-Spalten-Layout mit dynamischen Abkürzungen

**Status:** Draft, awaiting user approval
**Branch:** `feature/multi-column-layout`
**Datum:** 2026-05-30

## Ziel
Die Supplierliste muss auch bei vielen Lehrer-Ausfällen vollständig auf einem
Bildschirm bleiben. Bisher wird ab ~30 Zeilen automatisch auf 2 Spalten
geschaltet — das reicht bei großen Vertretungstagen (40–80 Zeilen) nicht aus.
Wir bauen ein adaptives 1- bis 4-Spalten-Layout, das die tatsächlich verfügbare
Bildschirmhöhe ausmisst und bei Platznot bis zu 4 Spalten erzeugt. Die
„Art"-Spalte (Vertretung/Entfall/Raumwechsel/…) wird ab 3 Spalten als
Einbuchstaben-Badge dargestellt, damit die Zeilen schmaler werden.

## Nicht-Ziele
- Kein Vertikales Scrollen einführen (Anzeige bleibt „auf einen Blick")
- Kein responsives Mobile-Layout (Schul-Monitor hat fixe Auflösung)
- Keine Refactorings außerhalb der Layout-Logik

## Architektur

### Verantwortlichkeits-Trennung

```
Server-Side (fetch_untis.py)             Client-Side (Browser)
┌─────────────────────────────┐         ┌─────────────────────────────┐
│ Eine flache "logische Liste":│         │ JS-Layout-Engine:           │
│  ├─ Lehrer-Gruppe A (header  │         │  1. Container vermessen     │
│  │   + rows)                 │ ──→     │  2. Items in N Buckets      │
│  ├─ Lehrer-Gruppe B          │         │     verteilen               │
│  ├─ …                        │         │  3. Class .cols-N am        │
│  └─ Cancel-Sektion           │         │     Wrapper setzen          │
│                              │         │  4. ResizeObserver triggert │
│ KEINE Server-side-Spalten    │         │     Re-Layout               │
│ mehr (TWO_COL_THRESHOLD weg) │         │                             │
└─────────────────────────────┘         └─────────────────────────────┘
```

Trennung der Concerns:
- **Server**: rendert eine flache, semantisch korrekte Tabelle. Kein Wissen über Spalten.
- **Browser**: misst Platz, verteilt, schaltet Anzeige um.

## Komponenten

### 1. Server-Side: flache Render-Ausgabe

`scripts/fetch_untis.py` (`build_day_content`) wird so umgebaut, dass:
- Pro Tag genau **eine** Tabelle ausgegeben wird (statt 1 oder 2 abhängig von Threshold)
- Jede Lehrer-Gruppe (Header + Zeilen) ist ein semantisches Block-Element mit
  einem `data-block`-Attribut: `data-block="teacher"` bzw. `data-block="cancel"`
- Die Cancel-Sektion bleibt eine atomare Einheit am Ende der Liste

Die `TWO_COL_THRESHOLD`-Konstante wird entfernt. Die `split_chunks()`-Funktion
wird entfernt.

### 2. Server-Side: Doppel-Label im Badge

Die ART-Badges bekommen beide Versionen ins DOM:

```html
<span class="badge b-sup">
  <span class="badge-full">Vertr.</span>
  <span class="badge-short">V</span>
</span>
```

Erweiterte `ART_MAP`:

```python
ART_MAP = {
    "subst":      ("s-sup",   "b-sup",   "Vertr.",     "V"),
    "cancel":     ("s-ent",   "b-ent",   "Entfall",    "E"),
    "roomchange": ("s-raum",  "b-raum",  "Raum",       "R"),
    "free":       ("s-frei",  "b-frei",  "Freistunde", "F"),
    "pause":      ("s-pause", "b-pause", "Pause",      "P"),
}
```

### 3. Client-Side: Layout-Engine (~80 Zeilen JS)

Algorithmus:

```
function layoutSection(section):
    blocks    = section.querySelectorAll('[data-block]')
    container = section.querySelector('.layout-wrapper')

    available   = container.offsetHeight
    totalHeight = sum(block.offsetHeight for block in blocks)
    cols        = min(4, max(1, ceil(totalHeight / available)))

    if cols == 1:
        # Nichts zu tun — Default-Anzeige
        container.classList.add('cols-1')
        return

    # Items in N Buckets verteilen — first-fit nach Höhe
    buckets = [[] for _ in range(cols)]
    bucket_heights = [0] * cols
    for block in blocks:
        idx = argmin(bucket_heights)
        buckets[idx].append(block)
        bucket_heights[idx] += block.offsetHeight

    # Cancel-Block (letzter Block) immer in letzte Spalte schieben
    last_bucket_idx = cols - 1
    # … falls Cancel nicht schon dort ist, verschieben

    # Klonen pro Bucket in eigene <table>-Wrapper
    container.classList.add(f'cols-{cols}')
    container.innerHTML = ''
    for bucket in buckets:
        col_table = createTableWrapper(bucket)
        container.appendChild(col_table)
```

Trigger:
- `DOMContentLoaded`: einmaliger Layout-Lauf
- `ResizeObserver` auf `<body>`: re-layout bei Browser-Resize, 250 ms debounced
- Nach `location.reload()`: läuft automatisch wieder beim Page-Load

### 4. Client-Side: CSS für Spalten + Abkürzungen

`css/style.css`:

```css
/* Default: kurzes Label versteckt */
.badge-short { display: none; }

/* Ab 3 Spalten: lang → kurz */
.cols-3 .badge-full, .cols-4 .badge-full { display: none; }
.cols-3 .badge-short, .cols-4 .badge-short { display: inline-flex; }

/* Kurzform-Badge: rund statt rechteckig */
.cols-3 .badge, .cols-4 .badge {
    width: 18px; height: 18px;
    padding: 0; border-radius: 50%;
    display: inline-flex;
    align-items: center; justify-content: center;
    font-size: 11px;
}

/* Spalten-Container: nur Flex-Verteilung */
.layout-wrapper {
    display: flex;
    flex-direction: row;
    gap: 20px;
    height: 100%;
}

.layout-wrapper > .col { flex: 1; min-width: 0; }
```

## Abkürzungs-Mapping

| Vollform | Kurz | Farbe (bestehend) | Bedeutung |
|---|---|---|---|
| `Vertr.` | **V** | Orange `#d99228` | Vertretung |
| `Entfall` | **E** | Rot `#e05050` | Entfall |
| `Raum` | **R** | Blau `#5a9fe0` | Raumwechsel |
| `Freistunde` | **F** | Grün `#4ab870` | Freistunde |
| `Pause` | **P** | Lila `#b090e8` | Pausenaufsicht |

Text-Spalte (b/ub/MA + Bemerkungen) bleibt **immer** in voller Form.

## Edge Cases & Verhalten

### Container-Vermessung
- Verfügbare Höhe = `.plan-section`-Höhe minus Summary-Bar minus Day-Title-Bar
- Min-Breite pro Spalte = 280 px → auf schmalen Bildschirmen wird die max-Spaltenzahl
  durch `floor(containerWidth / 280)` begrenzt
- Max-Spalten = **4** (mehr wird unleserlich)

### Pro-Section unabhängig
Heute-Section und Morgen-Section bekommen jeweils ihre eigene Layout-Berechnung.
Heute kann 2 Spalten haben, Morgen 4 — je nach Inhalt.

### Cancel-Sektion
- Bleibt atomares Item (Header + Cancel-Zeilen zusammen)
- Wird nach der first-fit-Verteilung explizit in die **letzte** Spalte verschoben
- Wenn so groß dass sie eine eigene Spalte braucht: Layout-Engine reserviert sie alleine

### Lehrer-Gruppen-Atomizität
- Lehrer-Header + alle seine Zeilen sind ein Block (`data-block="teacher"`)
- Wird **niemals** geteilt
- Wenn eine Gruppe größer als Container-Höhe → bleibt trotzdem ungeteilt, könnte überlappen
  (in der Praxis: max ~10 Zeilen pro Lehrer — unkritisch)

### Refresh-Verhalten
- Bei meta-refresh / `location.reload()`: kompletter Re-Render → Layout läuft frisch
- Bei `ResizeObserver`-Trigger: nur Re-Layout, kein Reload
- 60s-Soft-Reload greift wie bisher

### JS deaktiviert
- Fallback: alles in einer Spalte, lange Labels. Anzeige ist noch lesbar, nur knapper.

## Was entfernt wird
- `TWO_COL_THRESHOLD = 30` (Konstante)
- `split_chunks(chunks)` (Funktion)
- Der If/Else-Branch in `build_day_content` für 1- vs 2-Spalten

## Was neu kommt
- `scripts/fetch_untis.py`:
  - Flache Render-Ausgabe in `build_day_content`
  - `ART_MAP` um Kurz-Label erweitert (5. Tupel-Element)
  - `<span class="badge-full"></span><span class="badge-short"></span>` im `render_row`
  - `data-block`-Attribute auf den Block-Containern
- `css/style.css`:
  - `.cols-N`-Regeln für Spalten-Layout
  - `.badge-short`-Regeln + Kurz-Badge-Styling
  - `.layout-wrapper`-Container-Regeln
- `index.html` JS (inline):
  - `layoutSection(section)` Engine
  - `ResizeObserver` mit 250 ms Debounce

## Testing-Plan

1. **Unit-artig** (für Layout-Berechnung): Mock-DOM, verschiedene Block-Anzahlen + Höhen
   → erwartete Bucket-Verteilung
2. **Smoke-Test im Browser**:
   - Wenig Inhalt → `.cols-1`, lange Labels
   - Mittel (~30 Zeilen) → `.cols-2`, lange Labels
   - Viel (~50 Zeilen) → `.cols-3`, kurze Badges (V/E/R/F/P)
   - Sehr viel (~80 Zeilen) → `.cols-4`, kurze Badges
3. **Resize-Test**: Browser-Fenster verkleinern → Layout reagiert
4. **Cancel-Sektion-Test**: Bei jeder Spaltenanzahl muss sie unten rechts landen
5. **Smoke-Test mit Live-Daten** auf dem Schul-Monitor

## Risiken & Mitigation

- **Lehrer-Gruppe größer als Container** → ungeteilt belassen, könnte überlappen.
  Mitigation: extrem selten in der Praxis; ggf. später Sub-Splitting nach den
  Stunden-Zeilen ergänzen.
- **Inhalt ändert sich während Layout** (asynchroner Re-Render) → ResizeObserver
  hat 250 ms Debounce.
- **Flackern beim Initialen Layout** → Container ist initial mit `visibility: hidden`,
  wird erst nach Layout-Engine sichtbar gemacht.
- **Lange Labels werden in der Layout-Berechnung mitgemessen, ändern sich aber durch
  `.cols-N`** → Layout-Engine läuft *zweimal*: erst mit langem Label messen, dann
  mit `.cols-N` setzen + neu messen (re-fit, falls jetzt eine Spalte weniger reicht).
  Pragmatisch: nur ein Lauf, akzeptieren dass das Layout minimal sub-optimal sein kann.

## Out-of-Scope (für später)
- Vertikales Scrollen für extrem volle Tage (>80 Zeilen)
- Anpassbare Min-Spalten-Breite via Config
- Animation beim Layout-Wechsel
- A/B-Test verschiedener Spalten-Heuristiken
