# Multi-Column-Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adaptives 1-bis-4-Spalten-Layout für die Supplierliste, das die verfügbare Bildschirmhöhe ausmisst und bei Platznot Spalten hinzufügt. Ab 3 Spalten werden die Art-Labels (Vertr./Entfall/Raum/…) als runde Einbuchstaben-Badges dargestellt.

**Architecture:** Server-Side (Python) rendert eine flache Tabelle mit semantischen `data-block`-Markern. Client-Side (Vanilla JS, ~80 Zeilen) misst Container-Höhe, verteilt Blöcke in N Buckets per first-fit-decreasing, klont sie in N parallele `<table>`-Wrapper. CSS reagiert auf `.cols-N`-Klasse für Badge-Umschaltung.

**Tech Stack:** Python 3.9+ (stdlib), HTML/CSS/Vanilla JS. ResizeObserver-API. Tests: stdlib `unittest`. Spec: `docs/superpowers/specs/2026-05-30-multi-column-layout-design.md`.

---

## File Structure

**Geändert:**
- `scripts/fetch_untis.py`:
  - `ART_MAP` erweitert um Kurz-Label (5. Tupel-Position)
  - `render_row` schreibt `<span class="badge-full">…</span><span class="badge-short">…</span>` statt einem Text
  - `build_day_content` rendert flache Liste mit `data-block`-Marker, statt 1/2-Spalten-Split
  - `split_chunks` und `TWO_COL_THRESHOLD` werden entfernt
  - HTML-Template bekommt die Layout-Engine als `<script>`-Block
- `css/style.css`:
  - Neue Regeln für `.layout-wrapper`, `.cols-1`/`.cols-2`/`.cols-3`/`.cols-4`
  - `.badge-full` und `.badge-short` Regeln
  - Runde Kurz-Badges
- `tests/test_layout.py` (neu): Tests für `_distribute_blocks` Layout-Logik (pure function, JS-Algorithmus in Python-Form nachgebaut für TDD)

**Neu:**
- `tests/test_layout.py`

**Nicht angefasst:**
- `data/`, `manifest.json`, `sw.js`, `scripts/fetch_trains.py`

**Verantwortlichkeits-Schnitt:**
- Server kennt keine Spalten-Anzahl mehr — gibt nur eine flache Liste aus
- Browser-JS macht die Layout-Berechnung exklusiv
- CSS schaltet Badge-Form via Klassen-Cascade (kein extra JS für Labels nötig)

---

## Task 1: Branch-Check + Test-Skeleton für die Layout-Logik

**Files:**
- Modify: `tests/test_layout.py` (neu)

- [ ] **Step 1: Branch verifizieren**

```bash
git rev-parse --abbrev-ref HEAD
```
Expected: `feature/multi-column-layout`

Falls nicht: `git checkout feature/multi-column-layout`

- [ ] **Step 2: Test-Datei anlegen mit einem Smoke-Test**

`tests/test_layout.py`:
```python
import unittest


class TestSmokeImport(unittest.TestCase):
    def test_module_setup(self):
        # Wird in den nächsten Tasks durch echte Tests ersetzt
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Sanity-Lauf**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: alle bisherigen Tests + 1 neuer Smoke-Test passen.

- [ ] **Step 4: Commit**

```bash
git add tests/test_layout.py
git commit -m "Multi-Column: Test-Skeleton angelegt"
```

---

## Task 2: `_distribute_blocks` — pure Funktion (Python-Mirror des JS-Algorithmus)

**Files:**
- Create: `scripts/_layout_logic.py`
- Modify: `tests/test_layout.py`

Wir bauen die Verteilung-Logik in Python nach, weil sich TDD damit deutlich einfacher testet als in JS. Im Browser-JS wird der gleiche Algorithmus später 1:1 implementiert.

- [ ] **Step 1: Failing test schreiben**

`tests/test_layout.py` komplett ersetzen mit:

```python
import unittest

from scripts._layout_logic import distribute_blocks


