"""Moteur local : règles explicables, montants en centimes, stockage SQLite."""
import csv
import json
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timezone
from contextlib import closing
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


GAME_DERIVATIVES = re.compile(
    r"\b(poster|posters|affiche|affiches|guide|guides|livre|livres|manga|amiibo|figurine|figurines|"
    r"peluche|peluches|sticker|stickers|autocollant|autocollants|mug|tapis|coussin|tableau|"
    r"t-shirt|tee-shirt|t shirt|vetement|porte-cle|porte-cles|porte cle|porte cles|soundtrack|ost)\b"
)


def product_type_conflict(item, reference):
    """Le nom d’un jeu sur un produit dérivé ne suffit pas à identifier sa cartouche."""
    research_id = reference.get('research', {}).get('id')
    is_game = reference.get('category') == 'Jeux Switch' or isinstance(research_id, int) and 1 <= research_id <= 20
    if not is_game:
        return None
    title = norm(item.get('title', ''))
    hit = GAME_DERIVATIVES.search(title)
    if hit:
        explicit_game = re.search(r'\b(jeu|cartouche)\b', title)
        # Un véritable jeu peut inclure un bonus ; un poster qui mentionne « jeu » reste exclu.
        bonus = re.search(r'(?:avec|inclus|incluse|offert|bonus|\+)\s+(?:un |une |le |la )?' + re.escape(hit.group()) + r'\b', title)
        if not (explicit_game and bonus and explicit_game.start() < hit.start()):
            return f'Objet différent : {hit.group()} / produit dérivé, pas le jeu physique recherché'
    description = norm(item.get('description', '')).strip()
    if not re.search(r'\b(jeu|cartouche)\b', title) and GAME_DERIVATIVES.match(description):
        return 'Objet différent : la description identifie un produit dérivé, pas une cartouche'
    return None


