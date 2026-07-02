# Code Map

_171 functions across 19 modules._

> **Auto-generated** by `scripts/gen_codemap.py` — do not edit by hand.
> Regenerated on every commit (git pre-commit hook). The narrative *why*
> (heuristics, design decisions) lives in [`CLAUDE.md`](../CLAUDE.md);
> deep internals in [`docs/index.html`](index.html). This file is the
> **navigation index**: find the right function here, then open the code.

## Modules

- [`scripts/__init__.py`](#scriptsinitpy)
- [`scripts/_layout_logic.py`](#scriptslayoutlogicpy)
- [`scripts/diagnose_api.py`](#scriptsdiagnoseapipy)
- [`scripts/discover_api.py`](#scriptsdiscoverapipy)
- [`scripts/explore_rest.py`](#scriptsexplorerestpy)
- [`scripts/fetch_trains.py`](#scriptsfetchtrainspy)
- [`scripts/fetch_untis.py`](#scriptsfetchuntispy)
- [`scripts/gen_codemap.py`](#scriptsgencodemappy)
- [`tray/__init__.py`](#trayinitpy)
- [`tray/app.py`](#trayapppy)
- [`tray/autostart.py`](#trayautostartpy)
- [`tray/build.py`](#traybuildpy)
- [`tray/config_io.py`](#trayconfigiopy)
- [`tray/gui.py`](#trayguipy)
- [`tray/icons.py`](#trayiconspy)
- [`tray/paths.py`](#traypathspy)
- [`tray/schedule.py`](#trayschedulepy)
- [`tray/server.py`](#trayserverpy)
- [`tray/service.py`](#trayservicepy)

<h2 id="scriptsinitpy">scripts/__init__.py</h2>

_(no top-level functions or classes)_

<h2 id="scriptslayoutlogicpy">scripts/_layout_logic.py</h2>

__layout_logic.py – Verteilung von Render-Blöcken in N Spalten (Greedy-Fit)._

| Line | Definition | Summary |
|---:|---|---|
| 9 | `distribute_blocks(blocks: Iterable[dict], n_cols: int, available_height_per_col: int=None)` | Verteilt Blöcke in n_cols Spalten per Greedy-Fit von links nach rechts. |
| 52 | `fit_scale(content_height, available_height, scale_min, step=0.05)` | Größter Skalierungsfaktor in {1.0, 1-step, ...} >= scale_min, bei dem |
| 68 | `distribute_uncapped(block_heights, available_height_per_col, cancel_flags=None, cancel_header_h=0)` | Greedy-Verteilung in BELIEBIG viele Spalten (kein MAX_COLS-Limit). |
| 97 | `paginate_columns(columns, max_cols)` | Teilt eine Liste von Spalten in Seiten auf — höchstens max_cols pro Seite, |

<h2 id="scriptsdiagnoseapipy">scripts/diagnose_api.py</h2>

_diagnose_api.py – Zeigt ALLE Rohdaten von getSubstitutions ungefiltert an._

| Line | Definition | Summary |
|---:|---|---|
| 18 | `load_config()` | — |
| 28 | **`class WebUntis`** | — |
| 29 | &nbsp;&nbsp;`WebUntis.__init__(self, url, school_id, user, password)` | — |
| 40 | &nbsp;&nbsp;`WebUntis._rpc(self, method, params=None)` | — |
| 53 | &nbsp;&nbsp;`WebUntis.login(self)` | — |
| 58 | &nbsp;&nbsp;`WebUntis.logout(self)` | — |
| 64 | &nbsp;&nbsp;`WebUntis.get_substitutions(self, date_int)` | — |
| 69 | &nbsp;&nbsp;`WebUntis.rest_get(self, path)` | — |
| 80 | `analyse(substs, label)` | — |
| 156 | `main()` | — |

<h2 id="scriptsdiscoverapipy">scripts/discover_api.py</h2>

_discover_api.py – Systematische Erkundung aller WebUntis-API-Endpunkte_

| Line | Definition | Summary |
|---:|---|---|
| 31 | `load_config()` | — |
| 42 | **`class WebUntis`** | — |
| 43 | &nbsp;&nbsp;`WebUntis.__init__(self, url, school_id, user, password)` | — |
| 55 | &nbsp;&nbsp;`WebUntis.rpc(self, method, params=None)` | — |
| 74 | &nbsp;&nbsp;`WebUntis.rest(self, path)` | — |
| 89 | &nbsp;&nbsp;`WebUntis.login(self)` | — |
| 97 | &nbsp;&nbsp;`WebUntis.logout(self)` | — |
| 104 | `short(data, n=300)` | — |
| 114 | `save(name, data)` | — |
| 120 | `summarize(name, res)` | — |
| 143 | `section(title)` | — |
| 149 | `main()` | — |

<h2 id="scriptsexplorerestpy">scripts/explore_rest.py</h2>

_explore_rest.py – Erkundet die WebUntis REST API mit bestehenden Credentials._

| Line | Definition | Summary |
|---:|---|---|
| 17 | `load_config()` | — |
| 27 | `main()` | — |

<h2 id="scriptsfetchtrainspy">scripts/fetch_trains.py</h2>

_fetch_trains.py – holt die nächsten Abfahrten einer Bahnhaltestelle direkt_

| Line | Definition | Summary |
|---:|---|---|
| 30 | `resolve_config_path()` | Pfad zur config.env. Bevorzugt $SUPPLIERPLAN_CONFIG, damit die Datei mit |
| 37 | `resolve_data_out()` | Verzeichnis für trains.json. Die Datei MUSS ausgeliefert werden (die Seite |
| 54 | `_now_local()` | — |
| 59 | `atomic_write_json(path: Path, data: dict)` | Schreibt JSON atomar: erst .tmp, dann os.replace. |
| 68 | `classify_direction(destination: str, towards_substrings: Iterable[str])` | Liefert 'towards' wenn destination irgendeinen Substring aus |
| 80 | `extract_departure(leg: Any)` | Wandelt ein Leg-Objekt (Duck-Typ mit name, direction, dateTime, delay, |
| 99 | `filter_by_product_prefix(legs: Iterable[Any], prefixes: Iterable[str])` | Behält nur Legs, deren `name` mit einem der `prefixes` beginnt (case-insensitive). |
| 113 | `split_by_direction(legs: Iterable[Any], towards_substrings: Iterable[str], n_per_direction: int=1)` | Iteriert über Legs (oder Duck-Typ), klassifiziert nach Richtung, |
| 133 | `load_config(path: Path)` | Liest .env-style key=value-Paare. Kommentare (#) und Leerzeilen werden ignoriert. |
| 151 | `_mgate_request(svc_method: str, params: dict)` | Sendet eine mgate.exe-Anfrage und liefert das svcResL[0].res-dict zurück. |
| 181 | `_resolve_station_lid(name: str)` | Findet eine Station per LocMatch. Liefert (resolved_name, lid). |
| 197 | `search_stations(name: str, max_results: int=8)` | Sucht Stationen per HAFAS LocMatch und liefert mehrere Treffer als Liste von |
| 214 | `_parse_hafas_time(value: str)` | HAFAS-Zeitformat HHMMSS (oder DHHMMSS für nächster Tag) → timedelta seit Tagesbeginn. |
| 228 | **`class _OebbLeg`** | Duck-typed Leg-Objekt, identische Attribute wie _FakeLeg in den Tests. |
| 231 | &nbsp;&nbsp;`_OebbLeg.__init__(self, name, direction, dateTime, delay=None, cancelled=False, platform=None)` | — |
| 240 | `_fetch_departures(lid: str, max_jny: int=12)` | Holt das StationBoard für die Location-ID und liefert _OebbLeg-Liste. |
| 307 | `main()` | — |

<h2 id="scriptsfetchuntispy">scripts/fetch_untis.py</h2>

_fetch_untis.py – WebUntis Supplierplan Fetcher_

| Line | Definition | Summary |
|---:|---|---|
| 29 | `now_local()` | Aktuelle Ortszeit (oder System-Zeit falls ZoneInfo nicht verfügbar). |
| 33 | `today_local()` | — |
| 36 | `set_timezone(name)` | Überschreibt die globale Zeitzone aus config.env (TIMEZONE). |
| 49 | `esc(s)` | HTML-escape a value from external data sources. |
| 55 | `resolve_config_path()` | Pfad zur config.env. Bevorzugt $SUPPLIERPLAN_CONFIG — damit die Datei mit |
| 64 | `resolve_webroot()` | Verzeichnis für index.html + manifest.json. Über $SUPPLIERPLAN_WEBROOT in ein |
| 71 | `resolve_data_out()` | Verzeichnis für die Roh-/Übersichts-Dumps. Über $SUPPLIERPLAN_DATA lenkbar. |
| 98 | `load_config()` | — |
| 118 | **`class WebUntis`** | — |
| 119 | &nbsp;&nbsp;`WebUntis.__init__(self, url, school_id, user, password)` | — |
| 130 | &nbsp;&nbsp;`WebUntis._rpc(self, method, params=None)` | — |
| 146 | &nbsp;&nbsp;`WebUntis.login(self)` | — |
| 151 | &nbsp;&nbsp;`WebUntis.logout(self)` | — |
| 157 | &nbsp;&nbsp;`WebUntis.get_substitutions(self, date_int, department_id=0)` | — |
| 162 | &nbsp;&nbsp;`WebUntis.get_timegrid(self)` | — |
| 165 | &nbsp;&nbsp;`WebUntis.get_teachers(self)` | — |
| 168 | &nbsp;&nbsp;`WebUntis.get_holidays(self)` | — |
| 171 | &nbsp;&nbsp;`WebUntis.get_klassen(self)` | — |
| 174 | &nbsp;&nbsp;`WebUntis.get_element_periods(self, element_type, element_id, date_obj)` | REST weekly/data für EIN Element an `date_obj` → [(startTime, cellState), …] |
| 195 | &nbsp;&nbsp;`WebUntis.get_latest_import_time(self)` | — |
| 204 | `build_timegrid(days)` | — |
| 216 | `build_break_lookup(days)` | — |
| 230 | `fmt_time(t)` | — |
| 234 | `find_current_period(timegrid)` | — |
| 242 | `lesson_indicator(timegrid, now_t, today, holiday_set)` | Zustand für den Header-„Laufende/Nächste Stunde"-Block (ADR 0001). |
| 281 | `now_hhmm()` | — |
| 286 | `parse_holidays(holidays)` | Wandelt die Untis-Ferienliste in ein Set von date-Objekten. |
| 303 | `next_school_day(start, holiday_set)` | Erster Werktag nach `start`, der kein Ferien-/Feiertag ist. |
| 310 | `_usable_holiday_name(name)` | Untis-`name` nur wenn menschenlesbar: enthält Buchstaben UND ist nicht das |
| 321 | `build_holiday_info(holidays)` | Untis-Ferienliste → dict[date] -> (name\|None, is_multiday). |
| 341 | `skipped_free_days(today, next_day, holiday_info)` | Liste der zwischen `today` und `next_day` (exklusiv) übersprungenen FREIEN |
| 376 | `configure_skip_teachers(value)` | Ergänzt SKIP_NAMES um die in config.env (SKIP_TEACHERS) gelisteten |
| 385 | `teacher_absence_entry(periods, timegrid)` | `periods` = [(startTime, cellState), …] eines Lehrers an einem Tag. |
| 404 | `_consecutive_runs(nums)` | Sortierte Ganzzahlen → Liste zusammenhängender Läufe (konsekutive Werte). |
| 419 | `class_absence_entry(periods, timegrid, min_block=2)` | `periods` = [(startTime, cellState), …] einer Klasse an einem Tag. |
| 436 | `sweep_absences(untis, teachers, klassen, date_obj, timegrid)` | Voll-Sweep via weekly/data über ALLE Lehrer + Klassen für `date_obj`. |
| 471 | `_absence_cache_path()` | — |
| 475 | `load_absence_cache()` | {date_iso: {"teachers": [...], "classes": [...]}}; {} bei Fehler/fehlend. |
| 483 | `save_absence_cache(cache)` | Atomar schreiben (alte Datei bleibt bei Fehler intakt). |
| 492 | `build_teacher_lookup(teachers)` | — |
| 507 | `_dedupe_names(items)` | Liste von dicts mit 'name' zu Liste eindeutiger Namen ohne '---' / leer. |
| 518 | `_is_meaningful_subst(s)` | True wenn die Substitution überhaupt eine echte Änderung darstellt. |
| 529 | `_has_real_subst_teacher(s)` | True wenn ein echter Vertretungs-Lehrer im te[] steht (orgid + Name != '---'). |
| 536 | `process_substitutions(substs, timegrid, break_lookup, day='today')` | — |
| 664 | `group_by_teacher(rows)` | — |
| 672 | `extract_absent_periods(groups)` | {lehrer_kuerzel: set(std)} aller abwesenden Lehrer eines Tages, abgeleitet aus |
| 691 | `compute_absent(groups, full_absent_kuerzel=None)` | `full_absent_kuerzel`: Set der Lehrer-Kürzel, die laut weekly/data den |
| 736 | `render_summary_bar(teachers, classes)` | — |
| 773 | `render_text(txt, settings)` | — |
| 788 | `render_teacher_header(kuerzel, teacher_lookup, day='today')` | — |
| 802 | `render_day_separator(d)` | — |
| 806 | `_fach_html(fach: str)` | Liefert Fach mit Lang- und Kurz-Variante. |
| 815 | `_klasse_html(klasse: str)` | Begrenzt die Klassen-Anzeige auf max. 2 Einträge, damit eine Zeile |
| 832 | `_kuerzel_cell(r, settings)` | — |
| 836 | `_std_cell(r, settings)` | — |
| 839 | `_fach_cell(r, settings)` | — |
| 842 | `_klasse_cell(r, settings)` | — |
| 845 | `_lehrer_cell(r, settings)` | — |
| 861 | `_art_cell(r, settings)` | — |
| 872 | `_raum_cell(r, settings)` | — |
| 882 | `_text_cell(r, settings)` | — |
| 885 | `_row_class(r)` | — |
| 901 | `render_row(r, settings)` | — |
| 913 | `build_day_content(groups, teacher_lookup, day, settings)` | Rendert eine flache Tabelle pro Tag. Die Aufteilung in 1–4 Spalten |
| 977 | `render_train_widget(enabled: bool)` | Liefert den HTML-Stub für das Zug-Widget im Header. |
| 994 | `parse_overflow_config(config)` | Liest die OVERFLOW_*-Keys aus config.env und liefert ein dict für die |
| 1031 | **`class DisplaySettings`** | Unveränderliches Bündel der ANZEIGE-Config (siehe CONTEXT.md „DisplaySettings"). |
| 1059 | &nbsp;&nbsp;`DisplaySettings.from_config(cls, config)` | Baut das Paket aus dem rohen config.env-dict. Alle Klemmen/Validierungen/ |
| 1118 | `generate_html(groups_today, groups_tomorrow, today_date, tomorrow_date, teacher_lookup, indicator, settings, import_time=None, today_classes_override=None, tomorrow_classes_override=None, today_teachers_override=None, tomorrow_teachers_override=None, today_full_absent=None, tomorrow_full_absent=None, tomorrow_skipped=None)` | — |
| 2018 | `purge_cloudflare_cache(zone_id, token, host=None)` | Löscht den Cloudflare-Cache nach dem Generieren der index.html. |
| 2039 | `write_manifest(settings)` | Erzeugt manifest.json passend zu Schulname, Logo, Plan-Titel und Theme. |
| 2075 | `write_data_dump(today_substs, tomorrow_substs, today_rows, tomorrow_rows, holidays, import_time, today_date, tomorrow_date)` | Schreibt zwei Dateien ins data/-Verzeichnis: |
| 2169 | `main(refresh_absences=None)` | refresh_absences: True erzwingt einen frischen weekly/data-Sweep (sonst Cache). |

<h2 id="scriptsgencodemappy">scripts/gen_codemap.py</h2>

_Generate docs/CODEMAP.md — an auto-maintained function index for AI/human navigation._

| Line | Definition | Summary |
|---:|---|---|
| 25 | `py_files()` | Yield repo-relative paths of all .py files under SCAN_DIRS, sorted. |
| 39 | `_ann(node)` | Render an annotation/expression node back to source, best-effort. |
| 49 | `format_signature(args)` | Reconstruct a readable parameter list from an ast.arguments node. |
| 84 | `first_doc_line(node)` | First non-empty line of a node's docstring, or '' if none. |
| 96 | `md_escape(s)` | Escape the few characters that would break a Markdown table cell. |
| 101 | `collect(path)` | Return (module_doc, rows) for one file. rows = (lineno, label, sig, summary). |
| 123 | `render()` | Build the full CODEMAP.md text. |
| 174 | `main()` | — |

<h2 id="trayinitpy">tray/__init__.py</h2>

_(no top-level functions or classes)_

<h2 id="trayapppy">tray/app.py</h2>

_Einstieg der Tray-App: pystray-Icon, Menü, Single-Instance, Wiring._

| Line | Definition | Summary |
|---:|---|---|
| 20 | `_acquire_single_instance(data_dir)` | Single-Instance über eine exklusiv gesperrte Lock-Datei im Datenverzeichnis. |
| 44 | `_static_dir()` | Wurzel der statischen Assets: assets/ neben der .exe (gebaut) oder der |
| 54 | `_ensure_data_dir()` | Legt das beschreibbare Datenverzeichnis an (web/, data/, config.env aus |
| 69 | `_test_connection(values)` | — |
| 82 | `main()` | — |
| 207 | `_report_crash(text)` | Schreibt den Traceback in crash.log (neben der .exe und in %TEMP%) und zeigt |

<h2 id="trayautostartpy">tray/autostart.py</h2>

_Autostart über HKCU\...\Run. Logik gegen ein injizierbares Backend testbar._

| Line | Definition | Summary |
|---:|---|---|
| 7 | `enable_autostart(reg, name, command)` | — |
| 11 | `disable_autostart(reg, name)` | — |
| 15 | `is_autostart(reg, name)` | — |
| 19 | **`class WinRegistry`** | Echtes Backend (nur auf Windows). Kapselt winreg auf den Run-Key. |
| 21 | &nbsp;&nbsp;`WinRegistry.__init__(self)` | — |
| 26 | &nbsp;&nbsp;`WinRegistry.set_value(self, name, value)` | — |
| 31 | &nbsp;&nbsp;`WinRegistry.delete_value(self, name)` | — |
| 39 | &nbsp;&nbsp;`WinRegistry.get_value(self, name)` | — |

<h2 id="traybuildpy">tray/build.py</h2>

_Baut Supplierplan.exe (PyInstaller, one-folder) und optional den Inno-Setup-_

| Line | Definition | Summary |
|---:|---|---|
| 30 | `stage_assets(app_out: Path)` | Legt assets/ neben die exe (css, fonts, logo, sw.js, config.env.example). |
| 43 | `build_exe()` | — |
| 62 | `_find_iscc()` | ISCC.exe finden: PATH, dann Program Files, dann per-User (winget-Default |
| 82 | `build_installer()` | — |

<h2 id="trayconfigiopy">tray/config_io.py</h2>

_Lesen/Schreiben der config.env ohne Kommentare/Struktur zu zerstören._

| Line | Definition | Summary |
|---:|---|---|
| 5 | `parse_config_text(text: str)` | KEY=value-Paare aus config.env-Text. Reine Kommentar-/Leerzeilen werden |
| 20 | `render_config_env(existing_text: str, values: dict)` | Aktualisiert vorhandene KEY=-Zeilen mit values, behält Kommentare/Reihenfolge, |
| 38 | `read_config_env(path: Path)` | config.env-Datei → dict (leeres dict, wenn nicht vorhanden). |
| 46 | `write_config_env(values: dict, path: Path, template: Path=None)` | Schreibt values in path. Basis ist die vorhandene Datei, sonst das Template, |

<h2 id="trayguipy">tray/gui.py</h2>

_tkinter-Konfigurationsfenster. Liest/schreibt config.env über config_io._

| Line | Definition | Summary |
|---:|---|---|
| 76 | `_make_widget(frame, kind, extra, current_value)` | Erzeugt das passende Eingabe-Widget + StringVar. Auswahlfelder (bool/choice) |
| 97 | `_station_dialog(parent, search_fn, target_var)` | Modaler Such-Dialog: Teilname tippen → HAFAS-Treffer anklicken → exakter |
| 166 | `open_config_window(config_path, template_path=None, on_saved=None, test_connection=None, on_refresh=None, on_refresh_absences=None, busy_getter=None, status_getter=None, station_search=None, help_url=None, on_close=None, focus_requested=None)` | Öffnet das Einstellungen-Fenster. |

<h2 id="trayiconspy">tray/icons.py</h2>

_Erzeugt das Tray-Icon (gefüllter Kreis) in Grün (läuft) oder Rot (gestoppt)._

| Line | Definition | Summary |
|---:|---|---|
| 8 | `make_icon(running: bool, size: int=64)` | — |

<h2 id="traypathspy">tray/paths.py</h2>

_Pfad-Auflösung für die Tray-App (beschreibbares Datenverzeichnis)._

| Line | Definition | Summary |
|---:|---|---|
| 7 | `_default_can_write(path: Path)` | Prüft Schreibbarkeit, indem testweise eine Datei angelegt wird. |
| 19 | `resolve_data_dir(exe_dir: Path, localappdata: Path, can_write=None)` | Beschreibbares Datenverzeichnis: bevorzugt neben der .exe (portabel), |
| 28 | `app_dir()` | Verzeichnis der laufenden .exe bzw. des Scripts (PyInstaller-kompatibel). |
| 35 | `data_dir()` | Konkret aufgelöstes Datenverzeichnis für diese Maschine. |

<h2 id="trayschedulepy">tray/schedule.py</h2>

_Reine Zeitplan-Logik für den Abwesenheits-Lauf (testbar, ohne Threads/IO)._

| Line | Definition | Summary |
|---:|---|---|
| 14 | `parse_times(spec)` | "HH:MM,HH:MM,…" → sortierte Liste von (hour, minute). Müll/ungültige |
| 32 | `next_run_time(now: datetime, times)` | Nächster Zeitpunkt strikt nach `now`, der einer der `times` entspricht. |

<h2 id="trayserverpy">tray/server.py</h2>

_Gehärteter statischer Webserver-Thread._

| Line | Definition | Summary |
|---:|---|---|
| 15 | `is_path_allowed(path: str)` | True, wenn der angefragte URL-Pfad ausgeliefert werden darf. |
| 27 | **`class HardenedHandler`** | — |
| 30 | &nbsp;&nbsp;`HardenedHandler.translate_path(self, path)` | — |
| 45 | &nbsp;&nbsp;`HardenedHandler.list_directory(self, path)` | — |
| 49 | &nbsp;&nbsp;`HardenedHandler.send_head(self)` | — |
| 55 | &nbsp;&nbsp;`HardenedHandler.log_message(self, *args)` | — |
| 59 | `serve_web(web_dir, port, host='0.0.0.0', static_dir=None)` | Startet den Server in einem Thread. Gibt (httpd, thread) zurück; Stoppen via |

<h2 id="trayservicepy">tray/service.py</h2>

_Hintergrund-Dienst: ruft die bestehenden Fetch-main() auf Timern auf und_

| Line | Definition | Summary |
|---:|---|---|
| 16 | **`class Service`** | — |
| 17 | &nbsp;&nbsp;`Service.__init__(self, data_dir: Path, static_dir=None, log=print)` | — |
| 35 | &nbsp;&nbsp;`Service.busy(self)` | True, solange irgendein Untis-Lauf läuft (für Button-Ausgrauen). |
| 40 | &nbsp;&nbsp;`Service._apply_env(self)` | — |
| 45 | &nbsp;&nbsp;`Service._cfg_int(self, key, default)` | — |
| 51 | &nbsp;&nbsp;`Service.run_untis_once(self, refresh_absences=False)` | Ein Untis-Lauf. refresh_absences=True erzwingt den weekly/data-Sweep |
| 72 | &nbsp;&nbsp;`Service.refresh_now(self)` | Manueller regulärer Lauf (Button), nicht-blockierend. No-op, wenn schon |
| 79 | &nbsp;&nbsp;`Service.refresh_absences_now(self)` | Manueller Abwesenheits-Lauf (Button), nicht-blockierend. No-op bei |
| 87 | &nbsp;&nbsp;`Service.run_trains_once(self)` | — |
| 95 | &nbsp;&nbsp;`Service._record_error(self, what, exc)` | — |
| 107 | &nbsp;&nbsp;`Service._schedule(self, fn, interval)` | — |
| 116 | &nbsp;&nbsp;`Service._schedule_absences(self)` | Plant den nächsten Abwesenheits-Lauf zur nächsten festen Lokalzeit |
| 136 | &nbsp;&nbsp;`Service.start(self)` | — |
| 156 | &nbsp;&nbsp;`Service.stop(self)` | — |
