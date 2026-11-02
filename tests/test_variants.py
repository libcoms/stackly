"""Saved variants: persistence, Russian search and access boundaries, without an HTTP process."""
import sys, os, sqlite3, unittest, shutil, subprocess
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
import stackly_api as A

class VariantTest(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.row_factory = sqlite3.Row
        self.p = patch.object(A, 'db', return_value=self.con)
        self.p.start()
        with patch.object(A, 'DB_PATH', ':memory:'):
            A.migrate()
        for uid in (1, 2):
            self.con.execute("INSERT INTO users(id,email,name,pw_hash,created,role,subjects) VALUES(?,?,?,?,?,?,?)",
                             (uid, str(uid)+'@test.ru', 'Teacher', '', 0, 'teacher', '["Информатика"]'))
        self.h = object.__new__(A.Handler)
        self.h.current_user = lambda: self.con.execute('SELECT * FROM users WHERE id=1').fetchone()
        self.h.send_json = lambda status, body: setattr(self, 'response', (status, body))
        self.h.query = {}
        self.allowed = next(p['id'] for p in A.content_bank()[1] if not p.get('subject'))

    def tearDown(self):
        self.p.stop()
        self.con.close()

    def save(self, title='Пробник Ноябрь', bank=None):
        self.h.body = lambda: {'title': title, 'bank': [self.allowed] if bank is None else bank}
        self.h.variant_save()

    def test_persistence_search_and_owner(self):
        self.save(bank=[self.allowed, self.allowed])
        self.assertEqual(self.response[0], 201)
        self.h.query = {'q': 'НОЯБРЬ'}
        self.h.variants()
        vs = self.response[1]['variants']
        self.assertEqual(len(vs), 1)
        self.assertEqual(vs[0]['bank'], [self.allowed])
        self.h.query = {'q': 'нет такого'}
        self.h.variants()
        self.assertEqual(self.response[1]['variants'], [])
        self.h.query = {}
        self.h.current_user = lambda: self.con.execute('SELECT * FROM users WHERE id=2').fetchone()
        self.h.variants()
        self.assertEqual(self.response[1]['variants'], [])

    def test_validation_and_permissions(self):
        for title, bank in [('', [self.allowed]), ('x'*121, [self.allowed]), ('Test', []),
                            ('Test', ['missing']), ('Test', [self.allowed]*201), ('Test', [1])]:
            with self.subTest(title=title, bank=bank), self.assertRaises(A.ApiError):
                self.save(title, bank)
        self.con.execute("UPDATE users SET subjects='[]' WHERE id=1")
        with self.assertRaises(A.ApiError):
            self.save()
        self.con.execute("UPDATE users SET role='student' WHERE id=1")
        with self.assertRaises(A.ApiError):
            self.h.variants()
        with self.assertRaises(A.ApiError):
            self.save()

    def test_attempt_is_saved_without_grading_until_finish(self):
        self.save()
        vid = self.response[1]['id']
        expected = next(p['answer'] for p in A.content_bank()[1] if p['id'] == self.allowed)
        def call(answers, finish=False):
            self.h.body = lambda: {'id': vid, 'answers': answers, 'finish': finish}
            self.h.variant_attempt()
            return self.response[1]['attempt']
        draft = call({self.allowed: 'wrong'})
        self.assertEqual(draft['answers'][self.allowed], 'wrong')
        self.assertIsNone(draft['results'])
        self.assertIsNone(draft['finished'])
        self.h.variants()
        self.assertEqual(self.response[1]['variants'][0]['attempt']['answers'][self.allowed], 'wrong')
        final = call({self.allowed: expected}, True)
        self.assertTrue(final['finished'])
        self.assertEqual(final['results'][0]['status'], 'correct')
        with self.assertRaises(A.ApiError):
            call({self.allowed: 'changed'})
        self.assertEqual(self.h.variant_run(vid)['answers'][self.allowed], expected)
        self.h.current_user = lambda: self.con.execute('SELECT * FROM users WHERE id=2').fetchone()
        with self.assertRaises(A.ApiError):
            call({})

    def test_attempt_validation_empty_and_decimal_answers(self):
        self.save()
        vid = self.response[1]['id']
        for answers in ({'not-in-variant': '1'}, {self.allowed: 1}, {self.allowed: 'x'*4001}):
            self.h.body = lambda: {'id': vid, 'answers': answers}
            with self.assertRaises(A.ApiError):
                self.h.variant_attempt()
        self.h.body = lambda: {'id': vid, 'finish': True}
        self.h.variant_attempt()
        self.assertEqual(self.response[1]['attempt']['results'][0]['status'], 'unanswered')
        for a, b, expected in [('0.25','0,25',True), ('−3','-3',True), ('007','7',False), ('1; 2','1 2',True)]:
            self.assertEqual(A.variant_same_answer(a,b), expected)


class VariantNavigationTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is not installed')
    def test_variant_task_navigation(self):
        result = subprocess.run(['node', os.path.join(os.path.dirname(__file__), 'variants_check.js')],
                                capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
