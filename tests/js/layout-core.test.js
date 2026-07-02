// Node-Tests fuer die reine Layout-Mathematik (js/layout-core.js).
// Lauf: node --test tests/js/   — oder via `python -m unittest` (tests/test_layout_js.py).
// Ersetzt die frueheren Python-Mirror-Tests (test_layout.py / test_overflow.py):
// prueft jetzt die ECHTEN Browser-Funktionen, inkl. der frueher gedrifteten
// Cancel-Header-Semantik von distributeGreedy.
const test = require('node:test');
const assert = require('node:assert');
const { fitScale, distributeUncapped, paginateColumns, distributeGreedy } =
    require('../../js/layout-core.js');

function items(heights, cancelIdx) {
    cancelIdx = cancelIdx || [];
    return heights.map((h, i) => ({ height: h, isCancel: cancelIdx.includes(i) }));
}

// ── fitScale ──
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

// ── distributeUncapped ──
test('distributeUncapped: alles in eine Spalte', () => {
    assert.deepStrictEqual(distributeUncapped(items([50, 50, 50]), 300, 0), [[0, 1, 2]]);
});
test('distributeUncapped: Umbruch an Budgetgrenze', () => {
    assert.deepStrictEqual(distributeUncapped(items([100, 100, 100, 100]), 250, 0),
                           [[0, 1], [2, 3]]);
});
test('distributeUncapped: uebergrosser Block bekommt eigene Spalte', () => {
    assert.deepStrictEqual(distributeUncapped(items([500, 100]), 300, 0), [[0], [1]]);
});
test('distributeUncapped: leere Eingabe', () => {
    assert.deepStrictEqual(distributeUncapped([], 300, 0), [[]]);
});
test('distributeUncapped: cancel-Header reserviert Platz', () => {
    // 2x100 + Header 46 = 246 <= 250 fuer [0,1]; dritter (100) sprengt -> neue Spalte
    assert.deepStrictEqual(distributeUncapped(items([100, 100, 100], [0, 1, 2]), 250, 46),
                           [[0, 1], [2]]);
});

// ── paginateColumns ──
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

// ── distributeGreedy ──
test('distributeGreedy: Reihenfolge erhalten, Greedy-Fit', () => {
    assert.deepStrictEqual(distributeGreedy(items([100, 100, 100, 100]), 2, 250, 0),
                           [[0, 1], [2, 3]]);
});
test('distributeGreedy: uebergrosser Einzelblock eigene Spalte', () => {
    assert.deepStrictEqual(distributeGreedy(items([500, 100]), 2, 300, 0), [[0], [1]]);
});
test('distributeGreedy: Entfaelle ans Ende des Leseflusses', () => {
    // idx1 ist cancel -> hinter die regulaeren sortiert; passt mit in erste Spalte
    assert.deepStrictEqual(distributeGreedy(items([100, 50], [1]), 2, 300, 0),
                           [[0, 1], []]);
});
test('distributeGreedy: cancel-Header reserviert Platz pro Spalte', () => {
    // regular 200 in Spalte 0; cancel 60 + Header 46 -> 306 > 250 -> Spalte 1
    assert.deepStrictEqual(distributeGreedy(items([200, 60], [1]), 2, 250, 46),
                           [[0], [1]]);
});
test('distributeGreedy: reservierter Header wird nur einmal pro Spalte gezaehlt', () => {
    // zwei cancels 40+40; Header 46 nur beim ersten -> 40+46+40=126 <= 150 -> eine Spalte
    assert.deepStrictEqual(distributeGreedy(items([40, 40], [0, 1]), 2, 150, 46),
                           [[0, 1], []]);
});
