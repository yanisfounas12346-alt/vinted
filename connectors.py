"""Connecteurs réseau facultatifs, indépendants de l’interface."""
import os
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

def ebay_search(query):
    token = os.environ.get('EBAY_ACCESS_TOKEN', '').strip()
    if not token:
        raise ValueError('Définir EBAY_ACCESS_TOKEN avec un jeton OAuth eBay valide. Voir README.')
    params = urlencode(dict(q=query, limit=50, sort='newlyListed', filter='buyingOptions:{FIXED_PRICE},priceCurrency:EUR'))
    request = Request('https://api.ebay.com/buy/browse/v1/item_summary/search?' + params,
                      headers={'Authorization': 'Bearer ' + token, 'X-EBAY-C-MARKETPLACE-ID': 'EBAY_FR'})
    try:
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
    except HTTPError as e:
        raise ValueError(f'eBay HTTP {e.code} : vérifier accès, quota et expiration du jeton. Aucun nouvel essai automatique.') from None
    rows, skipped = [], 0
    for x in result.get('itemSummaries', []):
        shipping = x.get('shippingOptions', [])
        if x.get('price', {}).get('currency') != 'EUR' or not shipping or shipping[0].get('shippingCost', {}).get('currency') != 'EUR':
            skipped += 1
            continue
        rows.append(dict(id='ebay:' + x['itemId'], title=x['title'], description=x.get('condition', ''),
                         price=x['price']['value'], shipping=shipping[0]['shippingCost']['value'], buyer_fee='0',
                         seller_reviews=x.get('seller', {}).get('feedbackScore', 0), url=x.get('itemWebUrl', '')))
    return rows, skipped

