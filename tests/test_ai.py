"""Тест разбора кода с ИИ: API против поддельного RouterAI на локальном порту."""
import base64, json, os, sys, threading, unittest, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_api as T       # noqa: E402

KEY = 'rai-test-key'
AI_EMAIL, AI_STUDENT = 'ai.teacher@example.com', 'ai.student@example.com'


class FakeRouterAI:
    """Чат, распознавание и озвучка: запросы складываются в self.calls, ответы задаёт тест."""
    def __init__(self):
        self.calls, self.auth_ok = [], True
        self.reply = json.dumps({'say': 'В пятой строке шаг цикла [sigh] НЕ тот. Подумай, с какого числа начинать.', 'notes': '```\nfor x in range(2027, 10**10, 2027):\n```'})
        self.heard, self.speech_sec, self.fail = 'а почему шаг не тот', 10, False
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, body, ctype='application/json', code=200):
                self.send_response(code)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                fake.auth_ok = fake.auth_ok and self.headers.get('Authorization') == 'Bearer ' + KEY
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                fake.calls.append((self.path, body))
                if fake.fail:
                    return self.send(b'{"error": {"message": "upstream"}}', code=fake.fail if fake.fail is not True else 500)
                if self.path == '/chat/completions':
                    return self.send(json.dumps({'choices': [{'message': {'content': fake.reply}}], 'usage': {'cost': 0.42}}).encode())
                if self.path == '/audio/transcriptions':
                    return self.send(json.dumps({'text': fake.heard, 'usage': {'seconds': 5, 'cost': 0.01}}).encode())
                if self.path == '/audio/speech':
                    return self.send(b'\x01\x00' * 24000 * fake.speech_sec, 'audio/pcm')
                self.send(b'{}', code=404)

        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.url = f'http://127.0.0.1:{self.srv.server_address[1]}'
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def last(self, path):
        return [b for p, b in self.calls if p == path][-1]


