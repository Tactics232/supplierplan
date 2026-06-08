"""tkinter-Konfigurationsfenster. Liest/schreibt config.env über config_io.

Feldtypen (kind):
  "text"     – freies Textfeld
  "password" – maskiertes Textfeld
  "bool"     – Dropdown true/false (extra = Default)
  "choice"   – Dropdown mit festen Optionen (extra = (optionen, default))
Auswahlfelder verhindern Tippfehler/leere Werte bei Enums und Schaltern.
"""
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


def open_config_window(config_path, template_path=None, on_saved=None,
                       test_connection=None):
    """Öffnet das Fenster (modal). config_path: Pfad zur config.env."""
    config_path = Path(config_path)
    current = read_config_env(config_path)

    root = tk.Tk()
    root.title("Supplierplan – Einstellungen")
    root.geometry("540x470")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    vars_by_key = {}
    for tab_title, fields in TABS:
        frame = ttk.Frame(nb)
        nb.add(frame, text=tab_title)
        for row, (key, label, kind, extra) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w",
                                              padx=6, pady=4)
            w, var = _make_widget(frame, kind, extra, current.get(key, ""))
            w.grid(row=row, column=1, sticky="we", padx=6, pady=4)
            vars_by_key[key] = var
        frame.columnconfigure(1, weight=1)

    status = ttk.Label(root, text="")
    status.pack(fill="x", padx=8)

    def collect():
        return {k: v.get().strip() for k, v in vars_by_key.items()}

    def do_save():
        write_config_env(collect(), config_path, template=template_path)
        status.config(text="Gespeichert.")
        if on_saved:
            on_saved()

    def do_test():
        if not test_connection:
            return
        status.config(text="Teste Verbindung …")
        root.update_idletasks()
        ok, msg = test_connection(collect())
        status.config(text=("OK: " + msg) if ok else ("Fehler: " + msg))

    btns = ttk.Frame(root)
    btns.pack(fill="x", padx=8, pady=8)
    if test_connection:
        ttk.Button(btns, text="Verbindung testen", command=do_test).pack(side="left")
    ttk.Button(btns, text="Speichern", command=do_save).pack(side="right")
    ttk.Button(btns, text="Schließen", command=root.destroy).pack(side="right", padx=6)

    root.mainloop()
