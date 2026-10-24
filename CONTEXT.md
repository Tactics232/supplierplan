# Supplierplan – Domain Language

Glossary for the substitution-plan display (MS Roda-Roda-Gasse). Terms here are
the canonical vocabulary used across `fetch_untis.py`, the JS layout engine, CSS,
and docs. Definitions only — no implementation details.

## Language

**Entfall (cancellation)**:
A lesson that does not take place. In the data its row carries `art=cancel`; the
affected teacher is shown struck-through with no substitute.
_Avoid_: dropout, free period (a `free` period is a distinct `art`).

**Cancel placement**:
The display policy for where Entfall rows appear. Two modes, selected per school
via the `CANCEL_PLACEMENT` config key.

**Section mode** (`CANCEL_PLACEMENT=section`):
Every Entfall row is pulled out of its teacher group and collected into one
shared "Entfallende Stunden" block at the end of the day. This is the default.
_Avoid_: end block, cancel section (use "Section mode" when naming the policy).

**Inline mode** (`CANCEL_PLACEMENT=inline`):
Each Entfall row stays inside the block of the teacher it affects, rather than
being collected at the end. There is no shared "Entfallende Stunden" block.

**Teacher block**:
The per-teacher group of rows in a day, headed by `<Kürzel> First Last`. Grouped
by the teacher currently shown in the row.

**School day (Schultag)**:
A weekday (Mon–Fri) that is not a public holiday or Ferientag. The unit that
`next_school_day` lands on and that the Lesson indicator and Skipped-day line
reason about.
_Avoid_: "working day" (weekends are excluded, holidays too).

**Lesson indicator (Laufende / Nächste Stunde)**:
The header element naming the lesson currently in progress ("Laufende Stunde"),
or — during a break, before the first lesson, or after the last — the next
upcoming lesson ("Nächste Stunde"), rolling forward into the next School day when
today has no more lessons. It is **always present**: there is no "no lesson"
empty form. A filled, pulsing dot marks a running lesson; a hollow dot marks an
upcoming one.
_Avoid_: "current period" alone — it also surfaces the *next* lesson, and may
point at a future day.

**Empty state (Keine Vertretungen)**:
The centered, on-brand message shown when **neither** today **nor** the next
School day has any substitution row. It means regular lessons take place (good
news), not a data error, and carries the Untis data timestamp ("Stand: …").
_Avoid_: "no plan available", "error" — the data was fetched; it is simply empty.

**Skipped day (Übersprungener Tag)**:
A non-teaching calendar day lying between today and the next School day. Free
school days (public holiday, Ferien, schulautonom frei) are surfaced under the
"Nächster Schultag" label, named by their Untis `name` where human-readable,
else the generic "Feiertag" (single day) / "Ferien" (multi-day block). Weekends
are **not** labelled and never appear in the line.
_Avoid_: naming weekends here; relying on the Untis `longName` (it is a stale,
wrong-year date string).

**Absence bar (Abwesenheits-Leiste)**:
The "Abwesende Lehrer / Abwesende Klassen" line at the top of each day section.
A name alone means absent all day; `(ab 7)`, `(5–6)`, `(2, 4)` name the board
periods of the absence windows. Shows the whole day — past windows are not hidden.
When the source fails it reads `nicht verfügbar`, which is distinct from `—`
(nobody absent).
_Avoid_: rendering a failed fetch as an empty bar.

**Absence source (Abwesenheits-Quelle)**:
Where the Absence bar's data comes from, chosen via `ABSENCE_SOURCE`. **Monitor**
(default): the school's real absence records, read from the WebUntis monitor view
(`MONITOR_URL`). **Weekly**: an estimate derived from every teacher's and class's
timetable; it only sees absences that touch a lesson. Neither silently falls back
to the other.
_Avoid_: calling the weekly estimate "authoritative".

