#!/usr/bin/env bash
# Browser-Check für den Layout-Refactor (ADR 0002): Fixtures erzeugen, einen
# Server im Projekt-Root starten und die drei Seiten im Browser öffnen.
#
# Lauf aus dem Projekt-Root (im Claude-Prompt mit '!'-Präfix möglich):
#   bash tests/fixtures/layout/check.sh
# Stoppen: Strg+C (fährt den Server runter).
#
# WSL-Eigenheit: WSL hat kein Python -> Windows-Python für gen.py UND Server.
set -euo pipefail

PORT="${1:-8080}"
PY="${SUPPLIERPLAN_PYTHON:-/mnt/c/Users/Admin/AppData/Local/Python/bin/python.exe}"
ROOT="$(git rev-parse --show-toplevel)"
BASE="http://localhost:${PORT}/tests/fixtures/layout"

cd "$ROOT"

echo "== 1/3  Fixtures erzeugen =="
PYTHONIOENCODING=utf-8 "$PY" tests/fixtures/layout/gen.py

echo "== 2/3  Server auf :${PORT} (Projekt-Root) =="
PYTHONIOENCODING=utf-8 "$PY" -m http.server "$PORT" >/dev/null 2>&1 &
SRV=$!
trap 'echo; echo "Server stoppen ($SRV)"; kill "$SRV" 2>/dev/null || true' EXIT INT TERM

# kurz warten bis der Server lauscht
for _ in $(seq 1 20); do
  if curl -sf "http://localhost:${PORT}/" -o /dev/null 2>/dev/null; then break; fi
  sleep 0.25
done

echo "== 3/3  Seiten im Browser öffnen =="
for f in normal overflow cancel_heavy; do
  url="${BASE}/${f}.html"
  echo "   -> $url"
  cmd.exe /c start "" "$url" >/dev/null 2>&1 || explorer.exe "$url" >/dev/null 2>&1 || true
done

cat <<EOF

Soll-Verhalten (Details: tests/fixtures/layout/README.md):
  normal        sauberes 2-4-Spalten-Layout, nichts abgeschnitten, keine Konsolenfehler
  overflow      Skalieren -> Reduzieren -> Blaettern; "Morgen" bleibt sichtbar
  cancel_heavy  Entfall-Sektion ueber Spalten, GENAU 1 Ueberschrift je Spalte (Forts.)

Tipp: an jede URL '?ovdebug=1' haengen -> Overlay zeigt die gegriffene Ueberlauf-Stufe.
Fenster schmaeler ziehen (< 600px) -> Mobil-/Kompakt-Modus pruefen.

Server laeuft. Strg+C zum Beenden.
EOF

wait "$SRV"
