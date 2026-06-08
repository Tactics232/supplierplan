# Überlauf-Strategie Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wenn der Supplierplan zu voll für den Monitor ist, wird er gestuft (Skalieren→Reduzieren→Blättern) angepasst statt unten abgeschnitten; jede Stufe ist einzeln in `config.env` schaltbar, „Morgen" bleibt immer sichtbar.

**Architecture:** Die deterministische Entscheidungslogik (Skalierungsfaktor, Seiten-Aufteilung) liegt testbar in `scripts/_layout_logic.py`. Die bestehende Browser-JS-Layout-Engine in `scripts/fetch_untis.py` ruft dieselbe Logik nach der Spaltenverteilung auf und wendet sie via CSS-Variable (`--ov-scale`), Reduktions-Klassen und Seiten-Rotation auf das DOM an. Config wird wie `COMPACT_COL_WIDTH` als `window.OVERFLOW` ins HTML injiziert.

**Tech Stack:** Python 3 (stdlib, `unittest`), eingebettetes Vanilla-JS, CSS Custom Properties. Test-Runner: `python3 -m unittest`.

**Referenz-Spec:** `docs/superpowers/specs/2026-06-08-overflow-strategie-design.md`

---

## Dateien-Übersicht

- `scripts/_layout_logic.py` — **erweitern**: reine Funktionen `fit_scale`, `distribute_uncapped`, `paginate_columns` (testbarer Mirror).
- `tests/test_overflow.py` — **neu**: Unit-Tests für die drei Funktionen.
- `scripts/fetch_untis.py` — **ändern**: `parse_overflow_config()` (Python), Injektion `window.OVERFLOW`, Umbau der JS-`applyLayout`-Pipeline (Skalieren/Reduzieren/Blättern), kompakte Entfall-Liste.
- `tests/test_overflow_config.py` — **neu**: Unit-Tests für `parse_overflow_config`.
- `css/style.css` — **ändern**: skalierbare Schrift/Paddings via `--ov-scale`, `.reduce-text`/`.reduce-cancel`-Klassen, Seitenindikator `.ov-pageind`.
- `config.env.example`, `CLAUDE.md`, `README.md` — **ändern**: neue Keys dokumentieren.

Reihenfolge: erst die reine Logik + Tests (Tasks 1–3), dann Config (Task 4), dann CSS (Task 5), dann die JS-Engine (Tasks 6–8), dann Doku (Task 9).

---

## Task 1: Reine Skalierungs-Logik `fit_scale`

**Files:**
- Test: `tests/test_overflow.py`
- Modify: `scripts/_layout_logic.py`

- [ ] **Step 1: Failing test schreiben**

Erstelle `tests/test_overflow.py`:

```python
import unittest

from scripts._layout_logic import fit_scale


class TestFitScale(unittest.TestCase):
    def test_passt_ohne_skalierung(self):
        # Inhalt kleiner als verfügbar → Faktor 1.0
        self.assertEqual(fit_scale(100, 200, 0.65), 1.0)

    def test_exakt_passend_bleibt_1(self):
        self.assertEqual(fit_scale(100, 100, 0.65), 1.0)

    def test_skaliert_auf_groessten_passenden_faktor(self):
        # 120 muss in 100 passen → größter Schritt-Faktor mit 120*s <= 100
        # 0.85*120=102 (zu groß), 0.80*120=96 (passt) → 0.80
        self.assertEqual(fit_scale(120, 100, 0.6), 0.80)

    def test_geht_nicht_unter_min(self):
        # 200 in 100 passt selbst bei min nicht → gib min zurück
        self.assertEqual(fit_scale(200, 100, 0.65), 0.65)

    def test_available_null_gibt_min(self):
        self.assertEqual(fit_scale(100, 0, 0.65), 0.65)

    def test_leerer_inhalt_bleibt_1(self):
        self.assertEqual(fit_scale(0, 100, 0.65), 1.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen (muss fehlschlagen)**

Run: `python3 -m unittest tests.test_overflow -v`
Expected: FAIL mit `ImportError: cannot import name 'fit_scale'`

- [ ] **Step 3: `fit_scale` implementieren**

In `scripts/_layout_logic.py` am Dateiende anhängen:

```python
def fit_scale(content_height, available_height, scale_min, step=0.05):
    """Größter Skalierungsfaktor in {1.0, 1-step, ...} >= scale_min, bei dem
    content_height * faktor <= available_height. Passt es schon bei 1.0, kommt
    1.0 zurück; passt es selbst bei scale_min nicht, kommt scale_min zurück."""
    if content_height <= 0 or content_height <= available_height:
        return 1.0
    if available_height <= 0:
        return round(scale_min, 4)
    steps = int(round((1.0 - scale_min) / step))
    for i in range(steps + 1):
        s = round(1.0 - i * step, 4)
        if content_height * s <= available_height:
            return s
    return round(scale_min, 4)
```

- [ ] **Step 4: Test laufen lassen (muss bestehen)**

Run: `python3 -m unittest tests.test_overflow -v`
Expected: PASS (6 Tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/_layout_logic.py tests/test_overflow.py
git commit -m "feat(overflow): reine fit_scale-Logik + Tests"
```

---

## Task 2: Spalten ohne Obergrenze verteilen `distribute_uncapped`

