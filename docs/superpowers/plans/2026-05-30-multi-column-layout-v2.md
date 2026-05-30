# Multi-Column-Layout v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lehrer-Reihenfolge im Multi-Spalten-Layout strikt top-down (Block-Reihenfolge + Greedy-Fit), Compact-Mode breite-basiert statt nach Spaltenzahl getriggert, neue Mobile-Ansicht für Bildschirme < 600px, Compact-Schwelle konfigurierbar via `config.env`.

**Architecture:** Python rendert flache Tabelle wie in v1, ergänzt aber `fach-full`/`fach-short`-Spans für Aufsicht→Aufs.-Abkürzung und schreibt `window.COMPACT_COL_WIDTH` ins HTML. JS-Layout-Engine verteilt mit Greedy-Fit statt First-Fit-Min und prüft pro `applyLayout`-Lauf die tatsächliche Spaltenbreite — bei Unterschreiten der Schwelle wird `.compact-mode`-Klasse gesetzt. CSS reagiert auf `.compact-mode` + Mobile-Media-Query.

**Tech Stack:** Python 3.9+ (stdlib), HTML/CSS/Vanilla JS, CSS Media Queries, `unittest`. Spec: `docs/superpowers/specs/2026-05-30-multi-column-layout-v2-design.md`.

---

## File Structure

**Geändert:**
- `scripts/_layout_logic.py`:
  - `distribute_blocks` ersetzt durch Greedy-Fit-Algorithmus mit Parameter `available_height_per_col`
- `tests/test_layout.py`:
  - Tests ersetzt: alte 5 Tests entfernt, 4 neue für Greedy-Fit-Logik
- `scripts/fetch_untis.py`:
  - `load_config` schon vorhanden, kein Change
  - `main()`: `COMPACT_COL_WIDTH_PX` aus config lesen, an `generate_html` übergeben
  - `generate_html`-Signatur: neuer Parameter `compact_col_width`
  - `<head>`: neuer `<script>window.COMPACT_COL_WIDTH = N;</script>`
  - `render_row`: `fach`-Zelle bekommt `fach-full`/`fach-short`-Spans
  - JS-Layout-Engine: Greedy-Fit, Compact-Mode-Detection
  - Plan-Tag: `tag-full`/`tag-short`-Spans für Mobile-Kurzform
- `css/style.css`:
  - `.compact-mode`-Regeln (statt der `.cols-3`/`.cols-4`-Regeln, die entfernt werden)
  - Neue Spalten-Breiten unter `.compact-mode`
  - `.fach-short` + `.tag-short` Default versteckt
  - `@media (max-width: 600px)`-Block für Mobile-Header
- `config.env.example`:
  - Neue Zeile `COMPACT_COL_WIDTH_PX=320`

**Nicht angefasst:**
- `scripts/fetch_trains.py`, `manifest.json`, `sw.js`, `data/`

---

## Task 1: `distribute_blocks_greedy` — Greedy-Fit Algorithmus (TDD)

**Files:**
- Modify: `scripts/_layout_logic.py`
- Modify: `tests/test_layout.py`

- [ ] **Step 1: Failing tests schreiben**

`tests/test_layout.py` komplett ersetzen mit:

