# Absences come from the WebUntis monitor, not from the timetable

The "Abwesende Lehrer/Klassen" bars were derived from each teacher's and class's
timetable via `weekly/data` (`cellState` per period, ~94 calls per day, cached and
refreshed 3×/day). That turned out to be a guess, not a source, and it was wrong in
production. Against the school's own WebUntis monitor for 2026-11-03 it showed
**14 false absences in one day**:

- `SUBSTITUTION` in a teacher's own timetable means *either* "is being replaced"
  *or* "is the replacement". Ten present teachers who covered for colleagues were
  listed as absent with a period range.
- A taken-over break supervision has a `startTime` outside the lesson grid; the range
  came out empty and four teachers who taught all day were shown as **fully** absent.
- Absence windows without lessons in them (SeM/WeN "6–7" with no lesson at that time)
  are invisible in a timetable by construction.

We now read the **absence records themselves** from the endpoint behind the WebUntis
monitor view: `POST /WebUntis/monitor/substitution/data` with the school's monitor
format name (here `Roda Roda 2`, taken from the pasted monitor URL). Its
`absentElements` list each absent teacher/class with typed windows (`ALL_DAY`,
`FROM`, `FROM_TO`, …) and start/end times. On four checked school days it matched
the monitor exactly, because it *is* the monitor's data. It is one call per shown
day, so it runs on every regular run with no cache.

Decisions taken with it:

- **`ABSENCE_SOURCE=monitor` is the default; `weekly` stays as an explicitly chosen
  mode** for schools without a monitor format. There is **no automatic fallback**
  from monitor to weekly: the fallback would be exactly the guessing we just measured
  as wrong, and a wrong bar is worse than an honest "nicht verfügbar". A failed or
  unconfigured monitor fetch shows `nicht verfügbar` on the board (visibly distinct
  from "nobody absent"); details go to the log and the tray status only — the board
  is public.
- **Period numbers are converted to the board's own numbering** via the windows'
  start/end times (the monitor counts Untis unit names, one higher than our `Std`
  because of the 0th period). Board and bar must agree on one screen.
- **Whole-day bars stay whole-day**: past windows are not hidden during the day.
- The **`weekly` rule was rebuilt** on `orgId` instead of `cellState`: a period is
  away when another teacher replaces this one; `CANCEL` only counts when the teacher
  has at least one replaced period that day or no lesson at all. Over the same four
  days: 1 false alarm (was 14 on one day), 36 of 40 absences found. The remainder is
  undetectable from a timetable — documented as a limit, not a bug.

Considered and rejected: `classreg/absences/teachers` (500 for our account, as in
the 2026-06-27 investigation), and asking for broader user rights — the monitor
endpoint only needed the right format name (`-8520 access not allowed` was a wrong
format name, not missing rights).

Supersedes `docs/superpowers/specs/2026-06-27-absence-from-weekly-data-design.md`
as the default absence source.
