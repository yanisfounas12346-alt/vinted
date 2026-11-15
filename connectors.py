"""Collecte réelle. Aucun contournement ni enregistrement de cookies utilisateur."""
import json
import os
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, build_opener, HTTPCookieProcessor, urlopen
from engine import money

class SourceError(ValueError):
    pass


def request_json(url, headers=None, opener=None):
    try:
        response = (opener.open if opener else urlopen)(Request(url, headers=headers or {}), timeout=18)
        with response:
            raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise SourceError('Réponse trop volumineuse. Collecte suspendue.')
            data = json.loads(raw)
        if not isinstance(data, dict):
            raise SourceError('Format de réponse inattendu. Collecte suspendue.')
        return data
    except HTTPError as exc:
        if exc.code in (401,403,429):
            raise SourceError(f'HTTP {exc.code} : accès refusé, jeton expiré ou limite atteinte. Source suspendue, aucun contournement. Utiliser le pont navigateur pour les annonces visibles.') from None
        raise SourceError(f'HTTP {exc.code}. Source suspendue ; réessayer manuellement plus tard.') from None
    except (URLError, TimeoutError, OSError):
        raise SourceError('Connexion indisponible ou délai dépassé. Source suspendue ; vérifier le réseau.') from None
    except (json.JSONDecodeError, UnicodeError):
        raise SourceError('Réponse non JSON : interface modifiée ou page de vérification. Source suspendue.') from None


def normalize_vinted(data):
    if not isinstance(data.get('items'), list):
        raise SourceError('Vinted : liste items absente. Le schéma a changé ; source suspendue.')
    rows, skipped = [], 0
    for item in data['items']:
        try:
            price = item.get('price') or {}
            if price.get('currency_code', price.get('currency')) != 'EUR':
                skipped += 1
                continue
            money(price['amount'])
            if item.get('id') is None or not isinstance(item.get('title'), str) or not item['title'].strip():
                raise ValueError()
            photo = item.get('photo') or {}
            rows.append(dict(id='vinted:'+str(item['id']), title=item['title'], price=str(price['amount']),
                shipping=None, buyer_fee=None, seller_reviews=None,
                description=item.get('description') or '', url=urljoin('https://www.vinted.fr/', str(item.get('url') or '/items/'+str(item['id']))),
                image_url=photo.get('full_size_url') or photo.get('url') or '', source='vinted',
                condition_confirmed=False, collected_via='catalogue'))
        except (KeyError, ValueError, TypeError, AttributeError):
            skipped += 1
    return rows, skipped


class VintedClient:
    def __init__(self):
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
    def search(self, query):
        params = urlencode(dict(search_text=query, page=1, per_page=40, order='newest_first', currency='EUR'))
        headers={'Accept':'application/json','User-Agent':'Repere-PC/0.3 (local price monitor)',
                 'Platform':'web','Origin':'https://www.vinted.fr','Referer':'https://www.vinted.fr/','Locale':'fr-FR'}
        return normalize_vinted(request_json('https://api.vinted.fr/svc-catalogue/items?'+params, headers, self.opener))


def ebay_search(query, token=None):
    token = token or os.environ.get('EBAY_ACCESS_TOKEN', '').strip()
    if not token:
        raise SourceError('eBay : ajouter un jeton OAuth dans Connexions avant de lancer la recherche.')
    params = urlencode(dict(q=query, limit=50, sort='newlyListed', filter='buyingOptions:{FIXED_PRICE},priceCurrency:EUR'))
    result = request_json('https://api.ebay.com/buy/browse/v1/item_summary/search?'+params,
        {'Authorization':'Bearer '+token,'X-EBAY-C-MARKETPLACE-ID':'EBAY_FR'})
    if not isinstance(result.get('itemSummaries', []), list):
        raise SourceError('eBay : format inattendu. Source suspendue.')
    rows, skipped = [], 0
    for item in result.get('itemSummaries', []):
        try:
            if item['price']['currency'] != 'EUR':
                skipped += 1
                continue
            shipping = item.get('shippingOptions') or []
            cost = shipping[0].get('shippingCost', {}) if shipping else {}
            amount = cost.get('value') if cost.get('currency') == 'EUR' else None
            money(item['price']['value'])
            # Feedback score n’est pas un nombre d’avis positifs : à vérifier.
            rows.append(dict(id='ebay:'+item['itemId'], title=item['title'], description=item.get('condition', ''),
                price=item['price']['value'], shipping=amount, buyer_fee=None, seller_reviews=None,
                seller_feedback_score=(item.get('seller') or {}).get('feedbackScore'),
                url=item.get('itemWebUrl', ''), image_url=(item.get('image') or {}).get('imageUrl', ''),
                source='ebay', condition_confirmed=False, collected_via='browse_api'))
        except (KeyError, ValueError, TypeError):
            skipped += 1
    return rows, skipped