class AiTest(T.ServerCase):
    set_role = T.ClassroomTest.set_role

    @classmethod
    def setUpClass(cls):
        cls.rai = FakeRouterAI()
        cls.extra_env = {'STACKLY_AI_KEY': KEY, 'STACKLY_AI_API': cls.rai.url, 'STACKLY_AI_WEEK_SECONDS': '60',
                         'STACKLY_AI_USERS': f'{AI_EMAIL}, {AI_STUDENT.upper()}'}
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.rai.srv.shutdown()
        super().tearDownClass()

    def make(self, email, role):
        T.ServerCase.n += 1
        c = T.Client(self.base)
        st, r = c.call('POST', '/auth/register', {'email': email, 'name': 'Тест', 'password': 'Strong-pass-1'},
                       {'X-Real-IP': f'10.9.0.{T.ServerCase.n % 250 + 1}'})
        self.assertEqual(st, 201, r)
        if role != 'student':
            self.set_role(email, role)
            self.assertEqual(c.call('POST', '/me/teaching', {'subjects': ['Информатика']})[0], 200)
        return c

    def speech(self, c, sid):
        req = urllib.request.Request(self.base + '/ai/speech', method='POST', data=json.dumps({'id': sid}).encode(),
                                     headers={'Content-Type': 'application/json', 'Origin': T.ORIGIN, 'Cookie': c.cookie})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.headers.get('Content-Type'), r.read(), r.headers.get('X-AI-Used')
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get('Content-Type'), e.read(), None

    def test_review_talk_and_limit(self):
        code = 'for x in range(1, 10**10):\n    if x % 2027 == 0:\n        print(x)'
        # не из списка — функции не видно
        other = self.make('someone@example.com', 'teacher')
        self.assertNotIn('ai', other.call('GET', '/auth/me')[1]['user'])
        self.assertEqual(other.call('POST', '/ai/turn', {'pid': '25-1', 'code': code})[0], 403)

        t = self.make(AI_EMAIL, 'teacher')
        me = t.call('GET', '/auth/me')[1]['user']
        self.assertEqual((me['ai']['limit'], me['ai']['used']), (60, 0))
        self.assertEqual(t.call('POST', '/ai/turn', {'pid': '25-1', 'code': '  '})[1]['error'], 'no_code')
        self.assertEqual(t.call('POST', '/ai/turn', {'pid': 'nope', 'code': code})[0], 404)
        self.assertEqual(t.call('POST', '/ai/turn', {'pid': 'm1-g001', 'code': code})[0], 404)   # математика — не код

        # первый разбор: модель видит задачу, эталон и пронумерованный код ученика
        st, r = t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code})
        self.assertEqual(st, 200, r)
        self.assertEqual(r['say'], 'В пятой строке шаг цикла НЕ тот. Подумай, с какого числа начинать.')   # звуки — только в голосе
        self.assertTrue('range(2027' in r['notes'] and r['speech'])
        self.assertNotIn('ПРОЖАРКА', self.rai.last('/chat/completions')['messages'][0]['content'])
        self.assertEqual(r['heard'], '')
        sent = self.rai.last('/chat/completions')
        system, ask = sent['messages'][0]['content'], sent['messages'][-1]
        self.assertIn('Задание ЕГЭ №25', system)
        self.assertIn('ЭТАЛОН', system)
        self.assertIn('112157964 55332', system)                          # ответ эталона — только модели
        self.assertIn('  2|     if x % 2027 == 0:', system)
        self.assertEqual((ask['role'], ask['content'], len(sent['messages'])), ('user', 'Разбери моё решение.', 2))
        self.assertEqual(sent['model'], 'anthropic/claude-sonnet-5.5')
        self.assertTrue(self.rai.auth_ok)

        # озвучка: WAV, 10 секунд звука списываются; второй раз ту же реплику не озвучить
        st, ctype, wav, used = self.speech(t, r['speech'])
        self.assertEqual((st, ctype, wav[:4], wav[8:12]), (200, 'audio/wav', b'RIFF', b'WAVE'))
        self.assertEqual(len(wav), 44 + 2 * 24000 * 10)
        self.assertEqual(float(used), 10.0)
        tts = self.rai.last('/audio/speech')
        self.assertEqual((tts['model'], tts['response_format'], tts['input']), ('google/gemini-3.8-flash-tts', 'pcm', 'В пятой строке шаг цикла [sigh] НЕ тот. Подумай, с какого числа начинать.'))
        self.assertIn('эмоционально', tts['provider']['options']['google-ai-studio']['speech_metadata']['style'])
        self.assertIn('style', tts['provider']['options']['google-ai-studio']['speech_metadata'])
        self.assertEqual(self.speech(t, r['speech'])[0], 404)
        self.assertEqual(self.speech(other, 'x')[0], 403)

        # вопрос голосом: речь распознаётся, 5 секунд записи — в счёт лимита, история уходит модели по очереди
        hist = [{'role': 'user', 'text': 'Разбери моё решение.'}, {'role': 'assistant', 'text': r['say']},
                {'role': 'assistant', 'text': 'лишняя'}, {'role': 'hacker', 'text': 'x'}]
        audio = {'data': base64.b64encode(b'\x1aE\xdf\xa3' + b'0' * 4000).decode(), 'format': 'webm', 'seconds': 1}
        st, r2 = t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code, 'history': hist, 'audio': audio})
        self.assertEqual(st, 200, r2)
        self.assertEqual((r2['heard'], r2['ai']['used']), ('а почему шаг не тот', 15.0))
        stt = self.rai.last('/audio/transcriptions')
        self.assertEqual((stt['model'], stt['input_audio']['format'], stt['language']), ('openai/whisper-large-v3-turbo', 'webm', 'ru'))
        roles = [m['role'] for m in self.rai.last('/chat/completions')['messages']]
        self.assertEqual(roles, ['system', 'user', 'assistant', 'user'])
        self.assertEqual(self.rai.last('/chat/completions')['messages'][-1]['content'], 'а почему шаг не тот')
        self.assertEqual(t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code, 'audio': dict(audio, format='exe')})[1]['error'], 'bad_audio')

        # прожарка с матом: включает сам пользователь, модель получает правила, голос — манеру комика
        self.assertEqual(t.call('POST', '/ai/settings', {'roast': 3})[0], 400)
        self.assertEqual(t.call('POST', '/ai/settings', {'roast': True})[0], 400)
        self.assertEqual(other.call('POST', '/ai/settings', {'roast': 2})[0], 403)
        self.assertEqual(t.call('POST', '/ai/settings', {'roast': 2})[1]['ai']['roast'], 2)
        self.assertEqual(t.call('GET', '/auth/me')[1]['user']['ai']['roast'], 2)
        rr = t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code, 'text': 'жги'})[1]
        sent = self.rai.last('/chat/completions')
        self.assertIn('ЖЁСТКАЯ ПРОЖАРКА С МАТОМ', sent['messages'][0]['content'])
        self.assertEqual(sent['temperature'], 0.8)
        self.assertEqual(self.speech(t, rr['speech'])[0], 200)
        self.assertIn('жёсткой прожарке', self.rai.last('/audio/speech')['provider']['options']['google-ai-studio']['speech_metadata']['style'])
        t.call('POST', '/ai/settings', {'roast': 1})
        t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code, 'text': 'а без мата?'})
        self.assertIn('Без мата.', self.rai.last('/chat/completions')['messages'][0]['content'])
        self.rai.speech_sec = 1

        # модель ответила не JSON — текст целиком идёт в речь, без markdown
        self.rai.reply = 'Всё **верно**, молодец!'
        r3 = t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code, 'text': 'а так?'})[1]
        self.assertEqual((r3['say'], r3['notes']), ('Всё верно, молодец!', ''))

        # RouterAI упал — понятная ошибка, реплику можно озвучить потом
        self.rai.fail = True
        st, e = t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code})
        self.assertEqual((st, e['message']), (502, 'RouterAI ответил ошибкой 500: upstream. Попробуйте ещё раз через минуту'))
        self.assertEqual(self.speech(t, r3['speech'])[0], 502)
        # причина ошибки RouterAI — понятными словами: что чинить
        self.rai.fail = 401
        self.assertIn('не принял ключ', t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code})[1]['message'])
        self.rai.fail = 402
        self.assertIn('балансе RouterAI', t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code})[1]['message'])
        self.rai.fail = False

        # лимит: озвучка на 50 секунд добирает минуту, дальше — 429 до понедельника
        self.rai.speech_sec = 50
        self.assertEqual(self.speech(t, r3['speech'])[0], 200)
        st, e = t.call('POST', '/ai/turn', {'pid': '25-1', 'code': code})
        self.assertEqual((st, e['error']), (429, 'ai_limit'))
        self.assertGreaterEqual(t.call('GET', '/ai/status')[1]['ai']['used'], 60)
        self.assertEqual(self.speech(t, r2['speech'])[0], 429)

        # ученик из списка видит только задачи, которые ему выдали или открыли
        s = self.make(AI_STUDENT, 'student')
        self.assertIn('ai', s.call('GET', '/auth/me')[1]['user'])
        self.assertEqual(s.call('POST', '/ai/turn', {'pid': '25-1', 'code': code})[0], 404)


if __name__ == '__main__':
    unittest.main()
