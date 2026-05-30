# Design: Multi-Column-Layout v2 — Top-Down-Reihenfolge, Compact-Mode, Mobile-Header

**Status:** Draft, awaiting user approval
**Branch:** `feature/multi-column-layout` (Fortsetzung)
**Datum:** 2026-05-30
**Vorgänger-Spec:** `2026-05-30-multi-column-layout-design.md`

## Ziel
Die in v1 implementierte Multi-Column-Layout-Engine erweitern, sodass:
1. Lehrer-Reihenfolge bleibt strikt top-down erhalten (Block-Reihenfolge + Greedy-Fit
   statt first-fit-min).
2. Compact-Mode (runde Einbuchstaben-Badges + Fach-Kürzel) wird **breite-basiert**
   getriggert statt nach Spaltenanzahl. Damit sind auch Mobil-Bildschirme automatisch
   im Compact-Mode.
3. Mobile-Layout für Bildschirme < 600px: reduzierter Header, ausgeblendete Elemente.
4. Spalten-Breiten im Compact-Mode neu verteilt — mehr Platz für Raum (kein
   Umbruch mehr), weniger für die runden Mini-Badges.
5. Schwellenwert für Compact-Mode konfigurierbar via `config.env`.

## Display-Annahme (Production)
- **1080 × 1920 px Hochkant-Monitor** in der Schule.
- Vor `SHOW_TOMORROW_AFTER`-Schwelle: nur Heute-Section → volle 1920px Höhe.
- Ab Schwelle: Heute + Morgen → ca. 960px je Section.
- Bei voller Anzeige (großer Vertretungstag, beide Sections sichtbar): 3 Spalten
  à ~360px sind realistisch → kein Compact-Mode. Bei 4 Spalten à ~270px → Compact.

## Nicht-Ziele
- Kein vertikales Scrollen einführen.
- Keine Anpassung des Bahn-Widgets-Verhaltens (außer Position im Mobile-Header).

---

## Section 1 — Lehrer-Verteilung (Block-Reihenfolge + Greedy-Fit)

**Algorithmus** ersetzt das bisherige `first-fit-min`:

```python
def distribute_blocks_greedy(blocks, available_height_per_col, n_cols):
    """
    Lehrer in alphabetischer Reihenfolge durchgehen. Aktuelle Spalte
    füllen bis Höhen-Limit fast erreicht — dann nächste Spalte starten.
    Cancel-Blöcke kommen ans Ende der letzten Spalte.
    """
    regular = [b for b in blocks if b["kind"] != "cancel"]
    cancels = [b for b in blocks if b["kind"] == "cancel"]

    buckets = [[] for _ in range(n_cols)]
    current_col = 0
    current_height = 0

    for block in regular:
        # Würde dieser Block die Spalte sprengen UND ist nicht die letzte?
        if (current_height + block["height"] > available_height_per_col
                and current_col < n_cols - 1
                and len(buckets[current_col]) > 0):
            current_col += 1
            current_height = 0
        buckets[current_col].append(block)
        current_height += block["height"]

    for block in cancels:
        buckets[-1].append(block)

    return buckets
```

**Eigenschaften:**
- Lesefluss bleibt oben-links → unten-links → oben-rechts → unten-rechts
- Wenn ein einzelner Lehrer schon länger ist als `available_height_per_col`:
  er bekommt trotzdem eine eigene Spalte (`len(buckets[current_col]) > 0` Schutz)