```python
import unittest

from scripts._layout_logic import distribute_blocks


class TestDistributeBlocksGreedy(unittest.TestCase):
    """Block-Reihenfolge + Greedy-Fit: Lehrer alphabetisch (Eingabe-Reihenfolge)
    durchgehen, aktuelle Spalte füllen bis available-Höhe fast erreicht,
    dann nächste Spalte. Cancel-Blöcke ans Ende der letzten Spalte."""

    def test_block_reihenfolge_erhalten(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "B", "height": 100, "kind": "teacher"},
            {"id": "C", "height": 100, "kind": "teacher"},
            {"id": "D", "height": 100, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=2, available_height_per_col=250)
        # A+B = 200 ≤ 250, C würde 300 → wechsel zu Spalte 1, C+D = 200 ≤ 250
        self.assertEqual([b["id"] for b in result[0]], ["A", "B"])
        self.assertEqual([b["id"] for b in result[1]], ["C", "D"])

    def test_uebergroesse_einzelblock_bekommt_eigene_spalte(self):
        blocks = [
            {"id": "BIG", "height": 500, "kind": "teacher"},
            {"id": "small", "height": 100, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=2, available_height_per_col=300)
        # BIG passt nirgendwo, aber Spalte 0 ist leer → kommt rein
        # small würde 600 in Spalte 0 sprengen → in Spalte 1
        self.assertEqual([b["id"] for b in result[0]], ["BIG"])
        self.assertEqual([b["id"] for b in result[1]], ["small"])

    def test_cancel_immer_letzte_spalte(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "CANCEL", "height": 50, "kind": "cancel"},
        ]
        result = distribute_blocks(blocks, n_cols=3, available_height_per_col=300)
        # A in Spalte 0, Spalte 1 leer (kein weiterer regulärer Block),
        # Cancel landet in Spalte 2 (letzte)
        self.assertEqual([b["id"] for b in result[0]], ["A"])
        self.assertEqual(result[1], [])
        self.assertEqual([b["id"] for b in result[2]], ["CANCEL"])

    def test_alle_in_eine_spalte_wenn_platz_reicht(self):
        blocks = [
            {"id": "A", "height": 50, "kind": "teacher"},
            {"id": "B", "height": 50, "kind": "teacher"},
            {"id": "C", "height": 50, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=2, available_height_per_col=300)
        self.assertEqual([b["id"] for b in result[0]], ["A", "B", "C"])
        self.assertEqual(result[1], [])

    def test_leere_input_liste(self):
        result = distribute_blocks([], n_cols=2, available_height_per_col=300)
        self.assertEqual(result, [[], []])

    def test_cancel_zusammen_mit_teacher_in_letzter_spalte(self):
        blocks = [
            {"id": "A", "height": 200, "kind": "teacher"},
            {"id": "B", "height": 200, "kind": "teacher"},
            {"id": "CANCEL", "height": 80, "kind": "cancel"},
        ]
        result = distribute_blocks(blocks, n_cols=2, available_height_per_col=250)
        # A in Spalte 0, B würde 400 → wechsel zu Spalte 1
        # Cancel ans Ende der letzten = Spalte 1, nach B
        self.assertEqual([b["id"] for b in result[0]], ["A"])
        self.assertEqual([b["id"] for b in result[1]], ["B", "CANCEL"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — soll fehlschlagen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```

Expected: `TypeError: distribute_blocks() got an unexpected keyword argument 'available_height_per_col'`

- [ ] **Step 3: Implementation in `scripts/_layout_logic.py` ersetzen**

Komplett ersetzen mit:

```python
"""
_layout_logic.py – Verteilung von Render-Blöcken in N Spalten (Greedy-Fit).
Dient als testbarer Python-Mirror der JS-Layout-Engine im Browser.
"""

from typing import Iterable


def distribute_blocks(blocks: Iterable[dict], n_cols: int,
                       available_height_per_col: int = None) -> list:
    """Verteilt Blöcke in n_cols Spalten per Greedy-Fit von links nach rechts.
    Reihenfolge der Blöcke bleibt erhalten (top-down). Cancel-Blöcke
    (`kind == "cancel"`) landen am Ende der letzten Spalte.

    Wenn `available_height_per_col` None oder <= 0 ist, packt alles in Spalte 0
    (degenerierter Fall, sollte nicht produktiv passieren).
    """
    if n_cols < 1:
        n_cols = 1

    regular = [b for b in blocks if b.get("kind") != "cancel"]
    cancels = [b for b in blocks if b.get("kind") == "cancel"]

    buckets = [[] for _ in range(n_cols)]

    if not available_height_per_col or available_height_per_col <= 0:
        # Degeneriert: alles in Spalte 0
        buckets[0] = regular[:]
    else:
        current_col = 0
        current_height = 0
        for block in regular:
            block_h = block.get("height", 0)
            # Würde dieser Block die aktuelle Spalte sprengen?
            # Aber: nur wechseln, wenn die Spalte nicht leer ist (sonst hat ein
            # Übergrößer-Block keinen Platz und würde übersprungen werden).
            if (current_height + block_h > available_height_per_col
                    and current_col < n_cols - 1
                    and len(buckets[current_col]) > 0):
                current_col += 1
                current_height = 0
            buckets[current_col].append(block)
            current_height += block_h

    # Cancel-Blöcke ans Ende der letzten Spalte
    for block in cancels:
        buckets[-1].append(block)

    return buckets
```

