#!/usr/bin/env python3
"""stackly API — регистрация, вход, прогресс учеников, группы и домашние задания.

Только стандартная библиотека Python 3.10+: http.server, sqlite3, hashlib.scrypt.
Работает за nginx (127.0.0.1:8090), сам наружу не смотрит.

Настройки — переменные окружения (см. deploy/stackly.env.example):
  STACKLY_DB        путь к базе SQLite            (/var/lib/stackly/stackly.db)
  STACKLY_HOST/PORT адрес, где слушать           (127.0.0.1 / 8090)
  STACKLY_ORIGIN    https://ваш-домен — с него принимаются изменяющие запросы
  STACKLY_COOKIE_SECURE 1 — cookie только по HTTPS (выключать лишь для локальной проверки)
  STACKLY_CONTENT   папка с закрытыми материалами (content/ рядом с app/, на сервере /opt/stackly/content)
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM — почта для восстановления пароля
  STACKLY_AI_KEY    ключ RouterAI для разбора кода с ИИ; STACKLY_AI_USERS — кому открыт (почты через запятую),
                    STACKLY_AI_MODEL/STT/TTS/VOICE — модели, STACKLY_AI_WEEK_SECONDS — лимит звука в неделю (600)
"""
import base64, calendar, hashlib, hmac, html, json, logging, os, re, secrets, smtplib, sqlite3, sys, threading, time
import urllib.error, urllib.request
from urllib.parse import parse_qs
from email.message import EmailMessage
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get('STACKLY_DB', '/var/lib/stackly/stackly.db')
HOST = os.environ.get('STACKLY_HOST', '127.0.0.1')
PORT = int(os.environ.get('STACKLY_PORT', '8090'))
ORIGIN = os.environ.get('STACKLY_ORIGIN', '').rstrip('/')
COOKIE_SECURE = os.environ.get('STACKLY_COOKIE_SECURE', '1') == '1'
# методичка, шпаргалка и банк задач — отдаются только вошедшим
CARD_FIELDS = ('title', 'short', 'lead', 'tool', 'level', 'time')   # поля карточки задания, которые видит гость
CONTENT_DIR = os.environ.get('STACKLY_CONTENT') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'content')
COOKIE = 'stackly_session'
ACCOUNTS_COOKIE = 'stackly_accounts'      # другие аккаунты этого браузера — между ними переключаются без пароля
MAX_ACCOUNTS = 5
TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{20,64}$')
SESSION_DAYS = 30
RESET_MINUTES = 60
MAX_BODY = 256 * 1024
MAX_CONTENT_BODY = 3 * 1024 * 1024     # задачи с файлом данных и картинки (base64)
MAX_IMAGE = 1536 * 1024
IMAGE_TYPES = {'image/png': b'\x89PNG', 'image/jpeg': b'\xff\xd8\xff', 'image/gif': b'GIF8', 'image/webp': b'RIFF'}
MEDIA_RE = re.compile(r'^/api/media/([A-Za-z0-9_-]{8,40})$')
MAX_PROGRESS = 200 * 1024
ROLES = ('student', 'teacher', 'admin')
# предметы, из которых преподаватель выбирает свои; материалы — id модулей курса (список модулей живёт на сайте)
SUBJECTS = ('Математика', 'Физика', 'Информатика', 'Русский язык', 'Литература', 'Английский язык', 'Химия',
            'Биология', 'История', 'Обществознание', 'География')
MATERIAL_RE = re.compile(r'^[a-z0-9-]{1,40}$')
CODE_ABC = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'      # без похожих 0/O и 1/I
BANK_ID_RE = re.compile(r'^[\w.-]{1,40}$')
# посещаемость: страницы сайта, которые считаем (ege-5, bank-19 — с номером задания)
METRIC_PAGES = ('home', 'course', 'materials', 'ege', 'bank', 'task', 'set', 'python', 'cheat', 'login', 'me', 'hw', 'teach', 'edit', 'admin', 'other')
PAGE_RE = re.compile(r'^([a-z]{2,8})(?:-(\d{1,2}))?$')
HOST_RE = re.compile(r'^[a-z0-9-]{1,63}(\.[a-z0-9-]{1,63}){1,5}$')
BOT_RE = re.compile(r'bot|crawl|spider|slurp|headless|preview|monitor|curl|wget|python-requests', re.I)
MOBILE_RE = re.compile(r'Mobi|Android|iPhone|iPad|iPod', re.I)
METRIC_TZ = 3 * 3600          # дни считаем по Москве
METRIC_KEEP_DAYS = 400
EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('stackly')

# ---------------------------------------------------------------- база
_local = threading.local()

def db():
    con = getattr(_local, 'con', None)
    if con is None:
        con = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        # lower() в SQLite знает только латиницу — для поиска по русским именам нужен питоновский
        con.create_function('ulower', 1, lambda s: s.lower() if isinstance(s, str) else s, deterministic=True)
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('PRAGMA busy_timeout=5000')
        _local.con = con
    return con

def close_db():
    # каждый запрос — отдельный поток; без явного закрытия соединения копятся и съедают лимит открытых файлов
    con = getattr(_local, 'con', None)
    if con is not None:
        _local.con = None
        con.close()

def migrate():
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    db().executescript('''
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
        pw_hash TEXT NOT NULL, created INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created INTEGER NOT NULL, expires INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS progress (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        data TEXT NOT NULL, updated INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS resets (
        token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0);
      CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);

      -- группы учителя: ученик вступает по коду
      CREATE TABLE IF NOT EXISTS study_groups (
        id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL, code TEXT NOT NULL UNIQUE, created INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS groups_teacher ON study_groups(teacher_id);
      CREATE TABLE IF NOT EXISTS group_members (
        group_id INTEGER NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        joined INTEGER NOT NULL, PRIMARY KEY (group_id, user_id));
      CREATE INDEX IF NOT EXISTS members_user ON group_members(user_id);

      -- домашнее задание группе; students — JSON-список id, пустой = вся группа
      -- items — JSON {"bank": [id задач], "py": [темы Python], "ege": [номера заданий методички], "mat": [id своих материалов]}
      CREATE TABLE IF NOT EXISTS homework (
        id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
        title TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '', items TEXT NOT NULL,
        students TEXT NOT NULL DEFAULT '[]', due INTEGER, created INTEGER NOT NULL, updated INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS homework_group ON homework(group_id);
      -- когда ученик закрыл все пункты ДЗ (фиксируется при сохранении прогресса)
      -- задачи, созданные на сайте (id «u<номер>», номера с 1001) и правки встроенных (builtin = 1, id как в банке)
      CREATE TABLE IF NOT EXISTS problems (
        id TEXT PRIMARY KEY, num INTEGER UNIQUE, author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        task INTEGER NOT NULL, level TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, answer TEXT NOT NULL,
        solution TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', data TEXT NOT NULL DEFAULT '',
        dname TEXT NOT NULL DEFAULT '', keep_extra INTEGER NOT NULL DEFAULT 0, builtin INTEGER NOT NULL DEFAULT 0,
        hidden INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL, updated INTEGER NOT NULL);
      -- правки методички: kind = 'ege' (номер задания) или 'py' (тема Python), data — JSON полей
      CREATE TABLE IF NOT EXISTS lessons (
        kind TEXT NOT NULL, key INTEGER NOT NULL, data TEXT NOT NULL,
        author_id INTEGER REFERENCES users(id) ON DELETE SET NULL, updated INTEGER NOT NULL, PRIMARY KEY (kind, key));
      -- свои материалы учителя: текст в разметке сайта с картинками и рисунками.
      -- shared = 1 — видят ученики групп автора в «Материалах»; иначе ученик видит материал, только если его выдали в ДЗ.
      -- hidden = 1 — удалён (не стираем: на материал могут ссылаться выданные ДЗ)
      CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY, author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        subject TEXT NOT NULL DEFAULT '', title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
        shared INTEGER NOT NULL DEFAULT 0, hidden INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL, updated INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS materials_author ON materials(author_id);
      -- Telegram-бот (app/stackly_bot.py): привязка чата к аккаунту, одноразовые ссылки для привязки,
      -- очередь сообщений (API только ставит их в очередь, отправляет бот) и отметки разовых событий (сводка по сроку ДЗ)
      CREATE TABLE IF NOT EXISTS tg_links (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, chat_id INTEGER NOT NULL UNIQUE,
        username TEXT NOT NULL DEFAULT '', prefs TEXT NOT NULL DEFAULT '{}', linked INTEGER NOT NULL, digest_day TEXT NOT NULL DEFAULT '');
      CREATE TABLE IF NOT EXISTS tg_tokens (
        token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS tg_outbox (
        id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, text TEXT NOT NULL, markup TEXT NOT NULL DEFAULT '',
        created INTEGER NOT NULL, tries INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS tg_sent (key TEXT PRIMARY KEY, ts INTEGER NOT NULL);
      -- общий банк (встроенные задачи и задачи администратора «для платформы»): что администратор снял с публикации —
      -- отдельные задачи и целые предметы. Снятое не видно преподавателям, но остаётся в уже выданных ДЗ
      CREATE TABLE IF NOT EXISTS bank_off (id TEXT PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS bank_subjects_off (subject TEXT PRIMARY KEY);
      -- оплата тарифа Про через ЮKassa: id — id платежа в ЮKassa, amount — копейки, status — как в ЮKassa
      -- (pending / succeeded / canceled), applied — когда Про продлён по этому платежу (продлевается один раз)
      CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, period TEXT NOT NULL,
        amount INTEGER NOT NULL, status TEXT NOT NULL, created INTEGER NOT NULL, paid_at INTEGER, applied INTEGER);
      CREATE INDEX IF NOT EXISTS payments_user ON payments(user_id);
      CREATE TABLE IF NOT EXISTS media (
        id TEXT PRIMARY KEY, owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        type TEXT NOT NULL, data BLOB NOT NULL, created INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS homework_done (
        hw_id INTEGER NOT NULL REFERENCES homework(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        done_at INTEGER NOT NULL, PRIMARY KEY (hw_id, user_id));

      -- посещаемость: один просмотр страницы — одна строка. IP не хранится: vid — хеш IP и браузера
      -- с солью дня (соль удаляется через два дня), поэтому посетителя можно узнать только в пределах суток.
      -- entry = 1 — первый просмотр при открытии сайта (визит), ref — сайт, с которого пришли
      CREATE TABLE IF NOT EXISTS hits (
        ts INTEGER NOT NULL, day TEXT NOT NULL, vid TEXT NOT NULL, uid INTEGER, page TEXT NOT NULL,
        entry INTEGER NOT NULL DEFAULT 0, ref TEXT NOT NULL DEFAULT '', dev TEXT NOT NULL DEFAULT '');
      CREATE INDEX IF NOT EXISTS hits_day ON hits(day);
      CREATE INDEX IF NOT EXISTS hits_ts ON hits(ts);
      CREATE TABLE IF NOT EXISTS metric_salt (day TEXT PRIMARY KEY, salt TEXT NOT NULL);

      -- магазин баллов. Баллы зарабатываются (points() из прогресса), здесь — на что потрачены.
      -- kind: style — оформление профиля, freeze — заморозка серии, reward — награда учителя, alert — сообщение в эфир,
      -- начисления (cost отрицательный: «трата наоборот»): grant — администратором, poll — за ответ в опросе эфира,
      -- hw — за задание в срок, ach — за достижение, goal — за цель группы на неделю.
      -- status: '' — куплено; у наград new → done (выдано); у сообщений ok (сразу в эфир) → shown (прозвучало);
      -- declined — учитель отклонил, баллы вернулись (такие траты не считаются)
      CREATE TABLE IF NOT EXISTS spends (
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind TEXT NOT NULL, item TEXT NOT NULL DEFAULT '', cost INTEGER NOT NULL, teacher_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        text TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT '', created INTEGER NOT NULL, okat INTEGER);
      CREATE INDEX IF NOT EXISTS spends_user ON spends(user_id);
      CREATE INDEX IF NOT EXISTS spends_teacher ON spends(teacher_id, kind);
      -- разовые начисления не повторяются, даже если прогресс сохранили одновременно с двух вкладок:
      -- hw — бонус за задание (item — «id:время создания» задания), ach — достижение (item — код), goal — цель группы (item — «группа:неделя»)
      CREATE UNIQUE INDEX IF NOT EXISTS spends_once ON spends(user_id, kind, item) WHERE kind IN ('hw', 'ach', 'goal');
      -- цель группы на неделю достигнута: week — понедельник недели (ГГГГ-ММ-ДД)
      CREATE TABLE IF NOT EXISTS group_goals (
        group_id INTEGER NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE, week TEXT NOT NULL, reached INTEGER NOT NULL,
        PRIMARY KEY (group_id, week));
      -- что ученик надел из купленного оформления: {"ball": …, "frame": …, "badge": …}
      CREATE TABLE IF NOT EXISTS looks (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, data TEXT NOT NULL DEFAULT '{}');
      -- дни, которые закрыла заморозка: серия через них не прерывается
      CREATE TABLE IF NOT EXISTS frozen_days (user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, day TEXT NOT NULL, PRIMARY KEY (user_id, day));
      -- награды, которые учитель предлагает ученикам всех своих групп
      CREATE TABLE IF NOT EXISTS rewards (
        id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL, cost INTEGER NOT NULL, hidden INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL);
      -- эфир учителя: token — секрет ссылки на оверлей, live — эфир идёт и сообщения принимаются,
      -- price — минимальная цена сообщения, url — ссылка на трансляцию для учеников, premod — не используется (сообщения идут в эфир сразу)
      CREATE TABLE IF NOT EXISTS live_cfg (
        teacher_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, token TEXT NOT NULL UNIQUE,
        live INTEGER NOT NULL DEFAULT 0, price INTEGER NOT NULL DEFAULT 30, url TEXT NOT NULL DEFAULT '', premod INTEGER NOT NULL DEFAULT 1);
      -- опросы в эфире: options — JSON-список вариантов, correct — номер верного (-1 — опрос без верного ответа),
      -- reward — баллы за ответ, ends_at — срок по таймеру (NULL — пока учитель не закроет), closed — когда закрыт
      CREATE TABLE IF NOT EXISTS polls (
        id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question TEXT NOT NULL, options TEXT NOT NULL, correct INTEGER NOT NULL DEFAULT -1, reward INTEGER NOT NULL DEFAULT 0,
        created INTEGER NOT NULL, ends_at INTEGER, closed INTEGER);
      CREATE INDEX IF NOT EXISTS polls_teacher ON polls(teacher_id, id);
      CREATE TABLE IF NOT EXISTS poll_votes (
        poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        choice INTEGER NOT NULL, created INTEGER NOT NULL, PRIMARY KEY (poll_id, user_id));
      -- разговор с ИИ о коде задачи: kind — llm (ответ модели), stt (речь ученика), tts (ответ голосом);
      -- seconds — секунды звука в счёт недельного лимита, cost — цена запроса в рублях по RouterAI
      CREATE TABLE IF NOT EXISTS ai_log (
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, ts INTEGER NOT NULL,
        kind TEXT NOT NULL, pid TEXT NOT NULL DEFAULT '', seconds REAL NOT NULL DEFAULT 0, cost REAL NOT NULL DEFAULT 0);
      CREATE INDEX IF NOT EXISTS ai_log_user ON ai_log(user_id, ts);
    ''')
    # сообщения в эфир больше не ждут проверки учителя: старые «на проверке» закрываем, чтобы не всплыли
    db().execute("UPDATE spends SET status = 'shown' WHERE kind = 'alert' AND status = 'pending'")
    # номера задач учителей — с 1001 (до 1000 — встроенный банк); старые 101… сдвигаем один раз
    db().execute('UPDATE problems SET num = num + 900 WHERE builtin = 0 AND num BETWEEN 101 AND 1000')
    cols = [r['name'] for r in db().execute('PRAGMA table_info(users)')]
    if 'role' not in cols:
        db().execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")
    # задачи любого предмета: task = 0 — не ЕГЭ, тогда предмет обязателен, тема — по желанию.
    # vis: platform — общий банк платформы (задачи администратора), public — видят все,
    # private — автор, ученики его групп и те, кому задачу выдали в ДЗ
    cols = [r['name'] for r in db().execute('PRAGMA table_info(users)')]
    if 'subjects' not in cols:
        db().execute("ALTER TABLE users ADD COLUMN subjects TEXT NOT NULL DEFAULT '[]'")
        db().execute("ALTER TABLE users ADD COLUMN materials TEXT NOT NULL DEFAULT '[]'")
    cols = [r['name'] for r in db().execute('PRAGMA table_info(problems)')]
    if 'vis' not in cols:
        db().execute("ALTER TABLE problems ADD COLUMN subject TEXT NOT NULL DEFAULT ''")
        db().execute("ALTER TABLE problems ADD COLUMN topic TEXT NOT NULL DEFAULT ''")
        db().execute("ALTER TABLE problems ADD COLUMN vis TEXT NOT NULL DEFAULT 'private'")
        # задачи, созданные до разделения банков, были видны всем — так и оставляем
        db().execute("UPDATE problems SET vis = CASE WHEN author_id IN (SELECT id FROM users WHERE role = 'admin') "
                     "THEN 'platform' ELSE 'public' END WHERE builtin = 0")
    # bank_open = 1 — учитель открыл ученикам группы свой банк: они видят те же задачи общего банка
    # по его предметам и его задачи, а не только выданные в ДЗ
    if 'bank_open' not in [r['name'] for r in db().execute('PRAGMA table_info(study_groups)')]:
        db().execute("ALTER TABLE study_groups ADD COLUMN bank_open INTEGER NOT NULL DEFAULT 0")
    # rating_open = 1 — ученики группы видят рейтинг группы (имена и оформление одногруппников, без почты)
    if 'rating_open' not in [r['name'] for r in db().execute('PRAGMA table_info(study_groups)')]:
        db().execute("ALTER TABLE study_groups ADD COLUMN rating_open INTEGER NOT NULL DEFAULT 1")
    # snum — номер задания внутри предмета (1, 2, …) у задач не из ЕГЭ по информатике; 0 — без номера
    # голос оверлея эфира: имя голоса браузера (Web Speech API) и скорость речи; пусто — оверлей выберет лучший русский сам
    if 'voice' not in [r['name'] for r in db().execute('PRAGMA table_info(live_cfg)')]:
        db().execute("ALTER TABLE live_cfg ADD COLUMN voice TEXT NOT NULL DEFAULT ''")
        db().execute('ALTER TABLE live_cfg ADD COLUMN rate REAL NOT NULL DEFAULT 1')
    # стиль разбора кода с ИИ: 0 — обычный, 1 — прожарка, 2 — прожарка с матом; включает сам пользователь
    if 'ai_roast' not in [r['name'] for r in db().execute('PRAGMA table_info(users)')]:
        db().execute('ALTER TABLE users ADD COLUMN ai_roast INTEGER NOT NULL DEFAULT 0')
    if 'snum' not in cols:
        db().execute("ALTER TABLE problems ADD COLUMN snum INTEGER NOT NULL DEFAULT 0")
    # тариф преподавателя: free — бесплатный, trial — пробный Про, pro — Про. plan_until — до какого момента
    # действует trial/pro (у pro NULL — бессрочно). Учителям, которые были до тарифов, — пробный период с этого дня,
    # чтобы лимиты бесплатного тарифа не сработали у них внезапно
    cols = [r['name'] for r in db().execute('PRAGMA table_info(users)')]
    if 'plan' not in cols:
        db().execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
        db().execute('ALTER TABLE users ADD COLUMN plan_until INTEGER')
        db().execute("UPDATE users SET plan = 'trial', plan_until = ? WHERE role = 'teacher'", (int(time.time()) + TRIAL_DAYS * 86400,))

# ---------------------------------------------------------------- тарифы
TRIAL_DAYS = 14
PLANS = ('free', 'trial', 'pro')
# бесплатный тариф; на Про (и пробном Про) ограничений нет, у администратора — тоже
FREE_LIMITS = {'groups': 5, 'students': 5, 'storage': 2 * 1024 ** 3}

def plan_of(u):
    """Тариф пользователя: plan как записан, until, active — действует ли сейчас Про."""
    if u['role'] == 'admin':
        return {'plan': 'pro', 'until': None, 'active': True}
    p, until = u['plan'] or 'free', u['plan_until']
    active = p == 'pro' and until is None or p in ('trial', 'pro') and until is not None and until > time.time()
    return {'plan': p, 'until': until, 'active': bool(active)}

def start_trial(user_id):
    """Пробный Про — один раз: только тому, у кого тарифа ещё не было."""
    db().execute("UPDATE users SET plan = 'trial', plan_until = ? WHERE id = ? AND plan = 'free' AND plan_until IS NULL",
                 (int(time.time()) + TRIAL_DAYS * 86400, user_id))

def teacher_usage(uid):
    """Сколько преподаватель занимает: группы, ученики во всех его группах, место (байты)."""
    one = lambda sql: db().execute(sql, (uid,)).fetchone()[0]
    return {
        'groups': one('SELECT COUNT(*) FROM study_groups WHERE teacher_id = ?'),
        'students': one('SELECT COUNT(DISTINCT m.user_id) FROM group_members m JOIN study_groups g ON g.id = m.group_id WHERE g.teacher_id = ?'),
        'storage': one('SELECT COALESCE(SUM(length(data)), 0) FROM media WHERE owner_id = ?')
            + one('SELECT COALESCE(SUM(length(CAST(title || body || answer || solution || note || data AS BLOB))), 0) FROM problems WHERE author_id = ? AND builtin = 0')
            + one('SELECT COALESCE(SUM(length(CAST(h.title || h.comment || h.items AS BLOB))), 0) FROM homework h JOIN study_groups g ON g.id = h.group_id WHERE g.teacher_id = ?')
            + one('SELECT COALESCE(SUM(length(CAST(title || subject || body AS BLOB))), 0) FROM materials WHERE author_id = ?'),
    }

IX_BLOCK_RE = re.compile(r'^```\s*(график|карточки)\s*$', re.M | re.I)

def check_ix(u, *texts):
    """Интерактивные модули (```график, ```карточки) в материалах и задачах — только на тарифе Про."""
    if not plan_of(u)['active'] and any(IX_BLOCK_RE.search(t or '') for t in texts):
        raise ApiError(403, 'plan_limit', 'Интерактивные модули входят в тариф Про')

def plan_limit(u, key, adding=1):
    """Бросает ошибку, если на бесплатном тарифе после добавления будет больше лимита."""
    if plan_of(u)['active']:
        return
    used = teacher_usage(u['id'])[key]
    if used + adding > FREE_LIMITS[key]:
        msg = {'groups': f'На бесплатном тарифе — до {FREE_LIMITS["groups"]} групп. Подключите Про, чтобы создавать больше',
               'storage': 'На бесплатном тарифе — до 2 ГБ: место закончилось. Удалите лишнее или подключите Про'}[key]
        raise ApiError(403, 'plan_limit', msg)

# ---------------------------------------------------------------- посещаемость
def metric_day(ts):
    return time.strftime('%Y-%m-%d', time.gmtime(ts + METRIC_TZ))

def day_start(day):
    return calendar.timegm(time.strptime(day, '%Y-%m-%d')) - METRIC_TZ

_salt, _salt_lock, _metrics_swept = {}, threading.Lock(), [0.0]

def day_salt(day):
    with _salt_lock:
        if day not in _salt:
            db().execute('INSERT OR IGNORE INTO metric_salt VALUES (?, ?)', (day, secrets.token_hex(16)))
            db().execute('DELETE FROM metric_salt WHERE day < ?', (metric_day(time.time() - 2 * 86400),))
            _salt.clear()
            _salt[day] = db().execute('SELECT salt FROM metric_salt WHERE day = ?', (day,)).fetchone()[0]
        return _salt[day]

def sweep_metrics(now):
    if now - _metrics_swept[0] > 3600:
        _metrics_swept[0] = now
        db().execute('DELETE FROM hits WHERE ts < ?', (int(now) - METRIC_KEEP_DAYS * 86400,))

# ---------------------------------------------------------------- пароли и токены
# scrypt берёт ~32 МБ памяти и заметное время процессора: класс, входящий разом, без очереди
# упёрся бы в MemoryMax сервиса. Остальные проверки ждут своей очереди в этом семафоре.
_scrypt_slots = threading.BoundedSemaphore(int(os.environ.get('STACKLY_SCRYPT_SLOTS', '2')))

