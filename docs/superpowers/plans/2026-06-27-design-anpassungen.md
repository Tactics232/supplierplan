# Plan: Design-Anpassungen (Leer-Zustand, übersprungene Tage, Lesson indicator, Mobil)

Datum: 2026-06-27
Vokabular: siehe `CONTEXT.md` (School day, Lesson indicator, Empty state, Skipped day).
Entscheidung: `docs/adr/0001-lesson-indicator-always-visible.md`.

Vier unabhängige Features. Reihenfolge nach Risiko/Abhängigkeit: erst die testbaren
Kern-Funktionen (Lesson indicator, Skipped days) TDD-first, dann Render + CSS.

---

## Feature 3+4: Lesson indicator (Kern, TDD-first)

**Ziel:** Header-Element zeigt laufende Stunde, sonst die nächste — auch in den
nächsten Schultag rollend. Nie ausgeblendet. (ADR 0001)

### Pure function (testbar, kein Netz)
Neue Funktion in `fetch_untis.py`, ersetzt die Nutzung von `find_current_period`
(Zeile 236) am Aufrufer (Zeile 2055):

```
lesson_indicator(timegrid, now_t, today, holiday_set) -> dict | None
  # now_t = HHMM int; today = date; holiday_set wie parse_holidays
  # Rückgabe None nur wenn timegrid leer (Fallback: Element weglassen).
  # sonst dict:
  #   { "state": "running" | "upcoming",
  #     "nr": int, "start": "HH:MM", "end": "HH:MM",
  #     "day_offset": 0 (heute) | >0 (künftiger Schultag),
  #     "weekday_short": "Mo" (nur wenn day_offset>0) }
```

Logik:
1. `is_school_today = today.weekday() < 5 and today not in holiday_set`
2. Wenn `is_school_today` und eine Periode mit `s <= now_t <= e` → `state=running`.
3. Sonst wenn `is_school_today` und eine Periode mit `start > now_t` existiert →
   nächste solche (kleinster start) → `state=upcoming`, `day_offset=0`.
4. Sonst: erster Unterrichtstag = `next_school_day(today, holiday_set)`; nimm die
   Periode mit kleinstem start dieses Tages → `state=upcoming`, `day_offset>=1`,
   `weekday_short` gesetzt. (`day_offset` = Kalendertage Differenz, nur fürs Label
   „heute vs. künftig".)

`next_school_day` (Zeile 266) wird wiederverwendet. `find_current_period` kann als
dünner Wrapper bleiben oder entfallen (geprüft: nur am einen Aufrufer genutzt).

### Tests: `tests/test_lesson_indicator.py`
Mirror-Stil wie `test_absences.py` (importlib-Load von `fetch_untis.py`). TG wie dort.
Fälle:
- 10:00 mitten in Std 3 → running, nr=3.
- 08:52 in der Pause (zwischen Std 2 und 3) → upcoming, nr=3, day_offset=0.
- 07:30 vor Std 1 → upcoming, nr=1, day_offset=0.
- 14:00 nach letzter Std an einem Do → upcoming nächster Schultag (Fr), day_offset=1.
- Samstag 10:00 → upcoming, nr=1, nächster Schultag Mo, day_offset=2.
- Feiertag (today in holiday_set) → upcoming nächster Schultag.
- Leeres timegrid → None.

### Render (`generate_html`, Zeile 973–988)
Signatur ändern: statt `period_nr, period_start, period_end` ein `indicator`-Dict
(am Aufrufer Zeile 2086–2088 anpassen). Block:
- `running`: Label „Laufende Stunde", Punkt `.period-dot.running` (Puls), Wert
  `<nr>.<span class="period-unit"> Stunde</span>`, Zeit `<start> – <end>`.
- `upcoming`, day_offset 0: Label „Nächste Stunde", `.period-dot.next` (hohl), Wert
  wie oben, Zeit `ab <start>`.
- `upcoming`, day_offset>0: wie vor, Zeit `<weekday_short> <start>`.
- `indicator is None`: Element ganz weglassen.
Die „—"-Branch (Zeile 981–988) entfällt. `esc()` für alle Werte (sind aber rein
numerisch/aus Timegrid — trotzdem escapen).

---

## Feature 2: Skipped days (Kern, TDD-first)

