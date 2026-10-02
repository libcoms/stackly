stackly — сайт + API для своего сервера

  public/             готовый сайт (index.html, favicon.svg)
  app/stackly_api.py  API: регистрация, вход, прогресс (только стандартный Python 3, без пакетов)
  deploy/install.sh   первая установка:  sudo bash deploy/install.sh ваш-домен.ru
  deploy/update.sh    обновление:        sudo bash deploy/update.sh

Сертификат Reg.ru: положите в /etc/ssl/stackly/fullchain.crt (сертификат + цепочка CA)
и /etc/ssl/stackly/private.key ДО запуска install.sh. Без них будет выпущен Let's Encrypt.
Почта для восстановления пароля: /etc/stackly/stackly.env (SMTP_*), затем systemctl restart stackly-api.
База: /var/lib/stackly/stackly.db, копии каждую ночь в /var/backups/stackly (14 дней).