- [ ] **Step 4: Tests laufen lassen — sollen passen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```

Expected: alle Tests grün (22 alte aus test_fetch_trains + 6 neue aus test_layout = 28).

- [ ] **Step 5: Commit**

```bash
git add scripts/_layout_logic.py tests/test_layout.py
git commit -m "Multi-Column v2: distribute_blocks → Greedy-Fit (Block-Reihenfolge erhalten)"
```

---

## Task 2: `config.env` Variable + `<script>` mit Compact-Schwelle

**Files:**
- Modify: `config.env.example`
- Modify: `scripts/fetch_untis.py`

- [ ] **Step 1: `config.env.example` erweitern**

Am Ende von `config.env.example` ergänzen:

```
# Compact-Mode: ab welcher Spaltenbreite (in Pixel) die Art-Badges
# rund werden und "Aufsicht" auf "Aufs." gekürzt wird. Default: 320.
COMPACT_COL_WIDTH_PX=320
```

- [ ] **Step 2: `main()` in `fetch_untis.py` — Wert aus config lesen**

In `scripts/fetch_untis.py` finde den Aufruf von `generate_html` (in `main()`).
Vor dem Aufruf ergänzen:

```python
        try:
            compact_col_width = int(config.get("COMPACT_COL_WIDTH_PX", "320"))
        except ValueError:
            compact_col_width = 320
```

Den `generate_html`-Call erweitern um:
```python
            compact_col_width=compact_col_width,
```

- [ ] **Step 3: `generate_html`-Signatur ergänzen**

Aktuell etwa:
```python
def generate_html(groups_today, groups_tomorrow, today_date, tomorrow_date,
                  teacher_lookup, period_nr, period_start, period_end,
                  show_logo=False, import_time=None, train_enabled=False,
                  today_classes_override=None, tomorrow_classes_override=None):
```

Erweitern um `compact_col_width=320`:
```python
def generate_html(groups_today, groups_tomorrow, today_date, tomorrow_date,
                  teacher_lookup, period_nr, period_start, period_end,
                  show_logo=False, import_time=None, train_enabled=False,
                  today_classes_override=None, tomorrow_classes_override=None,
                  compact_col_width=320):
```

- [ ] **Step 4: Im HTML-Template `<script>` mit `window.COMPACT_COL_WIDTH` einfügen**

In `generate_html` im HTML-Template finde den `<head>`-Block (suche nach `<link rel="apple-touch-icon" href="logo.png">`). Direkt vor `</head>` einfügen:

```python
    <script>window.COMPACT_COL_WIDTH = {compact_col_width};</script>
```

Da `compact_col_width` ein int ist, kann er direkt in den f-string interpoliert werden.

- [ ] **Step 5: Sanity-Run**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```
Expected: läuft durch.

Verifizieren:
```bash
grep -c "window.COMPACT_COL_WIDTH" /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
```
Expected: `1`

- [ ] **Step 6: Tests laufen lassen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: 28 grün.

- [ ] **Step 7: Commit**

```bash
git add config.env.example scripts/fetch_untis.py
git commit -m "Multi-Column v2: COMPACT_COL_WIDTH_PX aus config.env, ins HTML als JS-Konstante"
```

---

## Task 3: `render_row` — `fach-full` + `fach-short` Spans

**Files:**
- Modify: `scripts/fetch_untis.py`

- [ ] **Step 1: Helper-Funktion einfügen**

In `scripts/fetch_untis.py` direkt vor `def render_row(r):` einfügen:

```python
def _fach_html(fach: str) -> str:
    """Liefert Fach mit Lang- und Kurz-Variante.
    Kurzform für 'Aufsicht' → 'Aufs.', sonst gleich."""
    short = "Aufs." if fach == "Aufsicht" else fach
    return (
        f'<span class="fach-full">{esc(fach)}</span>'
        f'<span class="fach-short">{esc(short)}</span>'
    )
```

- [ ] **Step 2: `render_row` anpassen**

In `render_row` finde:
```python
        f'<td class="c-fach">{esc(r["fach"])}</td>'
```

