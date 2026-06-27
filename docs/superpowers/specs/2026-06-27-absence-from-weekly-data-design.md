# Abwesende Lehrer & Klassen — autoritativ aus `weekly/data`

**Datum:** 2026-06-27
**Status:** ✅ Umgesetzt (2026-06-27). Kern: `sweep_absences`, `teacher_absence_entry`,
`class_absence_entry`, `get_element_periods`; Cache `data/absences.json`; CLI
`--refresh-absences`. Tests: `tests/test_absences.py`.
**Betroffen:** `scripts/fetch_untis.py` — Abwesenheits-Leisten oben in jeder Tages-Section

## Problem

Die „Abwesende Lehrer/Klassen"-Leisten waren falsch:

1. **Lehrer**: Die Abwesenheit wurde aus dem **Supplierplan** abgeleitet
   (`extract_absent_periods` → `compute_absent`). Die Stunden-Range war „min–max der
   Stunden, die der Lehrer gehabt hätte". Folge: Ein **ganztägig** abwesender Lehrer, der
   nur in Stunde 4–7 Unterricht hat, wurde als `Kürzel (4–7)` angezeigt — das suggeriert
   fälschlich Teil-Anwesenheit. `determine_full_absent` sollte das auf „nur Kürzel"
   runterstufen, griff aber nicht zuverlässig.
2. **Klassen**: `get_weekly_class_absences` war **doppelt kaputt** — `elementId=0`
   (Phantom, liefert leeres `elementPeriods: {"0": []}`) **und** falsches Feld
   (`state` steht selbst bei Entfall auf `REGULAR`; maßgeblich ist `cellState`).

## Untersuchung (Live-API, echte Daten)

Geprüft gegen die Schul-WebUntis am 2026-06-27 (Daten aus vergangenen Wochen, da kurz
vor den Ferien).

- **Dedizierte Endpunkte gibt es nicht für uns:** `classreg/absences/teachers` und
  `/students` → **500**, auch nach Rechte-Anpassung; `classreg/absences`,
  `classreg/events`, `api/v1/absences` → **404**. Kein „Liste alle Abwesenden"-Call.
- **Einziger verlässlicher Weg:** `weekly/data?elementType=<T>&elementId=<echte ID>`.
  `elementId=0` ist ein Phantom (leer/falsch) — niemals verwenden.
- **`cellState`-Semantik (verifiziert):**
  - Klassen (`elementType=1`): Werte `STANDARD`, `SUBSTITUTION`, `CANCEL`, `ADDITIONAL`.
    Eine **komplett abwesende Klasse** (Exkursion/Projekt) hat **alle** Stunden `CANCEL`
    und sonst nichts (Beispiel 2026-06-08: 1A/1B/1C/3B/3C je `{CANCEL: n}`).
  - Lehrer (`elementType=2`): anwesend = `STANDARD` / `BREAKSUPERVISION`;
    weg = `SUBSTITUTION` / `CANCEL`. Am 2026-06-16 sauber getrennt: 15 komplett
    abwesende Lehrer (kein einziges `STANDARD`/`BREAKSUPERVISION`) vs. 21 teil-abwesende.
  - ⚠️ Der Pseudo-Lehrer `Z Entfall` erscheint als „komplett abwesend" → muss über
    `SKIP_NAMES` gefiltert werden.

## Design-Entscheidungen (Grilling)

1. **Quelle = `weekly/data`, autoritativ.** Abwesenheit (Set, voll/teil, Range) wird pro
   Element direkt aus `weekly/data` bestimmt, nicht mehr aus dem Supplierplan.
2. **Lehrer:**
   - anwesend-Stunde = `cellState ∈ {STANDARD, BREAKSUPERVISION}`
   - **komplett abwesend** (keine anwesende Stunde) → **nur Kürzel** (keine Range)
   - **teil-abwesend** → Range `min–max` der Weg-Stunden (`SUBSTITUTION`/`CANCEL`)
   - Pseudo-Lehrer (`SKIP_NAMES`) ausschließen
3. **Klassen:**
   - weg-Stunde = `cellState == CANCEL`; anwesend = `STANDARD`/`SUBSTITUTION`/`ADDITIONAL`
   - Eine Klasse erscheint **nur**, wenn sie einen **zusammenhängenden Block von ≥2
     CANCEL-Stunden** hat (Einzelausfall ≠ „Klasse weg"). Angezeigt wird die Range des
     (längsten) Blocks; komplett abwesende Klasse = ein Block über den ganzen Tag.
4. **Abdeckung:** über **alle** echten Klassen-IDs (14) und Lehrer-IDs iterieren —
   unabhängig vom Supplierplan. `weekly/data` liefert eine ganze Woche pro Call → heute +
   nächster Schultag aus *einem* Call (Cache pro Element/Woche).

## Kosten

~14 Klassen + ~80 Lehrer = ~94 `weekly/data`-Calls je Run (Woche gecached, also nicht ×2
Tage). Jeder Call ~20 KB, in Summe ~15–20 s. Im 5-Minuten-Cron unkritisch. Pro Call
try/except → ein Fehler überspringt nur dieses Element (sichere Rückfallebene: Element
fällt aus der Leiste, statt den Run zu killen).

## Betroffene Funktionen

- **Neu/ersetzt:** generische `weekly/data`-Periodenabfrage (statt
  `get_weekly_class_absences` mit `elementId=0`), Lehrer- und Klassen-Abwesenheit darauf
  aufbauend; Block-Erkennung (≥2 konsekutiv) für Klassen.
- **Vereinfacht:** `extract_absent_periods`/`compute_absent` liefern die Abwesenheits-
  Leiste nicht mehr (Supplierplan bleibt nur Quelle der Tabellen-Zeilen).
- **Wiring:** `main()` baut Lehrer-/Klassen-Listen aus `weekly/data`,
  `generate_html(... today/tomorrow override-Listen ...)` bleibt von der Schnittstelle
  her gleich.

## Doku-Folgeschritte

- `CLAUDE.md`: Abschnitt „Abwesenheits-Leisten" auf die neue Quelle umschreiben; die
  `cellState`-Tabelle (Klasse vs. Lehrer) ergänzen.
- `docs/index.html` (Abschnitt „Absence bars"): cellState-Semantik aufnehmen.
