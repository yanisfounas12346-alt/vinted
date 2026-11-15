"""Cotes traçables : saisie manuelle ou percentile de ventes confirmées."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from engine import money


def validate_reference(value):
    ref = {key:str(value.get(key, '')).strip() for key in ('reference','aliases','floor','checked_on','source')}
    if not ref['reference'] or not ref['aliases'] or len(ref['aliases']) > 2000:
        raise ValueError('Nom et alias précis obligatoires')
    money(ref['floor'])
    if money(ref['floor']) > 0:
        if not ref['source'] or not ref['checked_on']:
            raise ValueError('Une cote positive exige une source et une date de contrôle')
        if date.fromisoformat(ref['checked_on']) > date.today():
            raise ValueError('Date de contrôle dans le futur')
    ref['basis'] = str(value.get('basis') or 'manual')
    ref['sample_count'] = int(value.get('sample_count') or 0)
    return ref


def calibrate(rows, references):
    if not isinstance(rows, list):
        raise ValueError('Liste de ventes attendue')
    names = {r['reference']:dict(r) for r in references}
    grouped = {}
    for index, row in enumerate(rows, 1):
        if row.get('reference') not in names:
            raise ValueError(f'Vente {index} : référence inconnue (nom exact requis)')
        sold = row.get('sold')
        if str(sold).lower() not in ('true','1','oui'):
            raise ValueError(f'Vente {index} : sold doit confirmer une vente terminée')
        age = (date.today() - date.fromisoformat(row['sold_on'])).days
        if not 0 <= age <= 90:
            raise ValueError(f'Vente {index} : date hors des 90 derniers jours')
        if not str(row.get('source','')).strip() or not str(row.get('condition','')).strip():
            raise ValueError(f'Vente {index} : source et état précis obligatoires')
        price = money(row['price'])
        if price <= 0:
            raise ValueError('Prix de vente nul')
        grouped.setdefault(row['reference'], []).append((price,row))
    updates = []
    for name, items in grouped.items():
        if len(items) < 5:
            raise ValueError(f'{name} : au moins 5 ventes comparables requises')
        if len({x[1]['condition'].strip().lower() for x in items}) != 1:
            raise ValueError(f'{name} : séparer les états et configurations avant calibration')
        sources = [str(x[1]['source']).strip() for x in items]
        if len(set(sources)) != len(sources):
            raise ValueError(f'{name} : sources dupliquées, dédoublonner les ventes')
        prices = sorted(x[0] for x in items)
        position = Decimal(len(prices)-1)*Decimal('0.2')
        lower = int(position)
        value = Decimal(prices[lower]) + (position-lower)*(prices[min(lower+1,len(prices)-1)]-prices[lower])
        floor = int(value.quantize(Decimal('1'),rounding=ROUND_HALF_UP)) / 100
        ref = names[name] | dict(floor=str(floor),checked_on=date.today().isoformat(),
            source=f'P20 de {len(items)} ventes importées ; preuves conservées dans data/sales.json',
            basis='sold_p20',sample_count=len(items),condition=items[0][1]['condition'])
        updates.append(ref)
    if not updates:
        raise ValueError('Aucune vente à calibrer')
    return updates
