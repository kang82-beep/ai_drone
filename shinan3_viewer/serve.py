"""Offline viewer server. No external network requests are needed."""
import argparse
import functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import webbrowser

parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=8765)
parser.add_argument('--no-browser',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parent
server=ThreadingHTTPServer(('127.0.0.1',args.port),functools.partial(SimpleHTTPRequestHandler,directory=str(root)))
url=f'http://127.0.0.1:{args.port}/'
print(f'Shinan 3 viewer: {url}',flush=True)
if not args.no_browser:webbrowser.open(url)
server.serve_forever()
