"""tkinter-Konfigurationsfenster. Liest/schreibt config.env über config_io."""
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from tray.config_io import read_config_env, write_config_env

TABS = [
    ("WebUntis", [
        ("UNTIS_URL", "WebUntis-URL", False),
        ("UNTIS_SCHOOL_ID", "Schul-ID", False),
        ("UNTIS_USER", "Benutzer", False),
        ("UNTIS_PASSWORD", "Passwort", True),
        ("UNTIS_DEPARTMENT_ID", "Abteilungs-ID", False),
        ("SKIP_TEACHERS", "Pseudo-Lehrer (Komma)", False),
    ]),
    ("Schule", [
        ("SCHOOL_NAME", "Schulname", False),
        ("SCHOOL_TYPE", "Schultyp", False),
        ("SCHOOL_LOCATION", "Ort", False),
        ("PLAN_TITLE", "Plan-Titel", False),
        ("LOGO_FILE", "Logo-Datei", False),
        ("SHOW_TOMORROW_AFTER", "Morgen ab (HH:MM)", False),
        ("TIMEZONE", "Zeitzone", False),
    ]),
    ("Züge", [
        ("TRAIN_STATION", "Station", False),
        ("TRAIN_DIR_TOWARDS", "Richtung (Komma)", False),
        ("TRAIN_PER_DIRECTION", "Züge je Richtung", False),
        ("TRAIN_PRODUCTS", "Produkte (z.B. S,REX)", False),
        ("TRAIN_DISABLED", "Deaktiviert (true/false)", False),
    ]),
    ("Anzeige", [
        ("THEME", "Theme (dark/light)", False),
        ("SHOW_CLOCK", "Uhr zeigen (true/false)", False),
        ("SHOW_LOGO", "Logo zeigen (true/false)", False),
        ("COMPACT_COL_WIDTH_PX", "Compact-Schwelle px", False),
        ("TEXT_BADGES", "Text-Badges", False),
    ]),
    ("Überlauf", [
        ("OVERFLOW_SCALE", "Skalieren (true/false)", False),
        ("OVERFLOW_SCALE_MIN", "Min-Faktor (0.3–1.0)", False),
        ("OVERFLOW_REDUCE", "Reduzieren (true/false)", False),
        ("OVERFLOW_PAGINATE", "Blättern (true/false)", False),
        ("OVERFLOW_PAGE_SECONDS", "Sekunden je Seite", False),
    ]),
    ("Cloudflare", [
        ("CLOUDFLARE_ZONE_ID", "Zone-ID", False),
        ("CLOUDFLARE_API_TOKEN", "API-Token", True),
        ("CLOUDFLARE_HOST", "Host", False),
    ]),
    ("Server", [
        ("SERVER_PORT", "Port", False),
        ("UNTIS_INTERVAL_SECONDS", "Untis-Intervall (s)", False),
        ("TRAIN_INTERVAL_SECONDS", "Zug-Intervall (s)", False),
    ]),
]


def open_config_window(config_path, template_path=None, on_saved=None,
                       test_connection=None):
    """Öffnet das Fenster (modal). config_path: Pfad zur config.env."""
    config_path = Path(config_path)
    current = read_config_env(config_path)

    root = tk.Tk()
    root.title("Supplierplan – Einstellungen")
    root.geometry("520x460")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    vars_by_key = {}
    for tab_title, fields in TABS:
        frame = ttk.Frame(nb)
        nb.add(frame, text=tab_title)
        for row, (key, label, is_pw) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            var = tk.StringVar(value=current.get(key, ""))
            entry = ttk.Entry(frame, textvariable=var, width=40,
                              show="*" if is_pw else "")
            entry.grid(row=row, column=1, sticky="we", padx=6, pady=4)
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
