"""Telegram sign-in: bot confirmation, browser binding, replay resistance and existing/new accounts."""
import os, sys, sqlite3, unittest
from unittest.mock import patch
from http.cookies import SimpleCookie
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
import stackly_api as A
import stackly_bot as B

class TelegramLoginTest(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:', isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.patches = [patch.object(A,'db',return_value=self.con),patch.object(B,'db',return_value=self.con),
                        patch.object(A,'DB_PATH',':memory:'),patch.object(A,'TG_TOKEN','test-token'),
                        patch.object(A,'TG_BOT','test_bot'),patch.object(A,'too_many',return_value=False),
                        patch.object(A,'hit'),patch.object(B,'tg',return_value=True),patch.object(B,'say')]
        for p in self.patches: p.start()
        A.migrate()
        self.h = object.__new__(A.Handler)
        self.h.client_ip = lambda: '127.0.0.1'
        self.h.send_json = lambda status,body,cookies=(): setattr(self,'response',(status,body,cookies))
        self.cookies = {}
        self.h.cookie = lambda name: self.cookies.get(name)
        self.h.current_user = lambda *a,**kw: None

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.con.close()

    def start(self,role='student'):
        self.h.body=lambda:{'role':role}
        self.h.tg_login_start()
        c=SimpleCookie();c.load(self.response[2][0]);self.cookies['stackly_tg_login']=c['stackly_tg_login'].value
        return self.response[1]['token']

    def confirm(self,token,uid=123):
        B.on_callback({'id':'callback','data':'auth:'+token,'from':{'id':uid,'first_name':'Тест'},
                       'message':{'chat':{'id':uid,'type':'private'}}})

    def poll(self,token):
        self.h.body=lambda:{'token':token}
        self.h.tg_login_poll()

    def test_new_account_browser_binding_and_replay(self):
        token=self.start('teacher');self.poll(token);self.assertTrue(self.response[1]['pending'])
        self.confirm(token)
        browser=self.cookies['stackly_tg_login'];self.cookies['stackly_tg_login']='other-browser'
        with self.assertRaises(A.ApiError):self.poll(token)
        self.cookies['stackly_tg_login']=browser;self.poll(token)
        u=self.response[1]['user'];self.assertEqual(u['role'],'teacher');self.assertEqual(u['name'],'Тест')
        self.assertTrue(self.con.execute('SELECT tg_only FROM users').fetchone()[0])
        with self.assertRaises(A.ApiError):self.poll(token)
        with self.assertRaises(A.ApiError):self.poll('unknown')

    def test_existing_account_keeps_id_role_and_expiration(self):
        self.con.execute("INSERT INTO users(id,email,name,pw_hash,created,role) VALUES(1,'teacher@example.com','Teacher','x',0,'teacher')")
        self.con.execute("INSERT INTO tg_links(user_id,chat_id,linked) VALUES(1,123,0)")
        token=self.start('student');self.confirm(token);self.poll(token)
        self.assertEqual(self.response[1]['user']['id'],1)
        self.assertEqual(self.response[1]['user']['role'],'teacher')
        token=self.start();self.con.execute('UPDATE tg_logins SET expires=0');self.confirm(token)
        with self.assertRaises(A.ApiError):self.poll(token)

    def test_callback_from_other_chat_and_role_escalation(self):
        token=self.start('admin')
        B.on_callback({'id':'callback','data':'auth:'+token,'from':{'id':999},'message':{'chat':{'id':123,'type':'private'}}})
        self.poll(token);self.assertTrue(self.response[1]['pending'])
        self.confirm(token);self.poll(token);self.assertEqual(self.response[1]['user']['role'],'student')

    def test_telegram_account_adds_email_before_unlinking(self):
        token=self.start();self.confirm(token);self.poll(token)
        uid=self.response[1]['user']['id']
        self.h.current_user=lambda:self.con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        with self.assertRaises(A.ApiError):self.h.tg_unlink()
        self.h.body=lambda:{'email':'real@example.com','password':'Strong-Secret-123'}
        self.h.tg_add_email();self.assertEqual(self.response[1]['user']['email'],'real@example.com')
        self.h.tg_unlink();self.assertEqual(self.response[1],{'ok':True})
