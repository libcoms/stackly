#!/usr/bin/env bash
# Назначить роль пользователю (он должен быть зарегистрирован на сайте):
#   sudo bash deploy/set-role.sh почта@пример.ру admin     — администратор (видит всех, назначает учителей)
#   sudo bash deploy/set-role.sh почта@пример.ру teacher   — учитель
#   sudo bash deploy/set-role.sh почта@пример.ру student   — обычный ученик
# Дальше роли удобнее менять в админ-панели на сайте.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo"; exit 1; }
[ $# = 2 ] || { sed -n '2,6p' "$0"; exit 1; }
DB="$(sed -n 's/^STACKLY_DB=//p' /etc/stackly/stackly.env)"
# от имени сервиса, чтобы файлы базы остались принадлежать ему
sudo -u stackly STACKLY_DB="${DB:-/var/lib/stackly/stackly.db}" python3 /opt/stackly/app/stackly_api.py set-role "$1" "$2"
