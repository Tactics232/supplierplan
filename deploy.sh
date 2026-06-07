#!/usr/bin/env bash
#
# deploy.sh — Supplierplan auf den LXC deployen.
#
#   1. Projektdateien  → /var/www/supplierplan/   (OHNE config.env!)
#   2. config.env      → /etc/supplierplan/config.env   (außerhalb des Webroots)
#
# config.env darf NIE in den Webroot, sonst liefert der Webserver Passwort +
# Cloudflare-Token aus. Daher der getrennte zweite rsync an den sicheren Ort.
#
# Aufruf:  ./deploy.sh        (oder:  bash deploy.sh)
#
set -euo pipefail

SRC="/mnt/c/Users/Admin/OneDrive/Programming/Claude/Supplier/"
HOST="root@192.168.10.134"

# SSH-Verbindung wiederverwenden → Passwort nur EINMAL für beide rsyncs.
CTL="/tmp/cm-supplierplan-%r@%h:%p"
SSH="ssh -o ControlMaster=auto -o ControlPath=$CTL -o ControlPersist=120"

echo "→ Projektdateien nach /var/www/supplierplan/ (ohne config.env) ..."
rsync -avz -e "$SSH" \
  --exclude='.claude' --exclude='Screenshot*' --exclude='.git' \
  --exclude='config.env' --exclude='deploy.sh' --exclude='data/' \
  "$SRC" "$HOST:/var/www/supplierplan/"

echo "→ config.env nach /etc/supplierplan/ (chmod 600) ..."
rsync -avz -e "$SSH" --chmod=F600 \
  "${SRC}config.env" "$HOST:/etc/supplierplan/config.env"

echo "✓ Deploy fertig."
