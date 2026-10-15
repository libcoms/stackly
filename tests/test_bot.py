"""Тест Telegram-бота: настоящий процесс app/stackly_bot.py против поддельного Bot API на локальном порту.

Проверяется путь целиком: привязка по ссылке из кабинета, уведомления о новом ученике и сданном ДЗ,
сводка после срока, кнопка «Напомнить не сдавшим», команды и тариф Про.
"""
import json, os, subprocess, sys, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_api as T       # noqa: E402 — общие ServerCase и Client


class FakeTelegram:
    """Bot API в памяти: копит вызовы, по getUpdates отдаёт подложенные сообщения."""
    def __init__(self):
        self.calls, self.updates, self.lock, self.n = [], [], threading.Lock(), 0
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                method = self.path.rsplit('/', 1)[-1]
                p = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
                if method == 'getUpdates':
                    end = time.time() + min(1, p.get('timeout', 0))
                    while time.time() < end:
                        with fake.lock:
                            got = [u for u in fake.updates if u['update_id'] >= p.get('offset', 0)]
                        if got:
                            break
                        time.sleep(.05)
                    res = got
                else:
                    with fake.lock:
                        fake.calls.append((method, p))
                    res = {'message_id': len(fake.calls)} if method in ('sendMessage', 'editMessageText') else True
                body = json.dumps({'ok': True, 'result': res}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.url = f'http://127.0.0.1:{self.srv.server_address[1]}'
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def push(self, chat, text=None, callback=None, username='teacher_tg'):
        with self.lock:
            self.n += 1
            if callback:
                up = {'update_id': self.n, 'callback_query': {'id': str(self.n), 'data': callback,
                                                              'message': {'message_id': 1, 'chat': {'id': chat, 'type': 'private'}}}}
            else:
                up = {'update_id': self.n, 'message': {'message_id': self.n, 'text': text, 'from': {'username': username},
                                                       'chat': {'id': chat, 'type': 'private'}}}
            self.updates.append(up)

    def sent(self, chat, method='sendMessage'):
        with self.lock:
            return [p for m, p in self.calls if m == method and p.get('chat_id') == chat]

    def wait(self, pred, what, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            r = pred()
            if r:
                return r
            time.sleep(.1)
        raise AssertionError(f'не дождались: {what}; вызовы: {self.calls[-6:]}')


class BotTest(T.ServerCase):
    extra_env = {'STACKLY_TG_TOKEN': 'TEST', 'STACKLY_TG_BOT': 'stackly_test_bot'}
    set_role = T.ClassroomTest.set_role
    user = T.ContentTest.user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tg = FakeTelegram()
        env = dict(os.environ, STACKLY_DB=cls.db, STACKLY_ORIGIN=T.ORIGIN, STACKLY_TG_TOKEN='TEST', STACKLY_TG_BOT='stackly_test_bot',
                   STACKLY_TG_API=cls.tg.url, STACKLY_TG_POLL='1', STACKLY_TG_TICK='.1', STACKLY_TG_PERIOD='.3', STACKLY_TG_DIGEST='99')
        cls.env = env
        cls.bot = subprocess.Popen([sys.executable, os.path.join(T.ROOT, 'app', 'stackly_bot.py')], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls):
        cls.bot.terminate()
        cls.bot.wait(5)
        cls.tg.srv.shutdown()
        super().tearDownClass()

    def link(self, c, chat):
        st, r = c.call('POST', '/tg/link', {})
        self.assertEqual(st, 200, r)
        self.assertTrue(r['url'].startswith('https://t.me/stackly_test_bot?start='))
        self.tg.push(chat, '/start ' + r['url'].split('start=')[1])
        self.tg.wait(lambda: any('Готово' in p['text'] for p in self.tg.sent(chat)), f'привязка чата {chat}')

    def last(self, chat, needle):
        return self.tg.wait(lambda: next((p for p in reversed(self.tg.sent(chat)) if needle in p['text']), None), f'«{needle}» в чате {chat}')

    def test_teacher_bot_flow(self):
        t, s, a = self.user('teacher'), self.user('student'), self.user('admin')
        st, r = t.call('GET', '/tg')
        self.assertEqual((r['enabled'], r['linked'], r['pro_required']), (True, False, False))
        self.link(t, 111)
        self.assertTrue(t.call('GET', '/tg')[1]['linked'])
        # чужая или старая ссылка не привязывает
        self.tg.push(999, '/start ' + 'x' * 24)
        self.last(999, 'Ссылка устарела')
        # новый ученик в группе — уведомление
        g = t.call('POST', '/teach/groups', {'name': '11А'})[1]['group']
        s.call('POST', '/me/groups/join', {'code': g['code']})
        self.last(111, 'Новый ученик в группе «11А»')
        self.link(s, 222)
        # ДЗ со сроком в прошлом: сводка после срока с кнопкой напоминания
        hw = t.call('POST', '/teach/homework', {'group_id': g['id'], 'title': 'Графы', 'items': {'bank': ['1-1']},
                                                 'due': int(time.time()) - 60})[1]['homework']
        msg = self.last(111, 'Прошёл срок задания «Графы»')
        self.assertIn('Сдали 0 из 1', msg['text'])
        self.assertEqual(msg['reply_markup']['inline_keyboard'][0][0]['callback_data'], f'r:{hw["id"]}')
        # «Напомнить не сдавшим» — сообщение ученику, повтор в течение 6 часов не шлётся
        self.tg.push(111, callback=f'r:{hw["id"]}')
        self.last(222, 'Напоминание от преподавателя')
        self.tg.wait(lambda: any(p.get('text') == 'Напомнили: 1' for m, p in self.tg.calls if m == 'answerCallbackQuery'), 'ответ на кнопку')
        self.tg.push(111, callback=f'r:{hw["id"]}')
        self.tg.wait(lambda: any('Уже напоминали' in (p.get('text') or '') for m, p in self.tg.calls if m == 'answerCallbackQuery'), 'повтор напоминания')
        # ученик сдал — уведомление преподавателю; /hw показывает прогресс
        self.assertEqual(s.call('PUT', '/progress', {'data': {'solved': ['1-1']}})[0], 200)
        self.last(111, 'выполнено задание «Графы»')
        self.tg.push(111, '/hw')
        self.last(111, 'Сдали 1 из 1')
        self.tg.push(111, '/student ')
        self.last(111, '/student Аня')
        self.tg.push(111, '/student Учен')
        self.last(111, 'Заданий сдано: 1 из 1')
        self.tg.push(222, '/hw')
        self.last(222, 'Все задания выполнены')
        # вечерняя сводка: час сводки 0 — значит, уже пора; в ней сданное сегодня задание
        r = subprocess.run([sys.executable, '-c', 'import stackly_bot as B; B.digests()'], cwd=os.path.join(T.ROOT, 'app'),
                           env=dict(self.env, STACKLY_TG_DIGEST='0'), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('«Графы»', self.last(111, 'Сводка за день')['text'])
        # выключенное уведомление не приходит
        self.tg.push(111, callback='p:join')
        self.tg.wait(lambda: self.tg.sent(111, 'editMessageText'), 'настройки')
        self.assertFalse(t.call('GET', '/tg')[1]['prefs']['join'])
        before = len(self.tg.sent(111))
        s2 = self.user('student')
        s2.call('POST', '/me/groups/join', {'code': g['code']})
        time.sleep(1.2)
        self.assertFalse(any('Новый ученик' in p['text'] for p in self.tg.sent(111)[before:]))
        # без Про бот преподавателю не отвечает и ссылку не выдаёт
        tid = t.call('GET', '/auth/me')[1]['user']['id']
        a.call('POST', '/admin/plan', {'user_id': tid, 'plan': 'free'})
        self.tg.push(111, '/hw')
        self.last(111, 'входит в тариф Про')
        self.assertEqual(t.call('POST', '/tg/link', {})[1]['error'], 'plan_limit')
        # /stop отвязывает чат
        self.tg.push(222, '/stop')
        self.last(222, 'Бот отключён')
        self.tg.wait(lambda: not s.call('GET', '/tg')[1]['linked'], 'отвязка ученика')


if __name__ == '__main__':
    unittest.main()
