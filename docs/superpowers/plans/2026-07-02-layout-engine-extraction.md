# Layout Engine Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the browser layout engine out of the `generate_html` f-string into a tested `js/layout-core.js` (pure math) + `js/layout.js` (DOM driver), delete the drift-prone Python mirror, and test the real JS with Node's built-in runner.

**Architecture:** The ~620-line inline `<script>` becomes two static files loaded via `<script src>`. The pure column/overflow math (`fitScale`, `distributeUncapped`, `paginateColumns`, `distributeGreedy`) lives in `layout-core.js` with **no** DOM reference (globals in the browser + a `module.exports` guard for Node). The driver measures heights and calls the core. `_layout_logic.py` and its two tests are retired; `parse_overflow_config` stays Python.

**Tech Stack:** Python 3.9 stdlib (unchanged runtime), plain browser JS (no build step, no `type=module`), Node built-in test runner (`node --test`, `node:assert`) at dev-time only.

**Reference docs:** `docs/adr/0002-layout-engine-extracted-and-tested.md` (the why), `CONTEXT.md` → *Layout core* / *Layout driver* / *Runtime invariant*.

**Test commands:**
- Python: `PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover -s tests -t .`
- Regenerate golden: prefix the same command with `GOLDEN_UPDATE=1`
- Node: `node --test tests/js/`

---

## File Structure

- `js/layout.js` — **new.** The full former inline script: PWA service-worker registration, the clock `tick()` loop, and the layout **driver** (`applyLayout`, `layoutAll`, `chooseColCount`, `maxColsByWidth`, `getBlocks`, `makeCancelHeader`, resize/debounce wiring). Reads `window.TZ`, `window.MAX_COLUMNS`, `window.COMPACT_COL_WIDTH`, `window.OVERFLOW`. Measures DOM, calls the core.
- `js/layout-core.js` — **new.** Pure math only: `fitScale`, `distributeUncapped`, `paginateColumns`, `distributeGreedy`. No `window`/`document`. Globals + `module.exports` guard.
- `scripts/fetch_untis.py` — **modify.** Remove the inline `<script>` block (currently lines 1391–2013), emit two `<script src>` tags, inject `window.TZ`, drop the now-unused `tz_js` interpolation into a global.
- `tests/js/layout-core.test.js` — **new.** Node tests for the four pure functions.
- `tests/test_layout_js.py` — **new.** unittest wrapper that shells to `node --test`, skips loudly if Node is absent.
- `tray/build.py` — **modify.** Add `js` to the shipped-assets list.
- `.git/hooks/pre-commit` (and `scripts/install-hooks.sh` if it hard-codes the body) — **modify.** Also run `node --test tests/js/`, loud-skip without Node.
- **Delete:** `scripts/_layout_logic.py`, `tests/test_layout.py`, `tests/test_overflow.py`.
- `tests/golden/generate_html_basic.html` — **regenerate** (inline script → `<script src>`).
- `tests/fixtures/layout/` — **new.** Three reproducible scenarios for the manual browser check.

---

## Task 1: Mechanical move — inline script → `js/layout.js` via `<script src>`

No logic change. Cut the script text out, un-double the f-string braces, turn the one interpolation into a global. This isolates "did relocation break loading" from the later refactor.

**Files:**
- Create: `js/layout.js`
- Modify: `scripts/fetch_untis.py` (lines 1149, 1317-ish head, 1391–2013), `tray/build.py`
- Regenerate: `tests/golden/generate_html_basic.html`

- [ ] **Step 1: Create `js/layout.js` from the inline block**

Copy the exact text currently between `<script>` (line 1391) and `</script>` (line 2013) into `js/layout.js`. Apply exactly two transforms, nothing else:

1. **Un-double every brace:** the block lives in a Python f-string, so literal braces are doubled. Replace `{{` → `{` and `}}` → `}` throughout the copied text. (Example: `if ('serviceWorker' in navigator) {{` becomes `if ('serviceWorker' in navigator) {`.)
2. **Replace the one interpolation:** the line `var tz   = {tz_js};` becomes `var tz   = window.TZ;`.

