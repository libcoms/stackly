"""Тесты API: запускают app/stackly_api.py на свободном порту с временной базой.

Запуск:  python3 -m unittest discover -s tests -v
"""
import json, os, socket, sqlite3, subprocess, sys, tempfile, time, unittest, urllib.error, urllib.request
from http.cookies import SimpleCookie

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGIN = 'https://stackly.test'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Client:
    def __init__(self, base):
        self.base, self.cookie = base, None

    def call(self, method, path, data=None, headers=None):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.base + path, data=body, method=method)
        if body is not None:
            req.add_header('Content-Type', 'application/json')
        req.add_header('Origin', ORIGIN)
        if self.cookie:
            req.add_header('Cookie', self.cookie)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            r = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            r = e
        for c in r.headers.get_all('Set-Cookie') or []:
            m = SimpleCookie(c)
            if 'stackly_session' in m:
                v = m['stackly_session'].value
                self.cookie = f'stackly_session={v}' if v else None
        raw = r.read()
        return r.status, (json.loads(raw) if raw else None)


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = os.path.join(cls.tmp.name, 'stackly.db')
        port = free_port()
        env = dict(os.environ, STACKLY_DB=cls.db, STACKLY_PORT=str(port), STACKLY_ORIGIN=ORIGIN,
                   STACKLY_COOKIE_SECURE='0', SMTP_HOST='')
        cls.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, 'app', 'stackly_api.py')], env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.base = f'http://127.0.0.1:{port}/api'
        for _ in range(50):
            try:
                urllib.request.urlopen(cls.base + '/health', timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError('API не запустился')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(5)
        cls.tmp.cleanup()

    n = 0

    def register(self, pw='Strong-pass-1'):
        ApiTest.n += 1
        c = Client(self.base)
        email = f'user{ApiTest.n}@example.com'
        st, body = c.call('POST', '/auth/register', {'email': email, 'name': 'Ученик', 'password': pw})
        self.assertEqual(st, 201, body)
        return c, email

    def reset_tokens(self, email):
        # токены в базе хранятся хешами — подменяем хеш на известный токен
        con = sqlite3.connect(self.db)
        uid = con.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()[0]
        return con, uid

    def test_register_login_progress(self):
        c, email = self.register()
        self.assertEqual(c.call('GET', '/auth/me')[0], 200)
        self.assertEqual(c.call('PUT', '/progress', {'data': {'solved': ['a']}})[0], 200)
        st, body = c.call('GET', '/progress')
        self.assertEqual(body['data'], {'solved': ['a']})
        self.assertEqual(c.call('POST', '/auth/logout', {})[0], 200)
        self.assertEqual(c.call('GET', '/auth/me')[0], 401)
        self.assertEqual(c.call('POST', '/auth/login', {'email': email, 'password': 'Strong-pass-1'})[0], 200)

    def test_weak_password_rejected(self):
        c = Client(self.base)
        st, body = c.call('POST', '/auth/register', {'email': 'weak@example.com', 'name': 'x', 'password': 'aaaaaaaa'})
        self.assertEqual((st, body['error']), (400, 'weak_password'))

    def test_foreign_origin_rejected(self):
        c = Client(self.base)
        st, _ = c.call('POST', '/auth/login', {'email': 'a@b.cd', 'password': 'x'}, {'Origin': 'https://evil.example'})
        self.assertEqual(st, 403)

    def test_cross_site_fetch_rejected_without_origin(self):
        req = urllib.request.Request(self.base + '/auth/logout', data=b'{}', method='POST',
                                     headers={'Content-Type': 'application/json', 'Sec-Fetch-Site': 'cross-site'})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(e.exception.code, 403)

    def test_bad_content_length(self):
        with socket.create_connection(('127.0.0.1', int(self.base.split(':')[2].split('/')[0])), timeout=5) as s:
            s.sendall(b'POST /api/auth/login HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n'
                      b'Content-Length: -5\r\nConnection: close\r\n\r\n')
            self.assertIn(b' 400 ', s.recv(200))

    def test_reset_invalidates_other_links(self):
        import hashlib
        c, email = self.register()
        con, uid = self.reset_tokens(email)
        exp = int(time.time()) + 3600
        for tok in ('first-token-aaaaaaaaaaaa', 'second-token-bbbbbbbbbbb'):
            con.execute('INSERT INTO resets VALUES (?,?,?,0)', (hashlib.sha256(tok.encode()).hexdigest(), uid, exp))
        con.commit(); con.close()
        anon = Client(self.base)
        st, body = anon.call('POST', '/auth/reset', {'token': 'first-token-aaaaaaaaaaaa', 'password': 'aaaaaaaa'})
        self.assertEqual((st, body['error']), (400, 'weak_password'))      # простой пароль не принимаем и при сбросе
        self.assertEqual(anon.call('POST', '/auth/reset', {'token': 'first-token-aaaaaaaaaaaa', 'password': 'New-pass-12'})[0], 200)
        st, body = Client(self.base).call('POST', '/auth/reset', {'token': 'second-token-bbbbbbbbbbb', 'password': 'Other-pass-34'})
        self.assertEqual((st, body['error']), (400, 'bad_token'))          # второе письмо больше не работает
        self.assertEqual(c.call('GET', '/auth/me')[0], 401)                 # старая сессия закрыта

    def test_password_guessing_limited(self):
        c, _ = self.register()
        codes = [c.call('POST', '/auth/password', {'old': f'wrong-{i}', 'new': 'New-pass-12'})[0] for i in range(9)]
        self.assertEqual(codes[:8], [400] * 8)
        self.assertEqual(codes[8], 429)

    def test_change_password_requires_strong_new(self):
        c, _ = self.register()
        st, body = c.call('POST', '/auth/password', {'old': 'Strong-pass-1', 'new': '11111111'})
        self.assertEqual((st, body['error']), (400, 'weak_password'))

    def test_rate_limiter_does_not_keep_empty_keys(self):
        # много неудачных попыток с разными адресами почты не должны оставлять пустые записи
        sys.path.insert(0, os.path.join(ROOT, 'app'))
        import stackly_api as api
        for i in range(100):
            api.too_many(f'em:probe{i}@x.ru', 8, 600)
        self.assertFalse(any(k.startswith('em:probe') for k in api._hits))


if __name__ == '__main__':
    unittest.main()
