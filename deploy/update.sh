#!/usr/bin/env bash
# Обновление сайта и API без потери данных:  sudo bash deploy/update.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
sqlite3 /var/lib/stackly/stackly.db ".backup /var/backups/stackly/before-update-$(date +%F-%H%M).db"
install -m 644 "$HERE/app/stackly_api.py" /opt/stackly/app/stackly_api.py
cp -r "$HERE/public/." /var/www/stackly/
systemctl restart stackly-api
nginx -t && systemctl reload nginx
echo "Обновлено. API: $(curl -s http://127.0.0.1:8090/api/health)"
