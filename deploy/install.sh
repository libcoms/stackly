#!/usr/bin/env bash
# Установка stackly на Ubuntu. Запуск из папки бандла:  sudo bash deploy/install.sh example.ru
# SSL: если в /etc/ssl/stackly/ лежат fullchain.crt и private.key (сертификат Reg.ru) — используются они,
# иначе скрипт выпускает бесплатный сертификат Let's Encrypt.
set -euo pipefail
DOMAIN="${1:?Укажите домен или IP: sudo bash deploy/install.sh example.ru [--self-signed]}"
SSL_MODE="${2:-auto}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo"; exit 1; }

echo "== 1/7 Пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q nginx python3 sqlite3 ufw ca-certificates openssl

echo "== 2/7 Пользователь и папки"
id stackly >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin stackly
install -d -m 755 /opt/stackly/app /opt/stackly/content /var/www/stackly /var/www/letsencrypt
install -d -m 750 -o stackly -g stackly /var/lib/stackly
install -d -m 700 /etc/stackly /var/backups/stackly
install -m 644 "$HERE/app/stackly_api.py" /opt/stackly/app/stackly_api.py
# закрытые материалы — вне папки сайта: их отдаёт API только вошедшим
cp -r "$HERE/content/." /opt/stackly/content/
chmod -R a+rX /opt/stackly/content
cp -r "$HERE/public/." /var/www/stackly/
chmod -R a+rX /var/www/stackly

echo "== 3/7 Настройки API"
if [ ! -f /etc/stackly/stackly.env ]; then
  sed "s#DOMAIN#$DOMAIN#g" "$HERE/deploy/stackly.env.example" > /etc/stackly/stackly.env
fi
chmod 600 /etc/stackly/stackly.env

echo "== 4/7 Сервисы"
install -m 644 "$HERE/deploy/stackly-api.service" "$HERE/deploy/stackly-backup.service" "$HERE/deploy/stackly-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now stackly-api.service stackly-backup.timer
systemctl restart stackly-api.service

echo "== 5/7 Файрвол"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null

echo "== 6/7 SSL"
if [ "$SSL_MODE" = "--self-signed" ]; then
  # временный самоподписанный сертификат: браузер покажет предупреждение, пока его не заменят настоящим
  install -d -m 755 /etc/ssl/stackly-selfsigned
  if [[ "$DOMAIN" =~ ^[0-9.]+$ ]]; then SAN="IP:$DOMAIN"; else SAN="DNS:$DOMAIN,DNS:www.$DOMAIN"; fi
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 -subj "/CN=$DOMAIN" -addext "subjectAltName=$SAN" \
    -keyout /etc/ssl/stackly-selfsigned/private.key -out /etc/ssl/stackly-selfsigned/cert.crt 2>/dev/null
  chmod 600 /etc/ssl/stackly-selfsigned/private.key
  CERT=/etc/ssl/stackly-selfsigned/cert.crt; KEY=/etc/ssl/stackly-selfsigned/private.key
  echo "Выпущен самоподписанный сертификат на 365 дней (временный)"
elif [ -f /etc/ssl/stackly/fullchain.crt ] && [ -f /etc/ssl/stackly/private.key ]; then
  CERT=/etc/ssl/stackly/fullchain.crt; KEY=/etc/ssl/stackly/private.key
  chmod 600 "$KEY"; echo "Используется сертификат из /etc/ssl/stackly"
else
  apt-get install -y -q certbot
  # временный http-сервер для проверки домена
  cat > /etc/nginx/sites-available/stackly <<NG
server { listen 80; listen [::]:80; server_name $DOMAIN www.$DOMAIN;
  location /.well-known/acme-challenge/ { root /var/www/letsencrypt; } location / { return 404; } }
NG
  ln -sf /etc/nginx/sites-available/stackly /etc/nginx/sites-enabled/stackly
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
  certbot certonly --webroot -w /var/www/letsencrypt -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --keep-until-expiring
  CERT=/etc/letsencrypt/live/$DOMAIN/fullchain.pem; KEY=/etc/letsencrypt/live/$DOMAIN/privkey.pem
  install -d /etc/letsencrypt/renewal-hooks/deploy
  printf '#!/bin/sh\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
  chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
fi

echo "== 7/7 nginx"
sed -e "s#DOMAIN#$DOMAIN#g" -e "s#SSL_CERT#$CERT#g" -e "s#SSL_KEY#$KEY#g" "$HERE/deploy/nginx-stackly.conf" > /etc/nginx/sites-available/stackly
ln -sf /etc/nginx/sites-available/stackly /etc/nginx/sites-enabled/stackly
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx >/dev/null
systemctl reload nginx

sleep 1
echo
echo "Проверка API: $(curl -s http://127.0.0.1:8090/api/health)"
echo "Готово: https://$DOMAIN"
echo "Почта для восстановления пароля: заполните SMTP_* в /etc/stackly/stackly.env и выполните  systemctl restart stackly-api"