Do **not** reformat, rename, or reorder anything else. The file starts with the `// ── PWA: Service-Worker registrieren ──` comment and ends with the final `})();`/closing of the former script body.

- [ ] **Step 2: Inject `window.TZ` and replace the inline block in `fetch_untis.py`**

The config globals are injected near line 1328. Add `TZ` alongside them. Find:

```python
    <script>window.COMPACT_COL_WIDTH = {compact_col_width};</script>
    <script>window.MAX_COLUMNS = {max_columns};</script>
    <script>window.OVERFLOW = {json.dumps(overflow_cfg)};</script>
```

Add one line (keep `tz_js = json.dumps(tz_name)` at line 1149 as the source):

```python
    <script>window.TZ = {tz_js};</script>
```

Then delete the entire inline `<script> … </script>` block (former lines 1391–2013) and replace it with:

```python
    <script src="js/layout-core.js?v={css_v}"></script>
    <script src="js/layout.js?v={css_v}"></script>
```

(`layout-core.js` does not exist yet — created in Task 2. For Task 1 it 404s harmlessly; the browser smoke test in Step 5 uses only `layout.js`. If you prefer a strictly-green intermediate, emit only the `layout.js` tag in Task 1 and add the `layout-core.js` tag in Task 2. Either is fine.)

- [ ] **Step 3: Ship `js/` from the tray build**

In `tray/build.py`, the asset list is around line 27:

```python
              ("sw.js", False), ("config.env.example", False)]
```

Add `("js", True)` (True = directory, copied via `copytree`) to that list so `js/layout*.js` lands in `assets/` and gets served by the tray. Verify the surrounding tuple shape (`(name, is_dir)`) matches before editing.

- [ ] **Step 4: Regenerate the golden and inspect the diff**

Run: `GOLDEN_UPDATE=1 PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest tests.test_generate_html_golden -v`
Expected: PASS (writes new golden).

Then `git diff tests/golden/generate_html_basic.html` and **confirm by eye** the only change is: the big inline `<script>` block replaced by the two `<script src>` lines, plus the new `window.TZ` line. Nothing else in the HTML body may have moved.

- [ ] **Step 5: Browser smoke test**

Generate a page and open it:
Run: `PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe scripts/fetch_untis.py` (or generate from a fixture in Task 6).
Open the resulting `index.html` in a browser served from the project root (so `js/layout.js` resolves). Expected: clock ticks, columns lay out, no console errors. The `layout-core.js` 404 is expected until Task 2 (functions are still defined inline in `layout.js` at this point — see note in Step 2; if you split the tag, the page is fully green here).

- [ ] **Step 6: Run the full Python suite**

Run: `PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover -s tests -t .`
Expected: PASS (mirror tests still green — untouched this task).

- [ ] **Step 7: Commit**

```bash
git add js/layout.js scripts/fetch_untis.py tray/build.py tests/golden/generate_html_basic.html
git commit -m "refactor(layout): JS-Engine aus generate_html in js/layout.js auslagern"
```

---

## Task 2: Split pure core into `js/layout-core.js`, refactor driver to pass measured arrays

Make the four pure functions operate on plain data (no DOM), move them to `layout-core.js`, and have the driver measure once and map indices back to nodes. Behavior-preserving.

**Files:**
- Create: `js/layout-core.js`
- Modify: `js/layout.js`, `scripts/fetch_untis.py` (only if the `layout-core.js` tag was deferred in Task 1)

- [ ] **Step 1: Create `js/layout-core.js` with the pure functions**

