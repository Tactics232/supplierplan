# Layout engine lives in a tested `layout-core.js`, not a Python mirror

The browser layout engine (~620 lines: column distribution, overflow
scale/reduce/paginate) was embedded as an f-string inside `generate_html`, and a
hand-written Python file `_layout_logic.py` re-implemented a subset of it *only*
so `tests/test_layout.py` / `tests/test_overflow.py` had something to assert
against. The tests verified the copy, not the shipped JS. The two drifted: the
mirror's `distribute_blocks` still modelled "cancels dumped into the last column"
while the real `distributeGreedy` had long since moved to per-column reserved
cancel headers — a live instance of tests staying green while the browser
diverged.

We **extracted the JS out of Python** into two static files and made the real
code the thing under test:

- `js/layout-core.js` — the **pure** layout math (`fitScale`,
  `distributeUncapped`, `paginateColumns`, `distributeGreedy`), zero
  `window`/`document`. Functions are globals in the browser plus a
  `module.exports` guard at the file end so Node can `require` them. This is what
  the tests import.
- `js/layout.js` — the **driver**: measures DOM heights
  (`getBoundingClientRect`), calls the core with pre-measured
  `{height, isCancel}` arrays, then `appendChild`s the result. Untested by
  machine (as it always was), verified in the browser.

Both are loaded via `<script src="…?v=…">` (core before driver), matching the
existing `css/style.css?v=` pattern. `_layout_logic.py` and its two Python tests
are deleted.

Why the split rather than testing one file behind a guard: making the pure math a
file with **no DOM reference at all** turns "pure and testable" into a structural
guarantee instead of a discipline. Drift becomes impossible because there is only
one implementation.

Tests run under Node's built-in runner (`node --test tests/js/`, `node:assert`) —
**no npm packages**. This treats "no external dependency" as a **runtime**
invariant (the LXC cron and the tray `.exe` stay pure Python stdlib; a `.js` file
read and served is still stdlib) but **not** a test-time one (Node runs only on
the developer machine). A Python wrapper test (`tests/test_layout_js.py`) shells
out to `node --test` so the JS suite rides along with `python -m unittest`, and
**skips loudly** ("node fehlt") when Node is absent — mirroring the pre-commit
hook's existing Python-finder. The pre-commit hook is extended to run the JS
suite too.

Considered and rejected:

- **jsdom to test the driver.** jsdom has no layout engine —
  `getBoundingClientRect()` returns `0` — so it cannot test the one thing the
  driver does (measure heights). First heavy npm dependency for near-zero value.
- **Keeping the Python mirror and enforcing sync by discipline.** That is the
  status quo that produced the drift.
- **A single `layout.js` with an `if (typeof document…)` guard.** Saves one file
  but re-mixes the pure and DOM concerns that caused the problem.

The remaining unautomated risk is the driver refactor (splitting measurement out
of `distributeGreedy`/`distributeUncapped`): there is no browser golden. It is
anchored by a manual browser check over three reproducible fixtures — a normal
2–4 column day, an overflow day (scale→reduce→paginate), and a day with a large
cancel section spanning columns (the case that had drifted).
