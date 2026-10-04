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


class ServerCase(unittest.TestCase):
    """Свой процесс API с пустой базой на каждый класс тестов."""
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
        ServerCase.n += 1
        c = Client(self.base)
        email = f'user{ServerCase.n}@example.com'
        # у каждого «ученика» свой адрес — иначе сработает лимит регистраций с одного IP
        st, body = c.call('POST', '/auth/register', {'email': email, 'name': 'Ученик', 'password': pw},
                          {'X-Real-IP': f'10.0.{ServerCase.n // 250}.{ServerCase.n % 250 + 1}'})
        self.assertEqual(st, 201, body)
        return c, email

    def reset_tokens(self, email):
        # токены в базе хранятся хешами — подменяем хеш на известный токен
        con = sqlite3.connect(self.db)
        uid = con.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()[0]
        return con, uid



class ApiTest(ServerCase):
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


class ClassroomTest(ServerCase):
    """Группы, домашние задания, роли."""

    def set_role(self, email, role):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'app', 'stackly_api.py'), 'set-role', email, role],
                           env=dict(os.environ, STACKLY_DB=self.db), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def teacher(self):
        c, email = self.register()
        self.set_role(email, 'teacher')
        return c, email

    def test_roles_and_access(self):
        student, _ = self.register()
        self.assertEqual(student.call('GET', '/auth/me')[1]['user']['role'], 'student')
        self.assertEqual(student.call('GET', '/teach/groups')[0], 403)
        self.assertEqual(student.call('GET', '/admin/users')[0], 403)
        t, _ = self.teacher()
        self.assertEqual(t.call('GET', '/teach/groups')[0], 200)
        self.assertEqual(t.call('GET', '/admin/users')[0], 403)

    def test_group_homework_flow(self):
        t, _ = self.teacher()
        st, body = t.call('POST', '/teach/groups', {'name': '11А'})
        self.assertEqual(st, 201)
        g = body['group']
        s1, _ = self.register(); s2, _ = self.register()
        self.assertEqual(s1.call('POST', '/me/groups/join', {'code': 'WRONG123'})[0], 404)
        self.assertEqual(s1.call('POST', '/me/groups/join', {'code': g['code'].lower()})[0], 200)   # регистр не важен
        self.assertEqual(s2.call('POST', '/me/groups/join', {'code': g['code']})[0], 200)
        sid1 = s1.call('GET', '/auth/me')[1]['user']['id']

        hw = {'group_id': g['id'], 'title': 'Графы', 'comment': 'К пятнице', 'due': int(time.time()) + 86400,
              'items': {'bank': ['b1', 'b2'], 'py': [3], 'ege': [1]}}
        st, body = t.call('POST', '/teach/homework', hw)
        self.assertEqual(st, 201, body)
        hid = body['homework']['id']
        # второе ДЗ — только первому ученику
        t.call('POST', '/teach/homework', dict(hw, title='Личное', students=[sid1]))
        self.assertEqual(len(s1.call('GET', '/me/homework')[1]['homework']), 2)
        self.assertEqual(len(s2.call('GET', '/me/homework')[1]['homework']), 1)

        # ученик решает часть — учитель видит прогресс; решает всё — фиксируется время сдачи
        s1.call('PUT', '/progress', {'data': {'solved': ['b1'], 'studied': [3], 'ege': [], 'att': {'b1': {'n': 2, 'c': 1}}}})
        grp = t.call('GET', f'/teach/group?id={g["id"]}')[1]
        status = next(h for h in grp['homework'] if h['id'] == hid)['status']
        self.assertEqual(status[str(sid1)][:2], [2, 4])
        self.assertIsNone(status[str(sid1)][2])
        m1 = next(m for m in grp['members'] if m['id'] == sid1)
        self.assertEqual((m1['stats']['solved'], m1['stats']['accuracy']), (1, 50))
        s1.call('PUT', '/progress', {'data': {'solved': ['b1', 'b2'], 'studied': [3], 'ege': [1]}})
        mine = {h['id']: h for h in s1.call('GET', '/me/homework')[1]['homework']}
        self.assertIsNotNone(mine[hid]['done_at'])

        # подробная статистика ДЗ: по каждому ученику и каждой задаче
        st, hs = t.call('GET', f'/teach/homework?id={hid}')
        self.assertEqual(st, 200, hs)
        me = next(x for x in hs['students'] if x['id'] == sid1)
        self.assertEqual((me['done'], me['total'], me['py'], me['ege']), (4, 4, [3], [1]))
        self.assertTrue(me['bank']['b1'][0])
        self.assertEqual(len(hs['students']), 2)
        # карточка ученика доступна учителю, но не чужому учителю
        self.assertEqual(t.call('GET', f'/teach/student?id={sid1}')[0], 200)
        other, _ = self.teacher()
        self.assertEqual(other.call('GET', f'/teach/student?id={sid1}')[0], 404)
        self.assertEqual(other.call('GET', f'/teach/group?id={g["id"]}')[0], 404)
        self.assertEqual(other.call('POST', '/teach/homework/delete', {'id': hid})[0], 404)
        self.assertEqual(other.call('GET', f'/teach/homework?id={hid}')[0], 404)

        # ученик ушёл из группы — ДЗ пропали
        s2.call('POST', '/me/groups/leave', {'id': g['id']})
        self.assertEqual(s2.call('GET', '/me/homework')[1]['homework'], [])
        # новый код — старый перестаёт работать
        old = g['code']
        t.call('POST', '/teach/groups/update', {'id': g['id'], 'new_code': True})
        self.assertEqual(s2.call('POST', '/me/groups/join', {'code': old})[0], 404)
        # удаление группы удаляет и ДЗ
        t.call('POST', '/teach/groups/delete', {'id': g['id']})
        self.assertEqual(s1.call('GET', '/me/homework')[1]['homework'], [])

    def test_homework_validation(self):
        t, _ = self.teacher()
        g = t.call('POST', '/teach/groups', {'name': 'Пн 18:00'})[1]['group']
        st, body = t.call('POST', '/teach/homework', {'group_id': g['id'], 'title': 'Пусто', 'items': {}})
        self.assertEqual((st, body['error']), (400, 'empty'))
        st, body = t.call('POST', '/teach/homework', {'group_id': g['id'], 'title': '', 'items': {'ege': [1]}})
        self.assertEqual((st, body['error']), (400, 'bad_title'))
        # мусорные пункты отбрасываются
        st, body = t.call('POST', '/teach/homework', {'group_id': g['id'], 'title': 'x',
                                                      'items': {'ege': [1, 99, 'a'], 'bank': ['ok-1', '<script>'], 'py': [0, 5]}})
        self.assertEqual(body['homework']['items'], {'bank': ['ok-1'], 'py': [5], 'ege': [1]})

    def test_admin_roles(self):
        a, email = self.register()
        self.set_role(email, 'admin')
        s, _ = self.register()
        sid = s.call('GET', '/auth/me')[1]['user']['id']
        self.assertEqual(a.call('POST', '/admin/role', {'user_id': sid, 'role': 'teacher'})[0], 200)
        self.assertEqual(s.call('GET', '/teach/groups')[0], 200)
        aid = a.call('GET', '/auth/me')[1]['user']['id']
        self.assertEqual(a.call('POST', '/admin/role', {'user_id': aid, 'role': 'student'})[0], 400)   # себя не понизить
        self.assertEqual(a.call('POST', '/admin/role', {'user_id': sid, 'role': 'root'})[0], 400)
        users = a.call('GET', '/admin/users?q=' + email.split('@')[0])[1]['users']
        self.assertEqual([u['email'] for u in users], [email])

    def test_join_bruteforce_limited(self):
        s, _ = self.register()
        codes = [s.call('POST', '/me/groups/join', {'code': f'ZZZZZZ{i:02d}'})[0] for i in range(11)]
        self.assertEqual(codes[-1], 429)


