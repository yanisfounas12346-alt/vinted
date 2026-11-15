"""Prévisions explicites : port achat/revente, commission sur port, plafonds par modèle."""
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
from engine import money
from datetime import date

D=Decimal
DEFAULT_PROFILE=dict(target_margin=10,activity_reserve_rate=.15,risk_rate=.05,ebay_fee_vat_rate=.20,
    ebay_regulatory_rate=.0035,ebay_fixed_fee=.35,buyer_fee_rate=.05,buyer_fee_fixed=.70,
    inbound_mode='shipped',carrier='mondial_relay',outbound_payer='buyer',max_position=33)
TARIFFS={
 'mondial_relay':[(250,4.15),(500,4.15),(1000,5.99),(2000,7.99),(3000,7.99),(4000,9.99)],
 'colissimo':[(250,5.49),(500,7.59),(750,9.29),(1000,9.59),(2000,11.19),(5000,17.39)]}


def rounded(value):
    return int(D(value).quantize(D('1'),rounding=ROUND_HALF_UP))


def tariff(weight_g,carrier):
    for limit,price in TARIFFS[carrier]:
        if weight_g<=limit:return money(price)
    raise ValueError('Poids hors grille tarifaire intégrée')


def validate_profile(values):
    result=DEFAULT_PROFILE | values
    for key in ('target_margin','ebay_fixed_fee','buyer_fee_fixed','max_position'):
        money(result[key])
    for key in ('activity_reserve_rate','risk_rate','ebay_fee_vat_rate','ebay_regulatory_rate','buyer_fee_rate'):
        number=D(str(result[key]))
        if not number.is_finite() or not 0<=number<=1:raise ValueError('Taux de frais invalide')
    if result['carrier'] not in TARIFFS or result['inbound_mode'] not in ('shipped','local') or result['outbound_payer'] not in ('buyer','seller'):
        raise ValueError('Mode de livraison invalide')
    return result


def quote(reference,profile,cash=10000,item=None):
    p=validate_profile(profile)
    research=reference.get('research',{})
    estimate=reference.get('resale_estimate')
    verified=money(reference.get('floor') or 0)
    resale=verified or (money(estimate) if estimate is not None else 0)
    weight=int(reference.get('packed_weight_g',500))
    postage=tariff(weight,p['carrier'])
    billed=postage if p['outbound_payer']=='buyer' else 0
    packaging=money(reference.get('packaging_eur',1))
    testing=money(reference.get('testing_eur',0))
    fixed=money(p['ebay_fixed_fee'])
    rate=D(str(reference.get('ebay_rate_ht',.09)))
    gross=resale+billed
    fees=rounded((D(gross)*(rate+D(str(p['ebay_regulatory_rate'])))+fixed)*(1+D(str(p['ebay_fee_vat_rate']))))
    reserve=rounded(D(gross)*D(str(p['activity_reserve_rate'])))
    risk=rounded(D(resale)*D(str(p['risk_rate'])))
    available=gross-postage-fees-reserve-risk-packaging-testing
    cap_total=max(0,min(money(p['max_position']),int(cash),available-money(p['target_margin']))) if resale else 0
    estimated_inbound=postage if p['inbound_mode']=='shipped' else 0
    raw_buyer_rate=D(str(p['buyer_fee_rate'])) if p['inbound_mode']=='shipped' else D(0)
    raw_buyer_fixed=money(p['buyer_fee_fixed']) if p['inbound_mode']=='shipped' else 0
    raw_cap=int((D(cap_total-estimated_inbound-raw_buyer_fixed)/(1+raw_buyer_rate)).quantize(D('1'),rounding=ROUND_FLOOR))
    try:fresh=0<=(date.today()-date.fromisoformat(research.get('reviewed_on',''))).days<=30
    except ValueError:fresh=False
    can_buy=bool((fresh or verified) and resale and raw_cap>0 and (verified or research.get('decision')!='suspendre'))
    item=item or dict(price=0,shipping=None,buyer_fee=None)
    price=money(item['price'])
    inbound_known=item.get('shipping') not in (None,'')
    fee_known=item.get('buyer_fee') not in (None,'')
    inbound=money(item['shipping']) if inbound_known else estimated_inbound
    buyer_fee=money(item['buyer_fee']) if fee_known else rounded(D(price)*raw_buyer_rate)+raw_buyer_fixed
    purchase_total=price+inbound+buyer_fee
    margin=available-purchase_total if resale else None
    # Le plafond affiché tient compte des frais réellement renseignés pour l’annonce.
    if fee_known:
        listing_cap=max(0,cap_total-inbound-buyer_fee)
    else:
        listing_cap=max(0,int((D(cap_total-inbound-raw_buyer_fixed)/(1+raw_buyer_rate)).quantize(D('1'),rounding=ROUND_FLOOR)))
    return dict(resale=resale,resale_is_verified=bool(verified),expected_gross=gross,
        outbound_shipping=postage,outbound_billed=billed,inbound_shipping=inbound,
        buyer_fee=buyer_fee,ebay_fees=fees,activity_reserve=reserve,risk_reserve=risk,
        packaging=packaging,testing=testing,purchase_total=purchase_total,
        margin=margin,cap_total=cap_total,cap_price=listing_cap,cap_price_standard=max(0,raw_cap),
        inbound_known=inbound_known,buyer_fee_known=fee_known,estimated_costs=not(inbound_known and fee_known),
        research_decision=research.get('decision','prudence'),can_buy=can_buy,data_fresh=fresh,
        carrier=p['carrier'],packed_weight_g=weight,target_margin=money(p['target_margin']),
        note='Prévision France ; poids emballé estimé ; port et frais Vinted à confirmer au paiement ; avant IR et charges fixes')
