import unittest
from unittest.mock import patch
import test_telegram_login as T
A,B=T.A,T.B
class WebhookTest(unittest.TestCase):
    setUp=T.TelegramLoginTest.setUp
    tearDown=T.TelegramLoginTest.tearDown
    start=T.TelegramLoginTest.start
    poll=T.TelegramLoginTest.poll
    def prepare(self):
        self.patches[-1].stop();self.patches[-2].stop()  # use actual transport capture, not mocked replies
        self.h.headers={'X-Telegram-Bot-Api-Secret-Token':'test-webhook-secret'}
    def deliver(self,update):
        self.h.body=lambda **kw:update
        with patch.object(A,'TG_WEBHOOK_SECRET','test-webhook-secret'):
            self.h.tg_webhook()
        return self.response[1]
    def test_private_start_links_and_replies_without_network(self):
        self.prepare()
        self.con.execute("INSERT INTO users(id,email,name,pw_hash,created,role) VALUES(1,'a@test.ru','Teacher','x',0,'teacher')")
        self.con.execute('INSERT INTO tg_tokens VALUES(?,?,?)',(A.sha('link-token'),1,9999999999))
        update={'update_id':1,'message':{'chat':{'id':123,'type':'private'},'from':{'id':123},'text':'/start link-token'}}
        with patch.object(B.urllib.request,'urlopen',side_effect=AssertionError('Must not access Telegram outbound')):
            reply=self.deliver(update)
            self.assertEqual(reply['method'],'sendMessage')
            self.assertIn('Готово',reply['text'])
            self.assertEqual(self.con.execute('SELECT user_id FROM tg_links WHERE chat_id=123').fetchone()[0],1)
            self.assertEqual(self.deliver(update),reply)
    def test_auth_confirmation_inline_response(self):
        self.prepare();token=self.start('teacher')
        update={'update_id':2,'message':{'chat':{'id':123,'type':'private'},'from':{'id':123},'text':'/start auth_'+token}}
        reply=self.deliver(update);self.assertIn('reply_markup',reply)
        callback={'update_id':3,'callback_query':{'id':'cb','data':'auth:'+token,'from':{'id':123,'first_name':'Тест'},'message':{'chat':{'id':123,'type':'private'}}}}
        reply=self.deliver(callback);self.assertEqual(reply['method'],'answerCallbackQuery')
        self.poll(token);self.assertEqual(self.response[1]['user']['role'],'teacher')
    def test_secret_required(self):
        self.prepare();self.h.headers={}
        with self.assertRaises(A.ApiError):self.deliver({'update_id':5})
