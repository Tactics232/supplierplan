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
