#!/bin/sh
# provision devkit: chay tren board Luckfox (root)
set -eu
ROOT="${1:-/opt/flytex}"
DATA="${2:-/data}"

command -v python3 >/dev/null || { echo "thieu python3"; exit 1; }
mkdir -p "$ROOT" "$DATA/clips" "$DATA/diag"

# Copy app/devkit neu chay tu thu muc repo
if [ -d "$(dirname "$0")/../../app" ]; then
    cp -r "$(dirname "$0")/../../app" "$ROOT/"
    cp -r "$(dirname "$0")/.." "$ROOT/devkit"
fi

if [ ! -f "$DATA/config.json" ]; then
    cp "$ROOT/devkit/config/devkit.json" "$DATA/config.json"
    echo "da tao $DATA/config.json - sua mqtt_host/apn"
fi

cp "$ROOT/devkit/systemd/flytex-device.service" /etc/systemd/system/
systemctl daemon-reload
echo "provision xong. Kiem tra:"
echo "  cd $ROOT && python3 -m flytex.cli selftest"
echo "  python3 devkit/scripts/devkit_check.py"
echo "  python3 devkit/scripts/feature_test.py --dry-run"