Ersetzen durch:
```python
        f'<td class="c-fach">{_fach_html(r["fach"])}</td>'
```

- [ ] **Step 3: Sanity-Run**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```

Verifizieren:
```bash
grep -c "fach-short" /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
```
Expected: > 0 (eine pro Tabellenzeile)

```bash
grep -c "fach-short\">Aufs\." /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
```
Expected: > 0 wenn Pausenaufsichten im Plan sind, sonst 0 (beides OK).

- [ ] **Step 4: Tests**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: 28 grün.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "Multi-Column v2: render_row schreibt fach-full/fach-short Spans (Aufsicht → Aufs.)"
```

---

## Task 4: Plan-Tag mit `tag-full` + `tag-short` Spans (Mobile-Wochentag-Kurzform)

**Files:**
- Modify: `scripts/fetch_untis.py`

- [ ] **Step 1: Wochentag-Kurzformen-Konstante**

In `scripts/fetch_untis.py` neben `WEEKDAYS` (sollte etwa Zeile 320 sein, oben in der Datei) ergänzen:

```python
WEEKDAYS_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
```

- [ ] **Step 2: Plan-Tag-Logik in `generate_html` anpassen**

In `generate_html` finde die Stelle, wo `day_label` (für die `tomorrow-only`-Anzeige im Plan-Tag) gebaut wird:

```python
        date_str_tom = (
            f"{WEEKDAYS[tomorrow_date.weekday()]}, "
            f"{tomorrow_date.day}. {MONTHS[tomorrow_date.month-1]} {tomorrow_date.year}"
        )
        if days_ahead == 1:
            day_label = f"Morgen · {date_str_tom}"
        else:
            day_label = f"Nächster Schultag · {date_str_tom}"
```

Direkt darunter (vor `if not show_today: tomorrow_only_label = day_label`) Kurzform vorbereiten:

```python
        date_str_tom_short = (
            f"{WEEKDAYS_SHORT[tomorrow_date.weekday()]}, "
            f"{tomorrow_date.day}. {MONTHS[tomorrow_date.month-1]} {tomorrow_date.year}"
        )
        if days_ahead == 1:
            day_label_short = f"Morgen · {date_str_tom_short}"
        else:
            day_label_short = f"Nä. Schultag · {date_str_tom_short}"
```

- [ ] **Step 3: `tomorrow_only_label` wird zur Markup-Variante**

Finde:
```python
        if not show_today:
            tomorrow_only_label = day_label
```

Ersetzen durch:
```python
        if not show_today:
            tomorrow_only_label_full  = day_label
            tomorrow_only_label_short = day_label_short
        else:
            tomorrow_only_label_full  = ""
            tomorrow_only_label_short = ""
```

(Variable umbenennen: aus `tomorrow_only_label` werden zwei Variablen.)

- [ ] **Step 4: `plan_tag_html`-Block anpassen**

Suche im Code nach:
```python
    if tomorrow_only_label:
        plan_tag_html = f'<span class="plan-tag tomorrow-only">{esc(tomorrow_only_label)}</span>'
    else:
        plan_tag_html = '<span class="plan-tag">Heute</span>'
```

Ersetzen durch:
```python
    if tomorrow_only_label_full:
        plan_tag_html = (
            f'<span class="plan-tag tomorrow-only">'
            f'<span class="tag-full">{esc(tomorrow_only_label_full)}</span>'
            f'<span class="tag-short">{esc(tomorrow_only_label_short)}</span>'
            f'</span>'
        )
    else:
        plan_tag_html = '<span class="plan-tag">Heute</span>'
```

- [ ] **Step 5: Sanity-Run**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```

Verifizieren (nur sichtbar wenn nur Morgen angezeigt wird):
```bash
grep -c "tag-short" /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
```
Expected: `0` (wenn heute Inhalt da) oder `1` (wenn nur Morgen sichtbar). Beides OK.

- [ ] **Step 6: Tests**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: 28 grün.

- [ ] **Step 7: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "Multi-Column v2: Plan-Tag tag-full/tag-short Spans für Mobile-Wochentag-Kurzform"
```

---

## Task 5: JS Layout-Engine — Greedy-Fit + Compact-Mode-Detection

**Files:**
- Modify: `scripts/fetch_untis.py`

