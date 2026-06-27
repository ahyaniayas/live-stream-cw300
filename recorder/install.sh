#!/bin/bash
# Jalankan sebagai root: sudo bash recorder/install.sh
set -e

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SYSTEMD=/etc/systemd/system

echo "Install dari $APP_DIR/recorder"

cp "$APP_DIR/recorder/recorder.service"  $SYSTEMD/
cp "$APP_DIR/recorder/watchdog.service"  $SYSTEMD/
cp "$APP_DIR/recorder/watchdog.timer"    $SYSTEMD/

systemctl daemon-reload
systemctl enable --now recorder.service
systemctl enable --now watchdog.timer

echo ""
echo "Status:"
systemctl is-active recorder.service watchdog.timer