**Files:**
- Modify: `scripts/_layout_logic.py`
- Modify: `tests/test_overflow.py`

- [ ] **Step 1: Failing test ergänzen**

In `tests/test_overflow.py` vor `if __name__` einfügen:

```python
from scripts._layout_logic import distribute_uncapped


class TestDistributeUncapped(unittest.TestCase):
    def test_alles_in_eine_spalte(self):
        # 3 Blöcke à 30, Budget 100 → passen alle in Spalte 0
        self.assertEqual(distribute_uncapped([30, 30, 30], 100), [[0, 1, 2]])

    def test_umbruch_an_budgetgrenze(self):
        # 60+60 > 100 → zweite Spalte
        self.assertEqual(distribute_uncapped([60, 60, 30], 100), [[0], [1, 2]])

    def test_uebergrosser_block_bekommt_eigene_spalte(self):
        # 150 > 100, aber Spalte leer → kommt rein; nächster bricht um
        self.assertEqual(distribute_uncapped([150, 40], 100), [[0], [1]])

    def test_leere_eingabe(self):
        self.assertEqual(distribute_uncapped([], 100), [[]])
```

- [ ] **Step 2: Test laufen lassen (muss fehlschlagen)**

Run: `python3 -m unittest tests.test_overflow -v`
Expected: FAIL mit `ImportError: cannot import name 'distribute_uncapped'`

- [ ] **Step 3: `distribute_uncapped` implementieren**

In `scripts/_layout_logic.py` anhängen:

```python
def distribute_uncapped(block_heights, available_height_per_col):
    """Greedy-Verteilung in BELIEBIG viele Spalten (kein MAX_COLS-Limit).
    Gibt eine Liste von Spalten zurück, jede Spalte eine Liste von Block-Indizes.
    Ein übergroßer Block bekommt eine eigene Spalte (kein Überspringen)."""
    cols = [[]]
    h = 0
    for i, bh in enumerate(block_heights):
        if cols[-1] and h + bh > available_height_per_col:
            cols.append([])
            h = 0
        cols[-1].append(i)
        h += bh
    return cols
```

- [ ] **Step 4: Test laufen lassen (muss bestehen)**

Run: `python3 -m unittest tests.test_overflow -v`
Expected: PASS (10 Tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/_layout_logic.py tests/test_overflow.py
git commit -m "feat(overflow): distribute_uncapped + Tests"
```

---

## Task 3: Spalten in Seiten chunken `paginate_columns`

**Files:**
- Modify: `scripts/_layout_logic.py`
- Modify: `tests/test_overflow.py`

- [ ] **Step 1: Failing test ergänzen**

In `tests/test_overflow.py` vor `if __name__` einfügen:

```python
from scripts._layout_logic import paginate_columns


class TestPaginateColumns(unittest.TestCase):
    def test_passt_in_eine_seite(self):
        cols = [[0], [1], [2]]
        self.assertEqual(paginate_columns(cols, 4), [[[0], [1], [2]]])

    def test_chunkt_in_seiten_zu_max_cols(self):
        cols = [[0], [1], [2], [3], [4]]
        # max 2 Spalten/Seite → 3 Seiten (2,2,1)
        self.assertEqual(
            paginate_columns(cols, 2),
            [[[0], [1]], [[2], [3]], [[4]]],
        )

    def test_max_cols_unter_eins_wird_eins(self):
        self.assertEqual(paginate_columns([[0], [1]], 0), [[[0]], [[1]]])
```

- [ ] **Step 2: Test laufen lassen (muss fehlschlagen)**

Run: `python3 -m unittest tests.test_overflow -v`
Expected: FAIL mit `ImportError: cannot import name 'paginate_columns'`

- [ ] **Step 3: `paginate_columns` implementieren**

In `scripts/_layout_logic.py` anhängen:

```python
def paginate_columns(columns, max_cols):
    """Teilt eine Liste von Spalten in Seiten zu je höchstens max_cols Spalten."""
    if max_cols < 1:
        max_cols = 1
    return [columns[i:i + max_cols] for i in range(0, len(columns), max_cols)]
```

- [ ] **Step 4: Test laufen lassen (muss bestehen)**

Run: `python3 -m unittest tests.test_overflow -v`
Expected: PASS (13 Tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/_layout_logic.py tests/test_overflow.py
git commit -m "feat(overflow): paginate_columns + Tests"
```

---

## Task 4: Config einlesen + als `window.OVERFLOW` injizieren

**Files:**
- Modify: `scripts/fetch_untis.py`
- Test: `tests/test_overflow_config.py`

- [ ] **Step 1: Failing test schreiben**

Erstelle `tests/test_overflow_config.py`:

```python
import unittest

from scripts.fetch_untis import parse_overflow_config


class TestParseOverflowConfig(unittest.TestCase):
    def test_defaults_wenn_leer(self):
        cfg = parse_overflow_config({})
        self.assertEqual(cfg, {
            "scale": True, "scale_min": 0.65,
            "reduce": True, "paginate": True, "page_seconds": 12,
        })

    def test_flags_aus(self):
        cfg = parse_overflow_config({
            "OVERFLOW_SCALE": "false",
            "OVERFLOW_REDUCE": "false",
            "OVERFLOW_PAGINATE": "false",
        })
        self.assertFalse(cfg["scale"])
        self.assertFalse(cfg["reduce"])
        self.assertFalse(cfg["paginate"])

    def test_scale_min_geklemmt(self):
        self.assertEqual(parse_overflow_config({"OVERFLOW_SCALE_MIN": "0.1"})["scale_min"], 0.3)
        self.assertEqual(parse_overflow_config({"OVERFLOW_SCALE_MIN": "2"})["scale_min"], 1.0)

    def test_scale_min_ungueltig_faellt_auf_default(self):
        self.assertEqual(parse_overflow_config({"OVERFLOW_SCALE_MIN": "abc"})["scale_min"], 0.65)

    def test_page_seconds_minimum(self):
        self.assertEqual(parse_overflow_config({"OVERFLOW_PAGE_SECONDS": "1"})["page_seconds"], 3)
        self.assertEqual(parse_overflow_config({"OVERFLOW_PAGE_SECONDS": "x"})["page_seconds"], 12)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen (muss fehlschlagen)**

Run: `python3 -m unittest tests.test_overflow_config -v`
Expected: FAIL mit `ImportError: cannot import name 'parse_overflow_config'`

- [ ] **Step 3: `parse_overflow_config` implementieren**

In `scripts/fetch_untis.py` direkt **vor** `def generate_html(` einfügen:

```python
def parse_overflow_config(config):
    """Liest die OVERFLOW_*-Keys aus config.env und liefert ein dict für die
    Injektion als window.OVERFLOW. Werte werden geklemmt; ungültige → Default."""
    def flag(key, default):
        v = config.get(key, "")
        if v == "":
            return default
        return v.strip().lower() == "true"

    try:
        smin = float(config.get("OVERFLOW_SCALE_MIN", "0.65"))
    except ValueError:
        smin = 0.65
    smin = min(1.0, max(0.3, smin))

    try:
        psec = int(config.get("OVERFLOW_PAGE_SECONDS", "12"))
    except ValueError:
        psec = 12
    psec = max(3, psec)

    return {
        "scale":        flag("OVERFLOW_SCALE", True),
        "scale_min":    round(smin, 4),
        "reduce":       flag("OVERFLOW_REDUCE", True),
        "paginate":     flag("OVERFLOW_PAGINATE", True),
        "page_seconds": psec,
    }
```

- [ ] **Step 4: Test laufen lassen (muss bestehen)**

Run: `python3 -m unittest tests.test_overflow_config -v`
Expected: PASS (5 Tests)

- [ ] **Step 5: `generate_html` um Parameter erweitern + Injektion**

In `scripts/fetch_untis.py` die Signatur von `generate_html(...)` ergänzen — nach
`today_full_absent=None, tomorrow_full_absent=None):` die letzte Zeile so ändern:

```python
                  today_full_absent=None, tomorrow_full_absent=None,
                  overflow_cfg=None):
