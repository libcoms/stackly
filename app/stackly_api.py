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
"""
import base64, hashlib, hmac, json, logging, os, re, secrets, smtplib, sqlite3, sys, threading, time
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
SESSION_DAYS = 30
RESET_MINUTES = 60
MAX_BODY = 256 * 1024
MAX_CONTENT_BODY = 3 * 1024 * 1024     # задачи с файлом данных и картинки (base64)
MAX_IMAGE = 1536 * 1024
IMAGE_TYPES = {'image/png': b'\x89PNG', 'image/jpeg': b'\xff\xd8\xff', 'image/gif': b'GIF8', 'image/webp': b'RIFF'}
MEDIA_RE = re.compile(r'^/api/media/([A-Za-z0-9_-]{8,40})$')
MAX_PROGRESS = 200 * 1024
ROLES = ('student', 'teacher', 'admin')
CODE_ABC = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'      # без похожих 0/O и 1/I
BANK_ID_RE = re.compile(r'^[\w.-]{1,40}$')
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
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('PRAGMA busy_timeout=5000')
        _local.con = con
    return con

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
      -- items — JSON {"bank": [id задач], "py": [темы Python], "ege": [номера заданий методички]}
      CREATE TABLE IF NOT EXISTS homework (
        id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
        title TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '', items TEXT NOT NULL,
        students TEXT NOT NULL DEFAULT '[]', due INTEGER, created INTEGER NOT NULL, updated INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS homework_group ON homework(group_id);
      -- когда ученик закрыл все пункты ДЗ (фиксируется при сохранении прогресса)
      -- задачи, созданные на сайте (id «u<номер>», номера с 101) и правки встроенных (builtin = 1, id как в банке)
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
      CREATE TABLE IF NOT EXISTS media (
        id TEXT PRIMARY KEY, owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        type TEXT NOT NULL, data BLOB NOT NULL, created INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS homework_done (
        hw_id INTEGER NOT NULL REFERENCES homework(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        done_at INTEGER NOT NULL, PRIMARY KEY (hw_id, user_id));
    ''')
    cols = [r['name'] for r in db().execute('PRAGMA table_info(users)')]
    if 'role' not in cols:
        db().execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")

# ---------------------------------------------------------------- пароли и токены
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=64 * 2**20, dklen=32)
    return 'scrypt$32768$8$1$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(dk).decode()

def check_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split('$')
        got = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             maxmem=64 * 2**20, dklen=len(base64.b64decode(dk)))
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

def progress_sets(data):
    solved = {str(x) for x in data.get('solved', []) if isinstance(x, (str, int))} if isinstance(data.get('solved'), list) else set()
    return {'bank': solved, 'py': _ints(data.get('studied')), 'ege': _ints(data.get('ege'))}

def hw_progress(items, sets):
    """(сделано пунктов, всего пунктов) по одному ДЗ."""
    total = done = 0
    for k in ('bank', 'py', 'ege'):
        for x in items.get(k, []):
            total += 1
            done += (str(x) if k == 'bank' else x) in sets[k]
    return done, total

def summary(data, updated):
    """Короткая статистика ученика для таблиц учителя."""
    sets = progress_sets(data)
    att = data.get('att') if isinstance(data.get('att'), dict) else {}
    tries = right = 0
    for a in att.values():
        if isinstance(a, dict):
            tries += int(a.get('n') or 0); right += int(a.get('c') or 0)
    days = {k for k, v in (data.get('days') or {}).items() if v} if isinstance(data.get('days'), dict) else set()
    today = time.time()
    day = lambda back: time.strftime('%Y-%m-%d', time.localtime(today - back * 86400))
    streak, back = 0, (0 if day(0) in days else 1)        # сегодня ещё не занимался — серия считается со вчера
    while day(back) in days:
        streak += 1; back += 1
    return {'solved': len(sets['bank']), 'studied': len(sets['py']), 'ege': len(sets['ege']),
            'tries': tries, 'right': right, 'accuracy': round(right / tries * 100) if tries else None,
            'active7': sum(day(i) in days for i in range(7)), 'streak': streak, 'updated': updated}

def hw_json(h):
    return {'id': h['id'], 'group_id': h['group_id'], 'title': h['title'], 'comment': h['comment'],
            'items': json.loads(h['items']), 'students': json.loads(h['students']), 'due': h['due'],
            'created': h['created'], 'updated': h['updated']}

def assigned_homework(user_id):
    """ДЗ, выданные ученику: во всех его группах, кроме адресованных другим ученикам."""
    rows = db().execute('SELECT h.*, g.name AS group_name, t.name AS teacher_name FROM homework h '
                        'JOIN group_members m ON m.group_id = h.group_id AND m.user_id = ? '
                        'JOIN study_groups g ON g.id = h.group_id JOIN users t ON t.id = g.teacher_id '
                        'ORDER BY COALESCE(h.due, h.created + 315360000), h.id', (user_id,)).fetchall()
    return [h for h in rows if not json.loads(h['students']) or user_id in json.loads(h['students'])]

def record_homework_done(user_id, data):
    sets, now = progress_sets(data), int(time.time())
    done = {r['hw_id'] for r in db().execute('SELECT hw_id FROM homework_done WHERE user_id = ?', (user_id,))}
    for h in assigned_homework(user_id):
        if h['id'] in done:
            continue
        d, t = hw_progress(json.loads(h['items']), sets)
        if t and d == t:
            db().execute('INSERT OR IGNORE INTO homework_done VALUES (?,?,?)', (h['id'], user_id, now))

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
        parts = [f'{COOKIE}={token}', 'Path=/', 'HttpOnly', 'SameSite=Lax', f'Max-Age={max_age}']
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

    def token(self):
        c = SimpleCookie(self.headers.get('Cookie') or '')
        return c[COOKIE].value if COOKIE in c else None

    def current_user(self, required=True):
        tok = self.token()
        row = None
        if tok:
            row = db().execute('SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id '
                               'WHERE s.token_hash = ? AND s.expires > ?', (sha(tok), int(time.time()))).fetchone()
        if row is None and required:
            raise ApiError(401, 'unauthorized', 'Нужно войти')
        return row

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
            ('GET', '/api/admin/users'): self.a_users,
            ('POST', '/api/admin/role'): self.a_role,
            # редактор задач и методички
            ('GET', '/api/content'): self.content,
            ('POST', '/api/content/problem'): self.c_problem_save,
            ('POST', '/api/content/problem/delete'): self.c_problem_delete,
            ('POST', '/api/content/lesson'): self.c_lesson_save,
            ('POST', '/api/content/lesson/reset'): self.c_lesson_reset,
            ('POST', '/api/media'): self.c_media_upload,
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

    # --- обработчики
    def health(self):
        db().execute('SELECT 1')
        self.send_json(200, {'ok': True})

    def user_json(self, u):
        return {'id': u['id'], 'email': u['email'], 'name': u['name'], 'created': u['created'], 'role': u['role']}

    def me(self):
        self.send_json(200, {'user': self.user_json(self.current_user())})

    def register(self):
        d = self.body()
        email = str(d.get('email', '')).strip().lower()
        name = re.sub(r'\s+', ' ', str(d.get('name', ''))).strip()
        pw = str(d.get('password', ''))
        ip = self.client_ip()
        if too_many('reg:' + ip, 10, 3600):
            raise ApiError(429, 'rate_limited', 'Слишком много регистраций с этого адреса, попробуйте через час')
        if not EMAIL_RE.match(email):
            raise ApiError(400, 'bad_email', 'Проверьте адрес почты')
        if not 1 <= len(name) <= 60:
            raise ApiError(400, 'bad_name', 'Укажите имя — от 1 до 60 символов')
        check_new_password(pw, email)
        hit('reg:' + ip)
        try:
            cur = db().execute('INSERT INTO users (email, name, pw_hash, created) VALUES (?,?,?,?)',
                               (email, name, hash_password(pw), int(time.time())))
        except sqlite3.IntegrityError:
            raise ApiError(409, 'email_taken', 'На эту почту уже есть аккаунт — войдите или восстановите пароль')
        u = db().execute('SELECT * FROM users WHERE id = ?', (cur.lastrowid,)).fetchone()
        self.send_json(201, {'user': self.user_json(u)}, [self.start_session(u['id'])])

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
        self.send_json(200, {'user': self.user_json(u)}, [self.start_session(u['id'])])

    def logout(self):
        tok = self.token()
        if tok:
            db().execute('DELETE FROM sessions WHERE token_hash = ?', (sha(tok),))
        self.send_json(200, {'ok': True}, [self.session_cookie('', 0)])

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
        self.send_json(200, {'ok': True}, [self.session_cookie('', 0)])

    def check_own_password(self, u, pw, message):
        key = f'pw:{u["id"]}'
        if too_many(key, 8, 600):
            raise ApiError(429, 'rate_limited', 'Слишком много попыток. Подождите 10 минут')
        if not check_password(pw, u['pw_hash']):
            hit(key)
            raise ApiError(400, 'bad_credentials', message)

    def content_js(self):
        self.current_user()
        body, etag = content_file('ege.js')
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
        record_homework_done(u['id'], data)
        self.send_json(200, {'ok': True, 'updated': now})

    # --- ученик: группы и домашние задания
    def my_groups(self):
        u = self.current_user()
        rows = db().execute('SELECT g.id, g.name, t.name AS teacher, m.joined FROM group_members m '
                            'JOIN study_groups g ON g.id = m.group_id JOIN users t ON t.id = g.teacher_id '
                            'WHERE m.user_id = ? ORDER BY m.joined', (u['id'],)).fetchall()
        self.send_json(200, {'groups': [dict(r) for r in rows]})

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
        db().execute('INSERT OR IGNORE INTO group_members VALUES (?,?,?)', (g['id'], u['id'], int(time.time())))
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
            members.append(dict(r, stats=summary(data, updated)))
        hws = db().execute('SELECT * FROM homework WHERE group_id = ? ORDER BY COALESCE(due, created + 315360000) DESC, id DESC',
                           (g['id'],)).fetchall()
        status = self.hw_status(hws, sets)
        teacher = db().execute('SELECT name FROM users WHERE id = ?', (g['teacher_id'],)).fetchone()['name']
        self.send_json(200, {'group': dict(g, teacher=teacher), 'members': members,
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
                             'stats': summary(data, updated),
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
        if not (bank or py or ege):
            raise ApiError(400, 'empty', 'Добавьте в задание хотя бы одну задачу или тему')
        due = d.get('due')
        if due is not None:
            due = self.int_arg(d, 'due')
            if not 1_600_000_000 < due < 4_000_000_000:
                raise ApiError(400, 'bad_due', 'Некорректный срок сдачи')
        member_ids = {r['user_id'] for r in db().execute('SELECT user_id FROM group_members WHERE group_id = ?', (g['id'],))}
        students = sorted(x for x in _ints(d.get('students')) if x in member_ids)
        items = json.dumps({'bank': bank, 'py': py, 'ege': ege})
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
                             'ege': [x for x in items.get('ege', []) if x in sets['ege']]})
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
        rows = db().execute('SELECT p.*, u.name AS author FROM problems p LEFT JOIN users u ON u.id = p.author_id '
                            'WHERE p.hidden = 0 OR p.builtin = 1 ORDER BY p.task, p.num').fetchall()
        problems = [{k: r[k] for k in ('id', 'num', 'task', 'level', 'title', 'body', 'answer', 'solution', 'note', 'data',
                                       'dname', 'author', 'author_id', 'updated')}
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
            task = int(d.get('task'))
        except (TypeError, ValueError):
            task = 0
        if not 1 <= task <= 27:
            raise ApiError(400, 'bad_task', 'Номер задания ЕГЭ — от 1 до 27')
        level = str(d.get('level', ''))
        if level not in ('Б', 'П', 'В'):
            raise ApiError(400, 'bad_level', 'Укажите сложность')
        f = {'task': task, 'level': level,
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
            num = max(100, db().execute('SELECT MAX(num) FROM problems').fetchone()[0] or 0) + 1
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
        hit(key)
        mid = secrets.token_urlsafe(12)
        db().execute('INSERT INTO media VALUES (?,?,?,?,?)', (mid, u['id'], kind, raw, int(time.time())))
        self.send_json(201, {'id': mid})

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

    # --- администратор
    def admin(self):
        u = self.current_user()
        if u['role'] != 'admin':
            raise ApiError(403, 'forbidden', 'Раздел доступен только администратору')
        return u

    def a_users(self):
        self.admin()
        q = '%' + str(self.query.get('q', '')).strip().lower().replace('%', '').replace('_', '') + '%'
        rows = db().execute('SELECT u.id, u.name, u.email, u.role, u.created, p.updated, '
                            '(SELECT COUNT(*) FROM group_members m WHERE m.user_id = u.id) AS groups_in, '
                            '(SELECT COUNT(*) FROM study_groups g WHERE g.teacher_id = u.id) AS groups_own '
                            'FROM users u LEFT JOIN progress p ON p.user_id = u.id '
                            'WHERE lower(u.email) LIKE ? OR lower(u.name) LIKE ? '
                            "ORDER BY CASE u.role WHEN 'admin' THEN 0 WHEN 'teacher' THEN 1 ELSE 2 END, u.created DESC LIMIT 300",
                            (q, q)).fetchall()
        total = db().execute('SELECT COUNT(*) FROM users').fetchone()[0]
        self.send_json(200, {'users': [dict(r) for r in rows], 'total': total})

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
        self.send_json(200, {'ok': True})


def cli_set_role(email, role):
    migrate()
    if role not in ROLES:
        sys.exit(f'Роль должна быть одной из: {", ".join(ROLES)}')
    if not db().execute('UPDATE users SET role = ? WHERE email = ?', (role, email.strip().lower())).rowcount:
        sys.exit(f'Пользователь {email} не найден — сначала зарегистрируйтесь на сайте')
    print(f'{email}: роль {role}')


def main():
    if len(sys.argv) == 4 and sys.argv[1] == 'set-role':
        return cli_set_role(sys.argv[2], sys.argv[3])
    migrate()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    log.info('stackly API слушает %s:%s, база %s', HOST, PORT, DB_PATH)
    srv.serve_forever()

if __name__ == '__main__':
    main()