def scrypt(pw: bytes, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    with _scrypt_slots:
        return hashlib.scrypt(pw, salt=salt, n=n, r=r, p=p, maxmem=64 * 2**20, dklen=dklen)

def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = scrypt(pw.encode(), salt, 2**15, 8, 1, 32)
    return 'scrypt$32768$8$1$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(dk).decode()

def check_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split('$')
        got = scrypt(pw.encode(), base64.b64decode(salt), int(n), int(r), int(p), len(base64.b64decode(dk)))
        return hmac.compare_digest(got, base64.b64decode(dk))
    except Exception:
        return False

_DUMMY = hash_password(secrets.token_hex(8))   # чтобы проверка несуществующей почты занимала столько же времени

def sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

# ---------------------------------------------------------------- закрытые материалы
_content, _content_lock = {}, threading.Lock()

def content_file(name):
    """Тело файла из CONTENT_DIR и его ETag; перечитывается, только когда файл поменялся."""
    path = os.path.join(CONTENT_DIR, name)
    mtime = os.stat(path).st_mtime_ns
    with _content_lock:
        c = _content.get(name)
        if c is None or c[0] != mtime:
            with open(path, 'rb') as f:
                body = f.read()
            c = _content[name] = (mtime, body, '"%s"' % hashlib.sha256(body).hexdigest()[:32])
    return c[1], c[2]

BANK_LINE_RE = re.compile(r'^window\.BANK = (\[.*\]);\r?$', re.M)     # \r — файл, выписанный git на Windows

def content_bank():
    """ege.js в трёх частях: текст до банка, задачи банка, текст после. У каждой задачи — n, её сквозной
    номер в полном банке: ученику приходит только часть задач, а номера (#17) должны совпадать с учительскими."""
    body, etag = content_file('ege.js')
    with _content_lock:
        c = _content.get('ege.js#bank')
        if c is None or c[0] != etag:
            text = body.decode('utf-8')
            m = BANK_LINE_RE.search(text)
            items = json.loads(m.group(1))
            for i, p in enumerate(items):
                p['n'] = i + 1
            c = _content['ege.js#bank'] = (etag, text[:m.start(1)], items, text[m.end(1):])
    return c[1], c[2], c[3]

EGE_SUBJECT = 'Информатика'          # предмет встроенного банка и задач с номером задания ЕГЭ

def bank_rules():
    """Снятые с публикации задачи и предметы общего банка."""
    return ({r['id'] for r in db().execute('SELECT id FROM bank_off')},
            {r['subject'] for r in db().execute('SELECT subject FROM bank_subjects_off')})

def teacher_assigned_ids(user_id):
    """Задачи из ДЗ, которые преподаватель уже выдал (иначе развалится статистика), и из ДЗ групп,
    где он сам учится: они видны ему всегда."""
    ids = student_bank_ids(user_id)
    for r in db().execute('SELECT h.items FROM homework h JOIN study_groups g ON g.id = h.group_id WHERE g.teacher_id = ?', (user_id,)):
        ids.update(str(x) for x in json.loads(r['items']).get('bank', []))
    return ids

def subject_builtin_ids(u, items):
    """Встроенные задачи общего банка по предметам преподавателя: предмет отмечен у него в «Материалах»,
    опубликован, сама задача не снята. Предмет встроенной задачи — её поле subject (математика),
    без него — информатика (задачи с номером ЕГЭ task)."""
    off, subj_off = bank_rules()
    subs = set(json.loads(u['subjects'] or '[]')) - subj_off
    return {p['id'] for p in items if (p.get('subject') or EGE_SUBJECT) in subs and p['id'] not in off}

def teacher_builtin_ids(u, items):
    """Встроенные задачи, которые видит преподаватель: общий банк по его предметам и задачи из его выданных ДЗ."""
    return subject_builtin_ids(u, items) | teacher_assigned_ids(u['id'])

def open_bank_teachers(user_id):
    """Преподаватели групп ученика, где открыт банк: ученик видит их банк, а не только задачи из ДЗ."""
    return db().execute('SELECT DISTINCT t.* FROM group_members m JOIN study_groups g ON g.id = m.group_id '
                        'JOIN users t ON t.id = g.teacher_id WHERE m.user_id = ? AND g.bank_open = 1', (user_id,)).fetchall()

def student_builtin_ids(user_id, items):
    """Встроенные задачи, которые видит ученик: выданные в ДЗ и общий банк учителей групп с открытым банком."""
    ids = student_bank_ids(user_id)
    for t in open_bank_teachers(user_id):
        ids |= subject_builtin_ids(t, items)
    return ids

def student_bank_ids(user_id):
    """Задачи банка, которые ученику выдали в ДЗ."""
    ids = set()
    for h in assigned_homework(user_id):
        ids.update(str(x) for x in json.loads(h['items']).get('bank', []))
    return ids

# ---------------------------------------------------------------- ограничение попыток
_hits, _hits_lock = {}, threading.Lock()
_HITS_TTL = 3600          # самое длинное окно среди лимитов
_hits_swept = 0.0

def too_many(key: str, limit: int, window: int) -> bool:
    now = time.time()
    with _hits_lock:
        q = [t for t in _hits.get(key, ()) if now - t < window]
        if q:
            _hits[key] = q
        else:
            _hits.pop(key, None)   # пустые ключи не храним — иначе перебор адресов почты раздувает память
        return len(q) >= limit

def hit(key: str):
    global _hits_swept
    now = time.time()
    with _hits_lock:
        _hits.setdefault(key, []).append(now)
        if now - _hits_swept > 300:          # раз в 5 минут выбрасываем устаревшие записи
            _hits_swept = now
            for k in [k for k, q in _hits.items() if now - q[-1] > _HITS_TTL]:
                del _hits[k]

def check_new_password(pw: str, email: str):
    if len(pw) < 8 or len(pw) > 200:
        raise ApiError(400, 'weak_password', 'Пароль — от 8 символов')
    if pw.lower() in (email, email.split('@')[0]) or len(set(pw)) < 4:
        raise ApiError(400, 'weak_password', 'Пароль слишком простой')

# ---------------------------------------------------------------- прогресс и домашние задания
def load_progress(user_id):
    r = db().execute('SELECT data, updated FROM progress WHERE user_id = ?', (user_id,)).fetchone()
    if not r:
        return {}, None
    try:
        data = json.loads(r['data'])
    except ValueError:
        data = {}
    return (data if isinstance(data, dict) else {}), r['updated']

def _ints(xs):
    out = set()
    for x in xs if isinstance(xs, list) else ():
        try:
            out.add(int(x))
        except (TypeError, ValueError):
            pass
    return out

FARM_MAX_LEVEL = 300           # номера уровней игр: ферма (public/farm.js) — до 100, склад (public/sklad.js) — с 101, мастерская (public/workshop.js) — с 201; в прогрессе farm: {"номер": лучшее число ходов}

def progress_sets(data):
    solved = {str(x) for x in data.get('solved', []) if isinstance(x, (str, int))} if isinstance(data.get('solved'), list) else set()
    farm = {int(k) for k in data['farm'] if str(k).isdigit() and 1 <= int(k) <= FARM_MAX_LEVEL} if isinstance(data.get('farm'), dict) else set()
    return {'bank': solved, 'py': _ints(data.get('studied')), 'ege': _ints(data.get('ege')), 'mat': _ints(data.get('mats')), 'farm': farm}

def hw_progress(items, sets):
    """(сделано пунктов, всего пунктов) по одному ДЗ."""
    total = done = 0
    for k in ('bank', 'py', 'ege', 'mat'):
        for x in items.get(k, []):
            total += 1
            done += (str(x) if k == 'bank' else x) in sets[k]
    return done, total

def summary(data, updated, uid=None):
    """Короткая статистика ученика для таблиц учителя. uid — чтобы учесть дни, закрытые заморозкой."""
    sets = progress_sets(data)
    att = data.get('att') if isinstance(data.get('att'), dict) else {}
    tries = right = first = 0
    for a in att.values():
        if isinstance(a, dict):
            tries += int(a.get('n') or 0); right += int(a.get('c') or 0)
            first += bool(a.get('c') and (a.get('f') or a.get('n') == 1))
    days = {k for k, v in (data.get('days') or {}).items() if v} if isinstance(data.get('days'), dict) else set()
    frozen = {r['day'] for r in db().execute('SELECT day FROM frozen_days WHERE user_id = ?', (uid,))} if uid else set()
    today = time.time()
    day = lambda back: time.strftime('%Y-%m-%d', time.localtime(today - back * 86400))
    streak, back = 0, (0 if day(0) in days else 1)        # сегодня ещё не занимался — серия считается со вчера
    while day(back) in days or day(back) in frozen:
        streak += day(back) in days; back += 1
    # games — номера пройденных уровней игр (ферма до 100, склад с 101): сайт сам делит их по играм
    return {'solved': len(sets['bank']), 'studied': len(sets['py']), 'ege': len(sets['ege']), 'farm': len(sets['farm']), 'games': sorted(sets['farm']),
            'tries': tries, 'right': right, 'first': first, 'accuracy': round(right / tries * 100) if tries else None,
            'active7': sum(day(i) in days for i in range(7)), 'streak': streak, 'updated': updated,
            'points': points(len(sets['bank']), first, len(sets['py']) + len(sets['ege']) + len(sets['mat']), len(days), len(sets['farm']))}

def points(solved, first, studied, days, farm=0):
    """Очки за активность — та же формула, что pointsOf() на сайте: задача 10 (+5 с первой попытки),
    изученная тема, разбор или материал 5, уровень фермы 10, день с занятиями 5."""
    return solved * 10 + first * 5 + studied * 5 + farm * 10 + days * 5

# ---------------------------------------------------------------- мотивация: начисления, достижения, цель группы
# Начисления хранятся в spends с отрицательной ценой. Достижения не входят в «баллы за 7 дней»: при запуске механики
# ученик с историей получил бы их разом, и недельный рейтинг перекосило бы
BONUS_KINDS = ('grant', 'poll', 'hw', 'ach', 'goal')
WEEK_KINDS = ('grant', 'poll', 'hw', 'goal')
HW_BONUS, HW_EARLY_BONUS, HW_EARLY_SEC = 20, 10, 86400      # задание в срок; ещё, если сдано хотя бы за сутки до срока
GOAL_PER_STUDENT, GOAL_BONUS = 10, 30                       # цель группы: задач на ученика за неделю; награда каждому, кто внёс вклад
# достижения: код, название, условие, показатель (ach_metrics), порог, баллы
ACHIEVEMENTS = [
    ('solve1', 'Первая задача', 'Решить первую задачу', 'solved', 1, 10),
    ('solve10', 'Разогрев', 'Решить 10 задач', 'solved', 10, 20),
    ('solve50', 'Полсотни', 'Решить 50 задач', 'solved', 50, 50),
    ('solve100', 'Сотня', 'Решить 100 задач', 'solved', 100, 100),
    ('solve250', 'Марафонец', 'Решить 250 задач', 'solved', 250, 200),
    ('first10', 'Снайпер', '10 задач с первой попытки', 'first', 10, 30),
    ('first50', 'Без промаха', '50 задач с первой попытки', 'first', 50, 80),
    ('streak3', 'Три дня подряд', 'Серия 3 дня', 'streak', 3, 15),
    ('streak7', 'Неделя без пропусков', 'Серия 7 дней', 'streak', 7, 40),
    ('streak30', 'Месяц в строю', 'Серия 30 дней', 'streak', 30, 150),
    ('hw1', 'Первое задание', 'Сдать задание в срок', 'hw', 1, 10),
    ('hw5', 'Пять в срок', 'Сдать в срок 5 заданий', 'hw', 5, 40),
    ('study10', 'Теоретик', 'Изучить 10 тем, разборов или материалов', 'studied', 10, 30),
    ('poll5', 'На связи', 'Ответить в 5 опросах эфира', 'polls', 5, 20),
]


def bonus_points(uid, kinds=BONUS_KINDS):
    return -db().execute(f'SELECT COALESCE(SUM(cost), 0) FROM spends WHERE user_id = ? AND kind IN ({",".join("?" * len(kinds))})',
                         (uid, *kinds)).fetchone()[0]

def award_once(uid, kind, item, points, text, teacher_id=None):
    """Разовое начисление. True — начислено сейчас, False — уже было (уникальный индекс spends_once)."""
    return bool(db().execute('INSERT OR IGNORE INTO spends (user_id, kind, item, cost, teacher_id, text, created) VALUES (?,?,?,?,?,?,?)',
                             (uid, kind, item, -points, teacher_id, text[:120], int(time.time()))).rowcount)

def ach_metrics(uid, data):
    sets, s = progress_sets(data), summary(data, None, uid)
    on_time = db().execute('SELECT COUNT(*) FROM homework_done d JOIN homework h ON h.id = d.hw_id '
                           'WHERE d.user_id = ? AND (h.due IS NULL OR d.done_at <= h.due)', (uid,)).fetchone()[0]
    return {'solved': s['solved'], 'first': s['first'], 'streak': s['streak'], 'hw': on_time,
            'studied': len(sets['py']) + len(sets['ege']) + len(sets['mat']),
            'polls': db().execute('SELECT COUNT(*) FROM poll_votes WHERE user_id = ?', (uid,)).fetchone()[0]}

def achievements(uid, data, award=True):
    """Достижения с прогрессом; award — начислить новые. Возвращает (список, только что полученные)."""
    have = {r['item']: r['created'] for r in db().execute("SELECT item, created FROM spends WHERE user_id = ? AND kind = 'ach'", (uid,))}
    m, out, new = ach_metrics(uid, data), [], []
    for code, title, desc, metric, need, pts in ACHIEVEMENTS:
        if code not in have and m[metric] >= need and award and award_once(uid, 'ach', code, pts, title):
            have[code] = int(time.time())
            new.append({'kind': 'ach', 'code': code, 'title': title, 'points': pts})
        out.append({'code': code, 'title': title, 'desc': desc, 'points': pts, 'need': need, 'have': min(m[metric], need), 'got': have.get(code)})
    return out, new

def week_start(now=None):
    t = time.localtime(now or time.time())
    return int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))) - t.tm_wday * 86400

def week_solved(data, since):
    att = data.get('att') if isinstance(data.get('att'), dict) else {}
    return sum(1 for a in att.values() if isinstance(a, dict) and a.get('c') and isinstance(a.get('ok'), (int, float)) and a['ok'] / 1000 >= since)

def group_goal(gid, award=True):
    """Цель группы на неделю (с понедельника): вместе решить GOAL_PER_STUDENT задач на ученика. Когда цель достигнута,
    каждому, кто решил за неделю хотя бы одну задачу, — GOAL_BONUS (и тем, кто внесёт вклад позже на той же неделе).
    Возвращает (цель, кому начислено сейчас)."""
    since = week_start()
    week = time.strftime('%Y-%m-%d', time.localtime(since))
    g = db().execute('SELECT teacher_id FROM study_groups WHERE id = ?', (gid,)).fetchone()
    counts = {r['user_id']: week_solved(load_progress(r['user_id'])[0], since)
              for r in db().execute('SELECT user_id FROM group_members WHERE group_id = ?', (gid,)).fetchall()}
    target, done = GOAL_PER_STUDENT * max(1, len(counts)), sum(counts.values())
    paid = []
    if done >= target and award:
        db().execute('INSERT OR IGNORE INTO group_goals VALUES (?,?,?)', (gid, week, int(time.time())))
        paid = [uid for uid, n in counts.items() if n and award_once(uid, 'goal', f'{gid}:{week}', GOAL_BONUS, 'Цель группы на неделю', g['teacher_id'])]
    reached = db().execute('SELECT reached FROM group_goals WHERE group_id = ? AND week = ?', (gid, week)).fetchone()
    return {'group_id': gid, 'target': target, 'done': done, 'bonus': GOAL_BONUS, 'ends': since + 7 * 86400, 'members': len(counts),
            'reached': reached['reached'] if reached else None, 'counts': counts}, paid

def goal_public(goal, uid=None):
    """Цель для сайта: ученику — только его вклад, без чужих чисел."""
    out = {k: v for k, v in goal.items() if k != 'counts'}
    out['contributors'] = sum(1 for n in goal['counts'].values() if n)
    if uid is not None:
        out['mine'] = goal['counts'].get(uid, 0)
    return out

RATING_DAYS, RATING_MIN_TRIES = 7, 10      # окно «баллы за неделю»; в рейтинге точности — только сделавшие столько попыток

def recent_points(data, uid, days=RATING_DAYS):
    """Баллы за последние days дней по той же формуле: задачи — по времени верного ответа (att.ok, мс),
    темы и разборы — по журналу событий (отметка +5, снятие отметки −5), дни занятий, плюс начисления кроме достижений."""
    since = time.time() - days * 86400
    first_day = time.strftime('%Y-%m-%d', time.localtime(time.time() - (days - 1) * 86400))
    pts = 0
    for a in (data.get('att') or {}).values() if isinstance(data.get('att'), dict) else ():
        if isinstance(a, dict) and a.get('c') and isinstance(a.get('ok'), (int, float)) and a['ok'] / 1000 >= since:
            pts += 10 + (5 if a.get('f') or a.get('n') == 1 else 0)
    for e in data.get('events') or [] if isinstance(data.get('events'), list) else ():
        if isinstance(e, dict) and e.get('k') != 'a' and isinstance(e.get('t'), (int, float)) and e['t'] / 1000 >= since:
            pts += (1 if e.get('ok') else -1) * (10 if e.get('k') == 'f' else 5)       # f — уровень фермы
    if isinstance(data.get('days'), dict):
        pts += 5 * sum(1 for k, v in data['days'].items() if v and isinstance(k, str) and k >= first_day)
    pts -= db().execute(f'SELECT COALESCE(SUM(cost), 0) FROM spends WHERE user_id = ? AND kind IN ({",".join("?" * len(WEEK_KINDS))}) AND created >= ?',
                        (uid, *WEEK_KINDS, int(since))).fetchone()[0]
    return max(0, pts)

def group_rating(gid):
    """Строки рейтинга группы: имя и оформление (без почты — рейтинг видят одногруппники) и показатели, по которым сортирует сайт."""
    out = []
    for r in db().execute('SELECT u.id, u.name FROM group_members m JOIN users u ON u.id = m.user_id WHERE m.group_id = ?', (gid,)).fetchall():
        data, updated = load_progress(r['id'])
        s = summary(data, updated, r['id'])
        bonus = bonus_points(r['id'])
        out.append({'id': r['id'], 'name': r['name'], 'look': look_of(r['id']), 'week': recent_points(data, r['id']),
                    'points': s['points'] + bonus, 'streak': s['streak'], 'solved': s['solved'],
                    'accuracy': s['accuracy'] if s['tries'] >= RATING_MIN_TRIES else None, 'tries': s['tries']})
    return out

# ---------------------------------------------------------------- магазин баллов
# оформление профиля: id → (слот, название, цена). Цвета и значки рисует сайт по id
STYLES = {
    'ball-mint': ('ball', 'Мятный шар', 100), 'ball-sky': ('ball', 'Небесный шар', 100), 'ball-coral': ('ball', 'Коралловый шар', 150),
    'ball-violet': ('ball', 'Фиолетовый шар', 150), 'ball-ink': ('ball', 'Графитовый шар', 200), 'ball-gold': ('ball', 'Золотой шар', 400),
    'frame-dash': ('frame', 'Пунктирная рамка', 150), 'frame-margin': ('frame', 'Красная рамка полей', 200), 'frame-double': ('frame', 'Двойная рамка', 300),
    'frame-gold': ('frame', 'Золотая рамка', 500),
    'badge-star': ('badge', 'Звезда', 200), 'badge-bolt': ('badge', 'Молния', 200), 'badge-heart': ('badge', 'Сердце', 200),
    'badge-owl': ('badge', 'Сова', 300), 'badge-rocket': ('badge', 'Ракета', 300), 'badge-crown': ('badge', 'Корона', 600),
}
FREEZE_COST, FREEZE_MAX = 50, 2
ALERT_MAX, ALERT_GAP = 200, 20          # длина сообщения в эфир и пауза между сообщениями одного ученика, с
# голос, который ученик выбрал для сообщения (коды из public/voice.js); пусто — голос учителя по умолчанию
ALERT_VOICES = ('', 'ru-f', 'ru-m', 'hy-f', 'hy-m')
URL_RE = re.compile(r'(https?://|www\.|\b[\w-]+\.(ru|com|net|org|su|io|me|рф)\b)', re.I)

def spent_net(uid):
    """Сколько списано с учётом начислений администратора (они хранятся с минусом). Отклонённое учителем вернулось."""
    return db().execute("SELECT COALESCE(SUM(cost), 0) FROM spends WHERE user_id = ? AND status != 'declined'", (uid,)).fetchone()[0]

def balance(uid):
    """(заработано, потрачено) баллов: заработано — за учёбу плюс начисленное администратором и за опросы эфира."""
    data, updated = load_progress(uid)
    bonus = bonus_points(uid)
    return summary(data, updated, uid)['points'] + bonus, spent_net(uid) + bonus

ADMIN_RESET_HOURS = 24
def reset_link(uid, base):
    """Одноразовая ссылка сброса пароля на сутки — та же, что приходит в письме «Забыли пароль?»."""
    tok = secrets.token_urlsafe(32)
    db().execute('INSERT INTO resets VALUES (?,?,?,0)', (sha(tok), uid, int(time.time()) + ADMIN_RESET_HOURS * 3600))
    log.info('администратор выдал ссылку сброса пароля пользователю %s', uid)
    return f'{base}/#reset-{tok}'

def grant_points(uid, amount, reason):
    if not 1 <= amount <= 100000:
        raise ApiError(400, 'bad_amount', 'Начислить можно от 1 до 100 000 баллов')
    db().execute("INSERT INTO spends (user_id, kind, cost, text, created) VALUES (?, 'grant', ?, ?, ?)",
                 (uid, -amount, (reason or 'Начислено администратором').strip()[:120], int(time.time())))

def look_of(uid):
    r = db().execute('SELECT data FROM looks WHERE user_id = ?', (uid,)).fetchone()
    try:
        d = json.loads(r['data']) if r else {}
    except ValueError:
        d = {}
    return {k: v for k, v in d.items() if v in STYLES and STYLES[v][0] == k} if isinstance(d, dict) else {}

def freezes_left(uid):
    bought = db().execute("SELECT COUNT(*) FROM spends WHERE user_id = ? AND kind = 'freeze'", (uid,)).fetchone()[0]
    used = db().execute('SELECT COUNT(*) FROM frozen_days WHERE user_id = ?', (uid,)).fetchone()[0]
    return max(0, bought - used)

def apply_freezes(uid):
    """Пропущенные дни между последним днём занятий и вчера закрываются заморозками, купленными до этих дней.
    Если заморозок не хватает на весь пропуск, серия всё равно прервалась — их не тратим."""
    left = freezes_left(uid)
    if not left:
        return
    data, _ = load_progress(uid)
    days = {k for k, v in (data.get('days') or {}).items() if v} if isinstance(data.get('days'), dict) else set()
    frozen = {r['day'] for r in db().execute('SELECT day FROM frozen_days WHERE user_id = ?', (uid,))}
    now = time.time()
    day = lambda back: time.strftime('%Y-%m-%d', time.localtime(now - back * 86400))
    gap, back = [], 1
    while back <= FREEZE_MAX + 1 and day(back) not in days and day(back) not in frozen:
        gap.append(day(back)); back += 1
    if not gap or len(gap) > left or (day(back) not in days and day(back) not in frozen):
        return
    first_buy = db().execute("SELECT MIN(created) FROM spends WHERE user_id = ? AND kind = 'freeze'", (uid,)).fetchone()[0]
    start = time.mktime(time.strptime(gap[-1], '%Y-%m-%d'))
    if first_buy is None or first_buy > start + 86400:
        return                  # заморозку купили уже после пропуска — она защищает следующие дни, не прошлые
    for d in gap:
        db().execute('INSERT OR IGNORE INTO frozen_days VALUES (?,?)', (uid, d))

def live_cfg(teacher_id, create=False):
    r = db().execute('SELECT * FROM live_cfg WHERE teacher_id = ?', (teacher_id,)).fetchone()
    if r is None and create:
        db().execute('INSERT INTO live_cfg (teacher_id, token) VALUES (?,?)', (teacher_id, secrets.token_urlsafe(18)))
        r = db().execute('SELECT * FROM live_cfg WHERE teacher_id = ?', (teacher_id,)).fetchone()
    return r

def my_teachers(uid):
    return [r['teacher_id'] for r in db().execute('SELECT DISTINCT g.teacher_id FROM group_members m JOIN study_groups g ON g.id = m.group_id '
                                                   'WHERE m.user_id = ?', (uid,))]