```javascript
// js/layout-core.js — reine Layout-Mathematik, KEIN window/document.
// Browser: Funktionen sind Globals. Node: via module.exports require-bar.
// Getestet in tests/js/layout-core.test.js. Siehe docs/adr/0002-*.

// Größter Skalierungsfaktor in {1.0, 1-step, …} >= scaleMin, bei dem
// contentH * f <= availH. Passt es bei 1.0, kommt 1.0; sonst runter bis scaleMin.
function fitScale(contentH, availH, scaleMin, step) {
    if (contentH <= 0 || contentH <= availH) return 1.0;
    if (availH <= 0) return Math.round(scaleMin * 10000) / 10000;
    var steps = Math.round((1.0 - scaleMin) / step);
    for (var i = 0; i <= steps; i++) {
        var s = Math.round((1.0 - i * step) * 10000) / 10000;
        if (contentH * s <= availH) return s;
    }
    return Math.round(scaleMin * 10000) / 10000;
}

// items: [{height, isCancel}]. Greedy-Fit in BELIEBIG viele Spalten.
// Gibt Spalten als Listen von Indizes in `items` zurück. Pro Spalte mit
// Entfällen wird cancelHeaderH für die später eingefügte Überschrift reserviert.
function distributeUncapped(items, availH, cancelHeaderH) {
    cancelHeaderH = cancelHeaderH || 0;
    var cols = [[]];
    var h = 0;
    var colHasCancel = false;
    for (var i = 0; i < items.length; i++) {
        var isCancel = !!items[i].isCancel;
        var bh = items[i].height;
        var extra = (isCancel && !colHasCancel) ? cancelHeaderH : 0;
        if (cols[cols.length - 1].length && h + bh + extra > availH) {
            cols.push([]); h = 0; colHasCancel = false;
            extra = isCancel ? cancelHeaderH : 0;
        }
        cols[cols.length - 1].push(i);
        h += bh + extra;
        if (isCancel) colHasCancel = true;
    }
    return cols;
}

// cols: Array von Spalten (Element-Typ egal — es wird nur die äußere Liste
// geteilt). Höchstens maxCols pro Seite, gleichmäßig verteilt (4 bei max 3 → 2+2).
function paginateColumns(cols, maxCols) {
    if (maxCols < 1) maxCols = 1;
    var n = cols.length;
    if (n === 0) return [];
    var nPages = Math.ceil(n / maxCols);
    var perPage = Math.ceil(n / nPages);
    var pages = [];
    for (var i = 0; i < n; i += perPage) pages.push(cols.slice(i, i + perPage));
    return pages;
}

// items: [{height, isCancel}]. Greedy in genau `cols` Spalten. Reguläre zuerst,
// Entfälle danach (bleiben am Ende des Leseflusses). Gibt `cols` Buckets von
// Indizes in `items` zurück; pro Spalte mit Entfällen cancelHeaderH reserviert.
function distributeGreedy(items, cols, availablePerCol, cancelHeaderH) {
    cancelHeaderH = cancelHeaderH || 0;
    var buckets = [];
    for (var i = 0; i < cols; i++) buckets.push([]);

    var regular = [], cancels = [];
    for (var j = 0; j < items.length; j++) {
        if (items[j].isCancel) cancels.push(j); else regular.push(j);
    }
    var ordered = regular.concat(cancels);

    var currentCol = 0, currentHeight = 0, colHasCancel = false;
    for (var k = 0; k < ordered.length; k++) {
        var idx = ordered[k];
        var isCancel = !!items[idx].isCancel;
        var h = items[idx].height;
        var extra = (isCancel && !colHasCancel) ? cancelHeaderH : 0;
        if (currentHeight + h + extra > availablePerCol
                && currentCol < cols - 1
                && buckets[currentCol].length > 0) {
            currentCol++;
            currentHeight = 0;
            colHasCancel = false;
            extra = isCancel ? cancelHeaderH : 0;
        }
        buckets[currentCol].push(idx);
        currentHeight += h + extra;
        if (isCancel) colHasCancel = true;
    }
    return buckets;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { fitScale, distributeUncapped, paginateColumns, distributeGreedy };
}
```

- [ ] **Step 2: Delete the four functions from `js/layout.js`**

