#!/usr/bin/env python3
"""stackly API — регистрация, вход и прогресс учеников.

Только стандартная библиотека Python 3.10+: http.server, sqlite3, hashlib.scrypt.
Работает за nginx (127.0.0.1:8090), сам наружу не смотрит.

Настройки — переменные окружения (см. deploy/stackly.env.example):
  STACKLY_DB        путь к базе SQLite            (/var/lib/stackly/stackly.db)
  STACKLY_HOST/PORT адрес, где слушать           (127.0.0.1 / 8090)
  STACKLY_ORIGIN    https://ваш-домен — с него принимаются изменяющие запросы
  STACKLY_COOKIE_SECURE 1 — cookie только по HTTPS (выключать лишь для локальной проверки)
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM — почта для восстановления пароля
"""
import base64, hashlib, hmac, json, logging, os, re, secrets, smtplib, sqlite3, threading, time
from email.message import EmailMessage
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get('STACKLY_DB', '/var/lib/stackly/stackly.db')
HOST = os.environ.get('STACKLY_HOST', '127.0.0.1')
PORT = int(os.environ.get('STACKLY_PORT', '8090'))
ORIGIN = os.environ.get('STACKLY_ORIGIN', '').rstrip('/')
COOKIE_SECURE = os.environ.get('STACKLY_COOKIE_SECURE', '1') == '1'
COOKIE = 'stackly_session'
SESSION_DAYS = 30
RESET_MINUTES = 60
MAX_BODY = 256 * 1024
MAX_PROGRESS = 200 * 1024
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
    ''')

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

# ---------------------------------------------------------------- ограничение попыток
_hits, _hits_lock = {}, threading.Lock()

def too_many(key: str, limit: int, window: int) -> bool:
    now = time.time()
    with _hits_lock:
        q = [t for t in _hits.get(key, []) if now - t < window]
        _hits[key] = q
        return len(q) >= limit

def hit(key: str):
    with _hits_lock:
        _hits.setdefault(key, []).append(time.time())

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
    def body(self):
        if not (self.headers.get('Content-Type') or '').startswith('application/json'):
            raise ApiError(415, 'bad_type', 'Ожидается JSON')
        n = int(self.headers.get('Content-Length') or 0)
        if n > MAX_BODY:
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
        path = self.path.split('?', 1)[0]
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
        }
        fn = handlers.get((method, path))
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
        return {'id': u['id'], 'email': u['email'], 'name': u['name'], 'created': u['created']}

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
        if len(pw) < 8 or len(pw) > 200:
            raise ApiError(400, 'weak_password', 'Пароль — от 8 символов')
        if pw.lower() in (email, email.split('@')[0]) or len(set(pw)) < 4:
            raise ApiError(400, 'weak_password', 'Пароль слишком простой')
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
        if len(pw) < 8 or len(pw) > 200:
            raise ApiError(400, 'weak_password', 'Пароль — от 8 символов')
        r = db().execute('SELECT * FROM resets WHERE token_hash = ? AND used = 0 AND expires > ?',
                         (sha(tok), int(time.time()))).fetchone()
        if not r:
            raise ApiError(400, 'bad_token', 'Ссылка устарела или уже использована. Запросите новую')
        db().execute('UPDATE resets SET used = 1 WHERE token_hash = ?', (sha(tok),))
        db().execute('UPDATE users SET pw_hash = ? WHERE id = ?', (hash_password(pw), r['user_id']))
        db().execute('DELETE FROM sessions WHERE user_id = ?', (r['user_id'],))   # выходим на всех устройствах
        u = db().execute('SELECT * FROM users WHERE id = ?', (r['user_id'],)).fetchone()
        self.send_json(200, {'user': self.user_json(u)}, [self.start_session(u['id'])])

    def change_password(self):
        u = self.current_user()
        d = self.body()
        if not check_password(str(d.get('old', '')), u['pw_hash']):
            raise ApiError(400, 'bad_credentials', 'Текущий пароль указан неверно')
        new = str(d.get('new', ''))
        if len(new) < 8 or len(new) > 200:
            raise ApiError(400, 'weak_password', 'Новый пароль — от 8 символов')
        db().execute('UPDATE users SET pw_hash = ? WHERE id = ?', (hash_password(new), u['id']))
        tok = self.token()
        db().execute('DELETE FROM sessions WHERE user_id = ? AND token_hash != ?', (u['id'], sha(tok or '')))
        self.send_json(200, {'ok': True})

    def delete_account(self):
        u = self.current_user()
        d = self.body()
        if not check_password(str(d.get('password', '')), u['pw_hash']):
            raise ApiError(400, 'bad_credentials', 'Пароль указан неверно')
        db().execute('DELETE FROM users WHERE id = ?', (u['id'],))
        self.send_json(200, {'ok': True}, [self.session_cookie('', 0)])

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
        self.send_json(200, {'ok': True, 'updated': now})


def main():
    migrate()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    log.info('stackly API слушает %s:%s, база %s', HOST, PORT, DB_PATH)
    srv.serve_forever()

if __name__ == '__main__':
    main()