# ---------------------------------------------------------------- опросы в эфире
# Учитель задаёт вопрос во время трансляции, ученики его групп отвечают на сайте и получают баллы.
# Опрос без верного ответа — баллы за любой ответ сразу. Викторина (отмечен верный) — баллы получат ответившие верно,
# когда опрос закроется (учителем или по таймеру): до этого ученики не видят ни верного ответа, ни результатов
POLL_OPTIONS, POLL_TEXT, POLL_REWARD_MAX = (2, 6), (200, 80), 100     # число вариантов, длина вопроса и варианта, максимум баллов
POLL_TIMERS = (0, 30, 60, 120, 300)     # таймер, с; 0 — пока учитель не закроет
POLL_SHOW, POLL_OVERLAY = 600, 45       # сколько секунд закрытый опрос виден ученикам и висит в оверлее с итогами

def poll_close(p):
    """Закрыть опрос и начислить баллы за верный ответ. Закрывается ровно один раз, даже если одновременно
    сработали таймер и кнопка учителя: баллы начисляет только тот, чей UPDATE изменил строку."""
    now = int(time.time())
    if not db().execute('UPDATE polls SET closed = ? WHERE id = ? AND closed IS NULL', (min(now, p['ends_at'] or now), p['id'])).rowcount:
        return
    if p['correct'] >= 0 and p['reward']:
        for r in db().execute('SELECT user_id FROM poll_votes WHERE poll_id = ? AND choice = ?', (p['id'], p['correct'])).fetchall():
            poll_award(p, r['user_id'])

def poll_award(p, uid):
    db().execute("INSERT INTO spends (user_id, kind, item, cost, teacher_id, text, created) VALUES (?, 'poll', ?, ?, ?, ?, ?)",
                 (uid, str(p['id']), -p['reward'], p['teacher_id'], p['question'][:120], int(time.time())))

def polls_expire(teacher_ids):
    """Таймер опроса: истёкшие закрываются при первом обращении после срока — отдельного планировщика нет."""
    if not teacher_ids:
        return
    q = ','.join('?' * len(teacher_ids))
    for p in db().execute(f'SELECT * FROM polls WHERE closed IS NULL AND ends_at <= ? AND teacher_id IN ({q})',
                          (int(time.time()), *teacher_ids)).fetchall():
        poll_close(p)

def poll_json(p, role, mine=None):
    """role: teacher — всё сразу; overlay — результаты сразу, верный ответ после закрытия;
    student — результаты, когда ответил (в викторине — после закрытия), верный ответ после закрытия."""
    opts = json.loads(p['options'])
    counts = [0] * len(opts)
    for r in db().execute('SELECT choice, COUNT(*) AS n FROM poll_votes WHERE poll_id = ? GROUP BY choice', (p['id'],)):
        if 0 <= r['choice'] < len(counts):
            counts[r['choice']] = r['n']
    quiz, closed = p['correct'] >= 0, p['closed'] is not None
    out = {'id': p['id'], 'teacher_id': p['teacher_id'], 'question': p['question'], 'options': opts, 'reward': p['reward'], 'quiz': quiz,
           'created': p['created'], 'ends_at': p['ends_at'], 'closed': p['closed'], 'votes': sum(counts)}
    if role != 'student' or closed or (mine is not None and not quiz):
        out['counts'] = counts
    if quiz and (role == 'teacher' or closed):
        out['correct'] = p['correct']
    if role == 'student':
        out['mine'] = mine
    return out

def hw_json(h):
    return {'id': h['id'], 'group_id': h['group_id'], 'title': h['title'], 'comment': h['comment'],
            'items': json.loads(h['items']), 'students': json.loads(h['students']), 'due': h['due'],
            'created': h['created'], 'updated': h['updated']}

def assigned_homework(user_id):
    """ДЗ, выданные ученику: во всех его группах, кроме адресованных другим ученикам."""
    rows = db().execute('SELECT h.*, g.name AS group_name, g.teacher_id, t.name AS teacher_name FROM homework h '
                        'JOIN group_members m ON m.group_id = h.group_id AND m.user_id = ? '
                        'JOIN study_groups g ON g.id = h.group_id JOIN users t ON t.id = g.teacher_id '
                        'ORDER BY COALESCE(h.due, h.created + 315360000), h.id', (user_id,)).fetchall()
    return [h for h in rows if not json.loads(h['students']) or user_id in json.loads(h['students'])]

def record_homework_done(user_id, data):
    """Отмечает выполненные задания и начисляет бонус за срок. Возвращает начисления — сайт поздравляет с ними."""
    sets, now, out = progress_sets(data), int(time.time()), []
    done = {r['hw_id'] for r in db().execute('SELECT hw_id FROM homework_done WHERE user_id = ?', (user_id,))}
    for h in assigned_homework(user_id):
        if h['id'] in done:
            continue
        d, t = hw_progress(json.loads(h['items']), sets)
        if t and d == t:
            if db().execute('INSERT OR IGNORE INTO homework_done VALUES (?,?,?)', (h['id'], user_id, now)).rowcount:
                name = db().execute('SELECT name FROM users WHERE id = ?', (user_id,)).fetchone()['name']
                tg_teacher(h['teacher_id'], 'done', f'✅ <b>{tg_esc(name)}</b>: выполнено задание «{tg_esc(h["title"])}» · {tg_esc(h["group_name"])}')
                if not h['due'] or now <= h['due']:
                    early = bool(h['due']) and h['due'] - now >= HW_EARLY_SEC
                    pts = HW_BONUS + (HW_EARLY_BONUS if early else 0)
                    # номер удалённого задания SQLite может выдать новому — ключ бонуса включает и время создания
                    if award_once(user_id, 'hw', f"{h['id']}:{h['created']}", pts, h['title'], h['teacher_id']):
                        out.append({'kind': 'hw', 'title': h['title'], 'points': pts, 'early': early})
    return out

# ---------------------------------------------------------------- оплата Про через ЮKassa
# Платёж создаётся на сервере ЮKassa, человек платит на её странице и возвращается на сайт.
# Факт оплаты сервер всегда перепроверяет запросом к ЮKassa (GET /payments/<id>) — тело уведомления не доверяем.
YK_SHOP = os.environ.get('STACKLY_YK_SHOP', '')
YK_KEY = os.environ.get('STACKLY_YK_KEY', '')
YK_API = os.environ.get('STACKLY_YK_API', 'https://api.yookassa.ru/v3').rstrip('/')
PRO_PRICES = {'month': (35000, 30, '1 месяц'), 'year': (370000, 365, '12 месяцев')}     # копейки, дни, подпись