class ContentTest(ServerCase):
    """Редактор: задачи учителей, правки встроенных задач и методички, картинки."""
    set_role = ClassroomTest.set_role

    def user(self, role):
        c, email = self.register()
        if role != 'student':
            self.set_role(email, role)
        return c

    P = {'task': 5, 'level': 'П', 'title': 'Моя задача', 'body': 'Найдите **N**.', 'answer': '42', 'solution': 'print(42)'}

    def content(self, c):
        return c.call('GET', '/content')[1]

    def test_teacher_problem_lifecycle(self):
        t, other, s = self.user('teacher'), self.user('teacher'), self.user('student')
        self.assertEqual(s.call('POST', '/content/problem', self.P)[0], 403)
        st, r = t.call('POST', '/content/problem', self.P)
        self.assertEqual(st, 200, r)
        pid = r['id']
        self.assertTrue(pid.startswith('u'))
        self.assertEqual(self.content(Client(self.base))['problems'], [])     # гостю задачи не отдаём
        p = next(x for x in self.content(s)['problems'] if x['id'] == pid)
        self.assertGreaterEqual(p['num'], 1001)
        self.assertEqual((p['answer'], p['builtin']), ('42', False))
        # второй учитель не может править чужую, автор — может
        self.assertEqual(other.call('POST', '/content/problem', dict(self.P, id=pid, title='Взлом'))[0], 403)
        self.assertEqual(t.call('POST', '/content/problem', dict(self.P, id=pid, title='Новое название'))[0], 200)
        self.assertEqual(next(x for x in self.content(t)['problems'] if x['id'] == pid)['title'], 'Новое название')
        # номер следующей задачи не повторяется даже после удаления
        self.assertEqual(t.call('POST', '/content/problem/delete', {'id': pid})[0], 200)
        self.assertNotIn(pid, [x['id'] for x in self.content(t)['problems']])
        pid2 = t.call('POST', '/content/problem', self.P)[1]['id']
        self.assertNotEqual(pid, pid2)

    def test_old_custom_numbers_move_past_builtin_range(self):
        # задачи учителей раньше нумеровались с 101 — теперь встроенный банк до 1000, их номера сдвигаются
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO problems (id, num, task, level, title, body, answer, created, updated) "
                    "VALUES ('u150', 150, 1, 'Б', 'старая', 'x', '1', 0, 0)")
        con.commit(); con.close()
        subprocess.run([sys.executable, os.path.join(ROOT, 'app', 'stackly_api.py'), 'set-role', 'x@x.ru', 'student'],
                       env=dict(os.environ, STACKLY_DB=self.db), capture_output=True)          # запуск = миграция
        con = sqlite3.connect(self.db)
        self.assertEqual(con.execute("SELECT num FROM problems WHERE id = 'u150'").fetchone()[0], 1050)
        con.close()

    def test_validation(self):
        t = self.user('teacher')
        for bad, code in ((dict(self.P, task=30), 'bad_task'), (dict(self.P, level='X'), 'bad_level'), (dict(self.P, answer=''), 'bad_answer'),
                          (dict(self.P, data='1 2 3', dname='../x'), 'bad_dname')):
            st, r = t.call('POST', '/content/problem', bad)
            self.assertEqual((st, r['error']), (400, code))

    def test_builtin_override_admin_only(self):
        t, a = self.user('teacher'), self.user('admin')
        self.assertEqual(t.call('POST', '/content/problem', dict(self.P, id='1-1'))[0], 403)
        self.assertEqual(a.call('POST', '/content/problem', dict(self.P, id='1-1', keep_extra=True))[0], 200)
        p = next(x for x in self.content(a)['problems'] if x['id'] == '1-1')
        self.assertEqual((p['builtin'], p['keep_extra'], p['num']), (True, True, None))
        a.call('POST', '/content/problem/delete', {'id': '1-1'})               # скрыть
        self.assertTrue(next(x for x in self.content(a)['problems'] if x['id'] == '1-1')['hidden'])
        a.call('POST', '/content/problem/delete', {'id': '1-1', 'restore': True})   # вернуть исходную
        self.assertNotIn('1-1', [x['id'] for x in self.content(a)['problems']])

    def test_lessons(self):
        t, a = self.user('teacher'), self.user('admin')
        les = {'kind': 'ege', 'key': 5, 'data': {'title': 'Новый заголовок', 'theory': 'Текст **жирный**', 'steps': ['раз', 'два']}}
        self.assertEqual(t.call('POST', '/content/lesson', les)[0], 403)
        self.assertEqual(a.call('POST', '/content/lesson', les)[0], 200)
        self.assertEqual(self.content(a)['lessons']['ege']['5']['title'], 'Новый заголовок')
        self.assertEqual(a.call('POST', '/content/lesson', dict(les, key=99))[0], 400)
        a.call('POST', '/content/lesson/reset', {'kind': 'ege', 'key': 5})
        self.assertEqual(self.content(a)['lessons']['ege'], {})

    def test_guest_sees_no_problems_or_writeups(self):
        t, a = self.user('teacher'), self.user('admin')
        t.call('POST', '/content/problem', self.P)
        a.call('POST', '/content/lesson', {'kind': 'ege', 'key': 7, 'data': {'title': 'Карточка', 'theory': 'Секретный разбор'}})
        a.call('POST', '/content/lesson', {'kind': 'py', 'key': 3, 'data': {'title': 'Тема', 'text': 'Открытый текст'}})
        g = self.content(Client(self.base))
        self.assertEqual(g['problems'], [])
        self.assertEqual(g['lessons']['ege']['7']['title'], 'Карточка')            # карточка на главной
        self.assertNotIn('theory', g['lessons']['ege']['7'])                       # а разбор — нет
        self.assertEqual(g['lessons']['py']['3']['text'], 'Открытый текст')        # учебник Python открыт
        self.assertTrue(self.content(t)['problems'])
        for kind, key in (('ege', 7), ('py', 3)):
            a.call('POST', '/content/lesson/reset', {'kind': kind, 'key': key})

    def test_media(self):
        import base64
        t, s = self.user('teacher'), self.user('student')
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg==')
        body = {'type': 'image/png', 'data': base64.b64encode(png).decode()}
        self.assertEqual(s.call('POST', '/media', body)[0], 403)
        st, r = t.call('POST', '/media', body)
        self.assertEqual(st, 201, r)
        with urllib.request.urlopen(f'{self.base}/media/{r["id"]}') as resp:
            self.assertEqual((resp.headers['Content-Type'], resp.read()), ('image/png', png))
            self.assertEqual(resp.headers['X-Content-Type-Options'], 'nosniff')
        # SVG и подмена типа не проходят
        svg = base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>').decode()
        self.assertEqual(t.call('POST', '/media', {'type': 'image/svg+xml', 'data': svg})[0], 400)
        self.assertEqual(t.call('POST', '/media', {'type': 'image/png', 'data': svg})[0], 400)


