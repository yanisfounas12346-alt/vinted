"""Moteur local : règles explicables, montants en centimes, stockage SQLite."""
import csv
import json
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


def money(value):
    try:
        n = Decimal(str(value).replace(',', '.'))
        if not n.is_finite() or n < 0:
            raise ValueError('Montant négatif ou non fini')
        return int((n * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError('Montant invalide') from exc


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text).lower()) if not unicodedata.combining(c))


TOXIC = re.compile(r'\b(hs|pour pieces|ne s.allume pas|champignon|bloque|boite vide|contrefacon|reproduction|rayure lentille|non teste|defectueux)\b')


def load_rows(path):
    path = Path(path)
    if path.stat().st_size > 5_000_000:
        raise ValueError('Fichier trop volumineux (maximum 5 Mo)')
    if path.suffix.lower() == '.json':
        rows = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(rows, list):
            raise ValueError('JSON attendu : liste d’annonces normalisées')
    else:
        with path.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
    return rows


def evaluate(item, references, config, cash):
    text = norm(item.get('title', '') + ' ' + item.get('description', ''))
    reasons = []
    match = [r for r in references if any(re.search(r'(?<!\w)' + re.escape(norm(a.strip())) + r'(?!\w)', text)
             for a in r['aliases'].split('|') if a.strip())]
    cost = money(item['price']) + money(item['shipping']) + money(item['buyer_fee'])
    if len(match) != 1:
        return {'status': 'À vérifier', 'reason': 'Référence absente ou ambiguë', 'floor': 0, 'margin': 0, 'cost': cost}
    ref = match[0]
    cost = money(item['price']) + money(item['shipping']) + money(item['buyer_fee'])
    floor = money(ref['floor'])
    fees = money(ref['floor']) * Decimal(str(config['sale_fee_rate']))
    tax = floor * Decimal(str(config['turnover_reserve_rate']))
    margin = floor - cost - int(fees + tax) - money(config['sale_shipping']) - money(config['packaging']) - money(config['risk_reserve'])
    if TOXIC.search(text):
        reasons.append('Défaut / authenticité / test à vérifier')
    if int(item.get('seller_reviews') or 0) < 3:
        reasons.append('Moins de 3 avis vendeur : contrôle nécessaire')
    try:
        age = (date.today() - date.fromisoformat(ref['checked_on'])).days
        valid = 0 <= age <= 30 and bool(ref.get('source')) and floor > 0
    except (ValueError, KeyError):
        valid = False
    if not valid:
        reasons.append('Cote non documentée ou âgée de plus de 30 jours')
    if margin < money(config['min_margin']):
        reasons.append('Marge insuffisante')
    if cost > min(money(config['max_position']), cash):
        reasons.append('Budget dépassé (frais inclus)')
    if money(item['price']) * 2 > floor:
        reasons.append('Prix supérieur à 50 % de la cote')
    return {'status': 'À vérifier' if reasons else 'Alerte', 'reason': ' ; '.join(reasons) or 'Critères remplis — inspection humaine requise',
            'floor': floor, 'margin': margin, 'cost': cost}


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('CREATE TABLE IF NOT EXISTS listings (id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT "repéré", cost INTEGER, bought_on TEXT, proceeds INTEGER, sold_on TEXT)')
        self.db.commit()

    def ingest(self, rows):
        # Valider tout le lot avant d’écrire : aucun import partiel silencieux.
        clean = []
        for index, row in enumerate(rows, 1):
            required = ('id', 'title', 'price', 'shipping', 'buyer_fee')
            if not isinstance(row, dict) or any(str(row.get(k, '')).strip() == '' for k in required):
                raise ValueError(f'Ligne {index} : champs obligatoires {required}')
            for k in ('price', 'shipping', 'buyer_fee'):
                money(row[k])
            if int(row.get('seller_reviews') or 0) < 0:
                raise ValueError('Nombre d’avis invalide')
            row = dict(row)
            row['id'] = str(row['id'])
            clean.append(row)
        count = 0
        with self.db:
            for row in clean:
                old = self.db.execute('SELECT status FROM listings WHERE id=?', (row['id'],)).fetchone()
                if old is None:
                    self.db.execute('INSERT INTO listings(id,payload) VALUES (?,?)', (row['id'], json.dumps(row, ensure_ascii=False)))
                    count += 1
                elif old['status'] == 'repéré':
                    self.db.execute('UPDATE listings SET payload=? WHERE id=?', (json.dumps(row, ensure_ascii=False), row['id']))
        return count

    def rows(self):
        return self.db.execute('SELECT * FROM listings ORDER BY rowid DESC').fetchall()

    def cash(self, initial):
        return money(initial) - sum((r['cost'] or 0) for r in self.rows() if r['status'] in ('acheté', 'vendu')) + sum((r['proceeds'] or 0) for r in self.rows() if r['status'] == 'vendu')

    def buy(self, item_id, cost, config):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT * FROM listings WHERE id=?', (item_id,)).fetchone()
            if not row or row['status'] != 'repéré':
                raise ValueError('Cet objet est déjà enregistré comme acheté ou vendu')
            if cost < 0 or cost > min(self.cash(config['initial_capital']), money(config['max_position'])):
                raise ValueError('Capital disponible ou plafond par objet insuffisant')
            self.db.execute('UPDATE listings SET status="acheté",cost=?,bought_on=? WHERE id=?', (cost, datetime.now(timezone.utc).isoformat(), item_id))

    def sell(self, item_id, proceeds):
        with self.db:
            cursor = self.db.execute('UPDATE listings SET status="vendu",proceeds=?,sold_on=? WHERE id=? AND status="acheté"', (proceeds, datetime.now(timezone.utc).isoformat(), item_id))
            if cursor.rowcount != 1:
                raise ValueError('Il faut d’abord enregistrer l’achat')