**Fully cancelled class (komplett entfallende Klasse)**:
A class that has lessons on a day and every one of them is cancelled. In monitor
mode it is added to the Absence bar as absent all day, shown like a real entry
(ADR 0004, switch `ABSENCE_DERIVE_CLASSES`). Typical cause: an excursion entered
only as teacher absences. A class without lessons that day is not one.
_Avoid_: deriving partial class absences from cancellations in monitor mode.

**Absence window (Abwesenheitsfenster)**:
One time span of an absence record (`ALL_DAY`, `FROM`, `FROM_TO`, …), given by
clock times and converted to board periods. A teacher can have several per day.
_Avoid_: using monitor unit numbers directly — they count one higher than the
board's `Std` (0th period).

**DisplaySettings**:
The immutable bundle of **display** configuration, derived once from `config.env`
by `DisplaySettings.from_config` and threaded explicitly into `generate_html`,
`build_day_content`, `render_row`/`render_text` and `write_manifest`. It is the
single home for every presentation knob (theme, school labels, column/overflow
behaviour, Plan title, logo, Cancel placement, text badges, PWA orientation, the
clock's timezone string). No render function reads a mutable module global any
more.
_Scope_: display only. It deliberately excludes the **data-pipeline** skip list
(`SKIP_NAMES`, set by `configure_skip_teachers`) and the **process-wide**
timezone object (`TZ`, set by `set_timezone`); `tz_name` here is only the string
handed to the client-side clock, not the `ZoneInfo`.
_Avoid_: calling it "the config" (that is the raw `config.env` dict) or a
"context"/"state" object; folding data-pipeline or timezone concerns into it.

**Layout core (`js/layout-core.js`)**:
The **pure** browser layout math — `fitScale`, `distributeUncapped`,
`paginateColumns`, `distributeGreedy` — operating only on pre-measured
`{height, isCancel}` arrays, with **no** `window`/`document` reference. It is the
single implementation of the column/overflow logic and the only thing the layout
tests import. Loaded in the browser as globals; `require`-able in Node via a
`module.exports` guard.
_Avoid_: "the mirror" — there is no longer a Python re-implementation; the retired
`_layout_logic.py` was the mirror.

**Layout driver (`js/layout.js`)**:
The DOM-facing half of the engine: it **measures** heights
(`getBoundingClientRect`), calls the Layout core with the measured arrays, and
`appendChild`s the resulting columns. Machine-untested by design (measurement
needs a real layout engine); verified in the browser against the layout fixtures.
_Avoid_: putting layout math here — arithmetic belongs in the Layout core.

**Runtime invariant ("no external dependency")**:
The rule that the shipped paths — LXC cron and the tray `.exe` — run pure Python
stdlib. Reading and serving a static `.js` file honours it. It is **not** a
test-time rule: Node (built-in `node --test`) runs the Layout core tests on the
developer machine only, and the wrapper test skips **loudly** where Node is
absent.
_Avoid_: reading it as "no tooling ever" — it constrains runtime, not the dev
toolchain.

## Tray service

Vocabulary for the local Windows tray application's background service.

**Regulärer Lauf (regular run)**:
A full board render that **reads** the absence cache rather than re-deriving it.
The cheap, frequent run. The Empty state, Lesson indicator and substitution rows
are all produced by it.
_Avoid_: "refresh" alone — it does not refresh absences.

**Abwesenheits-Lauf (absence run)**:
A full board render that additionally **forces a fresh weekly/data sweep**,
rewriting the absence cache. The expensive run (~94 element calls). Only exists
for the **Weekly** Absence source — with **Monitor**, every Regulärer Lauf fetches
absences fresh and there is no cache. Fires on a small fixed set of clock times and
on the manual "Abwesenheiten aktualisieren" trigger. A Regulärer Lauf falls back to
one self-healing sweep only when the cache is missing the day it needs.
_Avoid_: "sweep" used for the whole run — the sweep is the absence step inside it.