**Ziel:** dezente Sub-Zeile unter „Nächster Schultag", nur wenn ein freier Schultag
übersprungen wird. Wochenenden nie. (CONTEXT.md „Skipped day".)

### Holiday-Namen verfügbar machen
Neue/erweiterte Funktion neben `parse_holidays` (Zeile 249):
```
build_holiday_info(holidays_raw) -> dict[date] -> (name|None, is_multiday)
  # name = entry["name"] wenn "brauchbar", sonst None
  # brauchbar = enthält Buchstaben UND nicht regex ^Ferien\d+$
  #   (verworfen: "1.1.", "Ferien5"; behalten: "Fronleichnam", "Sommerferien",
  #    "schulautonom frei")
  # is_multiday = startDate != endDate des Entrys
  # longName wird IGNORIERT (stale/falsches Jahr — siehe CONTEXT.md).
```
`parse_holidays` (Set) bleibt für die Schultag-Logik; die Info-Map ist additiv.

### Pure function
```
skipped_free_days(today, next_day, holiday_info) -> list[(label, span_str)]
  # Iteriere d in (today, next_day) exklusiv:
  #   - d.weekday() >= 5  → überspringen (Wochenende, nie anzeigen)
  #   - sonst (muss freier Schultag sein): label = name or fallback
  #       fallback = "Ferien" wenn is_multiday sonst "Feiertag"
  # Aufeinanderfolgende Tage mit identischem label zu einem Segment mergen.
  # span_str: ein Tag → "Mo"; mehrere → "Mo–Mi" (WEEKDAYS_SHORT).
  # Rückgabe [] wenn nichts Freies dazwischen → keine Sub-Zeile rendern.
```

### Tests: `tests/test_skipped_days.py`
- Fr→Mo (nur WE) → [].
- Fr→Di, Mo=Fronleichnam → [("Fronleichnam","Mo")].
- Mi→Mo, Do=Fronleichnam, Fr=schulautonom frei, Sa/So WE → zwei Segmente, WE fehlt.
- mehrtägige Ferien (is_multiday, kein Name) → [("Ferien","Mo–Fr")].
- Einzel-Feiertag ohne Namen ("1.1.") → [("Feiertag","Do")].
- `build_holiday_info`: "Ferien5"→None, "Fronleichnam"→Name, "1.1."→None.

### Render
In `main` Segmente berechnen (nur wenn `show_tomorrow and (tomorrow-today).days>1`),
als Param `tomorrow_skipped` an `generate_html` durchreichen. Im
`tomorrow_section`-Titelbereich (Zeile 1055–1058) Sub-Zeile einfügen:
`<div class="skipped-days">übersprungen <span>Mo (Fronleichnam)</span> · …</div>`
nur wenn Liste nicht leer. `esc()` auf label (Untis-Namen!).

---

## Feature 1: Empty state (Render + CSS)

`generate_html` Zeile 1067–1072 ersetzen. Mittiger Panel:
```
<div class="empty-state center">
  <svg class="empty-check">✓</svg>
  <p class="empty-title">Keine Vertretungen</p>
  <p class="empty-stand">Stand: {import_time:%d.%m.%Y, %H:%M} Uhr</p>
</div>
```
`import_time` ist bereits Parameter. Fehlt es → „nach aktuellem Stand". `esc()` n/a
(keine API-Strings), aber `PLAN_TITLE` nicht mehr nötig.
Die tote Per-Tag-Branch (Zeile 840–843) bleibt unverändert (nie erreicht).

---

## CSS (`css/style.css`)

1. **Empty state** (`.empty-state`, ~Zeile zu suchen): flex-center vertikal+horizontal
   im Plan-Bereich, Karten-Look (border, radius, gedämpft), `.empty-check` grün,
   `.empty-title` groß, `.empty-stand` muted klein.
2. **Lesson indicator dot:** `.period-dot.running` = aktueller grüner Puls;
   `.period-dot.next` = hohl (transparent, 1.5px border `--c-muted`, kein Puls).
3. **Skipped days:** `.skipped-days` kleine, muted Zeile unter dem day-title-bar.
4. **Mobil (`@media max-width:600px`, Block ab Zeile 906):**
   - `.period-unit { display: none; }` (versteckt „ Stunde").
   - `.period-time { display: none; }` (Zeitzeile weg).
   - `.skipped-days` ggf. ausblenden oder kompakt (Mobil ist scrollbar; vermutlich
     behalten, aber prüfen).
   - sicherstellen `.current-period`/`.header-right` `white-space: nowrap` und nicht
     über den rechten Rand laufen (`● 3.` ist schmal genug).

---

## Reihenfolge / Verifikation
1. `lesson_indicator` + Tests (rot→grün).
2. `build_holiday_info` + `skipped_free_days` + Tests.
3. Render-Umbau in `generate_html` + Aufrufer + Signatur.
4. CSS (Empty state, dot, skipped, Mobil).
5. Lokaler Lauf: `PYTHONIOENCODING=utf-8 …/python.exe scripts/fetch_untis.py`,
   `index.html` im Browser prüfen (Breit / Schmal / Mobil via DevTools), inkl.
   Leer-Zustand (Tag ohne Vertretungen) und einem Wochenend-/Feiertags-Szenario.
6. `python -m pytest tests/` grün.
7. Code-Map regeneriert sich per pre-commit-Hook.

## Offen / bewusst nicht gelöst
- Laufend-vs-nächste ist mobil nur am Punkt (gefüllt/hohl) erkennbar — Label ist
  mobil ausgeblendet (bewusst, Feature-3-Entscheidung).
- Skipped-day-Datumsformat nutzt Wochentag-Kürzel ohne Datum; bei sehr langen
  Ferienblöcken evtl. später Datums-Spanne ergänzen.
