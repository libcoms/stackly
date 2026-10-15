#!/usr/bin/env bash
# Задать новый пароль пользователю, если письмо для сброса не доходит:
#   sudo bash deploy/set-password.sh почта@пример.ру
# Пароль спрашивается дважды и на экране не виден. После смены все сессии пользователя закрываются.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo"; exit 1; }
[ $# = 1 ] || { sed -n '2,4p' "$0"; exit 1; }
DB="$(sed -n 's/^STACKLY_DB=//p' /etc/stackly/stackly.env)"
# от имени сервиса, чтобы файлы базы остались принадлежать ему
sudo -u stackly STACKLY_DB="${DB:-/var/lib/stackly/stackly.db}" python3 /opt/stackly/app/stackly_api.py set-password "$1"