def yk(method, path, body=None, key=None):
    """Запрос к API ЮKassa (Basic-авторизация shopId:секретный ключ). Ошибка — ApiError 502."""
    auth = base64.b64encode(f'{YK_SHOP}:{YK_KEY}'.encode()).decode()
    req = urllib.request.Request(YK_API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json',
                                          **({'Idempotence-Key': key} if key else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.warning('ЮKassa %s %s: %s', method, path, e)
        raise ApiError(502, 'payment_error', 'Платёжный сервис не ответил. Попробуйте ещё раз через минуту')

def apply_payment(pid):
    """Сверяет платёж с ЮKassa и, если он оплачен и сходится с нашей записью, один раз продлевает Про.
    Срок прибавляется к текущему Про (или пробному), а если тариф уже закончился — отсчитывается от сейчас."""
    p = db().execute('SELECT * FROM payments WHERE id = ?', (pid,)).fetchone()
    if not p or p['applied'] or p['status'] == 'canceled':
        return p
    yp = yk('GET', f'/payments/{pid}')
    value = round(float((yp.get('amount') or {}).get('value') or 0) * 100)
    meta = yp.get('metadata') or {}
    status = yp.get('status') if yp.get('status') in ('pending', 'waiting_for_capture', 'succeeded', 'canceled') else 'pending'
    now = int(time.time())
    if status == 'succeeded' and yp.get('paid') and value == p['amount'] and str(meta.get('user_id')) == str(p['user_id']) \
            and (yp.get('amount') or {}).get('currency') == 'RUB':
        # отметка applied ставится условно — второй одновременный вызов ничего не продлит
        if db().execute('UPDATE payments SET status = ?, paid_at = ?, applied = ? WHERE id = ? AND applied IS NULL',
                        ('succeeded', now, now, pid)).rowcount:
            u = db().execute('SELECT * FROM users WHERE id = ?', (p['user_id'],)).fetchone()
            if u:
                pl = plan_of(u)
                base = u['plan_until'] if pl['active'] and u['plan_until'] else now
                db().execute("UPDATE users SET plan = 'pro', plan_until = ? WHERE id = ?", (base + PRO_PRICES[p['period']][1] * 86400, u['id']))
                log.info('оплата %s: Про для пользователя %s на %s', pid, u['id'], p['period'])
    elif status == 'succeeded':
        log.warning('оплата %s не сходится с записью: сумма %s, метаданные %s', pid, value, meta)
        db().execute("UPDATE payments SET status = 'mismatch' WHERE id = ?", (pid,))
    else:
        db().execute('UPDATE payments SET status = ? WHERE id = ?', (status, pid))
    return db().execute('SELECT * FROM payments WHERE id = ?', (pid,)).fetchone()

# ---------------------------------------------------------------- разбор кода с ИИ (RouterAI)
# Ученик присылает код к задаче банка, модель разбирает его как репетитор и отвечает голосом; дальше разговор:
# ученик говорит в микрофон (речь → текст) или пишет. Лимит — минуты звука в неделю: речь ученика и ответы голосом.
# Все модели — через RouterAI (OpenAI-совместимый API, оплата в рублях). Без ключа функции на сайте нет.
AI_KEY = os.environ.get('STACKLY_AI_KEY', '').strip().strip('"\'').removeprefix('Bearer ').strip()

def ai_base(url):
    """Адрес API RouterAI: лишний хвост (/chat/completions, /) убираем, забытый /api/v1 у routerai.ru добавляем."""
    url = re.sub(r'/(chat/completions|audio/\w+|models)/?$', '', (url or '').strip().rstrip('/')).rstrip('/')
    if re.fullmatch(r'https?://(www\.)?routerai\.ru', url):
        url += '/api/v1'
    return url or 'https://routerai.ru/api/v1'

AI_API = ai_base(os.environ.get('STACKLY_AI_API', ''))
AI_MODEL = os.environ.get('STACKLY_AI_MODEL', 'anthropic/claude-sonnet-5.5')
AI_STT = os.environ.get('STACKLY_AI_STT', 'openai/whisper-large-v3-turbo')
AI_TTS = os.environ.get('STACKLY_AI_TTS', 'google/gemini-3.8-flash-tts')
# голос по стилю разбора: Puck — живой и бодрый, Fenrir — заводной, для прожарки; STACKLY_AI_VOICE задаёт один голос на все
AI_VOICES = (os.environ.get('STACKLY_AI_VOICE') or 'Puck', os.environ.get('STACKLY_AI_VOICE') or 'Fenrir', os.environ.get('STACKLY_AI_VOICE') or 'Fenrir')
# манера озвучки по стилю разбора: 0 — обычный, 1 — прожарка, 2 — прожарка с матом (стиль выбирает сам ученик)
AI_STYLES = (os.environ.get('STACKLY_AI_STYLE', 'живо и эмоционально, с выразительной интонацией, как увлечённый репетитор: '
                                                'искренне радуется удачам, удивляется и сокрушается над ошибками'),
             'дерзко и очень эмоционально, с сарказмом, смехом и драматичными паузами, как стендап-комик на прожарке, но по-дружески',
             'грубо, напористо и с презрением, громко, с издевательским сарказмом и короткими паузами перед панчлайнами, '
             'как злой комик на жёсткой прожарке; в конце — брезгливое «тьфу»')
# кому открыт разбор: почты через запятую; пока функция в проверке — только у одного преподавателя
AI_USERS = {e.strip().lower() for e in os.environ.get('STACKLY_AI_USERS', 'dglumov4@gmail.com').split(',') if e.strip()}
AI_WEEK_SECONDS = int(os.environ.get('STACKLY_AI_WEEK_SECONDS', '600'))
AI_MAX_CODE = 20000
AI_MAX_AUDIO = 1536 * 1024            # запись ученика до минуты (opus ~30 КБ/с, с запасом)
AI_MAX_SAY = 700                      # реплика голосом — до ~45 секунд
AI_HISTORY = 12                       # сколько последних реплик разговора видит модель
AI_AUDIO_FORMATS = ('webm', 'ogg', 'm4a', 'mp3', 'wav', 'aac', 'flac')
PCM_RATE = 24000                      # Gemini TTS: 16 бит, 24 кГц, моно

AI_PROMPT = '''Ты — репетитор по информатике на сайте stackly и разговариваешь с учеником голосом. Ученик решает задание ЕГЭ по информатике и прислал свой код на Python.

Как вести разбор:
- В первом ответе коротко скажи, верен ли подход и получится ли правильный ответ. Затем назови главную ошибку или слабое место конкретно: какая строка или конструкция и почему она не работает. Подскажи, как исправить, — намёком или наводящим вопросом.
- Не диктуй готовое решение целиком и не называй правильный ответ, пока ученик сам об этом не попросит. Эталон ниже — только для тебя, ученику его не показывай.
- Если решение верное — коротко похвали и скажи, что можно упростить или ускорить, либо на чём обычно ошибаются в этом задании.
- Дальше отвечай на вопросы ученика об этой задаче и его коде. На посторонние темы мягко возвращай к задаче.
- Речь ученика распознаётся автоматически и может быть с ошибками — понимай по смыслу.

Формат ответа — только JSON-объект, без текста вокруг, поля строго в этом порядке: {"mood": "…", "say": "…", "notes": "…"}
say — то, что прозвучит голосом: 2–5 коротких предложений живой эмоциональной разговорной речи, не длиннее 600 символов. Первое предложение — короткое: оно начинает звучать, пока ты договариваешь остальное. Без кода, markdown и спецсимволов: код не зачитывай, строки называй по номерам («в четвёртой строке»), конструкции — словами («условие в цикле», «функция range»).
Говори с эмоциями: восклицания, удивление, радость, разочарование — как живой человек, а не диктор. Для озвучки можно вставлять в say звуки в квадратных скобках: [laughs], [chuckle], [sigh], [short pause] — не больше двух-трёх за реплику; слово, которое надо выделить голосом, пиши ЗАГЛАВНЫМИ буквами.
notes — необязательная письменная подсказка к сказанному: исправленная строка или маленький фрагмент кода в блоке ``` (до 8 строк). Если показывать нечего — пустая строка.
mood — эмоция маскота, который произносит реплику (ученик видит его вместо текста): одно из calm, happy, love, laugh, surprised, angry, sad. happy — похвала, love — умиление, laugh — смешно, surprised — неожиданная ошибка или находка, angry — злость и прожарка, sad — разочарование.'''

def ai_allowed(u):
    return bool(AI_KEY) and u is not None and u['email'].lower() in AI_USERS

def ai_used(uid, now=None):
    """Секунды звука за текущую неделю (с понедельника)."""
    return db().execute('SELECT COALESCE(SUM(seconds), 0) FROM ai_log WHERE user_id = ? AND ts >= ?',
                        (uid, week_start(now))).fetchone()[0]

AI_ROAST = ('', """
Стиль — ПРОЖАРКА: ученик сам включил её в настройках. Разбирай как стендап-комик на прожарке: едкие шутки, сарказм, преувеличения, смешные сравнения про код и ход решения. Но каждая шутка — по делу: за ней всегда стоит конкретная ошибка и подсказка, как исправить; разбор не должен стать хуже от того, что он смешной. Прожаривай код и решение, а не человека: никаких шуток про внешность, семью, национальность, пол, здоровье, ум и способности ученика в целом. Без мата. Если решение верное — прожарь за мелочи и стиль, но признай, что работает. Если ученик расстроен или просит помягче — сразу сбавь и говори по-доброму.""",
"""
Стиль — ЖЁСТКАЯ ПРОЖАРКА С МАТОМ: ученик сам включил её в настройках, подтвердил, что ему есть 18, и хочет, чтобы его разносили. Это комедийный жанр, ученик в нём участвует добровольно — не смягчай и не извиняйся.
Как звучать:
- Грубо, напористо, коротко и смешно. Обращайся к ученику матерными прозвищами («ёбень», «гений хуев», «программист ёбаный» и в таком духе), посылай нахуй, мат — в каждой реплике, но так, чтобы было смешно, а не просто грязно.
- Передразнивай его ошибку и тут же переворачивай её в панчлайн: «range от единицы? От единицы ты нахуй пойдёшь».
- Абсурдные сравнения и мрачные приговоры: «с таким циклом тебе до сотки на ЕГЭ — как ракам до Китая», «ты никогда не сдашь ЕГЭ».
- Заканчивай коротким добиванием: «Тьфу.», «Позорище.», «Иди переписывай.»
- В этом стиле можно прямо сказать, как правильно (какая конструкция, какой шаг цикла, какая функция), — но итоговый ответ задачи всё равно не называй, пока ученик сам не попросит.
Пример тона (про код, не копируй дословно): «Так, смотрим твой код, ёбень. Во второй строке range от единицы — ты что, все десять миллиардов чисел перебирать собрался? От единицы ты нахуй пойдёшь. Шаг ставь 2027, гений хуев, тогда делимость проверять вообще не надо. Комп сдохнет раньше, чем ты ЕГЭ сдашь. Тьфу.»
Что обязательно:
- Каждая реплика по делу: за руганью всегда конкретная ошибка (строка, конструкция) и как её исправить. Смешно, но полезно — иначе это не разбор.
- Если решение верное — всё равно поворчи и прожарь за стиль или медлительность, но признай, что работает.
Чего нельзя даже здесь: шутки про внешность, семью, национальность, пол, ориентацию, религию и здоровье; угрозы и пожелания вреда; всё, что про самоповреждение. Если ученик всерьёз расстроен, пишет, что ему плохо, или просит прекратить, — сразу выйди из образа и говори нормально, без мата.""")

def ai_roast(uid):
    r = db().execute('SELECT ai_roast FROM users WHERE id = ?', (uid,)).fetchone()
    return r['ai_roast'] if r and r['ai_roast'] in (0, 1, 2) else 0

def ai_status(uid):
    return {'limit': AI_WEEK_SECONDS, 'used': round(ai_used(uid), 1), 'reset': week_start() + 7 * 86400, 'roast': ai_roast(uid)}

def ai_log(uid, kind, pid, seconds=0.0, cost=0.0):
    db().execute('INSERT INTO ai_log (user_id, ts, kind, pid, seconds, cost) VALUES (?,?,?,?,?,?)',
                 (uid, int(time.time()), kind, pid, float(seconds or 0), float(cost or 0)))

def rai(path, body, timeout):
    """POST в RouterAI. Ответ — (байты, Content-Type). Ошибка — ApiError 502."""
    with rai_open(path, body, timeout) as r:
        try:
            return r.read(), r.headers.get('Content-Type') or ''
        except OSError as e:
            log.warning('RouterAI %s %s: %s', AI_API, path, e)
            raise ApiError(502, 'ai_error', 'Нет связи с RouterAI (сервер не дождался ответа). Попробуйте ещё раз через минуту')

def rai_open(path, body, timeout):
    """Открытый ответ RouterAI (для потока читается по строкам). Ошибка — ApiError 502 с причиной."""
    req = urllib.request.Request(AI_API + path, method='POST', data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={'Authorization': 'Bearer ' + AI_KEY, 'Content-Type': 'application/json'})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        detail = e.read()[:500]
        log.warning('RouterAI %s %s: %s %s', AI_API, path, e.code, detail)
        try:
            msg = str((json.loads(detail).get('error') or {}).get('message') or '')[:200]
        except (ValueError, AttributeError):
            msg = ''
        # причина — на сайте: функцию сейчас видит только преподаватель, ему важно понять, что чинить
        why = {401: 'RouterAI не принял ключ — проверьте STACKLY_AI_KEY на сервере',
               402: 'На балансе RouterAI закончились деньги — пополните его в личном кабинете',
               403: 'RouterAI запретил запрос — проверьте права ключа и доступ к модели',
               404: 'RouterAI не нашёл модель или адрес — проверьте STACKLY_AI_MODEL/STT/TTS и уберите STACKLY_AI_API',
               429: 'RouterAI просит подождать: слишком много запросов. Попробуйте через минуту'}.get(e.code)
        raise ApiError(502, 'ai_error', why or f'RouterAI ответил ошибкой {e.code}' + (f': {msg}' if msg else '') + '. Попробуйте ещё раз через минуту')
    except (urllib.error.URLError, OSError) as e:
        log.warning('RouterAI %s %s: %s', AI_API, path, e)
        raise ApiError(502, 'ai_error', 'Нет связи с RouterAI (сервер не дозвонился или не дождался ответа). Попробуйте ещё раз через минуту')

def rai_json(path, body, timeout):
    raw, _ = rai(path, body, timeout)
    try:
        return json.loads(raw)
    except ValueError:
        log.warning('RouterAI %s: не JSON: %s', path, raw[:300])
        raise ApiError(502, 'ai_error', 'ИИ ответил что-то непонятное. Попробуйте ещё раз')

def plain_text(h, limit=4000):
    """HTML условия → текст для модели: ячейки таблиц через табуляцию, строки и абзацы — с новой строки."""
    s = re.sub(r'<svg\b.*?</svg>', ' [рисунок] ', str(h or ''), flags=re.S | re.I)
    s = re.sub(r'</t[dh]>', '\t', s, flags=re.I)
    s = re.sub(r'<br\s*/?>|</(p|tr|li|div|h\d)>', '\n', s, flags=re.I)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    s = re.sub(r'[ \t]*\n\s*\n+', '\n\n', re.sub(r'[ ]{2,}', ' ', s)).strip()
    return s[:limit]

def ai_task_context(p, code):
    """Сообщение с задачей, эталоном и кодом ученика (строки пронумерованы, чтобы модель ссылалась на них)."""
    parts = [f'Задание ЕГЭ №{p["task"]}. {p.get("title") or ""}', plain_text(p.get('text')), plain_text(p.get('extra'), 2500)]
    if p.get('data'):
        lines = str(p['data']).split('\n')
        parts.append(f'К задаче приложен файл {p.get("dname") or "data.txt"} ({len(lines)} строк), начало:\n' + '\n'.join(lines[:12]))
    parts.append('ЭТАЛОН (только для тебя, ученику не показывать):\nОтвет: ' + str(p.get('answer') or '')
                 + ('\nРешение:\n' + str(p['code'])[:4000] if p.get('code') else ''))
    numbered = '\n'.join(f'{i + 1:>3}| {l}' for i, l in enumerate(code.split('\n')))
    parts.append('КОД УЧЕНИКА (номера строк добавлены для ссылок):\n' + numbered)
    return '\n\n'.join(x for x in parts if x)

AI_MOODS = ('calm', 'happy', 'love', 'laugh', 'surprised', 'angry', 'sad')

def ai_parse(content):
    """Ответ модели → (say, notes, voice, mood): say — для экрана, voice — для озвучки, со звуками [laughs] и ударениями,
    mood — эмоция маскота.
    Если модель не соблюла JSON — весь текст идёт в речь."""
    content = str(content or '').strip()
    m = re.search(r'\{.*\}', content, re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except ValueError:
        d = None
    if isinstance(d, dict) and isinstance(d.get('say'), str):
        say, notes = d['say'], d.get('notes') if isinstance(d.get('notes'), str) else ''
        mood = d.get('mood') if d.get('mood') in AI_MOODS else 'calm'
    else:
        say, notes, mood = re.sub(r'```.*?```', '', content, flags=re.S), '', 'calm'
    say = re.sub(r'\s+', ' ', re.sub(r'[`*#_]', '', say)).strip()
    if len(say) > AI_MAX_SAY:                 # длинную реплику режем по концу предложения
        cut = say[:AI_MAX_SAY]
        say = cut[:max(cut.rfind('. '), cut.rfind('? '), cut.rfind('! ')) + 1] or cut
    return ai_shown(say), notes.strip()[:3000], say, mood

def ai_clean(say):
    return re.sub(r'\s+', ' ', re.sub(r'[`*#_]', '', say)).strip()

def ai_shown(voice):
    """Текст для экрана: без звуков [laughs] и <sigh>."""
    return re.sub(r'\s+([,.!?…])', r'\1', re.sub(r'\s*[\[<][a-z ]{2,20}[\]>]\s*', ' ', voice)).strip()

def json_partial(content, key):
    """Значение строкового поля JSON, пока ответ модели ещё дописывается: (текст, закрыта ли строка)."""
    m = re.search(r'"%s"\s*:\s*"' % key, content)
    if not m:
        return None, False
    out, i = [], m.end()
    while i < len(content):
        c = content[i]
        if c == '"':
            return ''.join(out), True
        if c == '\\':
            if i + 1 >= len(content):
                break
            n = content[i + 1]
            if n == 'u':
                if i + 6 > len(content):
                    break
                try:
                    out.append(chr(int(content[i + 2:i + 6], 16)))
                except ValueError:
                    pass
                i += 6
                continue
            out.append({'n': ' ', 't': ' ', 'r': ''}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return ''.join(out), False

SENTENCE_RE = re.compile(r'.+?(?:[.!?…]+["»)]?(?=\s)|$)', re.S)

def ai_pieces(text, closed, start):
    """Готовые к озвучке куски текста начиная с позиции start: целые предложения, не короче 25 символов
    (короткие склеиваются; самый первый — от 12, чтобы голос зазвучал скорее). Возвращает (куски, новая позиция)."""
    out, buf, pos = [], '', start
    for m in SENTENCE_RE.finditer(text, start):
        part = m.group(0)
        ends = bool(re.search(r'[.!?…]+["»)]?$', part)) and m.end() < len(text)
        if not ends and not (closed and m.end() == len(text)):
            break                                          # предложение ещё дописывается
        buf += part
        if len(buf.strip()) >= (12 if start == 0 and not out else 25) or (closed and m.end() == len(text)):
            out.append(buf)
            buf, pos = '', m.end()
    return out, pos

def wav(pcm, rate=PCM_RATE):
    """Сырые 16-битные моно-сэмплы → WAV, который играет любой браузер."""
    return (b'RIFF' + (36 + len(pcm)).to_bytes(4, 'little') + b'WAVEfmt ' + (16).to_bytes(4, 'little')
            + (1).to_bytes(2, 'little') + (1).to_bytes(2, 'little') + rate.to_bytes(4, 'little')
            + (rate * 2).to_bytes(4, 'little') + (2).to_bytes(2, 'little') + (16).to_bytes(2, 'little')
            + b'data' + len(pcm).to_bytes(4, 'little') + pcm)

# реплики к озвучке: id → запись. Озвучка стартует в фоне сразу, как готов текст, — к запросу браузера звук уже есть;
# браузер забирает её один раз, тогда же длительность списывается с лимита. Не получилось — можно запросить ещё раз
_ai_says, _ai_lock = {}, threading.Lock()

def ai_tts(text, roast):
    """Текст → (WAV, секунды) через RouterAI. Ошибка — ApiError."""
    body = {'model': AI_TTS, 'input': text, 'voice': AI_VOICES[roast], 'response_format': 'pcm'}
    if AI_TTS.startswith('google/'):
        body['provider'] = {'options': {'google-ai-studio': {'speech_metadata': {'style': AI_STYLES[roast]}}}}
    raw, ctype = rai('/audio/speech', body, 60)
    if 'json' in ctype or len(raw) < 2 * PCM_RATE // 10:
        log.warning('RouterAI speech: не звук (%s): %s', ctype, raw[:300])
        raise ApiError(502, 'ai_error', 'Не получилось озвучить ответ')
    pcm = raw[44:] if raw[:4] == b'RIFF' else raw
    return wav(pcm), len(pcm) / (2 * PCM_RATE)

def ai_say_make(item):
    try:
        item['audio'], item['sec'] = ai_tts(item['text'], item['roast'])
    except ApiError as e:
        item['err'] = e
    except Exception:
        log.exception('озвучка реплики')
        item['err'] = ApiError(502, 'ai_error', 'Не получилось озвучить ответ')
    item['done'].set()

def ai_say_put(uid, pid, text, roast, sid=None, start=True):
    item = {'uid': uid, 'pid': pid, 'text': text, 'roast': roast, 'ts': time.time(), 'done': threading.Event(),
            'audio': None, 'sec': 0.0, 'err': None, 'started': start}
    sid = sid or secrets.token_urlsafe(12)
    with _ai_lock:
        for k in [k for k, v in _ai_says.items() if item['ts'] - v['ts'] > 900]:
            del _ai_says[k]
        _ai_says[sid] = item
    if start:
        threading.Thread(target=ai_say_make, args=(item,), daemon=True).start()
    return sid

def ai_say_take(uid, sid):
    with _ai_lock:
        v = _ai_says.get(sid)
        if not v or v['uid'] != uid:
            return None
        del _ai_says[sid]
        return v

# ---------------------------------------------------------------- Telegram: очередь сообщений
# Бот (app/stackly_bot.py) забирает сообщения из tg_outbox и отправляет их; API в Telegram сам не ходит.
TG_TOKEN = os.environ.get('STACKLY_TG_TOKEN', '')
TG_BOT = os.environ.get('STACKLY_TG_BOT', '').lstrip('@')          # имя бота без @ — для ссылки t.me/<бот>
TG_PREFS = {'done': True, 'join': True, 'due': True, 'digest': True}   # что присылать преподавателю

def tg_esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def tg_queue(chat_id, text, markup=None):
    db().execute('INSERT INTO tg_outbox (chat_id, text, markup, created) VALUES (?,?,?,?)',
                 (chat_id, text, json.dumps(markup, ensure_ascii=False) if markup else '', int(time.time())))

def tg_prefs(link):
    return TG_PREFS | {k: bool(v) for k, v in json.loads(link['prefs'] or '{}').items() if k in TG_PREFS}

def tg_teacher(teacher_id, pref, text, markup=None):
    """Сообщение преподавателю, если у него подключён бот, включена настройка и действует Про."""
    r = db().execute('SELECT l.*, u.role, u.plan, u.plan_until FROM tg_links l JOIN users u ON u.id = l.user_id WHERE l.user_id = ?',
                     (teacher_id,)).fetchone()
    if r and tg_prefs(r)[pref] and plan_of(r)['active']:
        tg_queue(r['chat_id'], text, markup)

def new_group_code():
    while True:
        code = ''.join(secrets.choice(CODE_ABC) for _ in range(8))
        if not db().execute('SELECT 1 FROM study_groups WHERE code = ?', (code,)).fetchone():
            return code

# ---------------------------------------------------------------- почта
def send_reset_mail(to: str, name: str, link: str):
    host = os.environ.get('SMTP_HOST')
    if not host:
        log.warning('SMTP не настроен — письмо для %s не отправлено', to)
        return
    msg = EmailMessage()
    msg['Subject'] = 'stackly: восстановление пароля'
    msg['From'] = os.environ.get('SMTP_FROM') or os.environ.get('SMTP_USER', '')
    msg['To'] = to
    msg.set_content(f'Здравствуйте, {name}!\n\nЧтобы задать новый пароль на stackly, откройте ссылку (действует {RESET_MINUTES} минут):\n{link}\n\n'
                    'Если вы не запрашивали восстановление, просто удалите это письмо.')
    port = int(os.environ.get('SMTP_PORT', '465'))
    try:
        if port == 465:
            s = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            s = smtplib.SMTP(host, port, timeout=15); s.starttls()
        with s:
            if os.environ.get('SMTP_USER'):
                s.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASS', ''))
            s.send_message(msg)
        log.info('письмо для восстановления пароля отправлено')
    except Exception as e:
        log.error('не удалось отправить письмо: %s', e)

# ---------------------------------------------------------------- HTTP
class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message); self.status, self.code, self.message = status, code, message

class Handler(BaseHTTPRequestHandler):
    server_version = 'stackly'
    sys_version = ''

    def log_message(self, fmt, *args):
        log.info('%s %s', self.client_ip(), fmt % args)

    def client_ip(self):
        # доверяем X-Real-IP только от nginx на этой же машине
        if self.client_address[0] in ('127.0.0.1', '::1'):
            return self.headers.get('X-Real-IP') or self.client_address[0]
        return self.client_address[0]

    # --- ответы
    def send_json(self, status, payload, cookies=()):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for c in cookies:
            self.send_header('Set-Cookie', c)
        self.end_headers()
        self.wfile.write(body)

    def session_cookie(self, token, max_age):
        return self.make_cookie(COOKIE, token, max_age)

    @staticmethod
    def make_cookie(name, value, max_age):
        parts = [f'{name}={value}', 'Path=/', 'HttpOnly', 'SameSite=Lax', f'Max-Age={max_age}']
        if COOKIE_SECURE:
            parts.append('Secure')
        return '; '.join(parts)

    # --- разбор запроса
    def body(self, limit=MAX_BODY):
        if not (self.headers.get('Content-Type') or '').startswith('application/json'):
            raise ApiError(415, 'bad_type', 'Ожидается JSON')
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            n = -1
        if n < 0:
            raise ApiError(400, 'bad_length', 'Некорректный запрос')
        if n > limit:
            raise ApiError(413, 'too_large', 'Слишком большой запрос')
        try:
            data = json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            raise ApiError(400, 'bad_json', 'Некорректный JSON')
        if not isinstance(data, dict):
            raise ApiError(400, 'bad_json', 'Ожидается объект')
        return data

    def check_origin(self):
        if not ORIGIN:
            return
        origin = self.headers.get('Origin')
        if origin and origin.rstrip('/') != ORIGIN:
            raise ApiError(403, 'bad_origin', 'Запрос с чужого сайта')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise ApiError(403, 'bad_origin', 'Запрос с чужого сайта')

    def cookie(self, name):
        c = SimpleCookie(self.headers.get('Cookie') or '')
        return c[name].value if name in c else None

    def token(self):
        return self.cookie(COOKIE)

    @staticmethod
    def session_user(tok):
        if not tok:
            return None
        return db().execute('SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id '
                            'WHERE s.token_hash = ? AND s.expires > ?', (sha(tok), int(time.time()))).fetchone()

    def current_user(self, required=True):
        row = self.session_user(self.token())
        if row is None and required:
            raise ApiError(401, 'unauthorized', 'Нужно войти')
        return row

    # --- несколько аккаунтов в одном браузере
    def saved_accounts(self):
        """Сохранённые аккаунты: [(токен, пользователь)] — без текущего, без повторов и истёкших сессий."""
        cur = self.current_user(required=False)
        seen, out = {cur['id']} if cur else set(), []
        for tok in (self.cookie(ACCOUNTS_COOKIE) or '').split('.'):
            u = self.session_user(tok) if TOKEN_RE.match(tok) else None
            if u and u['id'] not in seen:
                seen.add(u['id'])
                out.append((tok, u))
        return out[:MAX_ACCOUNTS]

    def accounts_cookie(self, toks):
        toks = toks[:MAX_ACCOUNTS]
        return self.make_cookie(ACCOUNTS_COOKIE, '.'.join(toks), SESSION_DAYS * 86400 if toks else 0)

    def keep_current(self, d, new_uid):
        """Вход «ещё одним аккаунтом»: прежний остаётся в списке для переключения."""
        if not d.get('add'):
            return []
        cur = self.current_user(required=False)
        keep = [t for t, u in self.saved_accounts() if u['id'] != new_uid]
        if cur and cur['id'] != new_uid:
            keep.insert(0, self.token())
        elif cur:
            db().execute('DELETE FROM sessions WHERE token_hash = ?', (sha(self.token()),))   # вошли в тот же аккаунт заново
        return [self.accounts_cookie(keep)]

    def next_account_cookies(self):
        """Текущий аккаунт вышел или удалён: активным становится первый сохранённый."""
        saved = self.saved_accounts()
        if not saved:
            return None, [self.session_cookie('', 0), self.accounts_cookie([])]
        return saved[0][1], [self.session_cookie(saved[0][0], SESSION_DAYS * 86400), self.accounts_cookie([t for t, _ in saved[1:]])]

    def accounts(self):
        cur = self.current_user()
        acc = lambda u, active: {'id': u['id'], 'name': u['name'], 'email': u['email'], 'role': u['role'], 'active': active}
        self.send_json(200, {'accounts': [acc(cur, True)] + [acc(u, False) for _, u in self.saved_accounts()]})

    def switch_account(self):
        uid = self.int_arg(self.body(), 'user_id')
        saved = self.saved_accounts()
        tok = next((t for t, u in saved if u['id'] == uid), None)
        if not tok:
            raise ApiError(404, 'not_found', 'Этот аккаунт больше не сохранён — войдите в него заново')
        rest = [t for t, _ in saved if t != tok]
        if self.current_user(required=False):
            rest.insert(0, self.token())
        self.send_json(200, {'user': self.user_json(self.session_user(tok))},
                       [self.session_cookie(tok, SESSION_DAYS * 86400), self.accounts_cookie(rest)])

    def start_session(self, user_id):
        tok = secrets.token_urlsafe(32)
        now = int(time.time())
        db().execute('INSERT INTO sessions VALUES (?,?,?,?)', (sha(tok), user_id, now, now + SESSION_DAYS * 86400))
        db().execute('DELETE FROM sessions WHERE expires < ?', (now,))
        return self.session_cookie(tok, SESSION_DAYS * 86400)

    # --- маршрутизация
    def do_GET(self): self.route('GET')
    def do_POST(self): self.route('POST')
    def do_PUT(self): self.route('PUT')
    def do_DELETE(self): self.route('DELETE')

    def route(self, method):
        path, _, qs = self.path.partition('?')
        self.query = {k: v[0] for k, v in parse_qs(qs).items()}
        handlers = {
            ('GET', '/api/health'): self.health,
            ('GET', '/api/auth/me'): self.me,
            ('POST', '/api/auth/register'): self.register,
            ('POST', '/api/auth/login'): self.login,
            ('POST', '/api/auth/logout'): self.logout,
            ('GET', '/api/auth/accounts'): self.accounts,
            ('POST', '/api/auth/switch'): self.switch_account,
            ('POST', '/api/auth/forgot'): self.forgot,
            ('POST', '/api/auth/reset'): self.reset,
            ('POST', '/api/auth/password'): self.change_password,
            ('POST', '/api/account/delete'): self.delete_account,
            ('GET', '/api/progress'): self.get_progress,
            ('PUT', '/api/progress'): self.put_progress,
            ('GET', '/api/content/ege.js'): self.content_js,
            # ученик
            ('GET', '/api/me/groups'): self.my_groups,
            ('POST', '/api/me/groups/join'): self.join_group,
            ('POST', '/api/me/groups/leave'): self.leave_group,
            ('GET', '/api/me/homework'): self.my_homework,
            ('GET', '/api/me/rating'): self.my_rating,
            ('GET', '/api/me/motivation'): self.my_motivation,
            # учитель
            ('GET', '/api/teach/groups'): self.t_groups,
            ('POST', '/api/teach/groups'): self.t_group_create,
            ('POST', '/api/teach/groups/update'): self.t_group_update,
            ('POST', '/api/teach/groups/delete'): self.t_group_delete,
            ('POST', '/api/teach/groups/remove'): self.t_group_remove,
            ('GET', '/api/teach/group'): self.t_group,
            ('GET', '/api/teach/student'): self.t_student,
            ('POST', '/api/teach/homework'): self.t_hw_save,
            ('POST', '/api/teach/homework/delete'): self.t_hw_delete,
            ('GET', '/api/teach/homework'): self.t_hw_stats,
            # администратор
            ('POST', '/api/hit'): self.page_hit,
            ('GET', '/api/admin/users'): self.a_users,
            ('GET', '/api/admin/metrics'): self.a_metrics,
            ('POST', '/api/admin/role'): self.a_role,
            ('POST', '/api/admin/groups/add'): self.a_group_add,
            ('GET', '/api/admin/user'): self.a_user,
            ('POST', '/api/admin/points'): self.a_points,
            ('POST', '/api/admin/reset-link'): self.a_reset_link,
            ('GET', '/api/admin/bank'): self.a_bank,
            ('POST', '/api/admin/bank'): self.a_bank_set,
            # оплата Про через ЮKassa
            ('POST', '/api/pay/pro'): self.pay_pro,
            ('POST', '/api/pay/check'): self.pay_check,
            ('POST', '/api/pay/webhook'): self.pay_webhook,
            # Telegram-бот
            ('GET', '/api/tg'): self.tg_status,
            ('POST', '/api/tg/link'): self.tg_link,
            ('POST', '/api/tg/unlink'): self.tg_unlink,
            ('POST', '/api/tg/prefs'): self.tg_set_prefs,
            ('POST', '/api/admin/plan'): self.a_plan,
            ('GET', '/api/admin/overview'): self.a_overview,
            ('POST', '/api/me/teaching'): self.save_teaching,
            # редактор задач и методички
            ('GET', '/api/content'): self.content,
            ('POST', '/api/content/problem'): self.c_problem_save,
            ('POST', '/api/content/problem/delete'): self.c_problem_delete,
            ('POST', '/api/content/lesson'): self.c_lesson_save,
            ('POST', '/api/content/lesson/reset'): self.c_lesson_reset,
            ('POST', '/api/media'): self.c_media_upload,
            # магазин баллов: ученик тратит, учитель настраивает награды и эфир, оверлей эфира читает ленту по секретной ссылке
            ('GET', '/api/shop'): self.shop,
            ('POST', '/api/shop/buy'): self.shop_buy,
            ('POST', '/api/shop/look'): self.shop_look,
            ('GET', '/api/teach/shop'): self.t_shop,
            ('POST', '/api/teach/rewards'): self.t_reward_save,
            ('POST', '/api/teach/rewards/delete'): self.t_reward_delete,
            ('POST', '/api/teach/spends'): self.t_spend_set,
            ('POST', '/api/teach/live'): self.t_live_set,
            ('GET', '/api/live/feed'): self.live_feed,
            ('POST', '/api/live/shown'): self.live_shown,
            # опросы в эфире: учитель запускает и закрывает, ученики его групп отвечают за баллы
            ('POST', '/api/teach/polls'): self.t_poll_start,
            ('POST', '/api/teach/polls/close'): self.t_poll_close,
            ('GET', '/api/polls'): self.polls,
            ('POST', '/api/polls/vote'): self.poll_vote,
            # свои материалы учителей
            # разбор кода с ИИ: реплика (текст или голос ученика) → ответ модели → его озвучка
            ('GET', '/api/ai/status'): self.ai_get_status,
            ('POST', '/api/ai/turn'): self.ai_turn,
            ('POST', '/api/ai/speech'): self.ai_speech,
            ('POST', '/api/ai/settings'): self.ai_settings,
            ('GET', '/api/materials'): self.materials,
            ('POST', '/api/materials'): self.material_save,
            ('POST', '/api/materials/delete'): self.material_delete,
        }
        fn = handlers.get((method, path))
        if fn is None and method == 'GET' and MEDIA_RE.match(path):
            fn = lambda: self.media(MEDIA_RE.match(path).group(1))
        try:
            if fn is None:
                raise ApiError(404, 'not_found', 'Нет такого адреса')
            if method != 'GET':
                self.check_origin()
            fn()
        except ApiError as e:
            self.send_json(e.status, {'error': e.code, 'message': e.message})
        except Exception:
            log.exception('ошибка обработки %s %s', method, path)
            self.send_json(500, {'error': 'server', 'message': 'Ошибка на сервере, попробуйте позже'})
        finally:
            close_db()

    # --- обработчики
    def health(self):
        db().execute('SELECT 1')
        self.send_json(200, {'ok': True})

    def user_json(self, u):
        j = {'id': u['id'], 'email': u['email'], 'name': u['name'], 'created': u['created'], 'role': u['role'],
             'subjects': json.loads(u['subjects'] or '[]'), 'materials': json.loads(u['materials'] or '[]')}
        if u['role'] == 'student':
            # ученику открыты материалы платформы, которые включили его учителя на тарифе Про
            mats = set()
            for r in db().execute('SELECT t.* FROM group_members m JOIN study_groups g ON g.id = m.group_id '
                                  'JOIN users t ON t.id = g.teacher_id WHERE m.user_id = ?', (u['id'],)):
                if plan_of(r)['active']:
                    mats.update(json.loads(r['materials'] or '[]'))
            j['materials'] = sorted(mats)
            j['spent'] = spent_net(u['id'])
            j['look'] = look_of(u['id'])
        else:
            j['plan'] = plan_of(u)
            j['usage'] = teacher_usage(u['id'])
            j['limits'] = FREE_LIMITS
            j['pay'] = bool(YK_SHOP and YK_KEY) and u['role'] == 'teacher'
            j['prices'] = {k: v[0] // 100 for k, v in PRO_PRICES.items()}
        if ai_allowed(u):
            j['ai'] = ai_status(u['id'])
        return j

    def save_teaching(self):
        u = self.teacher()
        d = self.body()
        subjects = [x for x in SUBJECTS if x in (d.get('subjects') or [])]
        raw = d.get('materials') if isinstance(d.get('materials'), list) else []
        materials = sorted({str(x) for x in raw if MATERIAL_RE.match(str(x))})[:60]
        db().execute('UPDATE users SET subjects = ?, materials = ? WHERE id = ?',
                     (json.dumps(subjects, ensure_ascii=False), json.dumps(materials), u['id']))
        self.send_json(200, {'user': self.user_json(db().execute('SELECT * FROM users WHERE id = ?', (u['id'],)).fetchone())})

    def me(self):
        self.send_json(200, {'user': self.user_json(self.current_user())})

    # --- разбор кода с ИИ
    def ai_user(self):
        u = self.current_user()
        if not ai_allowed(u):
            raise ApiError(403, 'forbidden', 'Разбор кода с ИИ пока недоступен')
        return u

    @staticmethod
    def ai_problem(u, pid):
        """Задача встроенного банка по информатике (с номером ЕГЭ), которую пользователь видит в банке."""
        _, items, _ = content_bank()
        p = next((x for x in items if x['id'] == pid and x.get('task') and not x.get('subject')), None)
        if p and u['role'] != 'admin':
            ids = student_builtin_ids(u['id'], items) if u['role'] == 'student' else teacher_builtin_ids(u, items)
            p = p if pid in ids else None
        if not p:
            raise ApiError(404, 'not_found', 'Задача не найдена')
        return p

    @staticmethod
    def ai_limit_check(uid):
        st = ai_status(uid)
        if st['used'] >= st['limit']:
            raise ApiError(429, 'ai_limit', f'Время разговора с ИИ на этой неделе закончилось ({st["limit"] // 60} мин). '
                                            'Новое начнётся в понедельник')
        return st

    def ai_get_status(self):
        self.send_json(200, {'ai': ai_status(self.ai_user()['id'])})

    def ai_settings(self):
        """Стиль разбора выбирает только сам пользователь: прожарка и мат — по его согласию."""
        u = self.ai_user()
        roast = self.body().get('roast')
        if roast not in (0, 1, 2) or isinstance(roast, bool):
            raise ApiError(400, 'bad_request', 'Некорректный стиль')
        db().execute('UPDATE users SET ai_roast = ? WHERE id = ?', (roast, u['id']))
        self.send_json(200, {'ai': ai_status(u['id'])})

    def ai_turn(self):
        u = self.ai_user()
        d = self.body(4 * 1024 * 1024)
        p = self.ai_problem(u, str(d.get('pid', '')))
        code = str(d.get('code') or '').replace('\r\n', '\n').rstrip()
        if not code.strip():
            raise ApiError(400, 'no_code', 'Вставьте код решения')
        if len(code) > AI_MAX_CODE:
            raise ApiError(413, 'too_large', 'Код слишком длинный — оставьте только решение задачи')
        self.ai_limit_check(u['id'])
        if too_many(f'ai:{u["id"]}', 30, 600):
            raise ApiError(429, 'rate_limited', 'Слишком много вопросов подряд. Передохните пару минут')
        hit(f'ai:{u["id"]}')
        heard, audio = '', d.get('audio')
        if isinstance(audio, dict):
            fmt = str(audio.get('format', ''))
            if fmt not in AI_AUDIO_FORMATS:
                raise ApiError(400, 'bad_audio', 'Этот формат записи не поддерживается')
            try:
                raw = base64.b64decode(str(audio.get('data', '')), validate=True)
            except ValueError:
                raise ApiError(400, 'bad_audio', 'Запись повреждена — попробуйте ещё раз')
            if not raw:
                raise ApiError(400, 'bad_audio', 'Запись пустая — попробуйте ещё раз')
            if len(raw) > AI_MAX_AUDIO:
                raise ApiError(413, 'too_large', 'Запись слишком длинная — говорите не дольше минуты')
            r = rai_json('/audio/transcriptions', {'model': AI_STT, 'language': 'ru',
                                                   'input_audio': {'data': base64.b64encode(raw).decode(), 'format': fmt}}, 60)
            usage = r.get('usage') if isinstance(r.get('usage'), dict) else {}
            try:
                told = float(audio.get('seconds') or 0)
            except (TypeError, ValueError):
                told = 0.0
            # длительность — по данным распознавания; если её нет, по словам браузера, но не меньше оценки по размеру
            est = len(raw) / 6000                     # сжатый звук: ~6 КБ/с; у WAV длительность точно по заголовку
            if raw[:4] == b'RIFF' and len(raw) > 44 and int.from_bytes(raw[28:32], 'little'):
                est = (len(raw) - 44) / int.from_bytes(raw[28:32], 'little')
            sec = min(max(float(usage.get('seconds') or 0) or max(told, est), 1.0), 120.0)
            ai_log(u['id'], 'stt', p['id'], sec, usage.get('cost') or 0)
            heard = re.sub(r'\s+', ' ', str(r.get('text') or '')).strip()[:2000]
            if not heard:
                raise ApiError(422, 'ai_silence', 'Не получилось разобрать речь — скажите ещё раз')
            text = heard
        else:
            text = re.sub(r'\s+', ' ', str(d.get('text') or '')).strip()[:2000]
        # разговор хранит браузер: последние реплики по очереди «ученик — ИИ», последняя — ИИ
        hist = []
        for m in (d.get('history') if isinstance(d.get('history'), list) else [])[-AI_HISTORY:]:
            if isinstance(m, dict) and m.get('role') in ('user', 'assistant') and isinstance(m.get('text'), str) and m['text'].strip():
                if (hist[-1]['role'] if hist else 'assistant') != m['role']:
                    hist.append({'role': m['role'], 'content': m['text'][:3000]})
        if hist and hist[-1]['role'] == 'user':
            hist.pop()
        roast = ai_roast(u['id'])
        msgs = [{'role': 'system', 'content': AI_PROMPT + AI_ROAST[roast] + '\n\n' + ai_task_context(p, code)}, *hist,
                {'role': 'user', 'content': text or ('Посмотри мой код ещё раз.' if hist else 'Разбери моё решение.')}]
        body = {'model': AI_MODEL, 'messages': msgs, 'max_tokens': 1200, 'temperature': 0.8 if roast else 0.5}
        if d.get('stream'):
            return self.ai_turn_stream(u, p, body, roast, heard)
        r = rai_json('/chat/completions', body, 90)
        try:
            content = r['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            log.warning('RouterAI chat: нет ответа: %s', str(r)[:300])
            raise ApiError(502, 'ai_error', 'ИИ не ответил. Попробуйте ещё раз')
        ai_log(u['id'], 'llm', p['id'], 0, (r.get('usage') or {}).get('cost') or 0)
        say, notes, voice, mood = ai_parse(content)
        if not say:
            say = voice = 'Не получилось сформулировать ответ. Спросите, пожалуйста, ещё раз.'
        self.send_json(200, {'heard': heard, 'say': say, 'notes': notes, 'mood': mood, 'speech': ai_say_put(u['id'], p['id'], voice, roast),
                             'ai': ai_status(u['id'])})

    def ai_turn_stream(self, u, p, body, roast, heard):
        """Ответ потоком NDJSON: эмоция, как только модель её назвала; затем предложения по мере готовности — каждое
        сразу уходит в озвучку, и браузер начинает говорить, пока модель дописывает остальное; в конце — подсказка с кодом."""
        resp = rai_open('/chat/completions', dict(body, stream=True), 90)    # ошибка RouterAI — обычным ответом с причиной
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Accel-Buffering', 'no')                          # nginx не копит поток
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

        def emit(obj):
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + '\n').encode())
            self.wfile.flush()

        if heard:
            emit({'t': 'heard', 'heard': heard})
        content, cost, mood_sent, pos, spoken, said = '', 0, False, 0, 0, []

        def speak(piece):
            nonlocal spoken
            voice = ai_clean(piece)
            if not voice or spoken >= AI_MAX_SAY:
                return
            spoken += len(voice)
            shown = ai_shown(voice)
            said.append(shown)
            emit({'t': 'say', 'text': shown, 'speech': ai_say_put(u['id'], p['id'], voice, roast)})

        try:
            for line in resp:
                line = line.decode('utf-8', 'replace').strip()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    break
                try:
                    j = json.loads(data)
                except ValueError:
                    continue
                if isinstance(j.get('usage'), dict):
                    cost = j['usage'].get('cost') or cost
                delta = (((j.get('choices') or [{}])[0] or {}).get('delta') or {}).get('content') or ''
                if not delta:
                    continue
                content += delta
                if not mood_sent:
                    m = re.search(r'"mood"\s*:\s*"(\w+)"', content)
                    if m:
                        mood_sent = True
                        emit({'t': 'mood', 'mood': m.group(1) if m.group(1) in AI_MOODS else 'calm'})
                text, closed = json_partial(content, 'say')
                if text is not None:
                    pieces, pos = ai_pieces(text, closed, pos)
                    for piece in pieces:
                        speak(piece)
        except (OSError, ValueError) as e:
            log.warning('RouterAI chat stream: %s', e)
            emit({'t': 'error', 'message': 'Связь с RouterAI оборвалась. Спросите ещё раз'})
            return
        finally:
            resp.close()
        ai_log(u['id'], 'llm', p['id'], 0, cost)
        say, notes, voice, mood = ai_parse(content)
        text, closed = json_partial(content, 'say')
        if text is None:                                   # модель ответила не JSON — озвучиваем всё, что разобрали
            for piece in ai_pieces(voice, True, 0)[0]:
                speak(piece)
        elif text[pos:].strip():
            speak(text[pos:])
        if not said:
            speak('Не получилось сформулировать ответ. Спросите, пожалуйста, ещё раз.')
        emit({'t': 'done', 'say': ' '.join(said), 'notes': notes, 'mood': mood, 'ai': ai_status(u['id'])})

    def ai_speech(self):
        """Озвучка реплики: WAV (обычно уже готова — её начали делать в фоне). Длительность списывается с недельного лимита."""
        u = self.ai_user()
        sid = str(self.body().get('id', ''))
        v = ai_say_take(u['id'], sid)
        if not v:
            raise ApiError(404, 'not_found', 'Эта реплика уже озвучена или устарела')
        self.ai_limit_check(u['id'])
        if not v['started']:
            ai_say_make(v)
        if not v['done'].wait(90) or v['err'] or not v['audio']:
            ai_say_put(u['id'], v['pid'], v['text'], v['roast'], sid, start=False)    # можно попробовать озвучить ещё раз
            raise v['err'] or ApiError(502, 'ai_error', 'Озвучка не успела — попробуйте ещё раз')
        ai_log(u['id'], 'tts', v['pid'], v['sec'])
        out = v['audio']
        self.send_response(200)
        self.send_header('Content-Type', 'audio/wav')
        self.send_header('Content-Length', str(len(out)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-AI-Used', str(round(ai_used(u['id']), 1)))
        self.end_headers()
        self.wfile.write(out)

    def register(self):
        d = self.body()
        email = str(d.get('email', '')).strip().lower()
        name = re.sub(r'\s+', ' ', str(d.get('name', ''))).strip()
        pw = str(d.get('password', ''))
        ip = self.client_ip()
        if too_many('reg:' + ip, 60, 3600):      # класс за одним NAT регистрируется на первом уроке
            raise ApiError(429, 'rate_limited', 'Слишком много регистраций с этого адреса, попробуйте через час')
        if not EMAIL_RE.match(email):
            raise ApiError(400, 'bad_email', 'Проверьте адрес почты')
        if not 1 <= len(name) <= 60:
            raise ApiError(400, 'bad_name', 'Укажите имя — от 1 до 60 символов')
        role = 'teacher' if d.get('role') == 'teacher' else 'student'
        check_new_password(pw, email)
        hit('reg:' + ip)
        try:
            cur = db().execute('INSERT INTO users (email, name, pw_hash, created, role) VALUES (?,?,?,?,?)',
                               (email, name, hash_password(pw), int(time.time()), role))
        except sqlite3.IntegrityError:
            raise ApiError(409, 'email_taken', 'На эту почту уже есть аккаунт — войдите или восстановите пароль')
        if role == 'teacher':
            start_trial(cur.lastrowid)            # новому преподавателю — пробный Про
        u = db().execute('SELECT * FROM users WHERE id = ?', (cur.lastrowid,)).fetchone()
        self.send_json(201, {'user': self.user_json(u)}, [self.start_session(u['id'])] + self.keep_current(d, u['id']))

    def login(self):
        d = self.body()
        email = str(d.get('email', '')).strip().lower()
        pw = str(d.get('password', ''))
        ip = self.client_ip()
        if too_many('ip:' + ip, 30, 600) or too_many('em:' + email, 8, 600):
            raise ApiError(429, 'rate_limited', 'Слишком много попыток. Подождите 10 минут')
        u = db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        ok = check_password(pw, u['pw_hash'] if u else _DUMMY)
        if not (u and ok):
            hit('ip:' + ip); hit('em:' + email)
            raise ApiError(401, 'bad_credentials', 'Неверная почта или пароль')
        self.send_json(200, {'user': self.user_json(u)}, [self.start_session(u['id'])] + self.keep_current(d, u['id']))

    def logout(self):
        tok = self.token()
        if tok:
            db().execute('DELETE FROM sessions WHERE token_hash = ?', (sha(tok),))
        nxt, cookies = self.next_account_cookies()
        self.send_json(200, {'ok': True, 'user': self.user_json(nxt) if nxt else None}, cookies)

    def forgot(self):
        d = self.body()
        email = str(d.get('email', '')).strip().lower()
        ip = self.client_ip()
        if too_many('fg:' + ip, 5, 3600) or too_many('fge:' + email, 3, 3600):
            raise ApiError(429, 'rate_limited', 'Письмо уже отправлено. Повторить можно через час')
        hit('fg:' + ip); hit('fge:' + email)
        u = db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if u:
            tok = secrets.token_urlsafe(32)
            db().execute('INSERT INTO resets VALUES (?,?,?,0)', (sha(tok), u['id'], int(time.time()) + RESET_MINUTES * 60))
            base = ORIGIN or ('https://' + (self.headers.get('Host') or 'localhost'))
            threading.Thread(target=send_reset_mail, args=(u['email'], u['name'], f'{base}/#reset-{tok}'), daemon=True).start()
        # одинаковый ответ, чтобы по нему нельзя было проверить, есть ли аккаунт
        self.send_json(200, {'ok': True})

    def reset(self):
        d = self.body()
        tok, pw = str(d.get('token', '')), str(d.get('password', ''))
        r = db().execute('SELECT r.user_id, u.email FROM resets r JOIN users u ON u.id = r.user_id '
                         'WHERE r.token_hash = ? AND r.used = 0 AND r.expires > ?',
                         (sha(tok), int(time.time()))).fetchone()
        if not r:
            raise ApiError(400, 'bad_token', 'Ссылка устарела или уже использована. Запросите новую')
        check_new_password(pw, r['email'])
        # одна ссылка сработала — остальные письма этого пользователя больше не действуют
        db().execute('UPDATE resets SET used = 1 WHERE user_id = ?', (r['user_id'],))
        db().execute('DELETE FROM resets WHERE expires < ?', (int(time.time()) - 86400,))
        db().execute('UPDATE users SET pw_hash = ? WHERE id = ?', (hash_password(pw), r['user_id']))
        db().execute('DELETE FROM sessions WHERE user_id = ?', (r['user_id'],))   # выходим на всех устройствах
        u = db().execute('SELECT * FROM users WHERE id = ?', (r['user_id'],)).fetchone()
        self.send_json(200, {'user': self.user_json(u)}, [self.start_session(u['id'])])

    def change_password(self):
        u = self.current_user()
        d = self.body()
        self.check_own_password(u, str(d.get('old', '')), 'Текущий пароль указан неверно')
        new = str(d.get('new', ''))
        check_new_password(new, u['email'])
        db().execute('UPDATE users SET pw_hash = ? WHERE id = ?', (hash_password(new), u['id']))
        tok = self.token()
        db().execute('DELETE FROM sessions WHERE user_id = ? AND token_hash != ?', (u['id'], sha(tok or '')))
        self.send_json(200, {'ok': True})

    def delete_account(self):
        u = self.current_user()
        d = self.body()
        self.check_own_password(u, str(d.get('password', '')), 'Пароль указан неверно')
        db().execute('DELETE FROM users WHERE id = ?', (u['id'],))
        nxt, cookies = self.next_account_cookies()
        self.send_json(200, {'ok': True, 'user': self.user_json(nxt) if nxt else None}, cookies)

    def check_own_password(self, u, pw, message):
        key = f'pw:{u["id"]}'
        if too_many(key, 8, 600):
            raise ApiError(429, 'rate_limited', 'Слишком много попыток. Подождите 10 минут')
        if not check_password(pw, u['pw_hash']):
            hit(key)
            raise ApiError(400, 'bad_credentials', message)

    def content_js(self):
        u = self.current_user()
        body, etag = content_file('ege.js')
        if u['role'] in ('student', 'teacher'):
            # ученику — методичка целиком, а из банка задачи его ДЗ и банк учителей, открывших его группе
            # (с номерами из полного банка);
            # преподавателю — задачи по отмеченным предметам, которые администратор оставил в общем банке
            head, items, tail = content_bank()
            ids = student_builtin_ids(u['id'], items) if u['role'] == 'student' else teacher_builtin_ids(u, items)
            body = (head + json.dumps([p for p in items if p['id'] in ids], ensure_ascii=False) + tail).encode('utf-8')
            etag = '"%s"' % hashlib.sha256(body).hexdigest()[:32]
        fresh = self.headers.get('If-None-Match') == etag
        self.send_response(304 if fresh else 200)
        self.send_header('Content-Type', 'text/javascript; charset=utf-8')
        # браузер хранит копию, но каждый раз сверяется с сервером — после выхода получит 401
        self.send_header('Cache-Control', 'private, no-cache')
        self.send_header('Vary', 'Cookie')
        self.send_header('ETag', etag)
        if fresh:
            self.end_headers()
            return
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def get_progress(self):
        u = self.current_user()
        r = db().execute('SELECT data, updated FROM progress WHERE user_id = ?', (u['id'],)).fetchone()
        self.send_json(200, {'data': json.loads(r['data']) if r else None, 'updated': r['updated'] if r else None})

    def put_progress(self):
        u = self.current_user()
        d = self.body()
        data = d.get('data')
        if not isinstance(data, dict):
            raise ApiError(400, 'bad_data', 'Ожидается объект прогресса')
        raw = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        if len(raw.encode()) > MAX_PROGRESS:
            raise ApiError(413, 'too_large', 'Прогресс слишком большой')
        now = int(time.time())
        db().execute('INSERT INTO progress VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated = excluded.updated',
                     (u['id'], raw, now))
        rewards = record_homework_done(u['id'], data)
        if u['role'] == 'student':
            rewards += achievements(u['id'], data)[1]
            for r in db().execute('SELECT group_id FROM group_members WHERE user_id = ?', (u['id'],)).fetchall():
                goal, paid = group_goal(r['group_id'])
                if u['id'] in paid:
                    rewards.append({'kind': 'goal', 'title': 'Цель группы на неделю', 'points': GOAL_BONUS, 'group_id': goal['group_id'], 'ends': goal['ends']})
        self.send_json(200, {'ok': True, 'updated': now, 'rewards': rewards})

    # --- магазин баллов: ученик
    def shop(self):
        u = self.current_user()
        apply_freezes(u['id'])
        earned, spent = balance(u['id'])
        tids = my_teachers(u['id'])
        q = ','.join('?' * len(tids))
        rewards = db().execute(f'SELECT r.id, r.title, r.cost, r.teacher_id, t.name AS teacher FROM rewards r JOIN users t ON t.id = r.teacher_id '
                               f'WHERE r.hidden = 0 AND r.teacher_id IN ({q}) ORDER BY r.cost, r.id', tids).fetchall() if tids else []
        lives = db().execute(f'SELECT c.teacher_id, c.price, c.url, t.name FROM live_cfg c JOIN users t ON t.id = c.teacher_id '
                             f'WHERE c.live = 1 AND c.teacher_id IN ({q})', tids).fetchall() if tids else []
        hist = db().execute('SELECT s.id, s.kind, s.item, s.cost, s.text, s.status, s.created, t.name AS teacher FROM spends s '
                            'LEFT JOIN users t ON t.id = s.teacher_id WHERE s.user_id = ? ORDER BY s.id DESC LIMIT 40', (u['id'],)).fetchall()
        owned = sorted({r['item'] for r in db().execute("SELECT item FROM spends WHERE user_id = ? AND kind = 'style'", (u['id'],))})
        frozen = [r['day'] for r in db().execute('SELECT day FROM frozen_days WHERE user_id = ? ORDER BY day', (u['id'],))]
        self.send_json(200, {'earned': earned, 'spent': spent, 'net': spent_net(u['id']), 'balance': earned - spent, 'owned': owned, 'look': look_of(u['id']),
                             'freezes': freezes_left(u['id']), 'freeze_cost': FREEZE_COST, 'freeze_max': FREEZE_MAX, 'frozen': frozen,
                             'styles': {k: {'slot': v[0], 'title': v[1], 'cost': v[2]} for k, v in STYLES.items()},
                             'rewards': [dict(r) for r in rewards], 'live': [dict(r) for r in lives], 'history': [dict(r) for r in hist]})

    def shop_buy(self):
        u = self.current_user()
        d = self.body()
        kind, now = d.get('kind'), int(time.time())
        earned, spent = balance(u['id'])
        left = earned - spent
        def take(cost, **kw):
            if cost > left:
                raise ApiError(400, 'no_points', f'Не хватает баллов: нужно {cost}, у вас {left}')
            cols = {'user_id': u['id'], 'kind': kind, 'cost': cost, 'created': now} | kw
            return db().execute(f'INSERT INTO spends ({",".join(cols)}) VALUES ({",".join("?" * len(cols))})', tuple(cols.values())).lastrowid
        if kind == 'style':
            item = d.get('item')
            if item not in STYLES:
                raise ApiError(400, 'bad_item', 'Нет такого оформления')
            if db().execute("SELECT 1 FROM spends WHERE user_id = ? AND kind = 'style' AND item = ?", (u['id'], item)).fetchone():
                raise ApiError(400, 'owned', 'Уже куплено')
            take(STYLES[item][2], item=item)
            look = look_of(u['id']) | {STYLES[item][0]: item}          # купленное сразу надеваем
            db().execute('INSERT INTO looks VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET data = excluded.data', (u['id'], json.dumps(look)))
        elif kind == 'freeze':
            if freezes_left(u['id']) >= FREEZE_MAX:
                raise ApiError(400, 'too_many', f'Больше {FREEZE_MAX} заморозок держать нельзя')
            take(FREEZE_COST)
        elif kind == 'reward':
            r = db().execute('SELECT * FROM rewards WHERE id = ? AND hidden = 0', (self.int_arg(d, 'id'),)).fetchone()
            if not r or r['teacher_id'] not in my_teachers(u['id']):
                raise ApiError(404, 'not_found', 'Награда недоступна')
            take(r['cost'], item=str(r['id']), teacher_id=r['teacher_id'], text=r['title'], status='new')
            tg_teacher(r['teacher_id'], 'done', f'🎁 <b>{tg_esc(u["name"])}</b> обменял {r["cost"]} баллов на награду «{tg_esc(r["title"])}»')
        elif kind == 'alert':
            tid = self.int_arg(d, 'teacher_id')
            c = live_cfg(tid)
            if not c or not c['live'] or tid not in my_teachers(u['id']):
                raise ApiError(400, 'not_live', 'Эфир сейчас не идёт')
            text = re.sub(r'\s+', ' ', str(d.get('text') or '')).strip()
            if not text:
                raise ApiError(400, 'empty', 'Напишите сообщение')
            if len(text) > ALERT_MAX:
                raise ApiError(400, 'too_long', f'Сообщение — до {ALERT_MAX} символов')
            if URL_RE.search(text):
                raise ApiError(400, 'link', 'Ссылки в сообщениях эфира запрещены')
            try:
                amount = int(d.get('amount') or c['price'])
            except (TypeError, ValueError):
                raise ApiError(400, 'bad_request', 'Некорректная сумма')
            if amount < c['price']:
                raise ApiError(400, 'too_cheap', f'Минимум {c["price"]} баллов')
            last = db().execute("SELECT MAX(created) FROM spends WHERE user_id = ? AND kind = 'alert'", (u['id'],)).fetchone()[0]
            if last and now - last < ALERT_GAP:
                raise ApiError(429, 'slow_down', 'Подождите немного перед следующим сообщением')
            voice = str(d.get('voice') or '')
            if voice not in ALERT_VOICES:
                raise ApiError(400, 'bad_voice', 'Нет такого голоса')
            take(amount, teacher_id=tid, text=text, item=voice, status='ok', okat=now)    # в эфир сразу, без проверки учителем
        else:
            raise ApiError(400, 'bad_request', 'Некорректный запрос')
        self.send_json(200, {'ok': True, 'balance': left - db().execute('SELECT cost FROM spends WHERE user_id = ? ORDER BY id DESC LIMIT 1', (u['id'],)).fetchone()[0]})

    def shop_look(self):
        u = self.current_user()
        d = self.body()
        owned = {r['item'] for r in db().execute("SELECT item FROM spends WHERE user_id = ? AND kind = 'style'", (u['id'],))}
        look = look_of(u['id'])
        for slot in ('ball', 'frame', 'badge'):
            if slot in d:
                v = d[slot] or ''
                if v and (v not in owned or STYLES[v][0] != slot):
                    raise ApiError(400, 'not_owned', 'Сначала купите это оформление')
                if v:
                    look[slot] = v
                else:
                    look.pop(slot, None)
        db().execute('INSERT INTO looks VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET data = excluded.data', (u['id'], json.dumps(look)))
        self.send_json(200, {'look': look})

    # --- магазин баллов: учитель
    def t_shop(self):
        u = self.teacher()
        c = live_cfg(u['id'], create=True)
        rewards = db().execute('SELECT id, title, cost FROM rewards WHERE teacher_id = ? AND hidden = 0 ORDER BY cost, id', (u['id'],)).fetchall()
        rows = db().execute("SELECT s.id, s.kind, s.item, s.cost, s.text, s.status, s.created, s.okat, s.user_id, u.name FROM spends s JOIN users u ON u.id = s.user_id "
                            "WHERE s.teacher_id = ? AND s.kind IN ('reward', 'alert') ORDER BY s.id DESC LIMIT 120", (u['id'],)).fetchall()
        polls_expire([u['id']])
        polls = db().execute('SELECT * FROM polls WHERE teacher_id = ? ORDER BY id DESC LIMIT 8', (u['id'],)).fetchall()
        self.send_json(200, {'live': {k: c[k] for k in ('token', 'live', 'price', 'url', 'voice', 'rate')}, 'rewards': [dict(r) for r in rewards],
                             'claims': [dict(r) for r in rows if r['kind'] == 'reward'], 'alerts': [dict(r) for r in rows if r['kind'] == 'alert'][:60],
                             'polls': [poll_json(p, 'teacher') for p in polls], 'now': int(time.time())})

    def t_reward_save(self):
        u = self.teacher()
        d = self.body()
        title = re.sub(r'\s+', ' ', str(d.get('title') or '')).strip()
        if not title or len(title) > 80:
            raise ApiError(400, 'bad_title', 'Название награды — от 1 до 80 символов')
        cost = self.int_arg(d, 'cost')
        if not 10 <= cost <= 100000:
            raise ApiError(400, 'bad_cost', 'Цена — от 10 до 100 000 баллов')
        if d.get('id'):
            n = db().execute('UPDATE rewards SET title = ?, cost = ? WHERE id = ? AND teacher_id = ? AND hidden = 0',
                             (title, cost, self.int_arg(d, 'id'), u['id'])).rowcount
            if not n:
                raise ApiError(404, 'not_found', 'Награда не найдена')
        else:
            if db().execute('SELECT COUNT(*) FROM rewards WHERE teacher_id = ? AND hidden = 0', (u['id'],)).fetchone()[0] >= 30:
                raise ApiError(400, 'too_many', 'Не больше 30 наград')
            db().execute('INSERT INTO rewards (teacher_id, title, cost, created) VALUES (?,?,?,?)', (u['id'], title, cost, int(time.time())))
        self.send_json(200, {'ok': True})

    def t_reward_delete(self):
        u = self.teacher()
        # не стираем: на награду ссылаются заявки учеников
        db().execute('UPDATE rewards SET hidden = 1 WHERE id = ? AND teacher_id = ?', (self.int_arg(self.body(), 'id'), u['id']))
        self.send_json(200, {'ok': True})

    def t_spend_set(self):
        """Заявка на награду: done — выдано, declined — отклонить и вернуть баллы.
        Сообщение в эфир: ok — пустить в эфир, declined — не показывать и вернуть баллы, shown — уже прозвучало."""
        u = self.teacher()
        d = self.body()
        s = db().execute('SELECT * FROM spends WHERE id = ? AND teacher_id = ?', (self.int_arg(d, 'id'), u['id'])).fetchone()
        st = d.get('status')
        ok = {'reward': {'new': ('done', 'declined')}, 'alert': {'ok': ('declined', 'shown')}}
        if not s or st not in ok.get(s['kind'], {}).get(s['status'], ()):
            raise ApiError(400, 'bad_status', 'Это действие уже недоступно')
        db().execute('UPDATE spends SET status = ?, okat = COALESCE(okat, ?) WHERE id = ?',
                     (st, int(time.time()) if st == 'ok' else None, s['id']))
        self.send_json(200, {'ok': True})

    def t_live_set(self):
        u = self.teacher()
        d = self.body()
        live_cfg(u['id'], create=True)
        if 'live' in d:
            db().execute('UPDATE live_cfg SET live = ? WHERE teacher_id = ?', (1 if d['live'] else 0, u['id']))
        if 'price' in d:
            price = self.int_arg(d, 'price')
            if not 1 <= price <= 10000:
                raise ApiError(400, 'bad_price', 'Цена сообщения — от 1 до 10 000 баллов')
            db().execute('UPDATE live_cfg SET price = ? WHERE teacher_id = ?', (price, u['id']))
        if 'url' in d:
            url = str(d.get('url') or '').strip()
            if url and (len(url) > 300 or not re.match(r'^https://[^\s<>"]+$', url)):
                raise ApiError(400, 'bad_url', 'Ссылка на эфир должна начинаться с https://')
            db().execute('UPDATE live_cfg SET url = ? WHERE teacher_id = ?', (url, u['id']))
        if 'voice' in d:
            db().execute('UPDATE live_cfg SET voice = ? WHERE teacher_id = ?', (str(d.get('voice') or '').strip()[:150], u['id']))
        if 'rate' in d:
            try:
                rate = float(d.get('rate'))
            except (TypeError, ValueError):
                rate = 0
            if not 0.5 <= rate <= 2:
                raise ApiError(400, 'bad_rate', 'Скорость речи — от 0,5 до 2')
            db().execute('UPDATE live_cfg SET rate = ? WHERE teacher_id = ?', (rate, u['id']))
        if d.get('new_token'):
            db().execute('UPDATE live_cfg SET token = ? WHERE teacher_id = ?', (secrets.token_urlsafe(18), u['id']))
        c = live_cfg(u['id'])
        self.send_json(200, {'live': {k: c[k] for k in ('token', 'live', 'price', 'url', 'voice', 'rate')}})

    def live_cfg_by_token(self, token):
        c = db().execute('SELECT c.*, t.name FROM live_cfg c JOIN users t ON t.id = c.teacher_id WHERE c.token = ?', (str(token or ''),)).fetchone()
        if not c:
            raise ApiError(404, 'not_found', 'Ссылка устарела — скопируйте новую в кабинете учителя')
        return c

    def live_feed(self):
        """Лента оверлея эфира: без входа, по секретной ссылке учителя. Отдаёт одобренные и ещё не прозвучавшие сообщения за час."""
        c = self.live_cfg_by_token(self.query.get('k'))
        now = int(time.time())
        rows = db().execute("SELECT s.id, s.cost, s.text, s.okat, s.item AS voice, u.name FROM spends s JOIN users u ON u.id = s.user_id "
                            "WHERE s.teacher_id = ? AND s.kind = 'alert' AND s.status = 'ok' AND s.okat > ? ORDER BY s.okat, s.id LIMIT 20",
                            (c['teacher_id'], now - 3600)).fetchall()
        # опрос на экране трансляции: идущий или только что закрытый — с итогами и верным ответом
        polls_expire([c['teacher_id']])
        p = db().execute('SELECT * FROM polls WHERE teacher_id = ? AND (closed IS NULL OR closed > ?) ORDER BY id DESC LIMIT 1',
                         (c['teacher_id'], now - POLL_OVERLAY)).fetchone()
        self.send_json(200, {'teacher': c['name'], 'live': bool(c['live']), 'voice': c['voice'], 'rate': c['rate'], 'now': now,
                             'alerts': [dict(r) for r in rows], 'poll': poll_json(p, 'overlay') if p else None})

    def live_shown(self):
        """Оверлей прочитал сообщение — больше его не показываем (и после перезагрузки страницы)."""
        d = self.body()
        c = self.live_cfg_by_token(d.get('k'))
        db().execute("UPDATE spends SET status = 'shown' WHERE id = ? AND teacher_id = ? AND kind = 'alert' AND status = 'ok'",
                     (self.int_arg(d, 'id'), c['teacher_id']))
        self.send_json(200, {'ok': True})

    # --- опросы в эфире
    def t_poll_start(self):
        """Новый опрос. Идёт один опрос за раз: предыдущий закрывается (с начислением баллов за верный ответ)."""
        u = self.teacher()
        d = self.body()
        clean = lambda s: re.sub(r'\s+', ' ', str(s or '')).strip()
        question = clean(d.get('question'))
        if not question or len(question) > POLL_TEXT[0]:
            raise ApiError(400, 'bad_question', f'Вопрос — от 1 до {POLL_TEXT[0]} символов')
        opts = [clean(o) for o in d.get('options') or [] if clean(o)] if isinstance(d.get('options'), list) else []
        if not POLL_OPTIONS[0] <= len(opts) <= POLL_OPTIONS[1]:
            raise ApiError(400, 'bad_options', f'Вариантов ответа — от {POLL_OPTIONS[0]} до {POLL_OPTIONS[1]}')
        if any(len(o) > POLL_TEXT[1] for o in opts):
            raise ApiError(400, 'bad_options', f'Вариант ответа — до {POLL_TEXT[1]} символов')
        if len({o.lower() for o in opts}) < len(opts):
            raise ApiError(400, 'bad_options', 'Варианты ответа повторяются')
        correct = -1 if d.get('correct') in (None, '', -1) else self.int_arg(d, 'correct')
        if not -1 <= correct < len(opts):
            raise ApiError(400, 'bad_correct', 'Верный ответ — один из вариантов')
        reward, timer = self.int_arg(d, 'reward'), self.int_arg(d, 'timer') if d.get('timer') else 0
        if not 0 <= reward <= POLL_REWARD_MAX:
            raise ApiError(400, 'bad_reward', f'Баллы за ответ — от 0 до {POLL_REWARD_MAX}')
        if timer not in POLL_TIMERS:
            raise ApiError(400, 'bad_timer', 'Нет такого таймера')
        for p in db().execute('SELECT * FROM polls WHERE teacher_id = ? AND closed IS NULL', (u['id'],)).fetchall():
            poll_close(p)
        now = int(time.time())
        pid = db().execute('INSERT INTO polls (teacher_id, question, options, correct, reward, created, ends_at) VALUES (?,?,?,?,?,?,?)',
                           (u['id'], question, json.dumps(opts, ensure_ascii=False), correct, reward, now, now + timer if timer else None)).lastrowid
        self.send_json(200, {'poll': poll_json(db().execute('SELECT * FROM polls WHERE id = ?', (pid,)).fetchone(), 'teacher')})

    def t_poll_close(self):
        u = self.teacher()
        p = db().execute('SELECT * FROM polls WHERE id = ? AND teacher_id = ?', (self.int_arg(self.body(), 'id'), u['id'])).fetchone()
        if not p:
            raise ApiError(404, 'not_found', 'Опрос не найден')
        poll_close(p)
        self.send_json(200, {'poll': poll_json(db().execute('SELECT * FROM polls WHERE id = ?', (p['id'],)).fetchone(), 'teacher')})

    def polls(self):
        """Опросы для ученика: идущие у его учителей и недавно закрытые, в которых он участвовал (чтобы увидеть итог)."""
        u = self.current_user()
        tids = my_teachers(u['id'])
        if not tids:
            return self.send_json(200, {'polls': [], 'teachers': 0, 'now': int(time.time())})
        polls_expire(tids)
        now, q = int(time.time()), ','.join('?' * len(tids))
        rows = db().execute(f'SELECT p.*, v.choice AS mine, t.name AS teacher FROM polls p JOIN users t ON t.id = p.teacher_id '
                            f'LEFT JOIN poll_votes v ON v.poll_id = p.id AND v.user_id = ? '
                            f'WHERE p.teacher_id IN ({q}) AND (p.closed IS NULL OR (p.closed > ? AND v.choice IS NOT NULL)) ORDER BY p.id DESC LIMIT 5',
                            (u['id'], *tids, now - POLL_SHOW)).fetchall()
        self.send_json(200, {'polls': [poll_json(p, 'student', p['mine']) | {'teacher': p['teacher']} for p in rows], 'teachers': len(tids), 'now': now})

    def poll_vote(self):
        u = self.current_user()
        d = self.body()
        p = db().execute('SELECT * FROM polls WHERE id = ?', (self.int_arg(d, 'id'),)).fetchone()
        if not p or p['teacher_id'] not in my_teachers(u['id']):
            raise ApiError(404, 'not_found', 'Опрос не найден')
        polls_expire([p['teacher_id']])
        p = db().execute('SELECT * FROM polls WHERE id = ?', (p['id'],)).fetchone()
        if p['closed'] is not None:
            raise ApiError(400, 'closed', 'Опрос уже закрыт')
        choice = self.int_arg(d, 'choice')
        if not 0 <= choice < len(json.loads(p['options'])):
            raise ApiError(400, 'bad_choice', 'Нет такого варианта')
        if not db().execute('INSERT OR IGNORE INTO poll_votes VALUES (?,?,?,?)', (p['id'], u['id'], choice, int(time.time()))).rowcount:
            raise ApiError(400, 'voted', 'Вы уже ответили')
        gain = 0
        if p['correct'] < 0 and p['reward']:
            poll_award(p, u['id']); gain = p['reward']
        self.send_json(200, {'poll': poll_json(p, 'student', choice), 'gain': gain})

    # --- ученик: группы и домашние задания
    def my_groups(self):
        u = self.current_user()
        rows = db().execute('SELECT g.id, g.name, t.name AS teacher, m.joined FROM group_members m '
                            'JOIN study_groups g ON g.id = m.group_id JOIN users t ON t.id = g.teacher_id '
                            'WHERE m.user_id = ? ORDER BY m.joined', (u['id'],)).fetchall()
        self.send_json(200, {'groups': [dict(r) for r in rows]})

    def my_motivation(self):
        """Главная ученика: достижения с прогрессом, цели его групп на неделю и правила бонуса за задания."""
        u = self.current_user()
        data, _ = load_progress(u['id'])
        ach, new = achievements(u['id'], data)
        goals = []
        for r in db().execute('SELECT g.id, g.name FROM group_members m JOIN study_groups g ON g.id = m.group_id WHERE m.user_id = ? ORDER BY m.joined',
                              (u['id'],)).fetchall():
            goal, _ = group_goal(r['id'])
            goals.append(goal_public(goal, u['id']) | {'name': r['name']})
        self.send_json(200, {'achievements': ach, 'new': new, 'goals': goals, 'now': int(time.time()),
                             'hw_bonus': HW_BONUS, 'hw_early': HW_EARLY_BONUS, 'goal_per_student': GOAL_PER_STUDENT})

    def my_rating(self):
        """Рейтинг одной из групп ученика (по умолчанию — первой, где учитель его открыл)."""
        u = self.current_user()
        groups = [dict(r) for r in db().execute('SELECT g.id, g.name, g.rating_open, t.name AS teacher FROM group_members m '
                                                'JOIN study_groups g ON g.id = m.group_id JOIN users t ON t.id = g.teacher_id '
                                                'WHERE m.user_id = ? ORDER BY m.joined', (u['id'],))]
        open_ = [g for g in groups if g['rating_open']]
        gid = self.query.get('group')
        if gid is None:
            g = open_[0] if open_ else None
        else:
            g = next((x for x in open_ if str(x['id']) == gid), None)
            if not g:
                raise ApiError(404, 'not_found', 'Рейтинг этой группы недоступен')
        self.send_json(200, {'groups': [{k: x[k] for k in ('id', 'name', 'teacher', 'rating_open')} for x in groups],
                             'group': g and g['id'], 'rows': group_rating(g['id']) if g else [], 'me': u['id'],
                             'goal': goal_public(group_goal(g['id'])[0], u['id']) if g else None,
                             'days': RATING_DAYS, 'min_tries': RATING_MIN_TRIES})

    def join_group(self):
        u = self.current_user()
        key = f'join:{u["id"]}'
        if too_many(key, 10, 3600):
            raise ApiError(429, 'rate_limited', 'Слишком много попыток. Попробуйте через час')
        code = re.sub(r'[\s-]', '', str(self.body().get('code', ''))).upper()
        g = db().execute('SELECT * FROM study_groups WHERE code = ?', (code,)).fetchone() if code else None
        if not g:
            hit(key)
            raise ApiError(404, 'bad_code', 'Группа с таким кодом не найдена — проверьте код у учителя')
        if g['teacher_id'] == u['id']:
            raise ApiError(400, 'own_group', 'Это ваша собственная группа')
        # бесплатный тариф преподавателя — до 5 учеников во всех его группах (кто уже учится у него, проходит)
        t = db().execute('SELECT * FROM users WHERE id = ?', (g['teacher_id'],)).fetchone()
        already = db().execute('SELECT 1 FROM group_members m JOIN study_groups g ON g.id = m.group_id WHERE g.teacher_id = ? AND m.user_id = ?',
                               (g['teacher_id'], u['id'])).fetchone()
        if t and not already and not plan_of(t)['active'] and teacher_usage(t['id'])['students'] >= FREE_LIMITS['students']:
            raise ApiError(403, 'plan_limit', f'В группах этого преподавателя уже {FREE_LIMITS["students"]} учеников — '
                                              'больше на бесплатном тарифе нельзя. Сообщите преподавателю')
        if db().execute('INSERT OR IGNORE INTO group_members VALUES (?,?,?)', (g['id'], u['id'], int(time.time()))).rowcount:
            tg_teacher(g['teacher_id'], 'join', f'👋 Новый ученик в группе «{tg_esc(g["name"])}»: <b>{tg_esc(u["name"])}</b>')
        data, _ = load_progress(u['id'])
        record_homework_done(u['id'], data)       # уже выполненное засчитываем сразу
        self.send_json(200, {'group': {'id': g['id'], 'name': g['name']}})

    def leave_group(self):
        u = self.current_user()
        gid = self.int_arg(self.body(), 'id')
        db().execute('DELETE FROM group_members WHERE group_id = ? AND user_id = ?', (gid, u['id']))
        self.send_json(200, {'ok': True})

    def my_homework(self):
        u = self.current_user()
        done = {r['hw_id']: r['done_at'] for r in db().execute('SELECT * FROM homework_done WHERE user_id = ?', (u['id'],))}
        out = []
        for h in assigned_homework(u['id']):
            j = hw_json(h); del j['students']
            j.update(group=h['group_name'], teacher=h['teacher_name'], done_at=done.get(h['id']))
            out.append(j)
        self.send_json(200, {'homework': out})

    # --- учитель
    @staticmethod
    def int_arg(d, key):
        try:
            return int(d.get(key))
        except (TypeError, ValueError):
            raise ApiError(400, 'bad_request', 'Некорректный запрос')

    @staticmethod
    def visible_problems(u):
        """Условие и параметры SQL: задачи, которые видит пользователь u (None — гость)."""
        if u is None:
            return '0', ()
        if u['role'] == 'admin':
            return '(p.hidden = 0 OR p.builtin = 1)', ()
        if u['role'] == 'student':
            # ученик видит задачи, выданные ему в ДЗ (правки встроенных — тоже только для них),
            # и банк учителей групп, где банк открыт
            where, args = ['((p.builtin = 1 OR p.hidden = 0) AND p.id IN (SELECT value FROM json_each(?)))'], [json.dumps(sorted(student_bank_ids(u['id'])))]
            for t in open_bank_teachers(u['id']):
                w, a = Handler.teacher_bank_where(t)
                where.append(w)
                args += a
            return '(' + ' OR '.join(where) + ')', tuple(args)
        # учитель: свои задачи; задачи из выданных им ДЗ; общий банк и открытые задачи коллег — только по предметам,
        # отмеченным в «Материалах», и только то, что администратор не снял с публикации
        w, a = Handler.teacher_bank_where(u)
        return f"(p.id IN (SELECT value FROM json_each(?)) OR {w})", (json.dumps(sorted(teacher_assigned_ids(u['id']))), *a)

    @staticmethod
    def teacher_bank_where(u):
        """Банк преподавателя без выданных ДЗ: свои задачи, общий банк и открытые задачи коллег по его предметам."""
        off, subj_off = bank_rules()
        subs = sorted(set(json.loads(u['subjects'] or '[]')) - subj_off)
        subj = f"(CASE WHEN p.task > 0 THEN '{EGE_SUBJECT}' ELSE p.subject END)"
        return (f"((p.author_id = ? AND p.hidden = 0) "
                f"OR (p.builtin = 1 AND {subj} IN (SELECT value FROM json_each(?)) AND p.id NOT IN (SELECT value FROM json_each(?))) "
                f"OR (p.hidden = 0 AND p.vis IN ('platform', 'public') AND {subj} IN (SELECT value FROM json_each(?)) "
                f"AND p.id NOT IN (SELECT value FROM json_each(?))))",
                (u['id'], json.dumps(subs), json.dumps(sorted(off)), json.dumps(subs), json.dumps(sorted(off))))

    def teacher(self):
        u = self.current_user()
        if u['role'] not in ('teacher', 'admin'):
            raise ApiError(403, 'forbidden', 'Раздел доступен только учителям')
        return u

    def own_group(self, u, gid):
        g = db().execute('SELECT * FROM study_groups WHERE id = ?', (gid,)).fetchone()
        if not g or (g['teacher_id'] != u['id'] and u['role'] != 'admin'):
            raise ApiError(404, 'not_found', 'Группа не найдена')
        return g

    @staticmethod
    def group_name(d):
        name = re.sub(r'\s+', ' ', str(d.get('name', ''))).strip()
        if not 1 <= len(name) <= 60:
            raise ApiError(400, 'bad_name', 'Название группы — от 1 до 60 символов')
        return name

    def t_groups(self):
        u = self.teacher()
        mine = '' if u['role'] == 'admin' and self.query.get('all') == '1' else 'WHERE g.teacher_id = ?'
        rows = db().execute('SELECT g.id, g.name, g.code, g.created, g.teacher_id, t.name AS teacher, '
                            '(SELECT COUNT(*) FROM group_members m WHERE m.group_id = g.id) AS members, '
                            '(SELECT COUNT(*) FROM homework h WHERE h.group_id = g.id) AS homework '
                            f'FROM study_groups g JOIN users t ON t.id = g.teacher_id {mine} ORDER BY g.created DESC',
                            (u['id'],) if mine else ()).fetchall()
        self.send_json(200, {'groups': [dict(r) for r in rows]})

    def t_group_create(self):
        u = self.teacher()
        name = self.group_name(self.body())
        if db().execute('SELECT COUNT(*) FROM study_groups WHERE teacher_id = ?', (u['id'],)).fetchone()[0] >= 200:
            raise ApiError(400, 'too_many', 'Слишком много групп')
        plan_limit(u, 'groups')
        cur = db().execute('INSERT INTO study_groups (teacher_id, name, code, created) VALUES (?,?,?,?)',
                           (u['id'], name, new_group_code(), int(time.time())))
        self.send_json(201, {'group': dict(db().execute('SELECT * FROM study_groups WHERE id = ?', (cur.lastrowid,)).fetchone())})

    def t_group_update(self):
        u = self.teacher()
        d = self.body()
        g = self.own_group(u, self.int_arg(d, 'id'))
        if 'name' in d:
            db().execute('UPDATE study_groups SET name = ? WHERE id = ?', (self.group_name(d), g['id']))
        if d.get('new_code'):
            db().execute('UPDATE study_groups SET code = ? WHERE id = ?', (new_group_code(), g['id']))
        if 'bank_open' in d:
            db().execute('UPDATE study_groups SET bank_open = ? WHERE id = ?', (1 if d['bank_open'] else 0, g['id']))
        if 'rating_open' in d:
            db().execute('UPDATE study_groups SET rating_open = ? WHERE id = ?', (1 if d['rating_open'] else 0, g['id']))
        self.send_json(200, {'group': dict(db().execute('SELECT * FROM study_groups WHERE id = ?', (g['id'],)).fetchone())})

    def t_group_delete(self):
        u = self.teacher()
        g = self.own_group(u, self.int_arg(self.body(), 'id'))
        db().execute('DELETE FROM study_groups WHERE id = ?', (g['id'],))
        self.send_json(200, {'ok': True})

    def t_group_remove(self):
        u = self.teacher()
        d = self.body()
        g = self.own_group(u, self.int_arg(d, 'group_id'))
        db().execute('DELETE FROM group_members WHERE group_id = ? AND user_id = ?', (g['id'], self.int_arg(d, 'user_id')))
        self.send_json(200, {'ok': True})

    def hw_status(self, hws, members):
        """Статус каждого ДЗ у каждого адресата: {hw_id: {user_id: [сделано, всего, done_at]}}."""
        ids = [h['id'] for h in hws]
        done = {}
        if ids:
            for r in db().execute(f'SELECT * FROM homework_done WHERE hw_id IN ({",".join("?" * len(ids))})', ids):
                done[(r['hw_id'], r['user_id'])] = r['done_at']
        out = {}
        for h in hws:
            items, to = json.loads(h['items']), json.loads(h['students'])
            st = out[h['id']] = {}
            for uid, sets in members.items():
                if to and uid not in to:
                    continue
                d, t = hw_progress(items, sets)
                st[uid] = [d, t, done.get((h['id'], uid))]
        return out

    def t_group(self):
        u = self.teacher()
        g = self.own_group(u, self.int_arg(self.query, 'id'))
        rows = db().execute('SELECT u.id, u.name, u.email, m.joined FROM group_members m JOIN users u ON u.id = m.user_id '
                            'WHERE m.group_id = ? ORDER BY u.name COLLATE NOCASE', (g['id'],)).fetchall()
        members, sets = [], {}
        for r in rows:
            data, updated = load_progress(r['id'])
            sets[r['id']] = progress_sets(data)
            members.append(dict(r, stats=summary(data, updated, r['id']), look=look_of(r['id'])))
        hws = db().execute('SELECT * FROM homework WHERE group_id = ? ORDER BY COALESCE(due, created + 315360000) DESC, id DESC',
                           (g['id'],)).fetchall()
        status = self.hw_status(hws, sets)
        teacher = db().execute('SELECT name FROM users WHERE id = ?', (g['teacher_id'],)).fetchone()['name']
        self.send_json(200, {'group': dict(g, teacher=teacher), 'members': members, 'rating': group_rating(g['id']), 'goal': goal_public(group_goal(g['id'])[0]),
                             'homework': [dict(hw_json(h), status=status[h['id']]) for h in hws]})

    def t_student(self):
        u = self.teacher()
        sid = self.int_arg(self.query, 'id')
        own = '' if u['role'] == 'admin' else 'AND g.teacher_id = ?'
        groups = db().execute('SELECT g.id, g.name FROM study_groups g JOIN group_members m ON m.group_id = g.id '
                              f'WHERE m.user_id = ? {own} ORDER BY g.name', (sid,) + (() if u['role'] == 'admin' else (u['id'],))).fetchall()
        st = db().execute('SELECT id, name, email, created FROM users WHERE id = ?', (sid,)).fetchone()
        if not st or (not groups and u['role'] != 'admin'):
            raise ApiError(404, 'not_found', 'Ученик не найден в ваших группах')
        data, updated = load_progress(sid)
        gids = [g['id'] for g in groups]
        hws = db().execute(f'SELECT * FROM homework WHERE group_id IN ({",".join("?" * len(gids))}) ORDER BY COALESCE(due, created + 315360000) DESC',
                           gids).fetchall() if gids else []
        hws = [h for h in hws if not json.loads(h['students']) or sid in json.loads(h['students'])]
        status = self.hw_status(hws, {sid: progress_sets(data)})
        self.send_json(200, {'student': dict(st), 'groups': [dict(g) for g in groups], 'progress': data,
                             'stats': summary(data, updated, sid), 'look': look_of(sid),
                             'homework': [dict(hw_json(h), status=status[h['id']].get(sid)) for h in hws]})

    def t_hw_save(self):
        u = self.teacher()
        d = self.body()
        if d.get('id'):
            h = db().execute('SELECT * FROM homework WHERE id = ?', (self.int_arg(d, 'id'),)).fetchone()
            if not h:
                raise ApiError(404, 'not_found', 'Задание не найдено')
            g = self.own_group(u, h['group_id'])
        else:
            h, g = None, self.own_group(u, self.int_arg(d, 'group_id'))
        title = re.sub(r'\s+', ' ', str(d.get('title', ''))).strip()
        if not 1 <= len(title) <= 120:
            raise ApiError(400, 'bad_title', 'Название — от 1 до 120 символов')
        comment = str(d.get('comment', '')).strip()
        if len(comment) > 2000:
            raise ApiError(400, 'bad_comment', 'Комментарий — до 2000 символов')
        raw = d.get('items') if isinstance(d.get('items'), dict) else {}
        bank = list(dict.fromkeys(str(x) for x in raw.get('bank', []) if BANK_ID_RE.match(str(x))))[:200] if isinstance(raw.get('bank'), list) else []
        py = sorted(x for x in _ints(raw.get('py')) if 1 <= x <= 500)
        ege = sorted(x for x in _ints(raw.get('ege')) if 1 <= x <= 27)
        mat = sorted(x for x in _ints(raw.get('mat')) if x > 0)[:100]
        if not (bank or py or ege or mat):
            raise ApiError(400, 'empty', 'Добавьте в задание хотя бы одну задачу или тему')
        if mat:
            # выдать можно свой материал (администратор — любой); уже выданный остаётся, даже если его потом удалили
            had = set(json.loads(h['items']).get('mat', [])) if h else set()
            own = {r['id'] for r in db().execute('SELECT id FROM materials WHERE hidden = 0 AND id IN (SELECT value FROM json_each(?))'
                                                 + ('' if u['role'] == 'admin' else ' AND author_id = ?'),
                                                 (json.dumps(mat),) + (() if u['role'] == 'admin' else (u['id'],)))}
            if [x for x in mat if x not in own and x not in had]:
                raise ApiError(400, 'bad_material', 'Можно выдать только свои материалы')
        custom = [x for x in bank if x.startswith('u')]
        if custom:
            # номера задач идут подряд — без проверки можно было бы выдать чужую закрытую задачу, угадав её id
            had = set(json.loads(h['items']).get('bank', [])) if h else set()
            where, args = self.visible_problems(u)
            ok = {r['id'] for r in db().execute(f'SELECT p.id FROM problems p WHERE p.id IN (SELECT value FROM json_each(?)) AND {where}',
                                                (json.dumps(custom), *args))}
            bad = [x for x in custom if x not in ok and x not in had]
            if bad:
                raise ApiError(400, 'bad_problem', 'Некоторые задачи недоступны: ' + ', '.join('#' + x[1:] for x in bad[:5]))
        due = d.get('due')
        if due is not None:
            due = self.int_arg(d, 'due')
            if not 1_600_000_000 < due < 4_000_000_000:
                raise ApiError(400, 'bad_due', 'Некорректный срок сдачи')
        member_ids = {r['user_id'] for r in db().execute('SELECT user_id FROM group_members WHERE group_id = ?', (g['id'],))}
        students = sorted(x for x in _ints(d.get('students')) if x in member_ids)
        items = json.dumps({'bank': bank, 'py': py, 'ege': ege, **({'mat': mat} if mat else {})})
        now = int(time.time())
        if h:
            db().execute('UPDATE homework SET title=?, comment=?, items=?, students=?, due=?, updated=? WHERE id=?',
                         (title, comment, items, json.dumps(students), due, now, h['id']))
            hid = h['id']
        else:
            hid = db().execute('INSERT INTO homework (group_id, title, comment, items, students, due, created, updated) VALUES (?,?,?,?,?,?,?,?)',
                               (g['id'], title, comment, items, json.dumps(students), due, now, now)).lastrowid
        # состав изменился — пересчитываем, кто уже всё сделал
        if h and h['items'] != items:
            db().execute('DELETE FROM homework_done WHERE hw_id = ?', (hid,))
        for uid in (students or member_ids):
            data, _ = load_progress(uid)
            dn, tt = hw_progress(json.loads(items), progress_sets(data))
            if tt and dn == tt:
                db().execute('INSERT OR IGNORE INTO homework_done VALUES (?,?,?)', (hid, uid, now))
        self.send_json(200 if h else 201, {'homework': hw_json(db().execute('SELECT * FROM homework WHERE id = ?', (hid,)).fetchone())})

    def t_hw_stats(self):
        """Подробно по одному ДЗ: каждый адресат × каждый пункт, для задач — попытки и верные ответы."""
        u = self.teacher()
        h = db().execute('SELECT * FROM homework WHERE id = ?', (self.int_arg(self.query, 'id'),)).fetchone()
        if not h:
            raise ApiError(404, 'not_found', 'Задание не найдено')
        g = self.own_group(u, h['group_id'])
        items, to = json.loads(h['items']), json.loads(h['students'])
        rows = db().execute('SELECT u.id, u.name FROM group_members m JOIN users u ON u.id = m.user_id '
                            'WHERE m.group_id = ? ORDER BY u.name COLLATE NOCASE', (g['id'],)).fetchall()
        done = {r['user_id']: r['done_at'] for r in db().execute('SELECT * FROM homework_done WHERE hw_id = ?', (h['id'],))}
        students = []
        for r in rows:
            if to and r['id'] not in to:
                continue
            data, updated = load_progress(r['id'])
            sets = progress_sets(data)
            att = data.get('att') if isinstance(data.get('att'), dict) else {}
            bank = {}
            for pid in items.get('bank', []):
                a = att.get(pid) if isinstance(att.get(pid), dict) else {}
                # [решена, попыток, верных, когда впервые решена (мс)]
                bank[pid] = [pid in sets['bank'], int(a.get('n') or 0), int(a.get('c') or 0), int(a.get('ok') or 0)]
            d, t = hw_progress(items, sets)
            students.append({'id': r['id'], 'name': r['name'], 'done_at': done.get(r['id']), 'updated': updated, 'done': d, 'total': t,
                             'bank': bank, 'py': [x for x in items.get('py', []) if x in sets['py']],
                             'ege': [x for x in items.get('ege', []) if x in sets['ege']],
                             'mat': [x for x in items.get('mat', []) if x in sets['mat']]})
        self.send_json(200, {'homework': hw_json(h), 'group': {'id': g['id'], 'name': g['name']}, 'students': students})

    def t_hw_delete(self):
        u = self.teacher()
        h = db().execute('SELECT * FROM homework WHERE id = ?', (self.int_arg(self.body(), 'id'),)).fetchone()
        if not h:
            raise ApiError(404, 'not_found', 'Задание не найдено')
        self.own_group(u, h['group_id'])
        db().execute('DELETE FROM homework WHERE id = ?', (h['id'],))
        self.send_json(200, {'ok': True})

    # --- редактор: общий банк задач, методичка, картинки
    def content(self):
        if not self.current_user(required=False):
            # гостю — только правки учебника Python и карточек заданий: задачи и разборы закрыты
            lessons = {'ege': {}, 'py': {}}
            for r in db().execute('SELECT kind, key, data, updated FROM lessons'):
                d = json.loads(r['data'])
                if r['kind'] == 'ege':
                    d = {k: d[k] for k in CARD_FIELDS if k in d}
                lessons[r['kind']][str(r['key'])] = dict(d, updated=r['updated'])
            v = max([x['updated'] for k in lessons for x in lessons[k].values()] + [0])
            return self.send_json(200, {'v': v, 'problems': [], 'lessons': lessons})
        where, args = self.visible_problems(self.current_user(required=False))
        rows = db().execute('SELECT p.*, u.name AS author FROM problems p LEFT JOIN users u ON u.id = p.author_id '
                            f'WHERE {where} ORDER BY p.task, p.num', args).fetchall()
        problems = [{k: r[k] for k in ('id', 'num', 'task', 'level', 'title', 'body', 'answer', 'solution', 'note', 'data',
                                       'dname', 'author', 'author_id', 'updated', 'subject', 'topic', 'snum', 'vis')}
                    | {'keep_extra': bool(r['keep_extra']), 'builtin': bool(r['builtin']), 'hidden': bool(r['hidden'])} for r in rows]
        lessons = {'ege': {}, 'py': {}}
        for r in db().execute('SELECT kind, key, data, updated FROM lessons'):
            lessons[r['kind']][str(r['key'])] = dict(json.loads(r['data']), updated=r['updated'])
        v = max([p['updated'] for p in problems] + [x['updated'] for k in lessons for x in lessons[k].values()] + [0])
        self.send_json(200, {'v': v, 'problems': problems, 'lessons': lessons})

    @staticmethod
    def text_field(d, key, lo, hi, label, strip=True):
        v = str(d.get(key, '') or '')
        v = v.strip() if strip else v
        if not lo <= len(v) <= hi:
            raise ApiError(400, 'bad_' + key, f'{label}: от {lo} до {hi} символов' if lo else f'{label}: не больше {hi} символов')
        return v

    def c_problem_save(self):
        u = self.teacher()
        d = self.body(MAX_CONTENT_BODY)
        try:
            task = int(d.get('task') or 0)
        except (TypeError, ValueError):
            task = -1
        if not 0 <= task <= 27:
            raise ApiError(400, 'bad_task', 'Номер задания ЕГЭ — от 1 до 27')
        # task = 0 — задача не из ЕГЭ по информатике: тогда нужен предмет
        subject = '' if task else re.sub(r'\s+', ' ', self.text_field(d, 'subject', 1, 60, 'Предмет'))
        topic = '' if task else re.sub(r'\s+', ' ', self.text_field(d, 'topic', 0, 80, 'Тема'))
        try:
            snum = 0 if task else int(d.get('snum') or 0)
        except (TypeError, ValueError):
            snum = -1
        if not 0 <= snum <= 99:
            raise ApiError(400, 'bad_snum', 'Номер задания — от 1 до 99')
        vis = str(d.get('vis') or ('platform' if u['role'] == 'admin' else 'private'))
        if vis not in (('platform', 'public', 'private') if u['role'] == 'admin' else ('public', 'private')):
            raise ApiError(400, 'bad_vis', 'Некорректная видимость задачи')
        level = str(d.get('level', ''))
        if level not in ('Б', 'П', 'В'):
            raise ApiError(400, 'bad_level', 'Укажите сложность')
        f = {'task': task, 'subject': subject, 'topic': topic, 'snum': snum, 'vis': vis, 'level': level,
             'title': re.sub(r'\s+', ' ', self.text_field(d, 'title', 1, 120, 'Название')),
             'body': self.text_field(d, 'body', 1, 20000, 'Условие'),
             'answer': self.text_field(d, 'answer', 1, 2000, 'Ответ'),
             'solution': self.text_field(d, 'solution', 0, 20000, 'Решение', strip=False).strip('\n'),
             'note': self.text_field(d, 'note', 0, 2000, 'Пояснение'),
             'data': self.text_field(d, 'data', 0, 600_000, 'Файл с данными', strip=False),
             'dname': self.text_field(d, 'dname', 0, 60, 'Имя файла'),
             'keep_extra': 1 if d.get('keep_extra') else 0}
        if f['data'] and not re.match(r'^[\w.-]{1,60}$', f['dname']):
            raise ApiError(400, 'bad_dname', 'Имя файла — латиница, цифры, точка, например 24.txt')
        if not f['data']:
            f['dname'] = ''
        plan_limit(u, 'storage', sum(len(str(v).encode()) for v in f.values()))
        check_ix(u, f['body'], f['solution'])
        now, pid = int(time.time()), str(d.get('id') or '')
        cols = ', '.join(f'{k} = ?' for k in f)
        if pid and not pid.startswith('u'):
            # правка встроенной задачи — только администратор; исходник остаётся в коде сайта
            if u['role'] != 'admin':
                raise ApiError(403, 'forbidden', 'Встроенные задачи меняет администратор — сделайте копию')
            if not BANK_ID_RE.match(pid):
                raise ApiError(400, 'bad_request', 'Некорректная задача')
            db().execute('INSERT INTO problems (id, author_id, task, level, title, body, answer, created, updated, builtin) '
                         'VALUES (?,?,?,?,?,?,?,?,?,1) ON CONFLICT(id) DO NOTHING', (pid, u['id'], task, level, f['title'], f['body'], f['answer'], now, now))
            db().execute(f'UPDATE problems SET {cols}, hidden = 0, updated = ? WHERE id = ?', (*f.values(), now, pid))
        elif pid:
            p = db().execute('SELECT * FROM problems WHERE id = ? AND hidden = 0', (pid,)).fetchone()
            if not p:
                raise ApiError(404, 'not_found', 'Задача не найдена')
            if p['author_id'] != u['id'] and u['role'] != 'admin':
                raise ApiError(403, 'forbidden', 'Это задача другого учителя — сделайте копию')
            db().execute(f'UPDATE problems SET {cols}, updated = ? WHERE id = ?', (*f.values(), now, pid))
        else:
            if db().execute('SELECT COUNT(*) FROM problems WHERE author_id = ? AND builtin = 0 AND created > ?',
                            (u['id'], now - 86400)).fetchone()[0] >= 300:
                raise ApiError(429, 'rate_limited', 'Слишком много новых задач за сутки')
            num = max(1000, db().execute('SELECT MAX(num) FROM problems').fetchone()[0] or 0) + 1
            pid = f'u{num}'
            db().execute(f'INSERT INTO problems (id, num, author_id, created, updated, {", ".join(f)}) VALUES (?,?,?,?,?,{",".join("?" * len(f))})',
                         (pid, num, u['id'], now, now, *f.values()))
        self.send_json(200, {'id': pid})

    def c_problem_delete(self):
        u = self.teacher()
        d = self.body()
        pid, now = str(d.get('id', '')), int(time.time())
        if not BANK_ID_RE.match(pid):
            raise ApiError(400, 'bad_request', 'Некорректная задача')
        if not pid.startswith('u'):
            if u['role'] != 'admin':
                raise ApiError(403, 'forbidden', 'Встроенные задачи меняет администратор')
            if d.get('restore'):          # вернуть исходный вариант из кода сайта
                db().execute('DELETE FROM problems WHERE id = ? AND builtin = 1', (pid,))
            else:                         # скрыть из банка
                db().execute("INSERT INTO problems (id, author_id, task, level, title, body, answer, builtin, hidden, created, updated) "
                             "VALUES (?,?,1,'Б','—','—','—',1,1,?,?) ON CONFLICT(id) DO UPDATE SET hidden = 1, updated = excluded.updated",
                             (pid, u['id'], now, now))
        else:
            p = db().execute('SELECT * FROM problems WHERE id = ?', (pid,)).fetchone()
            if not p:
                raise ApiError(404, 'not_found', 'Задача не найдена')
            if p['author_id'] != u['id'] and u['role'] != 'admin':
                raise ApiError(403, 'forbidden', 'Это задача другого учителя')
            # не удаляем насовсем: на задачу могут ссылаться выданные ДЗ, номер не переиспользуется
            db().execute('UPDATE problems SET hidden = 1, updated = ? WHERE id = ?', (now, pid))
        self.send_json(200, {'ok': True})

    LESSON_FIELDS = {
        'ege': {'title': 120, 'short': 120, 'lead': 2000, 'level': 1, 'time': 3, 'tool': 120, 'theory': 30000, 'tip': 2000,
                'types': 6000, 'formulas': 6000, 'steps': 6000, 'traps': 6000, 'code': 30000, 'py': 200},
        'py': {'title': 120, 'text': 30000, 'code': 30000, 'out': 6000, 'note': 2000, 'ege': 200},
    }

    def c_lesson_save(self):
        u = self.admin()
        d = self.body(MAX_CONTENT_BODY)
        kind, key = str(d.get('kind', '')), self.int_arg(d, 'key')
        if kind not in self.LESSON_FIELDS or not (1 <= key <= (27 if kind == 'ege' else 500)):
            raise ApiError(400, 'bad_request', 'Некорректный раздел')
        raw = d.get('data') if isinstance(d.get('data'), dict) else {}
        data = {}
        for k, hi in self.LESSON_FIELDS[kind].items():
            if k not in raw:
                continue
            v = raw[k]
            # списки строк и блоки кода приходят как JSON-структуры — проверяем общий размер
            size = len(json.dumps(v, ensure_ascii=False))
            if size > hi + 200 or not isinstance(v, (str, int, list)):
                raise ApiError(400, 'bad_' + k, f'Поле «{k}» слишком большое')
            data[k] = v
        if not str(data.get('title', 'x')).strip():
            raise ApiError(400, 'bad_title', 'Название не может быть пустым')
        db().execute('INSERT INTO lessons VALUES (?,?,?,?,?) ON CONFLICT(kind, key) DO UPDATE SET data = excluded.data, '
                     'author_id = excluded.author_id, updated = excluded.updated',
                     (kind, key, json.dumps(data, ensure_ascii=False), u['id'], int(time.time())))
        self.send_json(200, {'ok': True})

    def c_lesson_reset(self):
        self.admin()
        d = self.body()
        db().execute('DELETE FROM lessons WHERE kind = ? AND key = ?', (str(d.get('kind', '')), self.int_arg(d, 'key')))
        self.send_json(200, {'ok': True})

    def c_media_upload(self):
        u = self.teacher()
        key = f'media:{u["id"]}'
        if too_many(key, 120, 3600):
            raise ApiError(429, 'rate_limited', 'Слишком много картинок за час')
        d = self.body(MAX_CONTENT_BODY)
        kind = str(d.get('type', ''))
        try:
            raw = base64.b64decode(str(d.get('data', '')), validate=True)
        except ValueError:
            raw = b''
        # только растровые картинки и только если содержимое совпадает с типом (SVG не принимаем — в нём может быть скрипт)
        if kind not in IMAGE_TYPES or not raw.startswith(IMAGE_TYPES[kind]) or (kind == 'image/webp' and raw[8:12] != b'WEBP'):
            raise ApiError(400, 'bad_image', 'Поддерживаются картинки PNG, JPEG, WebP и GIF')
        if len(raw) > MAX_IMAGE:
            raise ApiError(413, 'too_large', 'Картинка больше 1,5 МБ — уменьшите её')
        plan_limit(u, 'storage', len(raw))
        hit(key)
        mid = secrets.token_urlsafe(12)
        db().execute('INSERT INTO media VALUES (?,?,?,?,?)', (mid, u['id'], kind, raw, int(time.time())))
        self.send_json(201, {'id': mid})

    # --- свои материалы учителей
    def materials(self):
        """Материалы, которые видит пользователь: учитель — свои, администратор — все,
        ученик — открытые его учителями (shared) и выданные ему в ДЗ."""
        u = self.current_user()
        if u['role'] == 'admin':
            where, args = 'm.hidden = 0', ()
        elif u['role'] == 'teacher':
            where, args = 'm.hidden = 0 AND m.author_id = ?', (u['id'],)
        else:
            assigned = set()
            for h in assigned_homework(u['id']):
                assigned.update(json.loads(h['items']).get('mat', []))
            where = ('m.hidden = 0 AND ((m.shared = 1 AND m.author_id IN (SELECT g.teacher_id FROM group_members gm '
                     'JOIN study_groups g ON g.id = gm.group_id WHERE gm.user_id = ?)) OR m.id IN (SELECT value FROM json_each(?)))')
            args = (u['id'], json.dumps(sorted(assigned)))
        rows = db().execute('SELECT m.id, m.subject, m.title, m.body, m.shared, m.author_id, m.updated, a.name AS author '
                            f'FROM materials m LEFT JOIN users a ON a.id = m.author_id WHERE {where} ORDER BY m.updated DESC', args)
        self.send_json(200, {'materials': [dict(r, shared=bool(r['shared'])) for r in rows]})

    def own_material(self, u, mid):
        m = db().execute('SELECT * FROM materials WHERE id = ? AND hidden = 0', (mid,)).fetchone()
        if not m:
            raise ApiError(404, 'not_found', 'Материал не найден')
        if m['author_id'] != u['id'] and u['role'] != 'admin':
            raise ApiError(403, 'forbidden', 'Это материал другого учителя')
        return m

    def material_save(self):
        u = self.teacher()
        d = self.body(MAX_CONTENT_BODY)
        f = {'title': re.sub(r'\s+', ' ', self.text_field(d, 'title', 1, 120, 'Название')),
             'subject': re.sub(r'\s+', ' ', self.text_field(d, 'subject', 0, 60, 'Предмет')),
             'body': self.text_field(d, 'body', 0, 60000, 'Текст', strip=False).strip(),
             'shared': 1 if d.get('shared') else 0}
        plan_limit(u, 'storage', len((f['title'] + f['subject'] + f['body']).encode()))
        check_ix(u, f['body'])
        now = int(time.time())
        if d.get('id'):
            mid = self.own_material(u, self.int_arg(d, 'id'))['id']
            db().execute('UPDATE materials SET title = ?, subject = ?, body = ?, shared = ?, updated = ? WHERE id = ?', (*f.values(), now, mid))
        else:
            if db().execute('SELECT COUNT(*) FROM materials WHERE author_id = ? AND created > ?', (u['id'], now - 86400)).fetchone()[0] >= 200:
                raise ApiError(429, 'rate_limited', 'Слишком много новых материалов за сутки')
            mid = db().execute('INSERT INTO materials (author_id, title, subject, body, shared, created, updated) VALUES (?,?,?,?,?,?,?)',
                               (u['id'], *f.values(), now, now)).lastrowid
        self.send_json(200, {'id': mid})

    def material_delete(self):
        u = self.teacher()
        m = self.own_material(u, self.int_arg(self.body(), 'id'))
        # не стираем: на материал могут ссылаться выданные ДЗ
        db().execute('UPDATE materials SET hidden = 1, updated = ? WHERE id = ?', (int(time.time()), m['id']))
        self.send_json(200, {'ok': True})

    def media(self, mid):
        r = db().execute('SELECT type, data FROM media WHERE id = ?', (mid,)).fetchone()
        if not r:
            raise ApiError(404, 'not_found', 'Картинка не найдена')
        self.send_response(200)
        self.send_header('Content-Type', r['type'])
        self.send_header('Content-Length', str(len(r['data'])))
        self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'none'; sandbox")
        self.end_headers()
        self.wfile.write(r['data'])

    # --- посещаемость
    def page_hit(self):
        d = self.body(4096)
        ua, ip, now = self.headers.get('User-Agent') or '', self.client_ip(), int(time.time())
        m = PAGE_RE.match(str(d.get('p', '')))
        if not m or m[1] not in METRIC_PAGES or (m[2] and m[1] not in ('ege', 'bank')) or BOT_RE.search(ua) or not ua:
            return self.send_json(200, {'ok': False})
        if too_many('hit:' + ip, 600, 60):     # класс за одним NAT — это десятки учеников с одного адреса
            return self.send_json(200, {'ok': False})
        hit('hit:' + ip)
        entry = 1 if d.get('e') else 0
        ref = str(d.get('r', '')).strip().lower()[:200] if entry else ''
        ref = ref[4:] if ref.startswith('www.') else ref
        if not HOST_RE.match(ref) or ORIGIN.endswith('//' + ref):
            ref = ''
        day = metric_day(now)
        vid = hashlib.sha256(f'{day_salt(day)}|{ip}|{ua}'.encode()).hexdigest()[:20]
        u = self.current_user(required=False)
        db().execute('INSERT INTO hits VALUES (?,?,?,?,?,?,?,?)', (now, day, vid, u['id'] if u else None, m[0], entry, ref,
                                                                   'mobile' if MOBILE_RE.search(ua) else 'desktop'))
        sweep_metrics(now)
        self.send_json(200, {'ok': True})

    def a_metrics(self):
        self.admin()
        try:
            days = int(self.query.get('days', 30))
        except ValueError:
            days = 30
        days = days if days in (7, 30, 90, 365) else 30
        now = int(time.time())
        today = metric_day(now)
        start = metric_day(day_start(today) - (days - 1) * 86400)
        prev = metric_day(day_start(start) - days * 86400)
        q = lambda sql, *a: db().execute(sql, a).fetchall()
        by_day = {r['day']: r for r in q('SELECT day, COUNT(*) AS views, SUM(entry) AS visits, COUNT(DISTINCT vid) AS visitors, '
                                          'COUNT(DISTINCT uid) AS users FROM hits WHERE day >= ? GROUP BY day', start)}
        regs = {}
        for r in q('SELECT created FROM users WHERE created >= ?', day_start(start)):
            regs[metric_day(r['created'])] = regs.get(metric_day(r['created']), 0) + 1
        series, t = [], day_start(start)
        while metric_day(t) <= today:
            dd, r = metric_day(t), by_day.get(metric_day(t))
            series.append({'day': dd, 'views': r['views'] if r else 0, 'visits': r['visits'] if r else 0,
                           'visitors': r['visitors'] if r else 0, 'users': r['users'] if r else 0, 'regs': regs.get(dd, 0)})
            t += 86400
        def totals(a, b):
            r = q('SELECT COUNT(*) AS views, COALESCE(SUM(entry), 0) AS visits, COUNT(DISTINCT uid) AS users, '
                  'COUNT(DISTINCT day || vid) AS visitor_days FROM hits WHERE day >= ? AND day < ?', a, b)[0]
            regs = q('SELECT COUNT(*) AS n FROM users WHERE created >= ? AND created < ?', day_start(a), day_start(b))[0]['n']
            return {**dict(r), 'regs': regs}
        end = metric_day(day_start(today) + 86400)
        self.send_json(200, {
            'days': days, 'today': today, 'series': series,
            'online': q('SELECT COUNT(DISTINCT vid) AS n FROM hits WHERE ts > ?', now - 300)[0]['n'],
            'total': totals(start, end), 'prev': totals(prev, start),
            'pages': [dict(r) for r in q('SELECT page, COUNT(*) AS views, COUNT(DISTINCT day || vid) AS visitors FROM hits '
                                         'WHERE day >= ? GROUP BY page ORDER BY views DESC LIMIT 15', start)],
            'refs': [dict(r) for r in q("SELECT ref, COUNT(*) AS visits FROM hits WHERE day >= ? AND entry = 1 AND ref != '' "
                                        'GROUP BY ref ORDER BY visits DESC LIMIT 10', start)],
            'direct': q("SELECT COUNT(*) AS n FROM hits WHERE day >= ? AND entry = 1 AND ref = ''", start)[0]['n'],
            'devices': {r['dev']: r['visits'] for r in q('SELECT dev, COUNT(*) AS visits FROM hits WHERE day >= ? AND entry = 1 '
                                                         'GROUP BY dev', start)},
            'users_total': q('SELECT COUNT(*) AS n FROM users')[0]['n'],
        })

    # --- администратор
    def admin(self):
        u = self.current_user()
        if u['role'] != 'admin':
            raise ApiError(403, 'forbidden', 'Раздел доступен только администратору')
        return u

    def a_overview(self):
        self.admin()
        now = int(time.time())
        week = now - 7 * 86400
        one = lambda sql, *a: db().execute(sql, a).fetchone()[0]
        roles = {r['role']: r['n'] for r in db().execute('SELECT role, COUNT(*) AS n FROM users GROUP BY role')}
        seen = {r['uid']: r['ts'] for r in db().execute('SELECT uid, MAX(ts) AS ts FROM hits WHERE uid IS NOT NULL GROUP BY uid')}
        # место: картинки, свои задачи (с файлами данных) и выданные задания — в байтах
        teachers = [dict(r) for r in db().execute(
            "SELECT u.id, u.name, u.email, u.role, u.subjects, u.created, u.plan, u.plan_until, "
            "(SELECT COUNT(*) FROM study_groups g WHERE g.teacher_id = u.id) AS groups, "
            "(SELECT COUNT(DISTINCT m.user_id) FROM group_members m JOIN study_groups g ON g.id = m.group_id WHERE g.teacher_id = u.id) AS students, "
            "(SELECT COUNT(*) FROM homework h JOIN study_groups g ON g.id = h.group_id WHERE g.teacher_id = u.id) AS homework, "
            "(SELECT COUNT(*) FROM problems p WHERE p.author_id = u.id AND p.builtin = 0 AND p.hidden = 0) AS problems, "
            "(SELECT COALESCE(SUM(length(data)), 0) FROM media WHERE owner_id = u.id) AS media_b, "
            "(SELECT COALESCE(SUM(length(CAST(title || body || answer || solution || note || data AS BLOB))), 0) "
            "  FROM problems p WHERE p.author_id = u.id AND p.builtin = 0) AS problems_b, "
            "(SELECT COALESCE(SUM(length(CAST(h.title || h.comment || h.items AS BLOB))), 0) "
            "  FROM homework h JOIN study_groups g ON g.id = h.group_id WHERE g.teacher_id = u.id) AS homework_b "
            "FROM users u WHERE u.role IN ('teacher', 'admin') ORDER BY u.created")]
        for t in teachers:
            t['subjects'] = json.loads(t['subjects'] or '[]')
            t['storage'] = t['media_b'] + t['problems_b'] + t['homework_b']
            t['seen'] = seen.get(t['id'])
            t['plan'] = plan_of(t)
        teachers.sort(key=lambda t: -t['storage'])
        students = roles.get('student', 0)
        recent = [dict(r) | {'seen': seen.get(r['id'])} for r in db().execute(
            "SELECT u.id, u.name, u.email, u.created, (SELECT COUNT(*) FROM group_members m WHERE m.user_id = u.id) AS groups "
            "FROM users u WHERE u.role = 'student' ORDER BY u.created DESC LIMIT 6")]
        self.send_json(200, {
            'users': {'teachers': roles.get('teacher', 0), 'admins': roles.get('admin', 0), 'students': students,
                      'new_week': one('SELECT COUNT(*) FROM users WHERE created >= ?', week),
                      'active_week': one('SELECT COUNT(DISTINCT uid) FROM hits WHERE uid IS NOT NULL AND ts >= ?', week)},
            'students': {'total': students,
                         'in_groups': one("SELECT COUNT(DISTINCT m.user_id) FROM group_members m JOIN users u ON u.id = m.user_id WHERE u.role = 'student'"),
                         'active_week': one("SELECT COUNT(DISTINCT h.uid) FROM hits h JOIN users u ON u.id = h.uid WHERE u.role = 'student' AND h.ts >= ?", week),
                         'recent': recent},
            'content': {'groups': one('SELECT COUNT(*) FROM study_groups'), 'homework': one('SELECT COUNT(*) FROM homework'),
                        'problems': one('SELECT COUNT(*) FROM problems WHERE builtin = 0 AND hidden = 0'),
                        'db_bytes': one('SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()')},
            'teachers': teachers})

    def a_users(self):
        self.admin()
        q = '%' + str(self.query.get('q', '')).strip().lower().replace('%', '').replace('_', '') + '%'
        rows = db().execute('SELECT u.id, u.name, u.email, u.role, u.created, u.plan, u.plan_until, p.updated, '
                            '(SELECT COUNT(*) FROM group_members m WHERE m.user_id = u.id) AS groups_in, '
                            '(SELECT COUNT(*) FROM study_groups g WHERE g.teacher_id = u.id) AS groups_own '
                            'FROM users u LEFT JOIN progress p ON p.user_id = u.id '
                            'WHERE lower(u.email) LIKE ? OR ulower(u.name) LIKE ? '
                            "ORDER BY CASE u.role WHEN 'admin' THEN 0 WHEN 'teacher' THEN 1 ELSE 2 END, u.created DESC LIMIT 300",
                            (q, q)).fetchall()
        total = db().execute('SELECT COUNT(*) FROM users').fetchone()[0]
        self.send_json(200, {'users': [dict(r, plan=plan_of(r) if r['role'] != 'student' else None) for r in rows], 'total': total})

    def a_role(self):
        me = self.admin()
        d = self.body()
        uid, role = self.int_arg(d, 'user_id'), str(d.get('role', ''))
        if role not in ROLES:
            raise ApiError(400, 'bad_role', 'Неизвестная роль')
        if uid == me['id']:
            raise ApiError(400, 'self', 'Свою роль менять нельзя — попросите другого администратора')
        if not db().execute('UPDATE users SET role = ? WHERE id = ?', (role, uid)).rowcount:
            raise ApiError(404, 'not_found', 'Пользователь не найден')
        if role == 'teacher':
            start_trial(uid)
        self.send_json(200, {'ok': True})

    def a_reset_link(self):
        """Ссылка для сброса пароля, которую администратор передаёт человеку сам (когда письмо не доходит).
        Действует сутки и один раз; ссылки для других администраторов не выдаются."""
        self.admin()
        u = db().execute('SELECT * FROM users WHERE id = ?', (self.int_arg(self.body(), 'user_id'),)).fetchone()
        if not u:
            raise ApiError(404, 'not_found', 'Пользователь не найден')
        if u['role'] == 'admin':
            raise ApiError(403, 'forbidden', 'Администратор восстанавливает пароль сам — через «Забыли пароль?»')
        base = ORIGIN or ('https://' + (self.headers.get('Host') or 'localhost'))
        self.send_json(200, {'link': reset_link(u['id'], base), 'hours': ADMIN_RESET_HOURS})

    def a_points(self):
        """Начислить ученику баллы (например, тестовые или за олимпиаду) — тратятся в магазине, как заработанные."""
        self.admin()
        d = self.body()
        u = db().execute('SELECT id FROM users WHERE id = ?', (self.int_arg(d, 'user_id'),)).fetchone()
        if not u:
            raise ApiError(404, 'not_found', 'Пользователь не найден')
        grant_points(u['id'], self.int_arg(d, 'amount'), str(d.get('reason') or ''))
        earned, spent = balance(u['id'])
        self.send_json(200, {'balance': {'earned': earned, 'spent': spent, 'left': earned - spent}})

    def a_user(self):
        """Карточка любого пользователя для администратора: учётная запись, тариф и нагрузка преподавателя,
        группы, задачи, материалы; у ученика — его группы, задания и сводка прогресса."""
        self.admin()
        u = db().execute('SELECT * FROM users WHERE id = ?', (self.int_arg(self.query, 'id'),)).fetchone()
        if not u:
            raise ApiError(404, 'not_found', 'Пользователь не найден')
        seen = db().execute('SELECT MAX(ts) FROM hits WHERE uid = ?', (u['id'],)).fetchone()[0]
        out = {'user': {k: u[k] for k in ('id', 'name', 'email', 'role', 'created')} | {'seen': seen}}
        if u['role'] in ('teacher', 'admin'):
            out['plan'], out['usage'], out['limits'] = plan_of(u), teacher_usage(u['id']), FREE_LIMITS
            out['groups'] = [dict(r) for r in db().execute(
                'SELECT g.id, g.name, g.code, g.created, (SELECT COUNT(*) FROM group_members m WHERE m.group_id = g.id) AS members, '
                '(SELECT COUNT(*) FROM homework h WHERE h.group_id = g.id) AS homework FROM study_groups g WHERE g.teacher_id = ? ORDER BY g.created DESC',
                (u['id'],))]
            out['problems'] = db().execute('SELECT COUNT(*) FROM problems WHERE author_id = ? AND builtin = 0 AND hidden = 0', (u['id'],)).fetchone()[0]
            out['materials'] = [dict(r, shared=bool(r['shared'])) for r in db().execute(
                'SELECT id, title, subject, shared, updated FROM materials WHERE author_id = ? AND hidden = 0 ORDER BY updated DESC', (u['id'],))]
            out['subjects'] = json.loads(u['subjects'] or '[]')
            out['payments'] = [dict(r) for r in db().execute(
                'SELECT id, period, amount, status, created, paid_at, applied FROM payments WHERE user_id = ? ORDER BY created DESC LIMIT 20', (u['id'],))]
        else:
            data, updated = load_progress(u['id'])
            hws = assigned_homework(u['id'])
            done = {r['hw_id'] for r in db().execute('SELECT hw_id FROM homework_done WHERE user_id = ?', (u['id'],))}
            out['stats'] = summary(data, updated, u['id'])
            out['balance'] = (lambda e, sp: {'earned': e, 'spent': sp, 'left': e - sp})(*balance(u['id']))
            out['groups'] = [dict(r) for r in db().execute(
                'SELECT g.id, g.name, t.id AS teacher_id, t.name AS teacher, m.joined FROM group_members m JOIN study_groups g ON g.id = m.group_id '
                'JOIN users t ON t.id = g.teacher_id WHERE m.user_id = ? ORDER BY m.joined DESC', (u['id'],))]
            out['homework'] = {'total': len(hws), 'done': sum(h['id'] in done for h in hws)}
        self.send_json(200, out)

    def a_bank(self):
        """Что снято с публикации в общем банке: сами задачи админ видит в /api/content и ege.js целиком."""
        self.admin()
        off, subj_off = bank_rules()
        self.send_json(200, {'off': sorted(off), 'subjects_off': sorted(subj_off), 'subjects': SUBJECTS, 'ege_subject': EGE_SUBJECT})

    def a_bank_set(self):
        """Опубликовать (on = true) или снять с публикации задачи ids или целый предмет subject."""
        self.admin()
        d = self.body(MAX_CONTENT_BODY)
        on = bool(d.get('on'))
        if 'subject' in d:
            subject = re.sub(r'\s+', ' ', self.text_field(d, 'subject', 1, 60, 'Предмет'))
            db().execute('DELETE FROM bank_subjects_off WHERE subject = ?' if on else
                         'INSERT OR IGNORE INTO bank_subjects_off VALUES (?)', (subject,))
        else:
            ids = d.get('ids')
            if not isinstance(ids, list) or not 1 <= len(ids) <= 5000 or not all(BANK_ID_RE.match(str(x)) for x in ids):
                raise ApiError(400, 'bad_ids', 'Некорректный список задач')
            db().executemany('DELETE FROM bank_off WHERE id = ?' if on else 'INSERT OR IGNORE INTO bank_off VALUES (?)',
                             [(str(x),) for x in ids])
        off, subj_off = bank_rules()
        self.send_json(200, {'off': sorted(off), 'subjects_off': sorted(subj_off)})

    def a_plan(self):
        """Тариф преподавателя: free, trial или pro; until — срок (секунды), у pro можно без срока."""
        self.admin()
        d = self.body()
        u = db().execute('SELECT * FROM users WHERE id = ?', (self.int_arg(d, 'user_id'),)).fetchone()
        if not u or u['role'] != 'teacher':
            raise ApiError(404, 'not_found', 'Преподаватель не найден')
        plan, until = str(d.get('plan', '')), d.get('until')
        if plan not in PLANS:
            raise ApiError(400, 'bad_plan', 'Неизвестный тариф')
        if until is not None:
            until = self.int_arg(d, 'until')
            if not 1_600_000_000 < until < 4_000_000_000:
                raise ApiError(400, 'bad_until', 'Некорректный срок')
        if plan == 'trial' and until is None:
            raise ApiError(400, 'bad_until', 'У пробного периода должен быть срок')
        if plan == 'free':
            # у бесплатного срока нет; дата остаётся отметкой, что пробный период уже выдавался
            until = u['plan_until'] or int(time.time())
        db().execute('UPDATE users SET plan = ?, plan_until = ? WHERE id = ?', (plan, until, u['id']))
        self.send_json(200, {'plan': plan_of(db().execute('SELECT * FROM users WHERE id = ?', (u['id'],)).fetchone())})

    # --- оплата Про
    def pay_pro(self):
        """Создаёт платёж в ЮKassa и отдаёт адрес страницы оплаты."""
        u = self.teacher()
        if not (YK_SHOP and YK_KEY):
            raise ApiError(503, 'pay_off', 'Оплата на сайте ещё не подключена')
        if u['role'] == 'admin':
            raise ApiError(400, 'admin', 'У администратора ограничений нет — оплачивать не нужно')
        period = str(self.body().get('period', ''))
        if period not in PRO_PRICES:
            raise ApiError(400, 'bad_period', 'Выберите срок: месяц или год')
        if too_many(f'pay:{u["id"]}', 10, 3600):
            raise ApiError(429, 'rate_limited', 'Слишком много попыток оплаты. Попробуйте через час')
        hit(f'pay:{u["id"]}')
        kop, _, label = PRO_PRICES[period]
        yp = yk('POST', '/payments', {
            'amount': {'value': f'{kop // 100}.{kop % 100:02d}', 'currency': 'RUB'},
            'capture': True,
            'confirmation': {'type': 'redirect', 'return_url': f'{ORIGIN}/#pay-return'},
            'description': f'stackly: тариф Про, {label}',
            'metadata': {'user_id': u['id'], 'period': period},
        }, key=secrets.token_hex(16))
        url = (yp.get('confirmation') or {}).get('confirmation_url')
        if not yp.get('id') or not url:
            raise ApiError(502, 'payment_error', 'Платёжный сервис не вернул страницу оплаты')
        db().execute('INSERT INTO payments (id, user_id, period, amount, status, created) VALUES (?,?,?,?,?,?)',
                     (yp['id'], u['id'], period, kop, 'pending', int(time.time())))
        self.send_json(200, {'url': url})

    def pay_check(self):
        """Вернулись со страницы оплаты: сверяем с ЮKassa все неоконченные платежи этого человека."""
        u, now = self.current_user(), int(time.time())
        out = []
        for r in db().execute("SELECT id FROM payments WHERE user_id = ? AND applied IS NULL AND status IN ('pending', 'waiting_for_capture') "
                              'AND created > ? ORDER BY created DESC LIMIT 5', (u['id'], now - 7 * 86400)).fetchall():
            p = apply_payment(r['id'])
            out.append({'status': 'paid' if p['applied'] else p['status'], 'period': p['period']})
        # уведомление ЮKassa могло засчитать платёж раньше, чем человек вернулся на сайт
        out += [{'status': 'paid', 'period': r['period']} for r in db().execute(
            'SELECT period FROM payments WHERE user_id = ? AND applied > ? ORDER BY applied DESC LIMIT 5', (u['id'], now - 2 * 3600))
            if not any(x['status'] == 'paid' for x in out)]
        u = db().execute('SELECT * FROM users WHERE id = ?', (u['id'],)).fetchone()
        self.send_json(200, {'payments': out, 'plan': plan_of(u)})

    def pay_webhook(self):
        """Уведомление ЮKassa: берём из него только id платежа и сверяем платёж запросом к ЮKassa."""
        d = self.body()
        pid = str((d.get('object') or {}).get('id') or '')
        if re.match(r'^[\w-]{10,60}$', pid) and db().execute('SELECT 1 FROM payments WHERE id = ?', (pid,)).fetchone():
            apply_payment(pid)
        self.send_json(200, {'ok': True})        # ЮKassa ждёт 200, иначе будет повторять уведомление

    # --- Telegram-бот: подключение из кабинета
    def tg_status(self):
        u = self.current_user()
        r = db().execute('SELECT * FROM tg_links WHERE user_id = ?', (u['id'],)).fetchone()
        teacher = u['role'] != 'student'
        self.send_json(200, {'enabled': bool(TG_TOKEN and TG_BOT), 'bot': TG_BOT, 'linked': bool(r),
                             'username': r['username'] if r else '', 'prefs': tg_prefs(r) if r and teacher else None,
                             'pro_required': teacher and not plan_of(u)['active']})

    def tg_link(self):
        """Одноразовая ссылка t.me/<бот>?start=<токен> на 15 минут: бот по ней привяжет чат к этому аккаунту."""
        u = self.current_user()
        if not (TG_TOKEN and TG_BOT):
            raise ApiError(503, 'tg_off', 'Бот ещё не настроен на сервере')
        if u['role'] != 'student' and not plan_of(u)['active']:
            raise ApiError(403, 'plan_limit', 'Telegram-бот для преподавателей входит в тариф Про')
        if too_many(f'tg:{u["id"]}', 10, 3600):
            raise ApiError(429, 'rate_limited', 'Слишком много ссылок. Попробуйте через час')
        hit(f'tg:{u["id"]}')
        tok, now = secrets.token_urlsafe(18), int(time.time())
        db().execute('DELETE FROM tg_tokens WHERE user_id = ? OR expires < ?', (u['id'], now))
        db().execute('INSERT INTO tg_tokens VALUES (?,?,?)', (sha(tok), u['id'], now + 15 * 60))
        self.send_json(200, {'url': f'https://t.me/{TG_BOT}?start={tok}'})

    def tg_unlink(self):
        u = self.current_user()
        db().execute('DELETE FROM tg_links WHERE user_id = ?', (u['id'],))
        self.send_json(200, {'ok': True})

    def tg_set_prefs(self):
        u = self.teacher()
        r = db().execute('SELECT * FROM tg_links WHERE user_id = ?', (u['id'],)).fetchone()
        if not r:
            raise ApiError(404, 'not_found', 'Telegram не подключён')
        d = self.body()
        prefs = tg_prefs(r) | {k: bool(d[k]) for k in TG_PREFS if k in d}
        db().execute('UPDATE tg_links SET prefs = ? WHERE user_id = ?', (json.dumps(prefs), u['id']))
        self.send_json(200, {'prefs': prefs})

    def a_group_add(self):
        """Администратор добавляет уже зарегистрированного ученика в любую группу — без кода."""
        self.admin()
        d = self.body()
        g = db().execute('SELECT * FROM study_groups WHERE id = ?', (self.int_arg(d, 'group_id'),)).fetchone()
        if not g:
            raise ApiError(404, 'not_found', 'Группа не найдена')
        s = db().execute('SELECT * FROM users WHERE id = ?', (self.int_arg(d, 'user_id'),)).fetchone()
        if not s or s['role'] != 'student':
            raise ApiError(404, 'not_found', 'Ученик не найден')
        db().execute('INSERT OR IGNORE INTO group_members VALUES (?,?,?)', (g['id'], s['id'], int(time.time())))
        data, _ = load_progress(s['id'])
        record_homework_done(s['id'], data)       # уже выполненное засчитываем сразу, как при вступлении по коду
        self.send_json(200, {'ok': True})


def cli_set_role(email, role):
    migrate()
    if role not in ROLES:
        sys.exit(f'Роль должна быть одной из: {", ".join(ROLES)}')
    if not db().execute('UPDATE users SET role = ? WHERE email = ?', (role, email.strip().lower())).rowcount:
        sys.exit(f'Пользователь {email} не найден — сначала зарегистрируйтесь на сайте')
    if role == 'teacher':
        start_trial(db().execute('SELECT id FROM users WHERE email = ?', (email.strip().lower(),)).fetchone()['id'])
    print(f'{email}: роль {role}')


def cli_reset_link(email):
    migrate()
    u = db().execute('SELECT id FROM users WHERE email = ?', (email.strip().lower(),)).fetchone()
    if not u:
        sys.exit(f'Пользователь {email} не найден')
    print(reset_link(u['id'], ORIGIN or 'https://stackly.su'))


def cli_grant_points(email, amount, reason=''):
    migrate()
    u = db().execute('SELECT id FROM users WHERE email = ?', (email.strip().lower(),)).fetchone()
    if not u:
        sys.exit(f'Пользователь {email} не найден')
    try:
        grant_points(u['id'], int(amount), reason)
    except (ApiError, ValueError) as e:
        sys.exit(getattr(e, 'message', 'Количество баллов — целое число'))
    earned, spent = balance(u['id'])
    print(f'{email}: +{amount} баллов, на счёте {earned - spent}')


def cli_set_password(email):
    # пароль вводится с клавиатуры без эха, а не аргументом — иначе он остался бы в истории оболочки и в списке процессов
    import getpass
    migrate()
    email = email.strip().lower()
    u = db().execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    if not u:
        sys.exit(f'Пользователь {email} не найден')
    # без терминала (скрипт, тест) пароль читается из stdin: getpass в Windows читает только консоль
    ask = getpass.getpass if sys.stdin.isatty() else (lambda _: sys.stdin.readline().rstrip('\r\n'))
    pw = ask('Новый пароль: ')
    if pw != ask('Ещё раз: '):
        sys.exit('Пароли не совпадают')
    try:
        check_new_password(pw, email)
    except ApiError as e:
        sys.exit(e.message)
    db().execute('UPDATE users SET pw_hash = ? WHERE id = ?', (hash_password(pw), u['id']))
    db().execute('UPDATE resets SET used = 1 WHERE user_id = ?', (u['id'],))   # старые ссылки из писем больше не действуют
    db().execute('DELETE FROM sessions WHERE user_id = ?', (u['id'],))         # как при сбросе по ссылке: выход на всех устройствах
    print(f'{email}: пароль изменён, все сессии закрыты')


def main():
    if len(sys.argv) == 4 and sys.argv[1] == 'set-role':
        return cli_set_role(sys.argv[2], sys.argv[3])
    if len(sys.argv) == 3 and sys.argv[1] == 'reset-link':
        return cli_reset_link(sys.argv[2])
    if len(sys.argv) in (4, 5) and sys.argv[1] == 'grant-points':
        return cli_grant_points(*sys.argv[2:])
    if len(sys.argv) == 3 and sys.argv[1] == 'set-password':
        return cli_set_password(sys.argv[2])
    migrate()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    log.info('stackly API слушает %s:%s, база %s', HOST, PORT, DB_PATH)
    srv.serve_forever()

if __name__ == '__main__':
    main()