class TestDistributeBlocks(unittest.TestCase):
    """Verteilt Blöcke (mit Höhe) in N Buckets per first-fit auf das aktuell
    kleinste Bucket. Letztes Item ('cancel') landet immer im letzten Bucket."""

    def test_one_column_keine_aufteilung(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "B", "height": 80, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=1)
        self.assertEqual(len(result), 1)
        self.assertEqual([b["id"] for b in result[0]], ["A", "B"])

    def test_zwei_spalten_balanced(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "B", "height": 100, "kind": "teacher"},
            {"id": "C", "height": 80, "kind": "teacher"},
            {"id": "D", "height": 80, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=2)
        self.assertEqual(len(result), 2)
        h0 = sum(b["height"] for b in result[0])
        h1 = sum(b["height"] for b in result[1])
        # First-fit: A (100) in 0, B (100) in 1, C (80) in 0 oder 1, D restlich
        # → beide haben 180
        self.assertEqual(h0, 180)
        self.assertEqual(h1, 180)

    def test_cancel_block_kommt_in_letzte_spalte(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "B", "height": 100, "kind": "teacher"},
            {"id": "C", "height": 100, "kind": "teacher"},
            {"id": "CANCEL", "height": 50, "kind": "cancel"},
        ]
        result = distribute_blocks(blocks, n_cols=3)
        # Cancel muss in der letzten Spalte sein
        last_col_ids = [b["id"] for b in result[-1]]
        self.assertIn("CANCEL", last_col_ids)

    def test_drei_spalten_first_fit(self):
        blocks = [
            {"id": "A", "height": 200, "kind": "teacher"},
            {"id": "B", "height": 50, "kind": "teacher"},
            {"id": "C", "height": 50, "kind": "teacher"},
            {"id": "D", "height": 50, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=3)
        self.assertEqual(len(result), 3)
        # A landet in Spalte 0, B in 1, C in 2, D in (1 oder 2)
        heights = [sum(b["height"] for b in col) for col in result]
        self.assertEqual(heights[0], 200)

    def test_leere_input_liste(self):
        result = distribute_blocks([], n_cols=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result, [[], []])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test ausführen — soll fehlschlagen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: `ImportError: cannot import name 'distribute_blocks' from 'scripts._layout_logic'`

- [ ] **Step 3: Implementation**

`scripts/_layout_logic.py` neu anlegen:

```python
"""
_layout_logic.py – Verteilung von Render-Blöcken in N Spalten (first-fit-min).
Dient als testbarer Python-Mirror der JS-Layout-Engine im Browser.
"""

from typing import Iterable


def distribute_blocks(blocks: Iterable[dict], n_cols: int) -> list:
    """Verteilt `blocks` (jeweils mit `height` und `kind`) auf `n_cols` Buckets.
    Algorithmus: First-fit-min — jeder Block kommt in das gerade kleinste Bucket.
    Sonderfall: Block mit `kind == "cancel"` wird zwingend in das letzte Bucket
    eingefügt (am Ende), egal welche Höhe die anderen haben.
    """
    if n_cols < 1:
        n_cols = 1

    buckets = [[] for _ in range(n_cols)]
    heights = [0] * n_cols

    for block in blocks:
        if block.get("kind") == "cancel":
            # Cancel separat behandeln (am Ende anhängen)
            continue
        # Index des Buckets mit geringster aktueller Höhe
        idx = heights.index(min(heights))
        buckets[idx].append(block)
        heights[idx] += block.get("height", 0)

    # Cancel-Block(s) ans Ende der letzten Spalte
    for block in blocks:
        if block.get("kind") == "cancel":
            buckets[-1].append(block)

    return buckets
```

- [ ] **Step 4: Test ausführen — soll passen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: alle Tests grün.

- [ ] **Step 5: Commit**

```bash
git add scripts/_layout_logic.py tests/test_layout.py
git commit -m "Multi-Column: distribute_blocks pure logic + Tests"
```

---

## Task 3: `ART_MAP` erweitern um Kurz-Label

**Files:**
- Modify: `scripts/fetch_untis.py`

- [ ] **Step 1: Bestehendes `ART_MAP` finden**

```bash
grep -n "ART_MAP = {" scripts/fetch_untis.py
```
Expected: Zeile ~484

- [ ] **Step 2: `ART_MAP` ersetzen**

In `scripts/fetch_untis.py`, finde:

```python
ART_MAP = {
    "subst":      ("s-sup",   "b-sup",   "Vertr."),
    "cancel":     ("s-ent",   "b-ent",   "Entfall"),
    "roomchange": ("s-raum",  "b-raum",  "Raum"),
    "free":       ("s-frei",  "b-frei",  "Freistunde"),
    "pause":      ("s-pause", "b-pause", "Pause"),
}
```

Ersetze durch:

```python
# 4-Tupel: (Zeilen-CSS-Klasse, Badge-CSS-Klasse, Lang-Label, Kurz-Label)
ART_MAP = {
    "subst":      ("s-sup",   "b-sup",   "Vertr.",     "V"),
    "cancel":     ("s-ent",   "b-ent",   "Entfall",    "E"),
    "roomchange": ("s-raum",  "b-raum",  "Raum",       "R"),
    "free":       ("s-frei",  "b-frei",  "Freistunde", "F"),
    "pause":      ("s-pause", "b-pause", "Pause",      "P"),
}
```

- [ ] **Step 3: `render_row` anpassen**

In `scripts/fetch_untis.py`, finde `def render_row(r):` (etwa Zeile 527).

Die Zeile:
```python
    row_cls, badge_cls, label = ART_MAP.get(r["art"], ("s-sup", "b-sup", r["art"]))
```

Ersetze durch:
```python
    row_cls, badge_cls, label_full, label_short = ART_MAP.get(
        r["art"], ("s-sup", "b-sup", r["art"], r["art"][:1].upper())
    )
```

Und finde innerhalb der return:
```python
f'<td class="c-art"><span class="badge {badge_cls}">{esc(label)}</span></td>'
```

Ersetze durch:
```python
f'<td class="c-art"><span class="badge {badge_cls}">'
f'<span class="badge-full">{esc(label_full)}</span>'
f'<span class="badge-short">{esc(label_short)}</span>'
f'</span></td>'
```

- [ ] **Step 4: Lauf zur Sanity-Probe**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```
Expected: läuft durch, schreibt index.html.

Verifizieren dass beide Spans im HTML stehen:
```bash
grep -c "badge-short" /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
```
Expected: > 0 (eine pro Tabellenzeile mit Vertretung)

- [ ] **Step 5: Bestehende Tests laufen lassen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: alle Tests grün.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "Multi-Column: ART_MAP um Kurz-Label erweitert, render_row schreibt beide Spans"
```

---

## Task 4: `build_day_content` auf flache Liste umbauen

**Files:**
- Modify: `scripts/fetch_untis.py`

- [ ] **Step 1: `TWO_COL_THRESHOLD` und `split_chunks` entfernen**

In `scripts/fetch_untis.py`:
- Finde Zeile `TWO_COL_THRESHOLD = 30` — Konstante komplett löschen.
- Finde `def split_chunks(chunks):` und den Funktionsblock dahinter — komplett löschen (ca. 8 Zeilen).

- [ ] **Step 2: `build_day_content` neu schreiben**

In `scripts/fetch_untis.py` die alte Funktion `build_day_content` (etwa Zeile 585–633) komplett ersetzen durch:

```python
def build_day_content(groups, teacher_lookup, day):
    """Rendert eine flache Tabelle pro Tag. Die Aufteilung in 1–4 Spalten
    übernimmt der Browser zur Laufzeit (Layout-Engine in JavaScript).
    Jede Lehrer-Gruppe ist als `data-block="teacher"` markiert, die
    Cancel-Sektion als `data-block="cancel"`."""

    if not groups:
        msg = "Kein Supplierplan für heute" if day == "today" else "Kein Supplierplan für morgen"
        return f'<div class="empty-state"><p>{msg}</p></div>'

    # Trenne Entfall-Zeilen (art=cancel) aus den Lehrer-Gruppen heraus
    cancel_rows    = []
    regular_groups = {}
    for kuerzel, rows in groups.items():
        regs = [r for r in rows if r.get("art") != "cancel"]
        cans = [r for r in rows if r.get("art") == "cancel"]
        if regs:
            regular_groups[kuerzel] = regs
        cancel_rows.extend(cans)

    # Flache HTML-Liste pro Lehrer-Gruppe; ein <tbody> pro Gruppe → data-block-Attribut
    blocks_html = []
    for kuerzel, rows in regular_groups.items():
        body = render_teacher_header(kuerzel, teacher_lookup, day)
        body += "".join(render_row(r) for r in rows)
        blocks_html.append(
            f'<tbody data-block="teacher" data-key="{esc(kuerzel)}">{body}</tbody>'
        )

    # Cancel-Section als eigenes tbody-Block
    if cancel_rows:
        cancel_rows.sort(key=lambda r: (r["sort_key"], r["kuerzel"]))
        day_tom = " tomorrow" if day == "tomorrow" else ""
        cancel_body = (
            f'<tr class="cancel-header{day_tom}">'
            f'<td colspan="8"><span class="ch-label">Entfallende Stunden</span></td>'
            f'</tr>'
            + "".join(render_row(r) for r in cancel_rows)
        )
        blocks_html.append(
            f'<tbody data-block="cancel">{cancel_body}</tbody>'
        )

    return (
        f'<div class="layout-wrapper cols-1">'
        f'<div class="col"><table>{COLGROUP}{THEAD}{"".join(blocks_html)}</table></div>'
        f'</div>'
    )
```

- [ ] **Step 3: Lauf zur Sanity-Probe**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```
Expected: läuft durch.

Verifizieren:
```bash
grep -c "layout-wrapper" /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
grep -c 'data-block="teacher"' /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
grep -c 'data-block="cancel"' /mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/index.html
```
Expected: `1` (oder `2` wenn beide Tage angezeigt werden) für `layout-wrapper`, jeweils > 0 für die Blocks.

- [ ] **Step 4: Tests laufen lassen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: alle Tests grün.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "Multi-Column: build_day_content rendert flache Tabelle mit data-block-Markern"
```

---

## Task 5: CSS für `.layout-wrapper`, `.cols-N` und Kurz-Badges

**Files:**
- Modify: `css/style.css`

- [ ] **Step 1: Bestehende `.columns`-Regeln finden**

```bash
grep -n "\.columns\s*{" css/style.css
```

Erwartete Stelle: ein Block mit `.columns { display: flex; ... }` etwa um Zeile 380.

- [ ] **Step 2: Alte `.columns`/`.columns.single`/`.col`-Regeln löschen**

In `css/style.css` finde den Block:

```css
.columns {
    display: flex;
    gap: 20px;
    flex: 1;
    min-height: 0;
    align-items: flex-start;
    overflow: hidden;
}

.col {
    flex: 1;
    min-width: 0;
}
```

(Falls noch `.columns.single` oder ähnliches dort steht — auch löschen.)

Komplett löschen.

- [ ] **Step 3: Neue Layout-Wrapper-Regeln einfügen**

An gleicher Stelle einfügen:

```css
/* ── Multi-Column Layout-Wrapper ───────────────────────── */
.layout-wrapper {
    display: flex;
    flex-direction: row;
    gap: 20px;
    flex: 1;
    min-height: 0;
    align-items: flex-start;
    overflow: hidden;
}

.layout-wrapper > .col {
    flex: 1;
    min-width: 0;
}

.layout-wrapper > .col table {
    width: 100%;
}
```

- [ ] **Step 4: Badge-Short Regeln am Ende der CSS-Datei ergänzen**

Am Ende von `css/style.css` ergänzen:

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

/* Bei 3+ Spalten: runde Kurz-Badges */
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

- [ ] **Step 5: HTML neu generieren und im Browser kurz schauen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```

Im Browser `index.html` öffnen — sollte einspaltig aussehen, lange Labels (`Vertr.`, `Entfall`).

- [ ] **Step 6: Commit**

```bash
git add css/style.css
git commit -m "Multi-Column: CSS für layout-wrapper, cols-N und Badge-Umschaltung"
```

---

## Task 6: JavaScript Layout-Engine

**Files:**
- Modify: `scripts/fetch_untis.py` (inline `<script>` im HTML-Template)

- [ ] **Step 1: Position für die neue JS-Funktion finden**

In `scripts/fetch_untis.py` finde den `<script>`-Block im HTML-Template. Suche
nach dem bestehenden `// ── Train-Widget Updater ──`-Kommentar — die Layout-Engine
kommt direkt **vor** diesem Block (also nach dem Auto-Refresh-IIFE und vor dem Train-Widget).

- [ ] **Step 2: Layout-Engine-Block einfügen**

In `scripts/fetch_untis.py` vor dem Train-Widget-Updater einfügen (alle `{` / `}`
verdoppelt, weil im Python-f-string):

```python
// ── Multi-Column Layout-Engine ──
(function () {{
    var MIN_COL_WIDTH = 280;  // px
    var MAX_COLS = 4;

    function getBlocks(wrapper) {{
        return Array.prototype.slice.call(
            wrapper.querySelectorAll('tbody[data-block]')
        );
    }}

    function chooseColCount(wrapper, blocks) {{
        var section = wrapper.closest('.plan-section');
        if (!section) return 1;
        var available = section.clientHeight - 40;  // grobe Reserve für headers
        if (available <= 0) return 1;

        var total = 0;
        for (var i = 0; i < blocks.length; i++) {{
            total += blocks[i].getBoundingClientRect().height;
        }}
        var byHeight = Math.max(1, Math.ceil(total / available));
        var byWidth  = Math.max(1, Math.floor(wrapper.clientWidth / MIN_COL_WIDTH));
        return Math.min(MAX_COLS, byHeight, byWidth);
    }}

    function distribute(blocks, cols) {{
        var buckets = [];
        var heights = [];
        for (var i = 0; i < cols; i++) {{ buckets.push([]); heights.push(0); }}

        // Reguläre Blöcke first-fit-min
        for (var j = 0; j < blocks.length; j++) {{
            var b = blocks[j];
            if (b.getAttribute('data-block') === 'cancel') continue;
            var minIdx = 0;
            for (var k = 1; k < cols; k++) {{
                if (heights[k] < heights[minIdx]) minIdx = k;
            }}
            buckets[minIdx].push(b);
            heights[minIdx] += b.getBoundingClientRect().height;
        }}

        // Cancel-Blöcke ans Ende des letzten Buckets
        for (var l = 0; l < blocks.length; l++) {{
            if (blocks[l].getAttribute('data-block') === 'cancel') {{
                buckets[cols - 1].push(blocks[l]);
            }}
        }}

        return buckets;
    }}

    function applyLayout(wrapper) {{
        var blocks = getBlocks(wrapper);
        if (blocks.length === 0) return;

        // cols-N-Klasse zurücksetzen, dann neu setzen
        wrapper.classList.remove('cols-1','cols-2','cols-3','cols-4');
        // Erst messen ohne Multi-Column → cols=1 für saubere Messung
        wrapper.classList.add('cols-1');

        var cols = chooseColCount(wrapper, blocks);
        wrapper.classList.remove('cols-1');
        wrapper.classList.add('cols-' + cols);

        if (cols === 1) return;  // nichts zu klonen, bleibt im Original-Container

        // Original-COLGROUP + THEAD aus der bestehenden Tabelle entnehmen
        var origTable   = wrapper.querySelector('table');
        var origColgroup = origTable.querySelector('colgroup');
        var origThead    = origTable.querySelector('thead');

        var buckets = distribute(blocks, cols);

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
    }}

    function layoutAll() {{
        var wrappers = document.querySelectorAll('.layout-wrapper');
        for (var i = 0; i < wrappers.length; i++) {{
            applyLayout(wrappers[i]);
        }}
    }}

    // Initial nach DOMContentLoaded (oder sofort wenn schon geladen)
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', layoutAll);
    }} else {{
        layoutAll();
    }}

    // Auf Resize 250 ms debounced
    var resizeTimer = null;
    window.addEventListener('resize', function () {{
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(layoutAll, 250);
    }});
}})();
```

- [ ] **Step 3: HTML generieren**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```

Im Browser öffnen. Mit DevTools → Elements: die `.layout-wrapper` sollte nach
DOM-Load eine `cols-1` / `cols-2` / `cols-3` / `cols-4`-Klasse haben, je nach
Inhalt + Höhe.

- [ ] **Step 4: Resize-Test im Browser**

Browser-Fenster verkleinern / vergrößern → Layout reagiert nach 250 ms.

- [ ] **Step 5: Tests laufen lassen (sanity)**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: alle Tests grün.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_untis.py
git commit -m "Multi-Column: JS Layout-Engine (first-fit-min, ResizeObserver, Cancel ans Ende)"
```

---

## Task 7: End-to-End Test im Browser mit verschieden vollen Tagen

**Files:** keine — manueller Test

- [ ] **Step 1: Kleine Datenmenge testen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py
```

Im Browser öffnen. Heute leer oder ~5 Zeilen → Erwartet: `.cols-1`, lange Labels.

- [ ] **Step 2: Mittlere Datenmenge — Browser-Fenster auf ca. 1000 px verkleinern**

Layout sollte auf `.cols-1` bleiben oder bei vielen Zeilen `.cols-2` werden.

- [ ] **Step 3: Große Datenmenge simulieren — testweise**

Browser-Fenster auf normale Größe. Falls aktuell <30 Zeilen: temporär in der
Browser-Konsole testen, ob Spalten-Schalter funktioniert:

```javascript
document.querySelectorAll('.layout-wrapper').forEach(w => {
    w.classList.remove('cols-1','cols-2');
    w.classList.add('cols-4');
});
```

Erwartung: Badges werden rund (V/E/R/F/P), Container teilt sich in 4 Spalten —
allerdings keine Block-Verteilung mehr, weil das nur via JS-Layout-Engine
passieren würde. Reset durch Page-Reload.

- [ ] **Step 4: Verifizieren dass Cancel-Sektion in der letzten Spalte landet**

Bei Tagen mit Entfällen: im DevTools Elements-Inspector prüfen, dass das
`<tbody data-block="cancel">` in der letzten `<div class="col">` der
`.layout-wrapper` ist.

- [ ] **Step 5: Kein Commit nötig** (manueller Test).

---

## Task 8: Doku aktualisieren (CLAUDE.md, Spec-Referenz)

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Sektion „Layout (CSS)" in CLAUDE.md finden**

```bash
grep -n "Layout (CSS)" CLAUDE.md
```

- [ ] **Step 2: Sektion ersetzen**

Finde den Block der ungefähr so aussieht:

```markdown
### Layout (CSS)
- **Heute leer + Morgen vorhanden:** Heute-Section wird komplett ausgeblendet
- **Beide sichtbar:** Heute = `flex: 0 1 auto` (Content-Größe),
  Morgen = `flex: 1 1 auto` (nimmt restlichen Platz)
  → Wenn heute schrumpft (Stunden vergehen), rutscht Morgen automatisch hoch
- **Tag-Headlines:**
  - Heute: rote Akzentlinie (`.day-title-bar.today`)
  - Morgen: blaue Akzentlinie
```

Ergänze darunter:

```markdown
### Multi-Column-Layout (Browser-seitig)

Die Supplierliste wird server-seitig als **flache Tabelle** ausgegeben (eine
`<tbody>`-Sektion pro Lehrer + eine für Cancel-Stunden, jeweils mit
`data-block`-Attribut). Eine JavaScript-Layout-Engine im Browser misst nach
DOMContentLoaded den verfügbaren Platz und verteilt die Blöcke per
first-fit-min auf 1–4 Spalten. Setzt am `.layout-wrapper`-Container die Klasse
`.cols-N` (1, 2, 3 oder 4).

Ab `.cols-3` schaltet CSS die Art-Badges (Vertr./Entfall/…) auf runde
Einbuchstaben-Form (V/E/R/F/P) um. Die Cancel-Sektion landet immer in der
letzten Spalte.

Re-Layout bei Browser-Resize (250 ms debounced) und bei jedem Page-Reload
(60 s Auto-Refresh greift wie bisher).
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Multi-Column: CLAUDE.md aktualisiert"
```

---

## Task 9: Branch pushen + Hand-Off

**Files:** keine

- [ ] **Step 1: Tests final laufen lassen**

```bash
PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover tests -v
```
Expected: alle grün (mindestens 22 alte + 5 neue von Task 2 = 27 Tests).

- [ ] **Step 2: Branch pushen**

```bash
git push -u origin feature/multi-column-layout
```

- [ ] **Step 3: Notiz: Cron / Deployment**

Branch bleibt offen für Review. Wenn der User mergt, läuft der Cron auf dem LXC
das nächste Mal mit dem neuen Layout — keine zusätzliche Konfiguration nötig
(reiner Code-Change).

---

## Test-Strategie Übersicht

Was automatisiert getestet wird (`tests/test_layout.py`):
- `distribute_blocks` — pure Logik: 1-Spalte, 2-Spalten balanced, Cancel-Sonderbehandlung, first-fit, leere Liste

Was **nicht** automatisiert getestet wird (manueller Smoke-Test):
- Browser-DOM-Mutation durch die JS-Layout-Engine
- Visuelles Rendering der runden Badges
- Resize-Verhalten

---

## Risiken & Mitigation (übernommen aus Spec)

1. **Lehrer-Gruppe größer als Container** → bleibt ungeteilt; in der Praxis irrelevant.
2. **Inhalt ändert sich während Layout** → ResizeObserver mit 250 ms Debounce.
3. **Flackern beim Initial-Layout** → akzeptiert (kurz, ~100 ms).
4. **Layout-Engine misst mit langen Labels und schaltet dann auf kurz** → akzeptiert,
   eventuell minimale Überdimensionierung. Pragmatik > Perfektion.