```

Direkt nach dem Funktionskopf (erste Zeile im Body) einfügen:

```python
    overflow_cfg = overflow_cfg or parse_overflow_config({})
```

Die Injektions-Zeile im `<head>` (aktuell `<script>window.COMPACT_COL_WIDTH = {compact_col_width};</script>`) um eine zweite Zeile ergänzen:

```python
    <script>window.COMPACT_COL_WIDTH = {compact_col_width};</script>
    <script>window.OVERFLOW = {json.dumps(overflow_cfg)};</script>
```

- [ ] **Step 6: Aufrufstelle in `main()` versorgen**

In `main()` vor dem `html = generate_html(` einfügen:

```python
        overflow_cfg = parse_overflow_config(config)
```

und im `generate_html(`-Aufruf nach `tomorrow_full_absent=tomorrow_full_absent,` ergänzen:

```python
            overflow_cfg=overflow_cfg,
```

- [ ] **Step 7: Syntax + Smoke prüfen**

Run: `python3 -m py_compile scripts/fetch_untis.py && python3 -m unittest discover -s tests`
Expected: keine Fehler, alle Tests PASS

- [ ] **Step 8: Commit**

```bash
git add scripts/fetch_untis.py tests/test_overflow_config.py
git commit -m "feat(overflow): config einlesen + window.OVERFLOW injizieren"
```

---

## Task 5: CSS — Skalierungs-Variable, Reduktions-Klassen, Seitenindikator

**Files:**
- Modify: `css/style.css`

- [ ] **Step 1: Skalierbare Schrift/Paddings einführen**

Ändere in `css/style.css` die folgenden Regeln so, dass höhenrelevante Werte mit
`var(--ov-scale, 1)` multipliziert werden (horizontale Paddings bleiben fix):

`tbody td` (aktuell `padding: 3px 10px; font-size: 13px;`) →
```css
tbody td {
    padding: calc(3px * var(--ov-scale, 1)) 10px;
    font-size: calc(13px * var(--ov-scale, 1));
}
```

`thead th` (aktuell `font-size: 10px; padding: 0 10px 6px;`) →
```css
thead th {
    font-size: calc(10px * var(--ov-scale, 1));
    padding: 0 10px calc(6px * var(--ov-scale, 1));
}
```
(die übrigen Eigenschaften der Regel unverändert lassen)

`tr.teacher-header td` (aktuell `padding: 10px 12px 7px;`) →
```css
tr.teacher-header td {
    background: var(--c-overlay);
    border-top: 1px solid var(--c-border);
    padding: calc(10px * var(--ov-scale, 1)) 12px calc(7px * var(--ov-scale, 1));
    border-left: none !important;
}
```

`tr.cancel-header td` (aktuell `padding: 7px 12px 7px;`) →
```css
tr.cancel-header td {
    background: rgba(255, 255, 255, 0.03);
    padding: calc(7px * var(--ov-scale, 1)) 12px;
    border-left: none !important;
}
```

- [ ] **Step 2: Reduktions-Klassen + Seitenindikator-Styling anhängen**

Am Ende von `css/style.css` anhängen:

```css
/* ── Überlauf-Reduktion ─────────────────────────────── */
/* Stufe 2a: Text-Spalte komplett ausblenden */
.layout-wrapper.reduce-text col.c-text,
.layout-wrapper.reduce-text th.c-text,
.layout-wrapper.reduce-text td.c-text {
    display: none;
}

/* Stufe 2b: Entfall-Sektion kompakt (kompakte Kürzel+Std-Liste) */
.layout-wrapper.reduce-cancel .ov-cancel-compact {
    font-size: calc(12px * var(--ov-scale, 1));
    line-height: 1.45;
    padding: 4px 12px 6px;
    color: var(--c-muted);
}
.layout-wrapper.reduce-cancel .ov-cancel-compact .occ-item {
    white-space: nowrap;
    margin-right: 10px;
}
.layout-wrapper.reduce-cancel .ov-cancel-compact .occ-k {
    text-decoration: line-through;
    color: var(--c-text);
}

/* ── Seitenindikator beim Blättern ──────────────────── */
.ov-pageind {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-d);
    font-size: 12px;
    color: var(--c-muted);
    padding: 2px 12px 6px;
}
.ov-pageind .ovp-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--c-border);
}
.ov-pageind .ovp-dot.active {
    background: var(--c-accent, #c8102e);
}
```

- [ ] **Step 3: Sichtprüfung (Skalierung bricht nichts an normalen Tagen)**

Run: `PYTHONIOENCODING=utf-8 python3 scripts/fetch_untis.py` (lokal) und `index.html`
im Browser öffnen.
Expected: Anzeige unverändert wie bisher (— `--ov-scale` ist 1, Reduktions-Klassen
sind nicht gesetzt; nur CSS vorhanden, noch nicht aktiviert).

- [ ] **Step 4: Commit**

```bash
git add css/style.css
git commit -m "feat(overflow): CSS für Skalierung, Reduktion, Seitenindikator"
```

---

## Task 6: JS-Engine — Überlauf-Erkennung + board-weite Skalierungs-Stufe

**Files:**
- Modify: `scripts/fetch_untis.py` (eingebetteter JS-Block „Multi-Column Layout-Engine v2", `applyLayout` + `layoutAll`)

Dieser Task baut `applyLayout` zu einer Pipeline um und macht die Skalierung
**board-weit** (ein Faktor für Heute UND Morgen, getrieben von der volleren Sektion —
laut Spec). Dafür berechnet `layoutAll` den Faktor in einem Mess-Vorlauf über alle
Wrapper und übergibt ihn an `applyLayout`. Die reine Logik aus `_layout_logic.py` wird
im JS gespiegelt. Verifikation visuell (eingebettetes Browser-JS).

- [ ] **Step 1: Hilfsfunktionen + JS-Spiegel der reinen Logik einfügen**

Im JS-Engine-IIFE (nach `var MAX_COLS = 4;`) einfügen:

```javascript
    var OV = window.OVERFLOW || {{
        scale: true, scale_min: 0.65, reduce: true, paginate: true, page_seconds: 12
    }};

    function sumHeights(blocks) {{
        var t = 0;
        for (var i = 0; i < blocks.length; i++) t += blocks[i].getBoundingClientRect().height;
        return t;
    }}

    // Spiegel von _layout_logic.fit_scale
    function fitScale(contentH, availH, scaleMin, step) {{
        step = step || 0.05;
        if (contentH <= 0 || contentH <= availH) return 1.0;
        if (availH <= 0) return scaleMin;
        var steps = Math.round((1.0 - scaleMin) / step);
        for (var i = 0; i <= steps; i++) {{
            var s = Math.round((1.0 - i * step) * 10000) / 10000;
            if (contentH * s <= availH) return s;
        }}
        return scaleMin;
    }}

    // Höhe der höchsten Spalte eines Bucket-Layouts (inkl. Cancel-Headerschätzung)
    function tallestBucketHeight(buckets) {{
        var max = 0;
        for (var c = 0; c < buckets.length; c++) {{
            var h = 0, hasCancel = false;
            for (var m = 0; m < buckets[c].length; m++) {{
                var b = buckets[c][m];
                h += b.getBoundingClientRect().height;
                if (b.getAttribute('data-block') === 'cancel' && !hasCancel) {{
                    h += CANCEL_HEADER_H; hasCancel = true;
                }}
            }}
            if (h > max) max = h;
        }}
        return max;
    }}

    // verfügbare Höhe pro Spalte — identisch in Mess- und Render-Pass nutzen
    function availFor(wrapper) {{
        var tableWrap = wrapper.closest('.table-wrap');
        if (!tableWrap) return 100;
        var sectionCount = tableWrap.querySelectorAll('.plan-section').length || 1;
        var a = Math.floor(tableWrap.clientHeight / sectionCount) - 60;
        return a < 100 ? 100 : a;
    }}

    // Mess-Vorlauf: welchen Skalierungsfaktor bräuchte diese Sektion, um in
    // MAX_COLS Spalten zu passen? (1.0 = kein Überlauf). Setzt den Wrapper auf
    // 1-Spalte ohne Skalierung, damit natürliche Höhen gemessen werden.
    function neededScale(wrapper) {{
        var blocks = getBlocks(wrapper);
        if (!blocks.length) return 1.0;
        wrapper.style.removeProperty('--ov-scale');
        wrapper.classList.remove('cols-2','cols-3','cols-4','compact-mode');
        wrapper.classList.add('cols-1');
        return fitScale(sumHeights(blocks), MAX_COLS * availFor(wrapper), OV.scale_min, 0.05);
    }}
```

- [ ] **Step 2: `applyLayout` auf Pipeline umbauen (Skalierung via Parameter)**

Ersetze die **gesamte** `function applyLayout(wrapper) {{ ... }}` durch:

```javascript
    function applyLayout(wrapper, boardScale) {{
        if (boardScale === undefined) boardScale = 1.0;
        // Reset aus vorherigem Lauf
        if (wrapper._ovTimer) {{ clearInterval(wrapper._ovTimer); wrapper._ovTimer = null; }}
        wrapper.style.removeProperty('--ov-scale');
        wrapper.classList.remove('reduce-text', 'reduce-cancel');
        var oldInd = wrapper.parentNode && wrapper.parentNode.querySelector('.ov-pageind');
        if (oldInd) oldInd.remove();

        var blocks = getBlocks(wrapper);
        if (blocks.length === 0) return;
        if (!wrapper.querySelector('table')) return;

        var availablePerCol = availFor(wrapper);

        // 1-Spalten-Reset für saubere Messung
        wrapper.classList.remove('cols-1','cols-2','cols-3','cols-4','compact-mode');
        wrapper.classList.add('cols-1');

        // Mobil (≤600px): Überlauf-Pipeline aus, altes Verhalten (Scroll)
        var isMobile = window.matchMedia('(max-width: 600px)').matches;

        // ── Stufe 1: Skalieren (board-weiter Faktor aus layoutAll) ──
        if (!isMobile && OV.scale && boardScale < 1.0) {{
            wrapper.style.setProperty('--ov-scale', boardScale);
        }}

        renderColumns(wrapper, blocks, availablePerCol, isMobile);
    }}
```

- [ ] **Step 3: `layoutAll` auf board-weiten Mess-Vorlauf umbauen**

Ersetze die **gesamte** `function layoutAll() {{ ... }}` durch:

```javascript
    function layoutAll() {{
        var wrappers = document.querySelectorAll('.layout-wrapper');
        var isMobile = window.matchMedia('(max-width: 600px)').matches;
        // Board-weiter Skalierungsfaktor: kleinster über alle Sektionen
        var boardScale = 1.0;
        if (!isMobile && OV.scale) {{
            for (var i = 0; i < wrappers.length; i++) {{
                var s = neededScale(wrappers[i]);
                if (s < boardScale) boardScale = s;
            }}
        }}
        for (var j = 0; j < wrappers.length; j++) {{
            applyLayout(wrappers[j], boardScale);
        }}
    }}
```

- [ ] **Step 4: Bestehenden Spalten-Build in `renderColumns` auslagern**

Füge **direkt nach** `applyLayout` eine neue Funktion `renderColumns` ein, die den
früheren Bau-Code (chooseColCount → distributeGreedy → DOM) enthält:

```javascript
    function renderColumns(wrapper, blocks, availablePerCol, isMobile) {{
        var cols = chooseColCount(wrapper, blocks, availablePerCol);
        wrapper.classList.remove('cols-1');
        wrapper.classList.add('cols-' + cols);

        var origTable = wrapper.querySelector('table');
        if (!origTable) return;
        var origColgroup = origTable.querySelector('colgroup');
        var origThead    = origTable.querySelector('thead');
        var ncols = origColgroup ? origColgroup.querySelectorAll('col').length : 8;
        var isTomorrow = !!wrapper.closest('.tomorrow-section');

        var buckets = distributeGreedy(blocks, cols, availablePerCol);

        wrapper.innerHTML = '';
        var cancelHeaderSeen = false;
        for (var c = 0; c < cols; c++) {{
            var colDiv = document.createElement('div');
            colDiv.className = 'col';
            var table = document.createElement('table');
            if (origColgroup) table.appendChild(origColgroup.cloneNode(true));
            if (origThead)    table.appendChild(origThead.cloneNode(true));
            var colCancelSeen = false;
            for (var m = 0; m < buckets[c].length; m++) {{
                var blk = buckets[c][m];
                if (blk.getAttribute('data-block') === 'cancel' && !colCancelSeen) {{
                    colCancelSeen = true;
                    table.appendChild(makeCancelHeader(ncols, cancelHeaderSeen, m > 0, isTomorrow));
                    cancelHeaderSeen = true;
                }}
                table.appendChild(blk);
            }}
            colDiv.appendChild(table);
            wrapper.appendChild(colDiv);
        }}

        var firstCol = wrapper.querySelector('.col');
        if (firstCol && firstCol.clientWidth < (window.COMPACT_COL_WIDTH || 320)) {{
            wrapper.classList.add('compact-mode');
        }}
    }}
```

- [ ] **Step 5: Sichtprüfung — Skalierung greift board-weit bei Überlauf, sonst nichts**

Run: `PYTHONIOENCODING=utf-8 python3 scripts/fetch_untis.py`, `index.html` öffnen.
Prüfen:
- Normaler Tag: unverändert (kein `--ov-scale` gesetzt, Layout wie zuvor).
- Browserfenster sehr niedrig ziehen → Schrift/Zeilen werden kleiner statt
  abgeschnitten (bis Mindestgröße 0.65), **Heute und Morgen gleich groß**.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "feat(overflow): board-weite JS-Pipeline mit Skalierungs-Stufe"
```

---

## Task 7: JS-Engine — Reduktions-Stufe (Text-Spalte + Entfall kompakt)

**Files:**
- Modify: `scripts/fetch_untis.py` (JS `applyLayout` + neue Helfer)

- [ ] **Step 1: Überlauf-Restcheck + Reduktion in `applyLayout` einfügen**

In `applyLayout`, **vor** der Zeile `renderColumns(wrapper, blocks, availablePerCol, isMobile);`,
einfügen:

```javascript
        // Hilfsmessung: läuft es bei aktueller cols-Verteilung noch über?
        function stillOverflows() {{
            var cols = chooseColCount(wrapper, blocks, availablePerCol);
            var buckets = distributeGreedy(blocks, cols, availablePerCol);
            return tallestBucketHeight(buckets) > availablePerCol && cols >= MAX_COLS;
        }}

        // ── Stufe 2: Reduzieren ──
        if (!isMobile && OV.reduce && stillOverflows()) {{
            wrapper.classList.add('reduce-text');         // 2a: Text-Spalte aus
            if (stillOverflows()) {{
                applyCancelCompact(wrapper);              // 2b: Entfall kompakt
                wrapper.classList.add('reduce-cancel');
                blocks = getBlocks(wrapper);             // Blockliste hat sich geändert
            }}
        }}
```

- [ ] **Step 2: `applyCancelCompact` implementieren**

Füge **nach** `renderColumns` ein:

```javascript
    // Wandelt alle einzelnen Cancel-Zeilen-Blöcke in EINEN kompakten Listenblock.
    // Liest Kürzel (c-lehrer) + Stunde (c-std) aus den vorhandenen Zeilen.
    function applyCancelCompact(wrapper) {{
        var cancelBlocks = Array.prototype.slice.call(
            wrapper.querySelectorAll('tbody[data-block="cancel"]')
        );
        if (cancelBlocks.length === 0) return;

        var items = [];
        for (var i = 0; i < cancelBlocks.length; i++) {{
            var row = cancelBlocks[i].querySelector('tr');
            if (!row) continue;
            var kEl = row.querySelector('.c-lehrer');
            var sEl = row.querySelector('.c-std');
            var k = kEl ? kEl.textContent.trim() : '';
            var s = sEl ? sEl.textContent.trim() : '';
            items.push({{ k: k, s: s }});
        }}

        // Neuen kompakten tbody-Block bauen (zählt als ein cancel-Block)
        var tb = document.createElement('tbody');
        tb.setAttribute('data-block', 'cancel');
        var tr = document.createElement('tr');
        var td = document.createElement('td');
        td.colSpan = 8;
        td.className = 'ov-cancel-compact';
        for (var j = 0; j < items.length; j++) {{
            var span = document.createElement('span');
            span.className = 'occ-item';
            var ks = document.createElement('span');
            ks.className = 'occ-k';
            ks.textContent = items[j].k;
            span.appendChild(ks);
            if (items[j].s) span.appendChild(document.createTextNode(' (' + items[j].s + ')'));
            td.appendChild(span);
        }}
        tr.appendChild(td);
        tb.appendChild(tr);

        // Alte Cancel-Blöcke ersetzen: ersten durch den kompakten, Rest entfernen
        cancelBlocks[0].parentNode.insertBefore(tb, cancelBlocks[0]);
        for (var d = 0; d < cancelBlocks.length; d++) cancelBlocks[d].remove();
    }}
```

- [ ] **Step 3: Sichtprüfung**

Run: `PYTHONIOENCODING=utf-8 python3 scripts/fetch_untis.py`, Browser sehr niedrig
ziehen, bis Skalierung am Minimum ist. Prüfen:
- Text-Spalte verschwindet, wenn Min-Skalierung nicht reicht.
- Bei weiterem Überlauf: „Entfallende Stunden" werden zur kompakten Kürzel-Liste.
- Morgen bleibt sichtbar.

- [ ] **Step 4: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "feat(overflow): Reduktions-Stufe (Text-Spalte aus, Entfall kompakt)"
```

---

## Task 8: JS-Engine — Blätter-Stufe (Pagination + Rotation + Indikator)

**Files:**
- Modify: `scripts/fetch_untis.py` (JS `applyLayout` + neue Helfer; nutzt
  `distribute_uncapped`/`paginate_columns`-Spiegel)

- [ ] **Step 1: JS-Spiegel von `distribute_uncapped` / `paginate_columns` einfügen**

Im JS-Engine-IIFE (z. B. nach `fitScale`) einfügen:

```javascript
    // Spiegel von _layout_logic.distribute_uncapped — arbeitet auf Block-Elementen
    function distributeUncapped(blocks, availH) {{
        var cols = [[]];
        var h = 0;
        for (var i = 0; i < blocks.length; i++) {{
            var bh = blocks[i].getBoundingClientRect().height;
            if (cols[cols.length - 1].length && h + bh > availH) {{ cols.push([]); h = 0; }}
            cols[cols.length - 1].push(blocks[i]);
            h += bh;
        }}
        return cols;
    }}

    // Spiegel von _layout_logic.paginate_columns
    function paginateColumns(cols, maxCols) {{
        if (maxCols < 1) maxCols = 1;
        var pages = [];
        for (var i = 0; i < cols.length; i += maxCols) pages.push(cols.slice(i, i + maxCols));
        return pages;
    }}
```

- [ ] **Step 2: Blätter-Zweig in `applyLayout` einfügen**

In `applyLayout`, die Zeile `renderColumns(wrapper, blocks, availablePerCol, isMobile);`
ersetzen durch:

```javascript
        // ── Stufe 3: Blättern ──
        if (!isMobile && OV.paginate && stillOverflows()) {{
            renderPaginated(wrapper, blocks, availablePerCol);
        }} else {{
            renderColumns(wrapper, blocks, availablePerCol, isMobile);
        }}
```

- [ ] **Step 3: `renderPaginated` implementieren**

Füge nach `applyCancelCompact` ein:

```javascript
    function renderPaginated(wrapper, blocks, availablePerCol) {{
        var origTable = wrapper.querySelector('table');
        if (!origTable) return;
        var origColgroup = origTable.querySelector('colgroup');
        var origThead    = origTable.querySelector('thead');
        var ncols = origColgroup ? origColgroup.querySelectorAll('col').length : 8;
        var isTomorrow = !!wrapper.closest('.tomorrow-section');

        var allCols = distributeUncapped(blocks, availablePerCol);
        var pages = paginateColumns(allCols, MAX_COLS);

        wrapper.classList.remove('cols-1');
        wrapper.classList.add('cols-' + MAX_COLS);

        // Seiten als getrennte .ov-page-Container bauen (alle im DOM, nur eine sichtbar)
        wrapper.innerHTML = '';
        var pageEls = [];
        var cancelHeaderSeen = false;
        for (var p = 0; p < pages.length; p++) {{
            var pageEl = document.createElement('div');
            pageEl.className = 'ov-page';
            pageEl.style.display = (p === 0 ? 'flex' : 'none');
            for (var c = 0; c < pages[p].length; c++) {{
                var colDiv = document.createElement('div');
                colDiv.className = 'col';
                var table = document.createElement('table');
                if (origColgroup) table.appendChild(origColgroup.cloneNode(true));
                if (origThead)    table.appendChild(origThead.cloneNode(true));
                var colCancelSeen = false;
                for (var m = 0; m < pages[p][c].length; m++) {{
                    var blk = pages[p][c][m];
                    if (blk.getAttribute('data-block') === 'cancel' && !colCancelSeen) {{
                        colCancelSeen = true;
                        table.appendChild(makeCancelHeader(ncols, cancelHeaderSeen, m > 0, isTomorrow));
                        cancelHeaderSeen = true;
                    }}
                    table.appendChild(blk);
                }}
                colDiv.appendChild(table);
                pageEl.appendChild(colDiv);
            }}
            wrapper.appendChild(pageEl);
            pageEls.push(pageEl);
        }}

        // .ov-page muss wie der bisherige Spalten-Flexcontainer wirken
        for (var e = 0; e < pageEls.length; e++) {{
            pageEls[e].style.display = (e === 0 ? 'flex' : 'none');
            pageEls[e].style.gap = getComputedStyle(wrapper).gap || '';
            pageEls[e].style.width = '100%';
        }}

        var firstCol = wrapper.querySelector('.col');
        if (firstCol && firstCol.clientWidth < (window.COMPACT_COL_WIDTH || 320)) {{
            wrapper.classList.add('compact-mode');
        }}

        if (pages.length <= 1) return;  // nichts zu rotieren

        // Indikator über dem Wrapper (in die Sektion einhängen)
        var ind = document.createElement('div');
        ind.className = 'ov-pageind';
        var label = wrapper.closest('.tomorrow-section') ? 'Morgen' : 'Heute';
        var txt = document.createElement('span');
        var dots = [];
        function setLabel(idx) {{
            txt.textContent = label + ' ' + (idx + 1) + '/' + pages.length;
            for (var d = 0; d < dots.length; d++) {{
                dots[d].className = 'ovp-dot' + (d === idx ? ' active' : '');
            }}
        }}
        ind.appendChild(txt);
        for (var d2 = 0; d2 < pages.length; d2++) {{
            var dot = document.createElement('span');
            dot.className = 'ovp-dot';
            ind.appendChild(dot); dots.push(dot);
        }}
        wrapper.parentNode.insertBefore(ind, wrapper);
        setLabel(0);

        // Rotation
        var cur = 0;
        wrapper._ovTimer = setInterval(function () {{
            pageEls[cur].style.display = 'none';
            cur = (cur + 1) % pageEls.length;
            pageEls[cur].style.display = 'flex';
            setLabel(cur);
        }}, (OV.page_seconds || 12) * 1000);
    }}
```

- [ ] **Step 4: CSS für `.ov-page` ergänzen**

In `css/style.css` ans Ende anhängen (damit Seiten wie der Spaltencontainer wirken):

```css
.layout-wrapper .ov-page {
    display: flex;
    gap: inherit;
    width: 100%;
}
```

Prüfe den vorhandenen `.layout-wrapper`-Flex/Gap-Stil (Spaltenabstand) und gleiche
`gap` ggf. an den bestehenden Wert an, falls `inherit` nicht greift.

- [ ] **Step 5: Sichtprüfung**

Run: `PYTHONIOENCODING=utf-8 python3 scripts/fetch_untis.py`, Browser sehr niedrig +
schmal ziehen, sodass selbst Min-Skalierung + Reduktion nicht reichen. Prüfen:
- Inhalt rotiert seitenweise alle 12 s, nichts wird abgeschnitten.
- Indikator „Heute 1/2" + Punkte stimmt und wechselt.
- Morgen-Sektion bleibt sichtbar (rotiert nur, wenn sie selbst überläuft).
- Beim Resize verschwindet der alte Timer (kein doppeltes Rotieren).

- [ ] **Step 6: Volle Test-Suite + Commit**

Run: `python3 -m unittest discover -s tests`
Expected: alle Tests PASS

```bash
git add scripts/fetch_untis.py css/style.css
git commit -m "feat(overflow): Blätter-Stufe mit Rotation + Seitenindikator"
```

---

## Task 9: Dokumentation (config.env.example, CLAUDE.md, README.md)

**Files:**
- Modify: `config.env.example`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: `config.env.example` ergänzen**

Am Ende von `config.env.example` anhängen:

```bash
# ── Überlauf-Strategie (Monitor zu voll) ──
# Greift nur bei echtem Überlauf; an normalen Tagen passiert nichts.
# Reihenfolge: Skalieren -> Reduzieren -> Blättern. "Morgen" bleibt immer sichtbar.
OVERFLOW_SCALE=true          # Stufe 1: alles verkleinern bis Mindestgröße
OVERFLOW_SCALE_MIN=0.65      # kleinster Faktor (0.65 = 65 %), Bereich 0.3–1.0
OVERFLOW_REDUCE=true         # Stufe 2: Text-Spalte aus, dann Entfall-Sektion kompakt
OVERFLOW_PAGINATE=true       # Stufe 3: überlaufende Sektion blättert seitenweise
OVERFLOW_PAGE_SECONDS=12     # Sekunden pro Seite beim Blättern (min. 3)
```

- [ ] **Step 2: `CLAUDE.md` ergänzen**

Im Abschnitt mit den Layout-/Config-Variablen (bei `COMPACT_COL_WIDTH_PX` …) einen
Absatz ergänzen:

```markdown
- **Überlauf-Strategie** (`OVERFLOW_*`): greift, wenn der Plan zu voll für den
  Bildschirm ist, gestuft **Skalieren → Reduzieren → Blättern**, jede Stufe einzeln
  schaltbar. `OVERFLOW_SCALE`/`_MIN` (Default true / 0.65), `OVERFLOW_REDUCE`
  (Text-Spalte aus, dann Entfall-Sektion kompakt), `OVERFLOW_PAGINATE` +
  `OVERFLOW_PAGE_SECONDS` (Default 12). „Morgen" bleibt in jeder Stufe sichtbar.
  Logik im JS-`applyLayout`, Mirror in `_layout_logic.py` (`fit_scale`,
  `distribute_uncapped`, `paginate_columns`). Config via `window.OVERFLOW` injiziert.
```

- [ ] **Step 3: `README.md` Konfig-Tabelle ergänzen**

In der `config.env`-Tabelle des README diese Zeilen ergänzen:

```markdown
| `OVERFLOW_SCALE` | – | `true` | Bei Überlauf alles verkleinern (Stufe 1) |
| `OVERFLOW_SCALE_MIN` | – | `0.65` | kleinster Skalierungsfaktor (0.3–1.0) |
| `OVERFLOW_REDUCE` | – | `true` | Bei Überlauf Text-Spalte aus / Entfall kompakt (Stufe 2) |
| `OVERFLOW_PAGINATE` | – | `true` | Bei Überlauf seitenweise blättern (Stufe 3) |
| `OVERFLOW_PAGE_SECONDS` | – | `12` | Sekunden pro Seite beim Blättern |
```

- [ ] **Step 4: Commit**

```bash
git add config.env.example CLAUDE.md README.md
git commit -m "docs(overflow): OVERFLOW_*-Keys dokumentieren"
```

---

## Abschluss

- [ ] **Volle Test-Suite grün:** `python3 -m unittest discover -s tests`
- [ ] **Manuelle Monitor-Prüfung** mit künstlich überfülltem Tag: nichts abgeschnitten,
  Morgen immer sichtbar, Stufen greifen in der Reihenfolge Skalieren→Reduzieren→Blättern,
  je nach `config.env`-Schaltern.
- [ ] **Deploy:** `./deploy.sh` (Server holt sich neue Keys aus `config.env`; fehlen sie,
  greifen die Defaults).
- [ ] **Push:** `git push`