- [ ] **Step 1: Layout-Engine-Block ersetzen**

In `scripts/fetch_untis.py` finde den `// ── Multi-Column Layout-Engine ──`-Block in der inline JS.

Den **kompletten** Block (vom Kommentar bis `}})();` direkt davor) ersetzen durch:

```python
// ── Multi-Column Layout-Engine v2 ──
(function () {{
    var MIN_COL_WIDTH = 280;  // für Spaltenzahl-Berechnung
    var MAX_COLS = 4;

    function getBlocks(wrapper) {{
        return Array.prototype.slice.call(
            wrapper.querySelectorAll('tbody[data-block]')
        );
    }}

    function chooseColCount(wrapper, blocks, availablePerCol) {{
        if (availablePerCol <= 0) return 1;
        var total = 0;
        for (var i = 0; i < blocks.length; i++) {{
            total += blocks[i].getBoundingClientRect().height;
        }}
        var byHeight = Math.max(1, Math.ceil(total / availablePerCol));
        var byWidth  = Math.max(1, Math.floor(wrapper.clientWidth / MIN_COL_WIDTH));
        return Math.min(MAX_COLS, byHeight, byWidth);
    }}

    function distributeGreedy(blocks, cols, availablePerCol) {{
        var buckets = [];
        for (var i = 0; i < cols; i++) buckets.push([]);

        var regular = [];
        var cancels = [];
        for (var j = 0; j < blocks.length; j++) {{
            if (blocks[j].getAttribute('data-block') === 'cancel') {{
                cancels.push(blocks[j]);
            }} else {{
                regular.push(blocks[j]);
            }}
        }}

        var currentCol = 0;
        var currentHeight = 0;
        for (var k = 0; k < regular.length; k++) {{
            var b = regular[k];
            var h = b.getBoundingClientRect().height;
            if (currentHeight + h > availablePerCol
                    && currentCol < cols - 1
                    && buckets[currentCol].length > 0) {{
                currentCol++;
                currentHeight = 0;
            }}
            buckets[currentCol].push(b);
            currentHeight += h;
        }}

        for (var l = 0; l < cancels.length; l++) {{
            buckets[cols - 1].push(cancels[l]);
        }}

        return buckets;
    }}

    function applyLayout(wrapper) {{
        var blocks = getBlocks(wrapper);
        if (blocks.length === 0) return;

        var tableWrap = wrapper.closest('.table-wrap');
        if (!tableWrap) return;
        var sectionCount = tableWrap.querySelectorAll('.plan-section').length || 1;
        var availablePerCol = Math.floor(tableWrap.clientHeight / sectionCount) - 60;
        if (availablePerCol < 100) availablePerCol = 100;

        // Reset für saubere Messung mit 1-Spalten-Layout
        wrapper.classList.remove('cols-1','cols-2','cols-3','cols-4');
        wrapper.classList.remove('compact-mode');
        wrapper.classList.add('cols-1');

        var cols = chooseColCount(wrapper, blocks, availablePerCol);

        // Early-Return: schon 1-spaltig und cols=1 → fertig (bis auf compact-Check)
        if (cols === 1 && wrapper.querySelectorAll('.col').length === 1) {{
            var firstCol1 = wrapper.querySelector('.col');
            if (firstCol1 && firstCol1.clientWidth < (window.COMPACT_COL_WIDTH || 320)) {{
                wrapper.classList.add('compact-mode');
            }}
            return;
        }}

        wrapper.classList.remove('cols-1');
        wrapper.classList.add('cols-' + cols);

        var origTable    = wrapper.querySelector('table');
        if (!origTable) return;
        var origColgroup = origTable.querySelector('colgroup');
        var origThead    = origTable.querySelector('thead');

        var buckets = distributeGreedy(blocks, cols, availablePerCol);

        // Container leeren und N neue Spalten/Tables anlegen
        wrapper.innerHTML = '';
        for (var c = 0; c < cols; c++) {{
            var colDiv = document.createElement('div');
            colDiv.className = 'col';
            var table = document.createElement('table');
            if (origColgroup) table.appendChild(origColgroup.cloneNode(true));
            if (origThead)    table.appendChild(origThead.cloneNode(true));
            for (var m = 0; m < buckets[c].length; m++) {{
                table.appendChild(buckets[c][m]);
            }}
            colDiv.appendChild(table);
            wrapper.appendChild(colDiv);
        }}

        // Compact-Mode prüfen nach Spalten-Build
        var firstCol = wrapper.querySelector('.col');
        if (firstCol && firstCol.clientWidth < (window.COMPACT_COL_WIDTH || 320)) {{
            wrapper.classList.add('compact-mode');
        }}
    }}

    function layoutAll() {{
        var wrappers = document.querySelectorAll('.layout-wrapper');
        for (var i = 0; i < wrappers.length; i++) {{
            applyLayout(wrappers[i]);
        }}
    }}

    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', layoutAll);
    }} else {{
        layoutAll();
    }}

    var resizeTimer = null;
    window.addEventListener('resize', function () {{
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(layoutAll, 250);
    }});
}})();
```