- Letzte Spalte darf länger als `available_height_per_col` werden (kein „backwards
  flow") — Cancel-Block würde sonst nicht reinpassen

**JS-Mirror** (in der Layout-Engine in `fetch_untis.py`):
- Gleicher Algorithmus 1:1 in JavaScript portiert
- Vor dem `distribute`-Aufruf: `availablePerCol = (tableWrap.clientHeight / sectionCount) - 60`

**Tests** (`tests/test_layout.py`): neue Test-Klasse `TestDistributeBlocksGreedy`:
- `test_block_reihenfolge_erhalten`: 4 Blöcke (A, B, C, D) à 100px, 2 Spalten,
  available=250 → Spalte 1 = [A, B], Spalte 2 = [C, D]
- `test_uebergroesse_einzelblock`: 1 Block à 500px + 1 à 100px, 2 Spalten,
  available=300 → Spalte 1 = [bigBlock], Spalte 2 = [smallBlock]
- `test_cancel_immer_letzte_spalte`: A (100) + Cancel (50), 3 Spalten,
  available=300 → Spalten 0+1 nicht touched, Spalte 2 = [A, Cancel]? Eher:
  A in Spalte 0, Cancel auch Spalte 2. → `[[A], [], [Cancel]]`
- `test_alle_in_eine_spalte_wenn_genug_platz`: 4 Blöcke à 50px, 2 Spalten,
  available=300 → alle in Spalte 0, Spalte 1 leer

Die alte `distribute_blocks`-Funktion wird **ersetzt**, nicht parallel gehalten.
Bestehende Tests (`TestDistributeBlocks`) werden aktualisiert oder durch neue ersetzt.

---

## Section 2 — Compact-Mode breite-basiert + `config.env`-Variable

**Trigger:** Spaltenbreite < `COMPACT_COL_WIDTH_PX` (Default 320) → Compact-Mode aktiv.

**Was Compact-Mode bewirkt:**
- Art-Badges werden rund (20×20px) mit Einbuchstaben (V/E/R/F/P)
- „Aufsicht" → „Aufs." (über doppelten `<span>` analog zu Badges)
- Spalten-Breiten umverteilt (siehe Section 4)

**Konfiguration** in `config.env`:
```
# Compact-Mode: ab welcher Spaltenbreite (Pixel) Badges rund werden
# und Aufsicht → Aufs. abgekürzt. Default: 320
COMPACT_COL_WIDTH_PX=320
```

`config.env.example` bekommt diese Zeile am Ende (nach den TRAIN_*-Variablen).

**Render-Mechanik:**
1. `fetch_untis.py` liest `COMPACT_COL_WIDTH_PX` (Default 320 wenn nicht gesetzt)
2. Schreibt in den HTML-`<head>`:
   ```html
   <script>window.COMPACT_COL_WIDTH = 320;</script>
   ```
3. Layout-Engine ergänzt in `applyLayout(wrapper)`:
   ```javascript
   var colWidth = wrapper.querySelector('.col').clientWidth;
   if (colWidth < window.COMPACT_COL_WIDTH) {
       wrapper.classList.add('compact-mode');
   } else {
       wrapper.classList.remove('compact-mode');
   }
   ```
4. CSS reagiert auf `.compact-mode` (nicht mehr auf `.cols-3`/`.cols-4`):
   ```css
   .compact-mode .badge-full { display: none; }
   .compact-mode .badge-short { display: inline-flex; }
   .compact-mode .badge { /* runde Form */ }
   .compact-mode .fach-full { display: none; }
   .compact-mode .fach-short { display: inline; }
   ```

**Render-Anpassung in `fetch_untis.py`:**

Die `fach`-Zelle bekommt analog zu den Badges zwei Spans:
```python
def fach_html(fach):
    """Liefert Fach mit Lang- und Kurz-Variante."""
    short = "Aufs." if fach == "Aufsicht" else fach
    return (
        f'<span class="fach-full">{esc(fach)}</span>'
        f'<span class="fach-short">{esc(short)}</span>'
    )
```

Wird in `render_row` aufgerufen statt `{esc(r["fach"])}` direkt.

---

## Section 3 — Mobile-Layout (< 600px)

CSS Media Query `@media (max-width: 600px)`:

**Ausgeblendet:**
- `.logo` (`display: none`)
- `.school-name`, `.school-sub`
- `.clock-date`, `.clock-time`
- `.legend`
- `.day-title-bar` (Heute/Morgen-Zwischenheader)
- `.period-label` (das Mini-Label „LAUFENDE STUNDE")

**Sichtbar / angepasst:**
- `.train-widget`: links angedockt (`margin-left: 0`, `flex: 1 1 auto` statt fester Breite)
- `.period-block`: kompakt rechts, nur Stundennummer + Zeit (ohne Label)
- `.plan-tag`: bleibt sichtbar, übernimmt die Tages-Anzeige

**Header-Layout in Mobile:**
```
┌───────────────────────────────────────────────────┐
│ [Train-Widget — links]      [Period-Value]       │
└───────────────────────────────────────────────────┘
[Plan-Tag: Morgen · Mo, 1. Juni 2026]
```

**Header-Höhe** wird in Mobile reduziert:
```css
@media (max-width: 600px) {
    :root { --h-header: 60px; }
}
```

**Plan-Tag bei wenig Breite:**
- `white-space: nowrap`
- Font-Size 11–12px statt 13px
- Falls weiter zu lang → Wochentag-Kurzform implementieren:
  - Statt „Montag, 1. Juni 2026" → „Mo, 1. Juni 2026"
  - Mechanik: Python schreibt beide Versionen als `<span>`s mit `tag-full`/`tag-short`,
    CSS schaltet ab `@media (max-width: 600px)` auf short

---

## Section 4 — Spalten-Breiten-Anpassungen

**Default-Spalten** (unverändert):

| Spalte | Anteil |
|---|---|
| c-kuerzel | 3% |
| c-std | 6% |
| c-fach | 16% |
| c-klasse | 12% |
| c-lehrer | 22% |
| c-art | 13% |
| c-raum | 9% |
| c-text | 19% |

**Compact-Mode** (Spalte schmaler als `COMPACT_COL_WIDTH_PX`):

| Spalte | Anteil | Begründung |
|---|---|---|
| c-kuerzel | 3% | unverändert |
| c-std | 7% | leicht mehr (`1/2` etc.) |
| c-fach | 14% | leicht reduziert (`Aufs.` braucht weniger) |
| c-klasse | 10% | reduziert (Klassen-Namen sind kurz) |
| c-lehrer | 24% | leicht mehr (Name kann lang sein) |
| c-art | 5% | viel kleiner (rundes 20×20px Badge) |
| c-raum | 13% | mehr Platz, kein Umbruch mehr |
| c-text | 24% | bleibt großzügig für Bemerkungen |

CSS-Mechanik:
```css
.compact-mode col.c-art    { width: 5%; }
.compact-mode col.c-klasse { width: 10%; }
.compact-mode col.c-raum   { width: 13%; }
/* ... usw. */
```

---

## Section 5 — Zusammenfassung Konfiguration

**Neue `config.env`-Variable:**
```
COMPACT_COL_WIDTH_PX=320
```

**Hartkodierte Schwellen (in Code):**
- Mobile-Breakpoint = 600px (CSS Media Query)
- `MIN_COL_WIDTH = 280` (JS, für Spaltenzahl-Berechnung in `chooseColCount`)
- `MAX_COLS = 4` (JS)

Bei Bedarf können diese später auch konfigurierbar gemacht werden.

---

## Architektur-Diagramm (Updates ggü v1)

```
Server-Side (fetch_untis.py)             Client-Side (Browser)
┌─────────────────────────────┐         ┌──────────────────────────┐
│ Flache Tabelle (wie v1)      │         │ Layout-Engine v2:        │
│ + fach-full/fach-short Spans │ ──→     │  1. Container vermessen  │
│ + COMPACT_COL_WIDTH ins JS   │         │  2. Greedy-Fit Verteilung│
│                              │         │  3. cols-N Klasse setzen │
│                              │         │  4. Wenn col-width <     │
│                              │         │     COMPACT_COL_WIDTH:   │
│                              │         │     compact-mode aktiv   │
│ CSS:                         │         │                          │
│ - .compact-mode (statt       │         │ Mobile-Header:           │
│   .cols-3/.cols-4)           │         │  via CSS Media-Query     │
│ - @media (max-width: 600px)  │         │  @media (max-width:600)  │
└─────────────────────────────┘         └──────────────────────────┘
```

---

## Was wegfällt (ggü v1)

- `.layout-wrapper.cols-3 .badge-full { display: none }` und ähnliche Cols-3/Cols-4-Regeln
  → ersetzt durch `.compact-mode .badge-full { display: none }`
- `first-fit-min`-Algorithmus → ersetzt durch `block-reihenfolge + greedy-fit`
- Bestehende Tests `TestDistributeBlocks` → ersetzt durch `TestDistributeBlocksGreedy`

---

## Risiken & Mitigation

1. **Greedy-Fit kann unausgewogen werden** — z.B. wenn 5 lange Lehrer + 1 kurzer
   und 2 Spalten: Spalte 1 = 5 lange, Spalte 2 = 1 kurzer. Spalte 1 könnte überlaufen.
   Mitigation: `available_height_per_col` mit großzügiger Reserve berechnet (-60px);
   Lesefluss ist wichtiger als perfekte Balance.

2. **Compact-Mode flackert bei resize** — bei Browser-Resize könnten die col-Breiten
   um den Schwellwert oszillieren. Mitigation: ResizeObserver hat 250ms Debounce.

3. **Mobile-View nicht getestet auf echten Geräten** — wir vermuten viel, sehen aber
   nicht. Mitigation: User testet im Browser-DevTools (Device-Toolbar) bei 360×640.

4. **`COMPACT_COL_WIDTH_PX`-Variable in config.env fehlt** — Fallback auf 320.

---

## Testing-Plan

**Unit-Tests** (`tests/test_layout.py`):
- 4 neue Tests für `distribute_blocks_greedy` (siehe Section 1)
- Alte `TestDistributeBlocks` werden gelöscht oder als `TestDistributeBlocksLegacy`
  weiterhin laufen (Entscheidung: löschen für Klarheit)

**Manuelle Tests im Browser:**
1. 1920×1080 portrait (echter Monitor): Heute leer → Morgen 1 Spalte ohne Compact
2. Volle Anzeige (Heute + Morgen, viele Vertretungen): 2-3 Spalten, Compact je nach Breite
3. Browser-Fenster auf 600px verkleinern: Mobile-Mode aktiv (Logo weg, Schulname weg, etc.)
4. DevTools Device-Toolbar 360×640: vollständiger Mobile-Look
5. Resize-Test: Spaltenanzahl ändert sich beim Vergrößern/Verkleinern

**Smoke-Test config:**
- `COMPACT_COL_WIDTH_PX=200` in config.env → Compact greift fast nie
- `COMPACT_COL_WIDTH_PX=500` → Compact greift schon bei 1-Spalten-Desktop
