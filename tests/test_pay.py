"""Тест оплаты Про через ЮKassa: API против поддельного API ЮKassa на локальном порту."""
import base64, json, os, sys, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_api as T       # noqa: E402

SHOP, KEY = '123456', 'test_secret'


class FakeYooKassa:
    """Платежи в памяти: POST /payments создаёт, GET /payments/<id> отдаёт; статус и сумму меняет тест."""
    def __init__(self):
        self.payments, self.auth_ok, self.idem, self.n = {}, True, [], 0
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def reply(self, obj, code=200):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def check(self):
                ok = self.headers.get('Authorization') == 'Basic ' + base64.b64encode(f'{SHOP}:{KEY}'.encode()).decode()
                fake.auth_ok = fake.auth_ok and ok
                return ok

            def do_POST(self):
                if not self.check():
                    return self.reply({'type': 'error'}, 401)
                p = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                fake.idem.append(self.headers.get('Idempotence-Key'))
                fake.n += 1
                pid = f'2f{fake.n:08d}-000f-5000-9000-1b68e7b15f3f'
                fake.payments[pid] = dict(p, id=pid, status='pending', paid=False)
                self.reply({'id': pid, 'status': 'pending', 'confirmation': {'type': 'redirect', 'confirmation_url': f'https://yoomoney.test/pay/{pid}'}})

            def do_GET(self):
                if not self.check():
                    return self.reply({'type': 'error'}, 401)
                pid = self.path.rsplit('/', 1)[-1]
                return self.reply(fake.payments[pid]) if pid in fake.payments else self.reply({'type': 'error'}, 404)

        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.url = f'http://127.0.0.1:{self.srv.server_address[1]}'
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def pay(self, pid):
        self.payments[pid].update(status='succeeded', paid=True)


class PayTest(T.ServerCase):
    user = T.ContentTest.user
    set_role = T.ClassroomTest.set_role

    @classmethod
    def setUpClass(cls):
        cls.yk = FakeYooKassa()
        cls.extra_env = {'STACKLY_YK_SHOP': SHOP, 'STACKLY_YK_KEY': KEY, 'STACKLY_YK_API': cls.yk.url}
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.yk.srv.shutdown()
        super().tearDownClass()

    def test_pro_payment(self):
        t, s, a = self.user('teacher'), self.user('student'), self.user('admin')
        me = t.call('GET', '/auth/me')[1]['user']
        self.assertEqual((me['pay'], me['prices']), (True, {'month': 10, 'year': 10}))      # временная цена для проверки оплаты
        trial_until = me['plan']['until']
        self.assertEqual(s.call('POST', '/pay/pro', {'period': 'month'})[0], 403)          # ученику платить не за что
        self.assertEqual(t.call('POST', '/pay/pro', {'period': 'week'})[1]['error'], 'bad_period')
        st, r = t.call('POST', '/pay/pro', {'period': 'month'})
        self.assertEqual(st, 200, r)
        pid = r['url'].rsplit('/', 1)[-1]
        sent = self.yk.payments[pid]
        self.assertEqual((sent['amount'], sent['capture'], sent['metadata']['user_id']), ({'value': '10.00', 'currency': 'RUB'}, True, me['id']))
        self.assertEqual(sent['confirmation']['return_url'], T.ORIGIN + '/#pay-return')
        self.assertTrue(self.yk.idem[-1] and self.yk.auth_ok)
        # пока не оплачено — тариф не меняется
        st, r = t.call('POST', '/pay/check', {})
        self.assertEqual((r['payments'][0]['status'], r['plan']['plan']), ('pending', 'trial'))
        # оплачено: месяц добавляется к ещё идущему пробному периоду, повторная проверка ничего не прибавляет
        self.yk.pay(pid)
        r = t.call('POST', '/pay/check', {})[1]
        self.assertEqual((r['payments'][0]['status'], r['plan']['plan'], r['plan']['active']), ('paid', 'pro', True))
        self.assertEqual(r['plan']['until'], trial_until + 30 * 86400)
        self.assertEqual(t.call('POST', '/pay/check', {})[1]['plan']['until'], trial_until + 30 * 86400)
        # годовая оплата через уведомление ЮKassa: id берётся из уведомления, статус — из самой ЮKassa
        pid2 = t.call('POST', '/pay/pro', {'period': 'year'})[1]['url'].rsplit('/', 1)[-1]
        hook = T.Client(self.base)
        self.assertEqual(hook.call('POST', '/pay/webhook', {'event': 'payment.succeeded', 'object': {'id': pid2}})[0], 200)   # ещё не оплачен
        self.assertEqual(t.call('GET', '/auth/me')[1]['user']['plan']['until'], trial_until + 30 * 86400)
        self.yk.pay(pid2)
        hook.call('POST', '/pay/webhook', {'event': 'payment.succeeded', 'object': {'id': pid2}})
        hook.call('POST', '/pay/webhook', {'event': 'payment.succeeded', 'object': {'id': pid2}})                         # повтор уведомления
        self.assertEqual(t.call('GET', '/auth/me')[1]['user']['plan']['until'], trial_until + 395 * 86400)
        # человек вернулся на сайт уже после уведомления — страница возврата всё равно видит оплату
        self.assertIn('paid', [x['status'] for x in t.call('POST', '/pay/check', {})[1]['payments']])
        self.assertEqual(hook.call('POST', '/pay/webhook', {'object': {'id': 'unknown-payment-id'}})[0], 200)
        # сумма не сходится — Про не продлевается
        pid3 = t.call('POST', '/pay/pro', {'period': 'month'})[1]['url'].rsplit('/', 1)[-1]
        self.yk.payments[pid3]['amount'] = {'value': '1.00', 'currency': 'RUB'}
        self.yk.pay(pid3)
        r = t.call('POST', '/pay/check', {})[1]
        self.assertEqual((r['payments'][0]['status'], r['plan']['until']), ('mismatch', trial_until + 395 * 86400))
        # администратор видит платежи в карточке преподавателя
        card = a.call('GET', f'/admin/user?id={me["id"]}')[1]
        self.assertEqual(sorted(p['status'] for p in card['payments']), ['mismatch', 'succeeded', 'succeeded'])


if __name__ == '__main__':
    unittest.main()
