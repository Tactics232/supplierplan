"""tkinter-Konfigurationsfenster. Liest/schreibt config.env über config_io.

Feldtypen (kind):
  "text"     – freies Textfeld
  "password" – maskiertes Textfeld
  "bool"     – Dropdown true/false (extra = Default)
  "choice"   – Dropdown mit festen Optionen (extra = (optionen, default))
Auswahlfelder verhindern Tippfehler/leere Werte bei Enums und Schaltern.
"""
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from tray.config_io import read_config_env, write_config_env

# (KEY, Label, kind, extra)
TABS = [
    ("WebUntis", [
        ("UNTIS_URL", "WebUntis-URL", "text", None),
        ("UNTIS_SCHOOL_ID", "Schul-ID", "text", None),
        ("UNTIS_USER", "Benutzer", "text", None),
        ("UNTIS_PASSWORD", "Passwort", "password", None),
        ("UNTIS_DEPARTMENT_ID", "Abteilungs-ID", "text", None),
        ("SKIP_TEACHERS", "Pseudo-Lehrer (Komma)", "text", None),
    ]),
    ("Schule", [
        ("SCHOOL_NAME", "Schulname", "text", None),
        ("SCHOOL_TYPE", "Schultyp", "text", None),
        ("SCHOOL_LOCATION", "Ort", "text", None),
        ("PLAN_TITLE", "Plan-Titel", "text", None),
        ("LOGO_FILE", "Logo-Datei", "text", None),
        ("SHOW_TOMORROW_AFTER", "Morgen ab (HH:MM)", "text", None),
        ("TIMEZONE", "Zeitzone", "text", None),
    ]),
    ("Züge", [
        ("TRAIN_STATION", "Station", "text", None),
        ("TRAIN_DIR_TOWARDS", "Richtung (Komma)", "text", None),
        ("TRAIN_PER_DIRECTION", "Züge je Richtung", "text", None),
        ("TRAIN_PRODUCTS", "Produkte (z.B. S,REX)", "text", None),
        ("TRAIN_DISABLED", "Deaktiviert", "bool", "false"),
    ]),
    ("Anzeige", [
        ("THEME", "Theme", "choice", (["dark", "light"], "dark")),
        ("SHOW_CLOCK", "Uhr zeigen", "bool", "true"),
        ("SHOW_LOGO", "Logo zeigen", "bool", "false"),
        ("COMPACT_COL_WIDTH_PX", "Compact-Schwelle px", "text", None),
        ("TEXT_BADGES", "Text-Badges", "text", None),
        ("MAX_COLUMNS", "Max. Spalten", "choice", (["1", "2", "3", "4"], "4")),
        ("CANCEL_PLACEMENT", "Entfall-Platzierung", "choice",
         (["section", "inline"], "section")),
        ("PWA_ORIENTATION", "PWA-Orientierung", "choice",
         (["any", "natural", "portrait", "landscape", "portrait-primary",
           "portrait-secondary", "landscape-primary", "landscape-secondary"], "any")),
    ]),
    ("Überlauf", [
        ("OVERFLOW_SCALE", "Skalieren", "bool", "true"),
        ("OVERFLOW_SCALE_MIN", "Min-Faktor (0.3–1.0)", "text", None),
        ("OVERFLOW_REDUCE", "Reduzieren", "bool", "true"),
        ("OVERFLOW_PAGINATE", "Blättern", "bool", "true"),
        ("OVERFLOW_PAGE_SECONDS", "Sekunden je Seite", "text", None),
    ]),
    ("Cloudflare", [
        ("CLOUDFLARE_ZONE_ID", "Zone-ID", "text", None),
        ("CLOUDFLARE_API_TOKEN", "API-Token", "password", None),
        ("CLOUDFLARE_HOST", "Host", "text", None),
    ]),
    ("Server", [
        ("SERVER_PORT", "Port", "text", None),
        ("UNTIS_INTERVAL_SECONDS", "Untis-Intervall (s)", "text", None),
        ("TRAIN_INTERVAL_SECONDS", "Zug-Intervall (s)", "text", None),
    ]),
]


