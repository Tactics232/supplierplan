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
