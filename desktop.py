"""Tableau de bord navigateur, lié exclusivement à 127.0.0.1."""
import csv
import io
import json
import secrets
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from connectors import ebay_search
from engine import Store, evaluate, load_rows, money

BASE = Path(__file__).resolve().parent
DEFAULT = dict(initial_capital=100, max_position=33, min_margin=25, sale_fee_rate=0,
               turnover_reserve_rate=0, sale_shipping=0, packaging=1, risk_reserve=5)

class Dashboard:
    def __init__(self, data_dir=None):
        self.directory = Path(data_dir or BASE / 'data')
        self.directory.mkdir(exist_ok=True)
        path = self.directory / 'config.json'
        self.config = DEFAULT | (json.loads(path.read_text()) if path.exists() else {})
        self.demo = False
        self.lock = threading.Lock()

    def store(self):
        return Store(self.directory / ('demo.sqlite3' if self.demo else 'portfolio.sqlite3'))

    def references(self):
        rows = load_rows(BASE / ('references_demo.csv' if self.demo else 'references.csv'))
        if self.demo:
            for row in rows:
                row['checked_on'] = date.today().isoformat()
        return rows

    def state(self, store):
        cash = store.cash(self.config['initial_capital'])
        rows = []
        invested, profit = 0, 0
        for row in store.rows():
            item = json.loads(row['payload'])
            result = evaluate(item, self.references(), self.config, cash)
            if row['status'] == 'acheté':
                invested += row['cost']
            if row['status'] == 'vendu':
                profit += row['proceeds'] - row['cost']
            rows.append(dict(row) | {'item': item, 'analysis': result})
        return dict(demo=self.demo, cash=cash, invested=invested, profit=profit, rows=rows,
                    config=self.config, references=self.references(), ebay_ready=bool(__import__('os').environ.get('EBAY_ACCESS_TOKEN')))

    def dispatch(self, action, payload):
        with self.lock:
            if action == 'mode':
                if not isinstance(payload.get('demo'), bool):
                    raise ValueError('Mode invalide')
                self.demo = payload['demo']
            store = self.store()
            try:
                if action == 'mode' and self.demo:
                    store.ingest(load_rows(BASE / 'annonces_demo.csv'))
                elif action == 'import':
                    text = payload['text'].lstrip('\ufeff')
                    rows = json.loads(text) if payload.get('format') == 'json' else list(csv.DictReader(io.StringIO(text)))
                    if not isinstance(rows, list):
                        raise ValueError('Une liste d’annonces est attendue')
                    store.ingest(rows)
                elif action == 'buy':
                    store.buy(str(payload['id']), money(payload['amount']), self.config)
                elif action == 'sell':
                    store.sell(str(payload['id']), money(payload['amount']))
                elif action == 'ebay':
                    if self.demo:
                        raise ValueError('Passer en mode réel pour utiliser eBay')
                    query = str(payload.get('query', '')).strip()
                    if not query or len(query) > 200:
                        raise ValueError('Recherche invalide')
                    rows, skipped = ebay_search(query)
                    store.ingest(rows)
                elif action == 'settings':
                    config = {key: float(str(payload[key]).replace(',', '.')) for key in DEFAULT}
                    for value in config.values():
                        money(value)
                    if config['sale_fee_rate'] + config['turnover_reserve_rate'] > 1:
                        raise ValueError('Le total des taux doit être inférieur ou égal à 1')
                    if store.cash(config['initial_capital']) < 0:
                        raise ValueError('Capital incompatible avec les opérations')
                    path = self.directory / 'config.json'
                    temp = path.with_suffix('.tmp')
                    temp.write_text(json.dumps(config, indent=2))
                    temp.replace(path)
                    self.config = config
                elif action not in ('state', 'mode'):
                    raise ValueError('Action inconnue')
                return self.state(store)
            finally:
                store.db.close()


def make_server(dashboard=None, port=0):
    dashboard = dashboard or Dashboard()
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def send(self, status, data, mime='application/json; charset=utf-8'):
            body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {'error': 'Hôte refusé'})
            path = urlparse(self.path).path
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/style.css': ('style.css', 'text/css'), '/dashboard.js': ('dashboard.js', 'text/javascript')}
            if path not in files:
                return self.send(404, {'error': 'Introuvable'})
            filename, mime = files[path]
            data = (BASE / 'web' / filename).read_bytes()
            if filename == 'index.html':
                data = data.replace(b'__SESSION_TOKEN__', token.encode())
            self.send(200, data, mime)
        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-Session-Token') != token:
                return self.send(403, {'error': 'Session locale invalide'})
            origin = self.headers.get('Origin')
            if origin and origin != f'http://127.0.0.1:{self.server.server_port}':
                return self.send(403, {'error': 'Origine refusée'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 5_000_000:
                    raise ValueError('Requête vide ou supérieure à 5 Mo')
                payload = json.loads(self.rfile.read(length))
                action = urlparse(self.path).path.removeprefix('/api/')
                state = dashboard.dispatch(action, payload)
                self.send(200, state)
            except (ValueError, KeyError, TypeError) as exc:
                self.send(400, {'error': str(exc)})
            except Exception:
                self.send(500, {'error': 'Action impossible. Vérifier les données et réessayer.'})
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)

if __name__ == '__main__':
    server = make_server()
    url = f'http://127.0.0.1:{server.server_port}'
    print('REPÈRE — Tableau de bord local : ' + url, flush=True)
    print('Garder cette fenêtre ouverte. Ctrl+C pour arrêter.', flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
