// js/layout-core.js — reine Layout-Mathematik, KEIN window/document.
// Browser: Funktionen sind Globals. Node: via module.exports require-bar.
// Getestet in tests/js/layout-core.test.js. Siehe docs/adr/0002-*.

// Größter Skalierungsfaktor in {1.0, 1-step, …} >= scaleMin, bei dem
// contentH * f <= availH. Passt es bei 1.0, kommt 1.0; sonst runter bis scaleMin.
function fitScale(contentH, availH, scaleMin, step) {
    step = step || 0.05;
    if (contentH <= 0 || contentH <= availH) return 1.0;
    if (availH <= 0) return scaleMin;
    var steps = Math.round((1.0 - scaleMin) / step);
    for (var i = 0; i <= steps; i++) {
        var s = Math.round((1.0 - i * step) * 10000) / 10000;
        if (contentH * s <= availH) return s;
    }
    return scaleMin;
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
    var perPage = Math.ceil(n / nPages);  // <= maxCols
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
