# Classes whose lessons are all cancelled count as absent, even in monitor mode

ADR 0003 made the WebUntis monitor the sole source of the absence bars. On
2026-11-03 classes 2A, 2B and 2C were on an excursion, yet "Abwesende Klassen" read
`—`. The school had entered the excursion only as **teacher** absences (the
accompanying teachers all day); their lessons were cancelled, so every single
lesson of the three classes was `CANCEL` (16, 12 and 13 periods), but no class
absence record or Untis event existed. The official monitor view shows no class
either, so the board matched the reference and was still useless for the day.
Entering excursions as class absences is the clean fix, but it depends on how the
office works and cannot be relied on.

We now add one rule on top of the monitor data: **a class whose lessons that day are
all cancelled is shown as absent all day.** The class timetables come from
`weekly/data` (one call per class, 14 classes ≈ 1 s per day), fresh on every run,
no cache.

Decisions taken with it:

- **Strict rule, not the weekly heuristic.** "All lessons cancelled" has no false
  positives worth worrying about; the weekly mode's "≥2 consecutive cancellations"
  caught partial cancellations and was part of what ADR 0003 measured as wrong.
  Partial class absences stay a monitor-only matter. A class with no lessons that
  day never counts.
- **Shown like a real entry**: just the class name, no marker. For the people in
  front of the monitor the provenance does not matter, and space is short on
  project days.
- **A real monitor entry wins** over the derived one (keeps its window).
- **Cancellation rows stay.** All "Entfallende Stunden" rows are still shown, even
  for classes the bar already lists — they also tell present teachers that they are
  free.
- **Derivation failure is soft**: the bar shows only the monitor classes and the
  error goes to the log. Unlike a failed monitor fetch this does not read
  `nicht verfügbar`; the derivation is a supplement, not the source.
- **Switchable** via `ABSENCE_DERIVE_CLASSES` (default `true`, only effective with
  `ABSENCE_SOURCE=monitor`), for schools that enter class absences properly and want
  to save the calls.

This mixes sources, which ADR 0003 otherwise avoids. It is not a fallback: the
monitor still has to succeed, and the rule only ever adds classes that are
provably without lessons.