def _make_widget(frame, kind, extra, current_value):
    """Erzeugt das passende Eingabe-Widget + StringVar. Auswahlfelder (bool/choice)
    sind readonly (nur auswählbar, kein Tippen)."""
    var = tk.StringVar()
    if kind == "bool":
        default = extra if extra in ("true", "false") else "true"
        var.set(current_value if current_value in ("true", "false") else default)
        w = ttk.Combobox(frame, textvariable=var, values=["true", "false"],
                         state="readonly", width=38)
    elif kind == "choice":
        options, default = extra
        var.set(current_value if current_value in options else default)
        w = ttk.Combobox(frame, textvariable=var, values=options,
                         state="readonly", width=38)
    else:  # text / password
        var.set(current_value)
        w = ttk.Entry(frame, textvariable=var, width=40,
                      show="*" if kind == "password" else "")
    return w, var


def _station_dialog(parent, search_fn, target_var):
    """Modaler Such-Dialog: Teilname tippen → HAFAS-Treffer anklicken → exakter
    Stationsname landet in target_var (= TRAIN_STATION). Suche läuft im Thread,
    Ergebnis via after() zurück (kein Einfrieren)."""
    win = tk.Toplevel(parent)
    win.title("Station suchen")
    win.geometry("400x340")
    win.transient(parent)

    q = tk.StringVar(value=(target_var.get() if target_var else ""))
    top = ttk.Frame(win)
    top.pack(fill="x", padx=8, pady=8)
    entry = ttk.Entry(top, textvariable=q)
    entry.pack(side="left", fill="x", expand=True)

    info = ttk.Label(win, text="Stationsname (Teil) eingeben und suchen.")
    lb = tk.Listbox(win)
    names = []

    def do_search():
        info.config(text="Suche …")
        lb.delete(0, tk.END)
        names.clear()
        term = q.get().strip()

        def work():
            try:
                hits = search_fn(term)
                err = None
            except Exception as e:
                hits, err = None, str(e)

            def show():
                if err is not None:
                    info.config(text="Fehler: " + err)
                    return
                if not hits:
                    info.config(text="Keine Treffer.")
                    return
                info.config(text=f"{len(hits)} Treffer – auswählen und Übernehmen.")
                for h in hits:
                    names.append(h["name"])
                    lb.insert(tk.END, h["name"])
            win.after(0, show)

        threading.Thread(target=work, daemon=True).start()

    ttk.Button(top, text="Suchen", command=do_search).pack(side="left", padx=(6, 0))
    info.pack(fill="x", padx=8)
    lb.pack(fill="both", expand=True, padx=8, pady=4)

    def take():
        sel = lb.curselection()
        if sel and target_var is not None:
            target_var.set(names[sel[0]])
            win.destroy()

    lb.bind("<Double-Button-1>", lambda e: take())
    btnf = ttk.Frame(win)
    btnf.pack(fill="x", padx=8, pady=8)
    ttk.Button(btnf, text="Übernehmen", command=take).pack(side="right")
    ttk.Button(btnf, text="Abbrechen", command=win.destroy).pack(side="right", padx=6)

    entry.focus_set()
    entry.bind("<Return>", lambda e: do_search())
    if q.get().strip():
        do_search()


