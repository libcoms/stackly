#!/usr/bin/env bash
# Обновление сайта и API без потери данных:  sudo bash deploy/update.sh
# Обновляет сайт, API, systemd-сервисы и конфиг nginx (домен и сертификат берутся из текущей установки).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo"; exit 1; }

echo "== Резервная копия базы"
install -d -m 700 /var/backups/stackly
if [ -f /var/lib/stackly/stackly.db ]; then
  sqlite3 /var/lib/stackly/stackly.db ".backup /var/backups/stackly/before-update-$(date +%F-%H%M%S).db"
  # копии перед обновлениями храним 14 дней, как и ночные
  find /var/backups/stackly -name 'before-update-*.db' -mtime +14 -delete
fi

echo "== Сайт и API"
install -m 644 "$HERE/app/stackly_api.py" /opt/stackly/app/stackly_api.py
rsync -a --delete "$HERE/public/" /var/www/stackly/ 2>/dev/null || cp -r "$HERE/public/." /var/www/stackly/
chmod -R a+rX /var/www/stackly

echo "== Сервисы"
install -m 644 "$HERE/deploy/stackly-api.service" "$HERE/deploy/stackly-backup.service" "$HERE/deploy/stackly-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl restart stackly-api

echo "== nginx"
SITE=/etc/nginx/sites-available/stackly
DOMAIN="$(sed -n 's#^STACKLY_ORIGIN=https\?://##p' /etc/stackly/stackly.env | tr -d '/[:space:]')"
CERT="$(awk '$1 == "ssl_certificate" { sub(";", "", $2); print $2; exit }' "$SITE" 2>/dev/null || true)"
KEY="$(awk '$1 == "ssl_certificate_key" { sub(";", "", $2); print $2; exit }' "$SITE" 2>/dev/null || true)"
if [ -n "$DOMAIN" ] && [ -n "$CERT" ] && [ -n "$KEY" ]; then
  cp "$SITE" "$SITE.bak"
  sed -e "s#DOMAIN#$DOMAIN#g" -e "s#SSL_CERT#$CERT#g" -e "s#SSL_KEY#$KEY#g" "$HERE/deploy/nginx-stackly.conf" > "$SITE"
  if nginx -t; then
    systemctl reload nginx
  else
    echo "Новый конфиг nginx не прошёл проверку — возвращаю прежний"
    mv "$SITE.bak" "$SITE"; nginx -t && systemctl reload nginx
    exit 1
  fi
else
  echo "Не удалось определить домен или сертификат — конфиг nginx не меняю"
  nginx -t && systemctl reload nginx
fi

sleep 1
echo "Обновлено. API: $(curl -s http://127.0.0.1:8090/api/health)"