Remove the `fitScale`, `distributeUncapped`, `paginateColumns`, `distributeGreedy` definitions from `layout.js` (they now live in the core and are available as globals because `layout-core.js` loads first). Also remove the `var CANCEL_HEADER_H = 46;` line **only if** you inline the constant at the call sites; otherwise keep it in the driver and pass it in.

- [ ] **Step 3: Refactor the driver call sites to measure → items → map back**

In `layout.js`, wherever the old DOM-coupled versions were called, build a measured `items` array and map returned indices back to nodes. The two call sites are inside `applyLayout` (the capped/greedy path) and the paginate path.

Add a small driver helper near the top of the driver section:

```javascript
// Misst die Blöcke einmal in reine {height, isCancel}-Werte für den Core.
function measureItems(blocks) {
    return blocks.map(function (b) {
        return {
            height: b.getBoundingClientRect().height,
            isCancel: b.getAttribute('data-block') === 'cancel'
        };
    });
}
```

Greedy call site — replace `var buckets = distributeGreedy(blocks, cols, availablePerCol);` with:

```javascript
        var items = measureItems(blocks);
        var idxBuckets = distributeGreedy(items, cols, availablePerCol, CANCEL_HEADER_H);
        var buckets = idxBuckets.map(function (col) {
            return col.map(function (i) { return blocks[i]; });
        });
```

Paginate call site — replace `var allCols = distributeUncapped(blocks, availablePerCol);` (and its use with `paginateColumns`) with:

```javascript
        var pItems = measureItems(blocks);
        var idxCols = distributeUncapped(pItems, availablePerCol, CANCEL_HEADER_H);
        var allCols = idxCols.map(function (col) {
            return col.map(function (i) { return blocks[i]; });
        });
```

`paginateColumns(allCols, MAX_COLS)` and `fitScale(...)` are called unchanged (they already take the right shapes: `allCols` is now node-columns, which `paginateColumns` slices fine; `fitScale` was always pure numbers).

Keep `var CANCEL_HEADER_H = 46;` in the driver so it can be passed in.

- [ ] **Step 4: Emit the `layout-core.js` tag (if deferred)**

If Task 1 emitted only the `layout.js` tag, add the core tag **before** it in `fetch_untis.py`:

```python
    <script src="js/layout-core.js?v={css_v}"></script>
    <script src="js/layout.js?v={css_v}"></script>
```

Regenerate the golden if the tag set changed: `GOLDEN_UPDATE=1 … -m unittest tests.test_generate_html_golden`.

- [ ] **Step 5: Browser smoke test — all three hard cases**

Serve the project root, open a generated `index.html`. Expected: identical layout to before the refactor — columns balanced, overflow scaling/pagination behaves, and the "Entfallende Stunden" section breaks across columns with one header per column. No console errors, no 404. Use the Task 6 fixtures if already available; otherwise eyeball the current live plan.

- [ ] **Step 6: Commit**

```bash
git add js/layout-core.js js/layout.js scripts/fetch_untis.py tests/golden/generate_html_basic.html
git commit -m "refactor(layout): reine Core-Mathematik in layout-core.js, Driver misst und mappt"
```

---

## Task 3: Node tests for `layout-core.js`

Port the existing `test_overflow.py` assertions verbatim in intent, and rewrite the `test_layout.py` intent against the **corrected** `distributeGreedy` (per-column cancel reservation, not "cancels in last column").

**Files:**
- Create: `tests/js/layout-core.test.js`

- [ ] **Step 1: Write the failing test file**

