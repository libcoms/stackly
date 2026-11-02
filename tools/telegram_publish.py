#!/usr/bin/env python3
"""Publish one approved caption + image daily to the configured Telegram channel.
Secrets are read from environment / ignored .env; never accepted as CLI arguments.
A delivery receipt is written before sending, so uncertain network outcomes never auto-duplicate.
"""
import argparse, datetime as dt, json, os, pathlib, secrets, sys, urllib.request, urllib.error
ROOT = pathlib.Path(__file__).resolve().parents[1]
MSK = dt.timezone(dt.timedelta(hours=3))

def config():
    values = {}
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1); values[k.strip()] = v.strip().strip('\"\'')
    values.update(os.environ)
    return values

def request(method, data=None, binary=None, content_type=None):
    cfg=config();token=cfg.get('STACKLY_TG_TOKEN') or cfg.get('TOKEN')
    if not token: raise RuntimeError('Telegram token is not configured')
    req=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,
        data=binary if binary is not None else json.dumps(data or {}).encode(),
        headers={'Content-Type':content_type or 'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=40) as r: result=json.load(r)
    except urllib.error.HTTPError as e:
        # Do not log e or its URL: it contains the credential.
        raise RuntimeError('Telegram rejected the request (HTTP '+str(e.code)+')') from None
    except Exception:
        raise RuntimeError('Telegram network request failed; token redacted') from None
    if not result.get('ok'): raise RuntimeError('Telegram API rejected request')
    return result['result']

def publish(channel, caption_path, image_path, day, dry_run=False):
    caption=pathlib.Path(caption_path).read_text(encoding='utf-8-sig').strip()
    if not caption or len(caption)>1024: raise ValueError('Photo caption must contain 1–1024 characters')
    image=pathlib.Path(image_path)
    if image.suffix.lower() not in ('.png','.jpg','.jpeg'): raise ValueError('Use a PNG or JPEG cover')
    if not image.is_file() or image.stat().st_size>10*1024*1024: raise ValueError('Image missing or exceeds 10 MB')
    if dry_run: return {'dry_run':True,'date':day,'channel':channel,'caption_chars':len(caption),'image':str(image)}
    if day != dt.datetime.now(MSK).date().isoformat(): raise ValueError('Publish only for the current Moscow date')
    state=ROOT/'marketing'/'.delivery';state.mkdir(exist_ok=True)
    receipt=state/(day+'.json')
    payload={'date':day,'channel':channel,'status':'sending','caption_file':str(caption_path),'image_file':str(image)}
    with receipt.open('x',encoding='utf-8') as f: json.dump(payload,f,ensure_ascii=False)
    boundary='stackly-'+secrets.token_hex(16);parts=[]
    for k,v in {'chat_id':channel,'caption':caption}.items():
        parts.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+k+'"\r\n\r\n'+v+'\r\n').encode())
    mime='image/png' if image.suffix.lower()=='.png' else 'image/jpeg'
    parts.extend([('--'+boundary+'\r\nContent-Disposition: form-data; name="photo"; filename="cover'+image.suffix.lower()+'"\r\nContent-Type: '+mime+'\r\n\r\n').encode(),image.read_bytes(),('\r\n--'+boundary+'--\r\n').encode()])
    try:
        result=request('sendPhoto',binary=b''.join(parts),content_type='multipart/form-data; boundary='+boundary)
    except Exception:
        payload['status']='uncertain';receipt.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8');raise
    payload.update(status='sent',message_id=result['message_id']);receipt.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    return payload

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['check','publish'])
    parser.add_argument('--channel',default='@stacklyai');parser.add_argument('--post');parser.add_argument('--image')
    parser.add_argument('--date',default=dt.datetime.now(MSK).date().isoformat());parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    try:
        if args.action=='check':
            me=request('getMe');chat=request('getChat',{'chat_id':args.channel});member=request('getChatMember',{'chat_id':args.channel,'user_id':me['id']})
            result={'bot':me['username'],'channel':chat.get('username'),'type':chat['type'],'status':member['status'],'can_post_messages':member.get('can_post_messages',False)}
        else: result=publish(args.channel,args.post,args.image,args.date,args.dry_run)
        print(json.dumps(result,ensure_ascii=False))
    except Exception as e:
        print(type(e).__name__+': '+str(e),file=sys.stderr);sys.exit(1)
if __name__=='__main__':main()
