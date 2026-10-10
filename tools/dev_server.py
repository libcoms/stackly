#!/usr/bin/env python3
"""Локальный просмотр сайта вместе с API — упрощённая замена nginx.

    python3 tools/dev_server.py        # затем откройте http://127.0.0.1:8000

Запускает app/stackly_api.py с базой в tools/.dev.db и раздаёт public/,
проксируя /api/* в API (как nginx на сервере).
"""
import http.server, os, subprocess, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, 'public')
API = 'http://127.0.0.1:8091'
PORT = 8000


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=PUBLIC, **k)

    def proxy(self, method):
        n = int(self.headers.get('Content-Length') or 0)
        req = urllib.request.Request(API + self.path, data=self.rfile.read(n) if n else None, method=method)
        for h in ('Content-Type', 'Cookie', 'Origin', 'User-Agent'):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])
        try:
            r = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            r = e
        data = r.read()
        self.send_response(r.status)
        for k, v in r.headers.items():
            if k.lower() in ('content-type', 'set-cookie', 'cache-control'):
                self.send_header(k, v)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith('/api/'):
            return self.proxy('GET')
        if not os.path.isfile(os.path.join(PUBLIC, self.path.split('?')[0].lstrip('/'))):
            self.path = '/index.html'          # как try_files в nginx
        super().do_GET()

    def do_POST(self): self.proxy('POST')
    def do_PUT(self): self.proxy('PUT')


def main():
    env = dict(os.environ, STACKLY_DB=os.path.join(ROOT, 'tools', '.dev.db'), STACKLY_PORT='8091',
               STACKLY_ORIGIN=f'http://127.0.0.1:{PORT}', STACKLY_COOKIE_SECURE='0')
    api = subprocess.Popen([sys.executable, os.path.join(ROOT, 'app', 'stackly_api.py')], env=env)
    time.sleep(0.5)
    print(f'Сайт: http://127.0.0.1:{PORT}  (Ctrl+C — остановить)')
    try:
        http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        api.terminate()


if __name__ == '__main__':
    main()