```javascript
const test = require('node:test');
const assert = require('node:assert');
const { fitScale, distributeUncapped, paginateColumns, distributeGreedy } =
    require('../../js/layout-core.js');

function items(heights, cancelIdx) {
    cancelIdx = cancelIdx || [];
    return heights.map((h, i) => ({ height: h, isCancel: cancelIdx.includes(i) }));
}

test('fitScale: passt ohne Skalierung -> 1.0', () => {
    assert.strictEqual(fitScale(100, 200, 0.65, 0.05), 1.0);
});
test('fitScale: exakt passend bleibt 1.0', () => {
    assert.strictEqual(fitScale(200, 200, 0.65, 0.05), 1.0);
});
test('fitScale: skaliert auf groessten passenden Faktor', () => {
    // 100 * 0.9 = 90 <= 90, 0.95 -> 95 > 90
    assert.strictEqual(fitScale(100, 90, 0.65, 0.05), 0.9);
});
test('fitScale: geht nicht unter min', () => {
    assert.strictEqual(fitScale(1000, 1, 0.65, 0.05), 0.65);
});
test('fitScale: available null gibt min', () => {
    assert.strictEqual(fitScale(100, 0, 0.65, 0.05), 0.65);
});
test('fitScale: leerer Inhalt bleibt 1.0', () => {
    assert.strictEqual(fitScale(0, 100, 0.65, 0.05), 1.0);
});

test('distributeUncapped: alles in eine Spalte', () => {
    const cols = distributeUncapped(items([50, 50, 50]), 300, 0);
    assert.deepStrictEqual(cols, [[0, 1, 2]]);
});
test('distributeUncapped: Umbruch an Budgetgrenze', () => {
    const cols = distributeUncapped(items([100, 100, 100, 100]), 250, 0);
    assert.deepStrictEqual(cols, [[0, 1], [2, 3]]);
});
test('distributeUncapped: uebergrosser Block bekommt eigene Spalte', () => {
    const cols = distributeUncapped(items([500, 100]), 300, 0);
    assert.deepStrictEqual(cols, [[0], [1]]);
});
test('distributeUncapped: leere Eingabe', () => {
    assert.deepStrictEqual(distributeUncapped([], 300, 0), [[]]);
});
test('distributeUncapped: cancel-Header reserviert Platz', () => {
    // 2x100 + Header 46 = 246 <= 250 fuer [0,1]; dritter (100) sprengt -> neue Spalte
    const cols = distributeUncapped(items([100, 100, 100], [0, 1, 2]), 250, 46);
    assert.deepStrictEqual(cols, [[0, 1], [2]]);
});

test('paginateColumns: passt in eine Seite', () => {
    assert.deepStrictEqual(paginateColumns([['a'], ['b']], 3), [[['a'], ['b']]]);
});
test('paginateColumns: verteilt gleichmaessig (4 bei max 3 -> 2+2)', () => {
    const pages = paginateColumns([[1], [2], [3], [4]], 3);
    assert.strictEqual(pages.length, 2);
    assert.strictEqual(pages[0].length, 2);
    assert.strictEqual(pages[1].length, 2);
});
test('paginateColumns: max unter 1 wird 1', () => {
    assert.strictEqual(paginateColumns([[1], [2]], 0).length, 2);
});
test('paginateColumns: leere Eingabe', () => {
    assert.deepStrictEqual(paginateColumns([], 3), []);
});

test('distributeGreedy: Reihenfolge erhalten, Greedy-Fit', () => {
    const b = distributeGreedy(items([100, 100, 100, 100]), 2, 250, 0);
    assert.deepStrictEqual(b, [[0, 1], [2, 3]]);
});
test('distributeGreedy: uebergrosser Einzelblock eigene Spalte', () => {
    const b = distributeGreedy(items([500, 100]), 2, 300, 0);
    assert.deepStrictEqual(b, [[0], [1]]);
});
test('distributeGreedy: Entfaelle ans Ende des Leseflusses', () => {
    // idx1 ist cancel -> hinter die regulaeren sortiert; passt mit in letzte Spalte
    const b = distributeGreedy(items([100, 50], [1]), 2, 300, 0);
    assert.deepStrictEqual(b, [[0, 1], []]);
});
test('distributeGreedy: cancel-Header reserviert Platz pro Spalte', () => {
    // regular 200 in Spalte 0; cancel 60 + Header 46 -> 306 > 250 -> Spalte 1
    const b = distributeGreedy(items([200, 60], [1]), 2, 250, 46);
    assert.deepStrictEqual(b, [[0], [1]]);
});
```

