"""Saved variants: persistence, Russian search and access boundaries, without an HTTP process."""
import sys, os, sqlite3, unittest
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
