import json
import tempfile
import unittest
from datetime import date
from desktop import Dashboard
from engine import evaluate
from pricing import DEFAULT_PROFILE, quote, tariff, validate_profile


def reference():
    return dict(reference='Test',aliases='model test',floor='0',source='',checked_on='',resale_estimate=40,
        packed_weight_g=500,packaging_eur=1,testing_eur=0,ebay_rate_ht=.09,
        research=dict(reviewed_on=date.today().isoformat(),decision='prudence',status='indicatif'))

class PricingTests(unittest.TestCase):
    def test_postage_weight_boundaries(self):
        self.assertEqual(tariff(500,'mondial_relay'),415)
        self.assertEqual(tariff(501,'mondial_relay'),599)
        self.assertEqual(tariff(1001,'mondial_relay'),799)
        self.assertEqual(tariff(250,'colissimo'),549)
        self.assertEqual(tariff(251,'colissimo'),759)
    def test_ebay_fees_include_billed_shipping_and_vat(self):
        q=quote(reference(),DEFAULT_PROFILE)
        self.assertEqual(q['expected_gross'],4415)
        self.assertEqual(q['ebay_fees'],537)
        self.assertEqual(q['activity_reserve'],662)
        self.assertEqual(q['cap_total'],1501)
        self.assertEqual(q['cap_price_standard'],967)
    def test_price_cap_actually_meets_margin_after_both_shipping_legs(self):
        ref=reference();initial=quote(ref,DEFAULT_PROFILE)
        item=dict(price=initial['cap_price_standard']/100,shipping=None,buyer_fee=None)
        q=quote(ref,DEFAULT_PROFILE,item=item)
        self.assertGreaterEqual(q['margin'],q['target_margin'])
        self.assertLessEqual(q['purchase_total'],q['cap_total'])
        self.assertTrue(q['estimated_costs'])
    def test_free_outbound_shipping_lowers_cap_not_ignored(self):
        paid=quote(reference(),DEFAULT_PROFILE)
        free=quote(reference(),DEFAULT_PROFILE|{'outbound_payer':'seller'})
        self.assertEqual(free['outbound_billed'],0)
        self.assertEqual(free['outbound_shipping'],415)
        self.assertLess(free['cap_price'],paid['cap_price'])
    def test_actual_inbound_overrides_estimate_no_double_count(self):
        q=quote(reference(),DEFAULT_PROFILE,item=dict(price=10,shipping=2.78,buyer_fee=1.2))
        self.assertEqual(q['purchase_total'],1398)
        self.assertEqual(q['margin'],1103)
        self.assertFalse(q['estimated_costs'])
    def test_cash_and_global_position_cap(self):
        q=quote(reference(),DEFAULT_PROFILE,cash=900)
        self.assertLessEqual(q['cap_total'],900)
    def test_local_purchase_removes_inbound_and_protection_only(self):
        q=quote(reference(),DEFAULT_PROFILE|{'inbound_mode':'local'},item=dict(price=10,shipping=None,buyer_fee=None))
        self.assertEqual(q['inbound_shipping'],0)
        self.assertEqual(q['buyer_fee'],0)
        self.assertEqual(q['outbound_shipping'],415)
    def test_provisional_reference_never_qualifies_as_verified_alert(self):
        item=dict(title='model test',price=1,shipping=0,buyer_fee=0,seller_reviews=20,condition_confirmed=True)
        result=evaluate(item,[reference()],{'max_position':33},10000,DEFAULT_PROFILE)
        self.assertEqual(result['status'],'À vérifier')
        self.assertTrue(result['estimate_only'])
        self.assertTrue(result['candidate'])
    def test_wrong_version_has_no_price_prediction(self):
        ref=reference()|{'forbidden_terms':['switch 2']}
        item=dict(title='model test switch 2',price=1,shipping=0,buyer_fee=0)
        result=evaluate(item,[ref],{},10000,DEFAULT_PROFILE)
        self.assertFalse(result['candidate'])
        self.assertNotIn('forecast',result)
    def test_suspended_and_stale_sources_do_not_create_candidates(self):
        ref=reference();ref['research']['decision']='suspendre'
        self.assertFalse(quote(ref,DEFAULT_PROFILE)['can_buy'])
        ref['research']['decision']='prudence';ref['research']['reviewed_on']='2020-01-01'
        self.assertFalse(quote(ref,DEFAULT_PROFILE)['can_buy'])
    def test_nan_profile_rejected(self):
        with self.assertRaises(ValueError):validate_profile(DEFAULT_PROFILE|{'risk_rate':'NaN'})
    def test_bundle_and_existing_custom_quotes_are_preserved(self):
        with tempfile.TemporaryDirectory() as path:
            d=Dashboard(path)
            first=d.references()[0]
            d.dispatch('reference_save',dict(reference=first['reference'],aliases=first['aliases'],floor=30,source='devis personnel',checked_on=date.today().isoformat()))
            state=d.dispatch('state',{})
            self.assertEqual(len(state['analysis']['items']),50)
            updated=next(r for r in state['references'] if r['reference']==first['reference'])
            self.assertEqual(updated['floor'],'30')
            self.assertIn('research',updated)
            self.assertEqual(len(Dashboard(path).dispatch('state',{})['analysis']['items']),50)

    def test_entered_weight_changes_postage_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as path:
            d=Dashboard(path);ref=d.references()[0]
            state=d.dispatch('reference_costs',dict(reference=ref['reference'],packed_weight_g=700,packaging_eur=2,testing_eur=3,ebay_rate_ht=.08))
            item=next(r for r in state['analysis']['items'] if r['reference']==ref['reference'])
            self.assertEqual(item['preview']['outbound_shipping'],599)
            self.assertEqual(Dashboard(path).references()[0]['packed_weight_g'],700)
    def test_invalid_weight_does_not_save_invalid_profile(self):
        with tempfile.TemporaryDirectory() as path:
            d=Dashboard(path);ref=d.references()[0]
            with self.assertRaises(ValueError):d.dispatch('reference_costs',dict(reference=ref['reference'],packed_weight_g=5001,packaging_eur=2,testing_eur=3,ebay_rate_ht=.08))
            self.assertEqual(d.references()[0]['packed_weight_g'],ref['packed_weight_g'])

    def test_real_bridge_listing_is_matched_and_forecast_without_fake_verified_price(self):
        with tempfile.TemporaryDirectory() as path:
            d=Dashboard(path)
            d.dispatch('bridge',{'rows':[dict(id='vinted:100',title='JBL Flip 6',price=5,url='https://www.vinted.fr/items/100-jbl-flip-6')]})
            row=d.dispatch('state',{})['rows'][0]
            self.assertEqual(row['analysis']['floor'],5000)
            self.assertEqual(row['analysis']['forecast']['outbound_shipping'],599)
            self.assertEqual(row['analysis']['forecast']['purchase_total'],1194)
            self.assertEqual(row['analysis']['margin'],1896)
            self.assertTrue(row['analysis']['estimate_only'])
            self.assertNotEqual(row['analysis']['status'],'Alerte')

    def test_legacy_saved_quote_merges_by_alias_without_ambiguous_duplicate(self):
        with tempfile.TemporaryDirectory() as path:
            from pathlib import Path
            Path(path,'references.json').write_text(json.dumps([dict(reference='Nintendo Switch Lite',aliases='switch lite',floor='75',source='devis personnel',checked_on=date.today().isoformat())]))
            d=Dashboard(path)
            matches=[r for r in d.references() if 'switch lite' in r['aliases'].split('|')]
            self.assertEqual(len(matches),1)
            self.assertEqual(matches[0]['floor'],'75')
            self.assertIn('research',matches[0])

if __name__=='__main__':unittest.main()
