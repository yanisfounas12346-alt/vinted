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
from scanner import Scanner
from valuation import validate_reference, calibrate
from contextlib import closing
from datetime import datetime, timezone
import os
import time
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
        self.lock = threading.RLock()
        self.ebay_token = os.environ.get('EBAY_ACCESS_TOKEN', '').strip()
        self.events = []
        self.bridge_last = None
        self.bridge_count = 0
        self.local_url = ''
        secret = self.directory / 'bridge-secret.txt'
        if not secret.exists():
            secret.write_text(secrets.token_urlsafe(32))
            try: secret.chmod(0o600)
            except OSError: pass
        self.bridge_token = secret.read_text().strip()
        self.scanner = Scanner(self.ingest_real, self.log, lambda:self.ebay_token)

    def store(self):
        return Store(self.directory / ('demo.sqlite3' if self.demo else 'portfolio.sqlite3'))

    def references(self):
        path = self.directory / 'references.json'
        rows = json.loads(path.read_text(encoding='utf-8')) if not self.demo and path.exists() else load_rows(BASE / ('references_demo.csv' if self.demo else 'references.csv'))
        if self.demo:
            for row in rows:
                row['checked_on'] = date.today().isoformat()
        return rows

    def state(self, store):
        cash = store.cash(self.config['initial_capital'])
        rows = []
        invested, profit = 0, 0
        references = self.references()
        for row in store.rows():
            item = json.loads(row['payload'])
            result = evaluate(item, references, self.config, cash)
            if row['status'] == 'acheté':
                invested += row['cost']
            if row['status'] == 'vendu':
                profit += row['proceeds'] - row['cost']
            rows.append(dict(row) | {'item': item, 'analysis': result})
        return dict(demo=self.demo, cash=cash, invested=invested, profit=profit, rows=rows,
                    config=self.config, references=references, ebay_ready=bool(self.ebay_token), scanner=self.scanner.snapshot(),
                    events=list(self.events[-30:]), bridge=dict(last_seen=self.bridge_last, received=self.bridge_count), version='0.3')

    def log(self, message, level='info'):
        with self.lock:
            self.events.append(dict(time=datetime.now(timezone.utc).isoformat(),message=str(message)[:500],level=level))
            self.events = self.events[-100:]

    def ingest_real(self, rows, event=None):
        with self.lock:
            if event and event.is_set():
                return 0
            with closing(Store(self.directory / 'portfolio.sqlite3')) as store:
                count = store.ingest(rows)
            return count

    def write_json(self, name, value):
        path = self.directory / name
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(path)

    def dispatch(self, action, payload):
        with self.lock:
            if action == 'mode':
                if not isinstance(payload.get('demo'), bool):
                    raise ValueError('Mode invalide')
                if self.scanner.snapshot()['running']:
                    raise ValueError('Arrêter la surveillance avant de changer de mode')
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
                elif action == 'patch':
                    store.patch(str(payload['id']),payload['values'])
                elif action == 'scan_start':
                    if self.demo:
                        raise ValueError('La surveillance réelle est indisponible en simulation')
                    self.scanner.start(payload['jobs'],payload.get('interval',90))
                    self.log('Surveillance réelle démarrée ; une recherche à la fois.')
                elif action == 'scan_stop':
                    self.scanner.stop()
                elif action == 'connection_info':
                    return dict(url=self.local_url,token=self.bridge_token,ebay_ready=bool(self.ebay_token))
                elif action == 'ebay_token':
                    token = str(payload.get('token','')).strip()
                    if len(token)>10000 or any(c in token for c in ('\r','\n')):
                        raise ValueError('Jeton invalide')
                    self.ebay_token = token
                    self.log('Jeton eBay mis à jour en mémoire uniquement.')
                elif action == 'reference_save':
                    if self.demo: raise ValueError('Revenir au réel pour modifier les cotes')
                    ref = validate_reference(payload)
                    refs = self.references()
                    refs = [r for r in refs if r['reference'] != ref['reference']] + [ref]
                    self.write_json('references.json',refs)
                    self.log('Cote enregistrée : '+ref['reference'])
                elif action == 'calibrate':
                    if self.demo: raise ValueError('Revenir au réel pour calibrer les cotes')
                    text = payload['text'].lstrip('\ufeff')
                    sales = json.loads(text) if payload.get('format')=='json' else list(csv.DictReader(io.StringIO(text)))
                    updates = calibrate(sales,self.references())
                    names = {r['reference'] for r in updates}
                    evidence_path=self.directory / 'sales.json'
                    previous=json.loads(evidence_path.read_text(encoding='utf-8')) if evidence_path.exists() else []
                    self.write_json('sales.json',previous+sales)
                    self.write_json('references.json',[r for r in self.references() if r['reference'] not in names]+updates)
                    self.log(f'Calibration P20 : {len(updates)} référence(s), ventes fournies par l’utilisateur.')
                elif action == 'bridge':
                    if not isinstance(payload.get('rows'),list) or len(payload['rows'])>500:
                        raise ValueError('Lot navigateur invalide (maximum 500)')
                    if payload.get('error'):
                        self.log('Pont suspendu : '+str(payload['error'])[:350], 'error')
                        return dict(received=0,new=0)
                    normalized=[]
                    for row in payload['rows']:
                        url=urlparse(str(row.get('url','')))
                        host=url.hostname or ''
                        source='vinted' if host in ('www.vinted.fr','vinted.fr') else 'leboncoin' if host in ('www.leboncoin.fr','leboncoin.fr') else None
                        if not source or url.scheme!='https' or not str(row.get('id','')).startswith(source+':'):
                            raise ValueError('Annonce hors des sources Vinted/Leboncoin autorisées')
                        normalized.append(dict(id=str(row['id']),title=str(row['title'])[:500],price=row['price'],
                            url=str(row['url'])[:2000],image_url=str(row.get('image_url',''))[:2000],
                            description=str(row.get('description',''))[:12000],shipping=None,buyer_fee=None,
                            seller_reviews=None,condition_confirmed=False,source=source,collected_via='browser_bridge'))
                    count=self.ingest_real(normalized)
                    self.bridge_last=datetime.now(timezone.utc).isoformat()
                    self.bridge_count+=len(normalized)
                    self.log(f'Pont navigateur : {len(normalized)} reçue(s), {count} nouvelle(s).')
                    return dict(received=len(normalized),new=count)
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
                    rows, skipped = ebay_search(query, self.ebay_token)
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
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://*.vinted.net https://*.vinted.fr https://*.leboncoin.fr https://*.ebayimg.com https://*.lbcimg.fr; connect-src 'self'; frame-ancestors 'none'")
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
            bridge = urlparse(self.path).path == '/api/bridge'
            valid_token = secrets.compare_digest(self.headers.get('X-Bridge-Token',''), dashboard.bridge_token) if bridge else secrets.compare_digest(self.headers.get('X-Session-Token',''),token)
            if not self.valid_host() or not valid_token:
                return self.send(403, {'error': 'Session locale invalide'})
            origin = self.headers.get('Origin')
            if origin and origin != f'http://127.0.0.1:{self.server.server_port}' and not (bridge and origin.startswith('chrome-extension://')):
                return self.send(403, {'error': 'Origine refusée'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 5_000_000:
                    raise ValueError('Requête vide ou supérieure à 5 Mo')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload,dict):
                    raise ValueError('Objet JSON attendu')
                action = urlparse(self.path).path.removeprefix('/api/')
                state = dashboard.dispatch(action, payload)
                self.send(200, state)
            except (ValueError, KeyError, TypeError) as exc:
                self.send(400, {'error': str(exc)})
            except Exception:
                self.send(500, {'error': 'Action impossible. Vérifier les données et réessayer.'})
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    dashboard.local_url = f'http://127.0.0.1:{server.server_port}'
    return server

if __name__ == '__main__':
    try:
        server = make_server(port=8765)
    except OSError:
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