- [ ] **Step 2: Run and verify green**

Run: `node --test tests/js/`
Expected: all tests PASS. If `distributeGreedy`'s cancel-reservation test fails, that means the refactor in Task 2 dropped the `cancelHeaderH` reserve — fix the core, not the test.

- [ ] **Step 3: Commit**

```bash
git add tests/js/layout-core.test.js
git commit -m "test(layout): Node-Tests fuer layout-core (Overflow + korrigierte Cancel-Logik)"
```

---

## Task 4: Wire Node tests into `unittest` + pre-commit hook

One command (`python -m unittest`) must run the JS suite too, skipping **loudly** without Node. The hook gets the same gate.

**Files:**
- Create: `tests/test_layout_js.py`
- Modify: `.git/hooks/pre-commit` (and `scripts/install-hooks.sh` if it writes the hook body)

- [ ] **Step 1: Write the wrapper test**

```python
"""Laesst die JS-Layout-Core-Tests (node --test) im selben `python -m unittest`
Lauf mitlaufen. Findet node mit denselben Fallbacks wie der pre-commit-Hook;
ist keiner da -> LAUT skippen (nicht gruen durchwinken)."""
import os
import shutil
import subprocess
import unittest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_node():
    cand = os.environ.get("SUPPLIERPLAN_NODE") or shutil.which("node")
    if cand:
        return cand
    for p in ("/home/richard/.local/bin/node",):
        if os.path.exists(p):
            return p
    return None


class TestLayoutCoreJS(unittest.TestCase):
    def test_node_layout_suite_passes(self):
        node = _find_node()
        if not node:
            self.skipTest("node fehlt — Layout-Core-Tests uebersprungen "
                          "(installiere node oder setze SUPPLIERPLAN_NODE)")
        proc = subprocess.run(
            [node, "--test", "tests/js/"],
            cwd=_HERE, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(
            proc.returncode, 0,
            "node --test tests/js/ fehlgeschlagen:\n"
            + proc.stdout + "\n" + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify it runs (or loud-skips)**

Run: `PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest tests.test_layout_js -v`
Expected: PASS (node present on this machine). To prove the loud skip: `SUPPLIERPLAN_NODE=/nonexistent … -m unittest tests.test_layout_js -v` → shows `skipped 'node fehlt …'`.

- [ ] **Step 3: Extend the pre-commit hook**

`.git/hooks/pre-commit` currently finds Python and regenerates the codemap. Append a node gate before the final `git add`. Insert:

```sh
# JS-Layout-Core-Tests — laut skippen, wenn node fehlt.
NODE=""
if [ -n "$SUPPLIERPLAN_NODE" ]; then
  NODE="$SUPPLIERPLAN_NODE"
elif command -v node >/dev/null 2>&1; then
  NODE="node"
elif [ -x "$HOME/.local/bin/node" ]; then
  NODE="$HOME/.local/bin/node"
fi
if [ -n "$NODE" ]; then
  "$NODE" --test "$ROOT/tests/js/" >&2 || {
    echo "pre-commit: layout-core JS-Tests rot — Commit abgebrochen" >&2
    exit 1
  }
else
  echo "pre-commit: node fehlt — JS-Layout-Tests uebersprungen" >&2
fi
```

If `scripts/install-hooks.sh` hard-codes the hook body, add the same block there so a re-install keeps it.

- [ ] **Step 4: Full suite green**

Run: `PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover -s tests -t .`
Expected: PASS, including `test_layout_js`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_layout_js.py .git/hooks/pre-commit scripts/install-hooks.sh
git commit -m "test(layout): JS-Tests in unittest-Suite + pre-commit-Hook (laut-skip ohne node)"
```