def open_config_window(config_path, template_path=None, on_saved=None,
                       test_connection=None, on_refresh=None,
                       on_refresh_absences=None, busy_getter=None,
                       status_getter=None, station_search=None,
                       help_url=None, on_close=None, focus_requested=None):
    """Öffnet das Einstellungen-Fenster.

    Alle Lauf-Callbacks (on_saved/on_refresh/on_refresh_absences) sind
    nicht-blockierend bzw. werden in einen Thread gelegt → kein Einfrieren.
    busy_getter/status_getter koppeln den Service-Zustand ein: solange ein Lauf
    aktiv ist, werden die Aktions-Buttons ausgegraut. focus_requested() lässt eine
    bereits offene Instanz nach vorne holen (Single-Window). station_search(term)
    liefert HAFAS-Treffer; help_url öffnet die Doku im Browser."""
    config_path = Path(config_path)
    current = read_config_env(config_path)

    root = tk.Tk()
    root.title("Supplierplan – Einstellungen")
    root.geometry("560x520")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    vars_by_key = {}
    status = ttk.Label(root, text="")

    def pick_logo():
        from tkinter import filedialog
        import shutil
        path = filedialog.askopenfilename(
            parent=root, title="Logo wählen",
            filetypes=[("Bilder", "*.png *.svg *.jpg *.jpeg *.webp"),
                       ("Alle Dateien", "*.*")])
        if not path:
            return
        web = config_path.parent / "web"
        try:
            web.mkdir(parents=True, exist_ok=True)
            name = Path(path).name
            shutil.copy2(path, web / name)
        except Exception as e:
            status.config(text=f"Logo-Kopie fehlgeschlagen: {e}")
            return
        vars_by_key["LOGO_FILE"].set(name)
        status.config(text=f"Logo gewählt: {name} – Speichern nicht vergessen.")

    def open_station_search():
        if station_search:
            _station_dialog(root, station_search, vars_by_key.get("TRAIN_STATION"))

    for tab_title, fields in TABS:
        frame = ttk.Frame(nb)
        nb.add(frame, text=tab_title)
        for row, (key, label, kind, extra) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w",
                                              padx=6, pady=4)
            cell = ttk.Frame(frame)
            cell.grid(row=row, column=1, sticky="we", padx=6, pady=4)
            w, var = _make_widget(cell, kind, extra, current.get(key, ""))
            w.pack(side="left", fill="x", expand=True)
            vars_by_key[key] = var
            if key == "LOGO_FILE":
                ttk.Button(cell, text="…", width=3, command=pick_logo
                           ).pack(side="left", padx=(4, 0))
            elif key == "TRAIN_STATION" and station_search:
                ttk.Button(cell, text="Suchen…", command=open_station_search
                           ).pack(side="left", padx=(4, 0))
        frame.columnconfigure(1, weight=1)

    status.pack(fill="x", padx=8)

    state = {"testing": False, "prev_sb": False}
    action_btns = []

    def set_actions(stt):
        for b in action_btns:
            b.config(state=stt)

    def collect():
        return {k: v.get().strip() for k, v in vars_by_key.items()}

    def do_save():
        write_config_env(collect(), config_path, template=template_path)
        status.config(text="Gespeichert.")
        if on_saved:
            threading.Thread(target=on_saved, daemon=True).start()

    def do_test():
        if not test_connection:
            return
        state["testing"] = True
        set_actions("disabled")
        status.config(text="Teste Verbindung …")
        values = collect()

        def work():
            ok, msg = test_connection(values)

            def show():
                status.config(text=("OK: " + msg) if ok else ("Fehler: " + msg))
                state["testing"] = False
            root.after(0, show)

        threading.Thread(target=work, daemon=True).start()

    def do_trigger(fn):
        set_actions("disabled")
        status.config(text="Aktualisierung läuft …")
        fn()   # service.refresh_now / refresh_absences_now (nicht-blockierend)

    def open_help():
        if help_url:
            import webbrowser
            webbrowser.open(help_url)

    btns = ttk.Frame(root)
    btns.pack(fill="x", padx=8, pady=8)
    if test_connection:
        b = ttk.Button(btns, text="Verbindung testen", command=do_test)
        b.pack(side="left"); action_btns.append(b)
    if on_refresh:
        b = ttk.Button(btns, text="Jetzt aktualisieren",
                       command=lambda: do_trigger(on_refresh))
        b.pack(side="left", padx=6); action_btns.append(b)
    if on_refresh_absences:
        b = ttk.Button(btns, text="Abwesenheiten aktualisieren",
                       command=lambda: do_trigger(on_refresh_absences))
        b.pack(side="left", padx=6); action_btns.append(b)
    if help_url:
        ttk.Button(btns, text="Hilfe", command=open_help).pack(side="left", padx=6)
    ttk.Button(btns, text="Speichern", command=do_save).pack(side="right")
    ttk.Button(btns, text="Schließen", command=root.destroy).pack(side="right", padx=6)

    def poll():
        sb = bool(busy_getter() if busy_getter else False)
        busy = sb or state["testing"]
        set_actions("disabled" if busy else "normal")
        if not state["testing"]:
            if sb:
                status.config(text="Aktualisierung läuft …")
            elif state["prev_sb"] and status_getter:
                status.config(text=status_getter())
        state["prev_sb"] = sb
        if focus_requested and focus_requested():
            try:
                root.deiconify(); root.lift(); root.focus_force()
            except Exception:
                pass
        root.after(400, poll)

    poll()
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    try:
        root.mainloop()
    finally:
        if on_close:
            on_close()
