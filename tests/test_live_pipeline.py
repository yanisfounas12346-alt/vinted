import json
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from connectors import normalize_vinted, SourceError
from desktop import Dashboard
from engine import Store, evaluate
from scanner import Scanner
from valuation import calibrate
from desktop import DEFAULT

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.d=Dashboard(self.tmp.name)
    def tearDown(self):
        self.d.scanner.stop_event.set()
        if self.d.scanner.thread:self.d.scanner.thread.join(2)
        self.tmp.cleanup()
    def test_live_item_unknown_cost_does_not_claim_margin(self):
        rows,skipped=normalize_vinted({'items':[{'id':12,'title':'New 3DS XL','price':{'amount':'20','currency_code':'EUR'},'photo':{'full_size_url':'https://images1.vinted.net/test.jpg'}}]})
        self.assertEqual(skipped,0)
        ref=[dict(reference='Nintendo New 3DS XL',aliases='new 3ds xl',floor='100',checked_on=date.today().isoformat(),source='devis')]
        result=evaluate(rows[0],ref,DEFAULT,10000)
        self.assertIsNone(result['margin'])
        self.assertTrue(result['candidate'])
        self.assertNotEqual(result['status'],'Alerte')
        self.d.ingest_real(rows)
        self.d.dispatch('patch',{'id':'vinted:12','values':{'shipping':'3','buyer_fee':'2','seller_reviews':5,'condition_confirmed':True}})
        from contextlib import closing
        with closing(self.d.store()) as store:
            item=json.loads(store.db.execute('SELECT payload FROM listings').fetchone()[0])
        self.assertEqual(evaluate(item,ref,DEFAULT,10000)['status'],'Alerte')
    def test_bad_schema_raises_not_empty_success(self):
        with self.assertRaises(SourceError):normalize_vinted({'data':[]})
    def test_bridge_no_fake_fees_and_deduplicates(self):
        payload={'rows':[dict(id='vinted:34',title='Console',price='20',url='https://www.vinted.fr/items/34-test',shipping=0)]}
        self.assertEqual(self.d.dispatch('bridge',payload)['new'],1)
        self.assertEqual(self.d.dispatch('bridge',payload)['new'],0)
        result=self.d.dispatch('state',{})
        self.assertIsNone(result['rows'][0]['item']['shipping'])
        self.assertIsNone(result['rows'][0]['analysis']['margin'])
    def test_bridge_invalid_host_rejected(self):
        with self.assertRaises(ValueError):self.d.dispatch('bridge',{'rows':[dict(id='vinted:1',url='https://evil.example/items/1',title='x',price=1)]})
    def test_calibration_uses_sold_p20_and_requires_five(self):
        ref=[dict(reference='X',aliases='model x',floor=0,source='',checked_on='')]
        sales=[dict(reference='X',price=p,sold_on=date.today().isoformat(),source='proof-'+str(i),condition='bon état complet',sold=True) for i,p in enumerate([80,90,100,110,120])]
        result=calibrate(sales,ref)[0]
        self.assertEqual(result['floor'],'88.0')
        with self.assertRaises(ValueError):calibrate(sales[:4],ref)
        sales[0]['sold']=False
        with self.assertRaises(ValueError):calibrate(sales,ref)
    def test_scanner_stops_on_access_error_without_retry(self):
        logs=[]
        scanner=Scanner(lambda rows,event:len(rows),lambda *a:logs.append(a),lambda:'')
        with patch('scanner.VintedClient.search',side_effect=SourceError('HTTP 403')) as search:
            scanner.start([{'source':'vinted','query':'new 3ds xl'}],60)
            scanner.thread.join(2)
            self.assertFalse(scanner.snapshot()['running'])
            self.assertEqual(scanner.snapshot()['stage'],'error')
            self.assertEqual(search.call_count,1)
    def test_stopped_scan_drops_late_results(self):
        started,release=threading.Event(),threading.Event()
        ingested=[]
        def slow(_client,_query):
            started.set();release.wait(2);return [],0
        scanner=Scanner(lambda rows,event:ingested.append(rows),lambda *args:None,lambda:'')
        with patch('scanner.VintedClient.search',slow):
            scanner.start([{'source':'vinted','query':'test'}],60)
            self.assertTrue(started.wait(2));scanner.stop();release.set();scanner.thread.join(2)
            self.assertEqual(ingested,[])
    def test_verified_costs_invalidated_when_price_changes(self):
        row=dict(id='vinted:1',title='X',price=20,shipping=None,buyer_fee=None)
        self.d.ingest_real([row])
        self.d.dispatch('patch',{'id':row['id'],'values':{'shipping':3,'buyer_fee':2}})
        self.d.ingest_real([dict(row,price=25)])
        self.assertIsNone(self.d.dispatch('state',{})['rows'][0]['item']['buyer_fee'])

if __name__=='__main__':unittest.main()