class ContentAccessTest(ServerCase):
    """Методичка, шпаргалка и банк задач — только после входа."""
    def fetch(self, c, headers=None):
        req = urllib.request.Request(self.base + '/content/ege.js', headers=dict(headers or {}))
        if c.cookie:
            req.add_header('Cookie', c.cookie)
        try:
            r = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            r = e
        return r.status, r.headers, r.read()

    def test_guest_gets_401(self):
        st, _, body = self.fetch(Client(self.base))
        self.assertEqual(st, 401)
        self.assertNotIn(b'window.BANK', body)

    def test_user_gets_content_and_loses_it_after_logout(self):
        c, _ = self.register()
        st, h, body = self.fetch(c)
        self.assertEqual(st, 200)
        self.assertTrue(h['Content-Type'].startswith('text/javascript'))
        self.assertIn('private', h['Cache-Control'])
        self.assertIn(b'window.STACKLY_CONTENT = true', body)
        st, _, body = self.fetch(c, {'If-None-Match': h['ETag']})
        self.assertEqual((st, body), (304, b''))
        cookie = c.cookie
        c.call('POST', '/auth/logout', {})
        c.cookie = cookie                                   # старая cookie после выхода не работает
        self.assertEqual(self.fetch(c, {'If-None-Match': h['ETag']})[0], 401)


if __name__ == '__main__':
    unittest.main()