def evaluate(item, references, config, cash, profile=None):
    text = norm(str(item.get('title', '')) + ' ' + str(item.get('description', '')))
    price = money(item['price'])
    known_costs = all(item.get(k) is not None and str(item[k]).strip() != '' for k in ('shipping', 'buyer_fee'))
    cost = price + sum(money(item[k]) for k in ('shipping', 'buyer_fee') if item.get(k) not in (None, ''))
    match = [r for r in references if any(re.search(r'(?<!\w)' + re.escape(norm(a.strip())) + r'(?!\w)', text)
             for a in r['aliases'].split('|') if a.strip())]
    # Garder l’alias le plus spécifique en cas de chevauchement (New 3DS XL / 3DS XL).
    if len(match) > 1:
        lengths = [(max((len(norm(a.strip())) for a in r['aliases'].split('|') if norm(a.strip()) in text), default=0), r) for r in match]
        largest = max(n for n, _ in lengths)
        match = [r for n, r in lengths if n == largest]
    result = dict(status='À vérifier', reason='', floor=0, margin=None, cost=cost, costs_known=known_costs, reference=None, candidate=False)
    reasons = []
    if not known_costs:
        reasons.append('Port et/ou protection acheteur inconnus : compléter la fiche')
    if len(match) != 1:
        result['reason'] = 'Référence absente ou ambiguë' + (' ; ' + ' ; '.join(reasons) if reasons else '')
        return result
    ref = match[0]
    result['reference'] = ref.get('reference')
    conflict = product_type_conflict(item, ref)
    if conflict:
        result.update(status='Exclu', reason=conflict)
        return result
    if any(re.search(r'(?<!\w)'+re.escape(norm(term))+r'(?!\w)',text) for term in ref.get('forbidden_terms',[])):
        result['reason']='Version, contenu ou état incompatible avec cette fiche de prix'
        return result
    if ref.get('research'):
        from pricing import quote, DEFAULT_PROFILE
        forecast=quote(ref,profile or DEFAULT_PROFILE,cash,item)
        result.update(floor=forecast['resale'], margin=forecast['margin'],cost=forecast['purchase_total'],
            costs_known=not forecast['estimated_costs'],forecast=forecast,estimate_only=not forecast['resale_is_verified'])
        try:
            age=(date.today()-date.fromisoformat(ref.get('checked_on',''))).days
        except ValueError:
            age=9999
        valid=forecast['resale_is_verified'] and 0<=age<=30 and bool(ref.get('source'))
        if not valid:reasons.append('Estimation documentée provisoire : ventes comparables insuffisantes pour une cote validée')
        if forecast['estimated_costs']:reasons.append('Livraison et frais d’achat estimés, à confirmer au paiement')
        if TOXIC.search(text):reasons.append('Défaut / authenticité à contrôler')
        if int(item.get('seller_reviews') or 0)<3:reasons.append('Avis positifs du vendeur à contrôler')
        if item.get('condition_confirmed') is not True:reasons.append('État, version et accessoires à valider')
        if not forecast['can_buy']:reasons.append('Modèle suspendu ou marge insuffisante dans ce scénario de livraison')
        if price>forecast['cap_price'] or forecast['purchase_total']>forecast['cap_total']:
            reasons.append('Prix au-dessus du plafond frais compris')
        result['candidate']=bool(forecast['can_buy'] and forecast['cap_price']>0 and price<=forecast['cap_price'] and not TOXIC.search(text))
        result['status']='Alerte' if not reasons else 'À vérifier'
        result['reason']=' ; '.join(dict.fromkeys(reasons)) or 'Critères remplis, disponibilité à vérifier avant achat'
        return result
    floor = money(ref['floor'])
    result['floor'] = floor
    try:
        age = (date.today() - date.fromisoformat(ref['checked_on'])).days
        valid = 0 <= age <= 30 and bool(ref.get('source')) and floor > 0
    except (ValueError, KeyError):
        valid = False
    if not valid:
        reasons.append('Cote à documenter ou âgée de plus de 30 jours')
    if TOXIC.search(text):
        reasons.append('Défaut / authenticité / test à vérifier')
    if int(item.get('seller_reviews') or 0) < 3:
        reasons.append('Avis positifs du vendeur à vérifier (minimum 3)')
    if item.get('condition_confirmed') is not True:
        reasons.append('État et authenticité non validés')
    if floor and known_costs:
        fees = Decimal(floor) * (Decimal(str(config['sale_fee_rate'])) + Decimal(str(config['turnover_reserve_rate'])))
        margin = floor - cost - int(fees.quantize(Decimal('1'), rounding=ROUND_HALF_UP)) - sum(money(config[k]) for k in ('sale_shipping', 'packaging', 'risk_reserve'))
        result['margin'] = margin
        if margin < money(config['min_margin']):
            reasons.append('Marge insuffisante')
    if cost > min(money(config['max_position']), cash):
        reasons.append('Budget dépassé (frais connus inclus)')
    if price * 2 > floor:
        reasons.append('Prix supérieur à 50 % de la cote')
    result['candidate'] = valid and price * 2 <= floor and not TOXIC.search(text) and price <= min(money(config['max_position']), cash)
    result['status'] = 'À vérifier' if reasons else 'Alerte'
    result['reason'] = ' ; '.join(reasons) or 'Critères remplis — vérifier encore la disponibilité avant paiement'
    return result


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('CREATE TABLE IF NOT EXISTS listings (id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT "repéré", cost INTEGER, bought_on TEXT, proceeds INTEGER, sold_on TEXT)')
        self.db.commit()

    def close(self):
        self.db.close()

    def ingest(self, rows):
        # Valider tout le lot avant d’écrire : aucun import partiel silencieux.
        clean = []
        for index, row in enumerate(rows, 1):
            required = ('id', 'title', 'price')
            if not isinstance(row, dict) or any(str(row.get(k, '')).strip() == '' for k in required):
                raise ValueError(f'Ligne {index} : champs obligatoires {required}')
            money(row['price'])
            for k in ('shipping', 'buyer_fee'):
                if row.get(k) not in (None, ''):
                    money(row[k])
                else:
                    row[k] = None
            if not isinstance(row.get('title'),str) or not isinstance(row.get('description',''),str):
                raise ValueError('Titre et description doivent être du texte')
            if int(row.get('seller_reviews') or 0) < 0:
                raise ValueError('Nombre d’avis invalide')
            row = dict(row)
            if 'condition_confirmed' in row and not isinstance(row['condition_confirmed'],bool):
                row['condition_confirmed'] = str(row['condition_confirmed']).lower() in ('true','1','oui')
            row['id'] = str(row['id'])
            clean.append(row)
        count = 0
        with self.db:
            for row in clean:
                old = self.db.execute('SELECT status,payload FROM listings WHERE id=?', (row['id'],)).fetchone()
                if old is None:
                    self.db.execute('INSERT INTO listings(id,payload) VALUES (?,?)', (row['id'], json.dumps(row, ensure_ascii=False)))
                    count += 1
                elif old['status'] == 'repéré':
                    previous = json.loads(old['payload'])
                    locked = previous.get('_verified_fields', [])
                    if money(previous['price']) != money(row['price']):
                        locked = [k for k in locked if k not in ('buyer_fee','shipping')]
                    for key in locked:
                        row[key] = previous.get(key)
                    row['_verified_fields'] = locked
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

    def patch(self, item_id, values):
        row = self.db.execute('SELECT * FROM listings WHERE id=?', (item_id,)).fetchone()
        if not row or row['status'] != 'repéré':
            raise ValueError('Seules les annonces non achetées sont modifiables')
        item = json.loads(row['payload'])
        allowed = ('shipping', 'buyer_fee', 'seller_reviews', 'condition_confirmed', 'description')
        locked = set(item.get('_verified_fields', []))
        for key in allowed:
            if key not in values:
                continue
            value = values[key]
            if key in ('shipping','buyer_fee'):
                if value not in ('', None):
                    money(value)
                else:
                    value = None
            elif key == 'seller_reviews':
                value = int(value) if value not in ('', None) else None
                if value is not None and value < 0:
                    raise ValueError('Avis invalides')
            elif key == 'condition_confirmed':
                if not isinstance(value, bool):
                    raise ValueError('Confirmation invalide')
            elif not isinstance(value, str) or len(value) > 12000:
                raise ValueError('Description trop longue')
            item[key] = value
            locked.add(key)
        item['_verified_fields'] = sorted(locked)
        with self.db:
            self.db.execute('UPDATE listings SET payload=? WHERE id=?', (json.dumps(item, ensure_ascii=False), item_id))
