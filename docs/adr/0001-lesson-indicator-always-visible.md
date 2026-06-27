# Lesson indicator is always visible and rolls into the next school day

The header "Laufende Stunde" element originally showed the current period from the
time-of-day grid and a "—" placeholder otherwise — and an early request was to
*hide* it on non-school days ("nur an Tagen mit Unterricht"). We instead made it
**always present**: when no lesson is running (break, before the first lesson,
after the last, or on a weekend/holiday) it shows the **next** upcoming lesson,
rolling forward into the next School day ("Nächste Stunde · 1. · Mo 08:00"). A
filled pulsing dot marks a running lesson, a hollow dot an upcoming one.

Why: a monitor in a hallway is most useful when it always answers "what's next",
including first thing in the morning and over the weekend. A hidden element
answers nothing; a "—" placeholder is noise. The trade-off is that the indicator
now needs the holiday set and the next-school-day lookup (it is no longer a pure
function of the clock), and on a weekend it deliberately points at a future day —
which is surprising until you know this decision.

Considered and rejected: hiding the element on non-school days (the original ask),
and showing "Unterricht beendet" / "—" after the last lesson. Both were dropped in
favour of always surfacing the next lesson.
