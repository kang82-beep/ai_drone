"""Serve the web console with a small API over the site history database.

  python serve_console.py            # http://127.0.0.1:8765

Opened from this server, the console issues work orders and stores field results in
results/history.db. Opened as a file (web/index.html) it still works, but results stay
in that browser only. Only this PC can reach the server (127.0.0.1).
"""
import argparse
import json
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pv_inspector import history

ROOT = Path(__file__).resolve().parent
LOCK = threading.Lock()  # one writer at a time on the SQLite file


class Handler(SimpleHTTPRequestHandler):
    db_path = None
    flight_id = None

    def log_message(self, fmt, *args):  # keep the console quiet except for errors
        if not str(args[1] if len(args) > 1 else '').startswith(('2', '3')):
            super().log_message(fmt, *args)

    def send_json(self, value, code=200):
        body = json.dumps(value, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        length = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(length) or b'{}')

    def do_GET(self):
        if self.path.startswith('/api/'):
            return self.api('GET')
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith('/api/'):
            return self.send_json({'error': 'not found'}, 404)
        return self.api('POST')

    def api(self, method):
        try:
            with LOCK:
                db = history.connect(self.db_path)
                try:
                    return self.route(db, method)
                finally:
                    db.close()
        except (KeyError, ValueError) as error:
            return self.send_json({'error': str(error)}, 400)

    def route(self, db, method):
        path = self.path.split('?')[0]
        if method == 'GET' and path == '/api/health':
            return self.send_json({'ok': True, 'flight_id': self.flight_id})
        if method == 'GET' and path == '/api/snapshot':
            return self.send_json(history.snapshot(db, self.flight_id))
        data = self.body() if method == 'POST' else {}
        match = re.fullmatch(r'/api/orders/([^/]+)/status', path)
        if method == 'POST' and match:
            history.set_status(db, match[1], data['status'], data.get('actor', ''), data.get('note', ''))
            return self.send_json(history.snapshot(db, self.flight_id))
        match = re.fullmatch(r'/api/orders/([^/]+)/remove', path)
        if method == 'POST' and match:
            history.remove_module(db, match[1], data['module_id'], data.get('actor', ''))
            return self.send_json(history.snapshot(db, self.flight_id))
        if method == 'POST' and path == '/api/results':
            history.save_result(db, data['order_id'], data['module_id'],
                                **{k: v for k, v in data.items() if k not in ('order_id', 'module_id')})
            return self.send_json(history.snapshot(db, self.flight_id))
        if method == 'POST' and path == '/api/manual':
            history.add_manual(db, self.flight_id, data['module_id'], data.get('actor', ''))
            return self.send_json(history.snapshot(db, self.flight_id))
        return self.send_json({'error': 'not found'}, 404)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', default=str(ROOT / 'results' / 'history.db'))
    parser.add_argument('--flight', help='표시할 비행 (기본: 가장 최근에 가져온 비행)')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    db = history.connect(args.db)
    flight = args.flight or (db.execute('SELECT flight_id FROM flights ORDER BY flight_id DESC LIMIT 1').fetchone() or [None])[0]
    db.close()
    if not flight:
        raise SystemExit('이력 DB에 비행이 없습니다. 먼저 python run_flight.py 를 실행하세요.')
    Handler.db_path, Handler.flight_id = args.db, flight
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(ROOT / 'web')))
    print(f'웹 관제: http://127.0.0.1:{args.port}  (비행 {flight}, 종료: Ctrl+C)', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