(`.git/hooks/pre-commit` is not normally tracked; if `git add` reports nothing for it, that's fine — the tracked source is `scripts/install-hooks.sh`.)

---

## Task 5: Retire the Python mirror

The real JS is now the single, tested implementation. Delete the mirror and its tests. Keep `parse_overflow_config` + `test_overflow_config.py` (Python config parsing, not layout math).

**Files:**
- Delete: `scripts/_layout_logic.py`, `tests/test_layout.py`, `tests/test_overflow.py`

- [ ] **Step 1: Confirm nothing else imports the mirror**

Run: `grep -rn "_layout_logic" scripts tests tray`
Expected: only `tests/test_layout.py` and `tests/test_overflow.py` (both being deleted). If anything else references it, stop and reassess.

- [ ] **Step 2: Delete the files**

```bash
git rm scripts/_layout_logic.py tests/test_layout.py tests/test_overflow.py
```

- [ ] **Step 3: Full suite green**

Run: `PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe -m unittest discover -s tests -t .`
Expected: PASS. `test_overflow_config` still runs (untouched); `test_layout`/`test_overflow` are gone; `test_layout_js` covers the JS.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(layout): Python-Mirror _layout_logic + dessen Tests entfernt"
```

---

## Task 6: Reproducible fixtures + manual browser acceptance

The driver refactor has no automated browser proof. Anchor it with three saved scenarios that generate an `index.html` each.

**Files:**
- Create: `tests/fixtures/layout/README.md` + three generator inputs (config + raw data) or a small script

- [ ] **Step 1: Capture three scenarios**

Create `tests/fixtures/layout/` holding three reproducible inputs that drive `generate_html`, reusing the code-defined fixture pattern from `tests/test_generate_html_golden.py::_fixture`:

1. `normal.html` — a normal day, 2–4 teacher blocks, no overflow.
2. `overflow.html` — enough rows that `OVERFLOW_SCALE`/`REDUCE`/`PAGINATE` all engage (set a small viewport / many blocks).
3. `cancel_heavy.html` — a large "Entfallende Stunden" section (many `art=cancel` rows across whole absent classes) so the per-column cancel header logic is exercised.

Add a tiny generator `tests/fixtures/layout/gen.py` that builds each scenario's substitution list and writes the three HTML files via `fu.generate_html(...)`, mirroring `_fixture()` + `_call()` in the golden test. Document in `README.md` how to run it and what to look for.

- [ ] **Step 2: Generate and eyeball**

Run: `PYTHONIOENCODING=utf-8 /mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe tests/fixtures/layout/gen.py`
Open each of the three HTML files served from the project root. Confirm:
- normal: clean 2–4 column balance, no clipping.
- overflow: board scales, then reduces, then paginates ("Morgen" stays visible); pages rotate.
- cancel_heavy: cancels flow across real column boundaries; exactly one "Entfallende Stunden" header per column (continuations marked "… (Forts.)").

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/layout/
git commit -m "test(layout): reproduzierbare Browser-Fixtures (Normal/Ueberlauf/Entfall-Sektion)"
```

---

## Self-Review Notes

- **Spec coverage:** Extraction (T1), pure-core split + driver refactor (T2), Node tests incl. corrected cancel drift (T3), loud-skip wiring + hook (T4), mirror deletion (T5), reproducible manual anchor (T6), tray shipping (T1/Step 3), runtime invariant preserved (no npm; `<script src>` only). All decisions from ADR 0002 mapped.
- **Type consistency:** core functions return **index** lists (`distributeUncapped`, `distributeGreedy`); the driver maps indices→nodes. `paginateColumns` and `fitScale` are shape-agnostic/numeric and unchanged. `cancelHeaderH` is a parameter everywhere (not a global) inside the core; the driver keeps `CANCEL_HEADER_H = 46` and passes it.
- **Non-obvious risk:** the f-string brace un-doubling in T1/Step 1 is the one place a mechanical error hides; the golden diff in T1/Step 4 is the guard.
