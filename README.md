# stackly

Методичка по ЕГЭ по информатике: все 27 заданий, учебник Python и банк задач с проверкой ответов.
Сайт работает на https://stackly.su.

## Состав

| Папка | Что внутри |
|---|---|
| `public/` | сайт: одна страница `index.html` (HTML, CSS и JS в одном файле) и `favicon.svg` |
| `app/stackly_api.py` | API: регистрация, вход, сброс пароля, прогресс. Только стандартный Python 3.10+, без пакетов |
| `deploy/` | установка на сервер: nginx, systemd-сервисы, ночные резервные копии, `install.sh`, `update.sh` |
| `tests/` | тесты API |
| `tools/dev_server.py` | локальный просмотр сайта вместе с API |
| `.github/workflows/` | CI (тесты, проверка nginx) и автодеплой из `main` |

База — SQLite, файл `/var/lib/stackly/stackly.db` на сервере (в репозиторий не попадает).
Резервные копии — каждую ночь в `/var/backups/stackly`, хранятся 14 дней.

## Локально

```bash
python3 tools/dev_server.py                 # сайт + API на http://127.0.0.1:8000
python3 -m unittest discover -s tests -v    # тесты API
```

## Сервер

Первая установка (Ubuntu):

```bash
sudo bash deploy/install.sh ваш-домен.ru
```

Сертификат Reg.ru: положите `fullchain.crt` (сертификат + цепочка CA) и `private.key` в `/etc/ssl/stackly/`
**до** запуска `install.sh`. Без них будет выпущен бесплатный сертификат Let's Encrypt.

Почта для восстановления пароля: заполните `SMTP_*` в `/etc/stackly/stackly.env`, затем
`systemctl restart stackly-api`.

Обновление вручную: `sudo bash deploy/update.sh` из папки с новой версией. Скрипт делает копию базы,
обновляет сайт, API, сервисы и конфиг nginx (домен и сертификат берутся из текущей установки).

## Автодеплой

Каждое изменение в ветке `main` проходит тесты и само выкладывается на сервер
(`.github/workflows/deploy.yml`). Для этого в Settings → Secrets and variables → Actions нужны секреты:

| Секрет | Значение |
|---|---|
| `DEPLOY_HOST` | адрес сервера |
| `DEPLOY_USER` | пользователь SSH (`root` или пользователь с sudo без пароля) |
| `DEPLOY_SSH_KEY` | приватный ключ, открытый ключ которого добавлен в `~/.ssh/authorized_keys` на сервере |
| `DEPLOY_KNOWN_HOSTS` | вывод `ssh-keyscan -H <адрес сервера>` |

Пока секретов нет, деплой пропускается. Запустить вручную: Actions → Deploy → Run workflow.
