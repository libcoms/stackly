import importlib.util, json, pathlib, tempfile, unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('publisher',ROOT/'tools'/'telegram_publish.py')
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
class PublisherTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=pathlib.Path(self.tmp.name)
        (self.root/'marketing').mkdir();self.caption=self.root/'post.txt';self.caption.write_text('Полезный пост https://stackly.su',encoding='utf-8')
        self.image=self.root/'cover.png';self.image.write_bytes(b'PNG fixture')
        self.day=P.dt.datetime.now(P.MSK).date().isoformat()
        self.p=patch.object(P,'ROOT',self.root);self.p.start()
    def tearDown(self):self.p.stop();self.tmp.cleanup()
    def test_one_photo_and_duplicate_guard(self):
        with patch.object(P,'request',return_value={'message_id':42}) as send:
            result=P.publish('@stacklyai',self.caption,self.image,self.day)
            self.assertEqual(result['message_id'],42);self.assertEqual(send.call_args.args[0],'sendPhoto')
            with self.assertRaises(FileExistsError):P.publish('@stacklyai',self.caption,self.image,self.day)
            self.assertEqual(send.call_count,1)
    def test_uncertain_send_is_not_retried(self):
        with patch.object(P,'request',side_effect=RuntimeError('network')) as send:
            with self.assertRaises(RuntimeError):P.publish('@stacklyai',self.caption,self.image,self.day)
            with self.assertRaises(FileExistsError):P.publish('@stacklyai',self.caption,self.image,self.day)
            self.assertEqual(send.call_count,1)
        receipt=json.loads((self.root/'marketing'/'.delivery'/(self.day+'.json')).read_text())
        self.assertEqual(receipt['status'],'uncertain')
    def test_dry_run_never_sends(self):
        with patch.object(P,'request') as send:
            self.assertTrue(P.publish('@stacklyai',self.caption,self.image,self.day,True)['dry_run']);send.assert_not_called()