WICHTIG: alle `{` und `}` müssen verdoppelt sein (`{{` und `}}`), weil im Python-f-string. Der Code oben ist schon korrekt escaped.

- [ ] **Step 2: Sanity-Run**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```

Expected: läuft durch (f-string-Render OK).

Verifizieren:
```bash
grep -c "distributeGreedy" /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
grep -c "compact-mode" /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
```
Expected: > 0 für beide.

- [ ] **Step 3: Tests**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: 28 grün.

- [ ] **Step 4: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "Multi-Column v2: JS-Engine auf Greedy-Fit + breite-basierten Compact-Mode"
```

---

## Task 6: CSS — `.compact-mode` Regeln, Spalten-Breiten, Default-Versteck von `*-short`

**Files:**
- Modify: `css/style.css`

- [ ] **Step 1: Alte `.cols-3`/`.cols-4`-Badge-Regeln entfernen**

In `css/style.css` finde den Block (vermutlich am Ende, „Adaptive Badge-Form"):

```css
/* ── Adaptive Badge-Form (Lang ↔ Kurz) ─────────────────── */
.badge-short { display: none; }

.layout-wrapper.cols-3 .badge-full,
.layout-wrapper.cols-4 .badge-full {
    display: none;
}

.layout-wrapper.cols-3 .badge-short,
.layout-wrapper.cols-4 .badge-short {
    display: inline-flex;
}

.layout-wrapper.cols-3 .badge,
.layout-wrapper.cols-4 .badge {
    width: 20px;
    height: 20px;
    padding: 0;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    line-height: 1;
}
```

Diesen Block **komplett ersetzen** durch:

```css
/* ── Compact-Mode (breite-basiert via JS) ───────────────── */
.badge-short  { display: none; }
.fach-short   { display: none; }
.tag-short    { display: none; }

.layout-wrapper.compact-mode .badge-full { display: none; }
.layout-wrapper.compact-mode .badge-short { display: inline-flex; }
.layout-wrapper.compact-mode .fach-full { display: none; }
.layout-wrapper.compact-mode .fach-short { display: inline; }

.layout-wrapper.compact-mode .badge {
    width: 20px;
    height: 20px;
    padding: 0;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    line-height: 1;
}

/* Compact-Mode: Spalten-Breiten umverteilt */
.layout-wrapper.compact-mode col.c-std     { width: 7%;  }
.layout-wrapper.compact-mode col.c-fach    { width: 14%; }
.layout-wrapper.compact-mode col.c-klasse  { width: 10%; }
.layout-wrapper.compact-mode col.c-lehrer  { width: 24%; }
.layout-wrapper.compact-mode col.c-art     { width: 5%;  }
.layout-wrapper.compact-mode col.c-raum    { width: 13%; }
.layout-wrapper.compact-mode col.c-text    { width: 24%; }
```

- [ ] **Step 2: Sanity-Run**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```
Expected: läuft durch.

Im Browser `index.html` aufrufen — sollte normal aussehen, lange Labels (`Vertr.`, `Aufsicht`).

Browser-Test mit Compact-Mode:
1. DevTools öffnen → Elements
2. Auf `.layout-wrapper` die Klasse `compact-mode` manuell hinzufügen
3. Spalten-Layout sollte: Badges rund, Aufsicht → Aufs., Raum-Spalte breiter

- [ ] **Step 3: Tests**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: 28 grün.

- [ ] **Step 4: Commit**

```bash
git add css/style.css
git commit -m "Multi-Column v2: CSS .compact-mode Regeln (Badges, Aufs., Spalten-Breiten)"
```

---

## Task 7: CSS — Mobile-Header (`@media (max-width: 600px)`)

**Files:**
- Modify: `css/style.css`

- [ ] **Step 1: Mobile-Media-Query am Ende von `css/style.css` ergänzen**

Komplett am Dateiende anfügen:

```css
/* ── Mobile-Layout (< 600px) ────────────────────────────── */
@media (max-width: 600px) {
    :root {
        --h-header: 60px;
    }

    /* Header reduzieren */
    .logo,
    .school-name,
    .school-sub,
    .clock-date,
    .clock-time,
    .period-label,
    .legend,
    .day-title-bar {
        display: none !important;
    }

    /* Header-Layout: Train links, Period rechts */
    .header {
        padding: 0 12px;
    }
    .header-left {
        gap: 0;
    }
    .train-widget {
        flex: 1 1 auto;
        margin: 0 12px 0 0;
        max-width: none;
    }
    .header-right {
        gap: 8px;
    }
    .period-value {
        font-size: 16px;
    }
    .period-time {
        font-size: 11px;
    }

    /* Plan-Tag Kurzform aktivieren */
    .plan-tag .tag-full  { display: none; }
    .plan-tag .tag-short { display: inline; }
    .plan-tag {
        font-size: 11px;
        white-space: nowrap;
    }

    /* Sub-Header (mit Plan-Tag) kompakter */
    .plan-header {
        padding: 0 12px;
        gap: 8px;
    }

    /* Tabellen-Padding reduzieren */
    .table-wrap {
        padding: 8px 12px;
    }

    /* Tabellen-Text etwas kleiner */
    tbody td {
        font-size: 12px;
        padding: 2px 6px;
    }
}
```

- [ ] **Step 2: Sanity-Run**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```
Expected: läuft durch.

- [ ] **Step 3: Browser-Test mit DevTools-Device-Toolbar**

1. Browser öffnen: `index.html`
2. DevTools (F12) → Device-Toolbar aktivieren (Strg+Shift+M oder Cmd+Shift+M)
3. Device wählen: „iPhone SE" (375 × 667) oder ähnlich < 600px
4. Erwartung:
   - Logo, Schulname/Subtitle, Uhrzeit, Datum, Legende **alle weg**
   - Train-Widget links, kompakte Period-Anzeige rechts
   - Plan-Tag wenn vorhanden: Wochentag-Kurzform („Mo, 1. Juni 2026")
   - Tabelle in 1 Spalte mit Compact-Mode (runde Badges, Aufs.)

- [ ] **Step 4: Tests**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: 28 grün.

- [ ] **Step 5: Commit**

```bash
git add css/style.css
git commit -m "Multi-Column v2: Mobile-Layout für <600px (reduzierter Header, Train links)"
```

---

## Task 8: End-to-End Browser-Test (manuell)

**Files:** keine — nur Tests

- [ ] **Step 1: Webserver starten**

```bash
/mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m http.server 8000
```

- [ ] **Step 2: Desktop-Test (1920×1080 oder ähnlich)**

`http://localhost:8000` öffnen.
- Wenige Lehrer (~5) → 1 Spalte, keine Compact-Mode (Spalten-Breite > 320)
- Heute leer + Morgen voll → 1 Spalte, breit, normaler Look

- [ ] **Step 3: Multi-Column-Test**

In DevTools Console:
```javascript
// Erzwingen: cols-3 ohne Re-Layout
document.querySelectorAll('.layout-wrapper').forEach(w => {
    w.classList.remove('cols-1');
    w.classList.add('cols-3');
});
```

Sieht: 3-Spalten-Layout (auch wenn Inhalt eigentlich nicht so viel war).

Reset via Reload.

- [ ] **Step 4: Compact-Mode-Test**

Browser-Fenster verkleinern (oder DevTools Width-Slider auf ~960px setzen). Bei 3 Spalten à ~280px sollte `.compact-mode` automatisch greifen → Badges rund, Aufsicht → Aufs.

- [ ] **Step 5: Mobile-Test**

DevTools Device-Toolbar → 375×667 oder 360×640.
- Erwartung wie in Task 7 Step 3.

- [ ] **Step 6: Konfigurations-Test**

In `config.env` testweise `COMPACT_COL_WIDTH_PX=500` setzen.
Skript ausführen → HTML neu generieren → Browser-Reload.
- Erwartung: Compact-Mode greift jetzt bei viel größeren Spaltenbreiten (sogar bei 1 Spalte am Desktop).

Zurücksetzen auf 320.

- [ ] **Step 7: Webserver stoppen**

`Ctrl+C` im Terminal mit dem Webserver.

Keine Commit nötig (manueller Test).

---

## Task 9: CLAUDE.md aktualisieren

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Bestehende Multi-Column-Sektion finden**

```bash
grep -n "Multi-Column-Layout" CLAUDE.md
```

- [ ] **Step 2: Sektion erweitern**

Suche die Sektion `### Multi-Column-Layout (Browser-seitig)` (sollte ca. 6 Zeilen lang sein) und ergänze am Ende:

```markdown

**Verteilung:** Block-Reihenfolge + Greedy-Fit. Lehrer in alphabetischer Reihenfolge,
aktuelle Spalte füllen bis Höhe-Limit, dann nächste Spalte. Lesefluss oben-links →
unten-links → oben-rechts → unten-rechts.

**Compact-Mode** (Badges rund, „Aufsicht" → „Aufs.", Raum-Spalte breiter) wird
breite-basiert getriggert: wenn die tatsächliche Spaltenbreite kleiner ist als
`COMPACT_COL_WIDTH_PX` (Default 320, konfigurierbar in `config.env`). Greift damit
sowohl bei 3–4 Spalten am Desktop als auch in der Mobilansicht.

**Mobile-Layout** (`@media (max-width: 600px)`): Logo, Schulname, Uhr, Datum,
Legende werden ausgeblendet. Train-Widget rückt an den linken Rand, Plan-Tag
zeigt Wochentag-Kurzform („Mo" statt „Montag").
```

- [ ] **Step 3: Konfiguration-Sektion auch ergänzen (falls vorhanden)**

```bash
grep -n "COMPACT_COL_WIDTH" CLAUDE.md
```

Wenn schon im Doku-Block: ok. Wenn nicht: in der Sektion mit den `config.env`-
Variablen ergänzen (suche `TRAIN_PRODUCTS` als Anker):

```markdown
- `COMPACT_COL_WIDTH_PX` (Default 320): Schwelle für Badge-Rundung + Aufs.-Kürzung
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "Multi-Column v2: CLAUDE.md aktualisiert (Greedy-Fit, Compact-Mode, Mobile)"
```

---

## Task 10: Branch pushen + Final-Review

**Files:** keine

- [ ] **Step 1: Alle Tests final**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: 28 grün (22 alte + 6 neue).

- [ ] **Step 2: Branch pushen**

```bash
git push
```

- [ ] **Step 3: Notiz für Deployment**

Branch ist `feature/multi-column-layout` (Fortsetzung des v1-Branches). Wenn der User mergt, sollte er einmal:
- `config.env` auf dem LXC ergänzen: `COMPACT_COL_WIDTH_PX=320` (Default-Verhalten ohne Änderung)
- rsync deployen
- Cron läuft das nächste Mal mit dem neuen Layout

---

## Test-Strategie

**Automatisiert** (`tests/test_layout.py`):
- 6 Tests für `distribute_blocks` (Greedy-Fit, Cancel, Übergrößen, leer)

**Manuell** (Browser):
- Desktop verschiedener Breiten: Compact-Mode-Trigger
- DevTools Device-Toolbar: Mobile-Header
- `config.env` mit verschiedenen `COMPACT_COL_WIDTH_PX`-Werten

---

## Risiken & Mitigation (übernommen aus Spec)

1. **Greedy-Fit kann letzte Spalte überlaufen lassen**, wenn alle Spalten voll sind
   und noch Lehrer kommen → akzeptiert; Lesefluss > Balance.
2. **Compact-Mode flackert bei Resize** → ResizeObserver 250ms Debounce.
3. **Mobile-Test nur in DevTools** → User testet auf echtem Smartphone vor finalem
   Merge.
