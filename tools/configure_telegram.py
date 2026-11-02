#!/usr/bin/env python3
"""Apply only Telegram configuration from ignored .env to the existing stackly server.
Credential travels over SSH stdin, never as an argument or console output.
"""
import argparse, json, pathlib, secrets, shlex, subprocess, sys
from telegram_publish import config, request, ROOT
REMOTE = '''import sys,json,os,re,subprocess
values=json.load(sys.stdin)
p='/etc/stackly/stackly.env'
text=open(p,encoding='utf-8').read()
for k,v in values.items():
 if not re.fullmatch(r'[A-Za-z0-9_:/@.\\-]+',v): raise ValueError('Invalid configuration value')
 line=k+'='+v
 if re.search(r'^'+k+r'=.*$',text,re.M): text=re.sub(r'^'+k+r'=.*$',lambda m:line,text,flags=re.M)
 else:text=text.rstrip()+'\\n'+line+'\\n'
tmp=p+'.telegram-update'
fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text)
os.chmod(tmp,0o600);os.replace(tmp,p)
subprocess.run(['systemctl','restart','stackly-api','stackly-bot'],check=True)
print('Telegram configuration applied; credentials redacted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',required=True);p.add_argument('--identity',required=True);p.add_argument('--webhook',action='store_true')
 a=p.parse_args();c=config();token=c.get('STACKLY_TG_TOKEN') or c.get('TOKEN')
 if not token:raise SystemExit('Telegram token is missing')
 data={'STACKLY_TG_TOKEN':token,'STACKLY_TG_BOT':'stackly_ai','STACKLY_TG_CHANNEL_URL':'https://t.me/stacklyai'}
 if a.webhook:
  secret=c.get('STACKLY_TG_WEBHOOK_SECRET') or secrets.token_urlsafe(32)
  data['STACKLY_TG_WEBHOOK_SECRET']=secret
  envfile=ROOT/'.env';text=envfile.read_text(encoding='utf-8-sig')
  import re
  line='STACKLY_TG_WEBHOOK_SECRET='+secret
  text=re.sub(r'^STACKLY_TG_WEBHOOK_SECRET=.*$',lambda m:line,text,flags=re.M) if re.search(r'^STACKLY_TG_WEBHOOK_SECRET=',text,re.M) else text.rstrip()+'\n'+line+'\n'
  envfile.write_text(text,encoding='utf-8')
 cmd=['ssh','-i',a.identity,'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes',a.host,'python3 -c '+shlex.quote(REMOTE)]
 r=subprocess.run(cmd,input=json.dumps(data).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if r.returncode: print('Telegram server configuration failed; credentials redacted',file=sys.stderr);return 1
 print(r.stdout.decode().strip())
 if a.webhook:
  try:
   request('setWebhook', {'url':'https://stackly.su/api/tg/webhook','secret_token':secret,'allowed_updates':['message','callback_query'],'drop_pending_updates':False})
   info=request('getWebhookInfo')
   print(json.dumps({'webhook_enabled':info.get('url')=='https://stackly.su/api/tg/webhook','pending_update_count':info.get('pending_update_count',0)}))
  except Exception:
   print('Webhook setup failed; credentials redacted',file=sys.stderr);return 1
 return 0
if __name__=='__main__':sys.exit(main())
