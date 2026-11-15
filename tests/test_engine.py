import tempfile
import unittest
from datetime import date
from pathlib import Path
from engine import Store, evaluate, money
from app import DEFAULT

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'test.db')
        self.item = dict(id='test:1', title='New 3DS XL', description='fonctionnelle', price='20', shipping='3', buyer_fee='2', seller_reviews='5',condition_confirmed=True)
        self.ref = [dict(aliases='new 3ds xl', floor='100', checked_on=date.today().isoformat(), source='relevé manuel')]
    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()
    def test_alert_includes_costs(self):
        result = evaluate(self.item, self.ref, DEFAULT, 10000)
        self.assertEqual(result['status'], 'Alerte')
        self.assertEqual(result['cost'], 2500)
        self.assertEqual(result['margin'], 6900)
    def test_invalid_shipping_rejected_atomically(self):
        bad = dict(self.item, id='bad', shipping='invalide')
        with self.assertRaises(ValueError): self.store.ingest([self.item, bad])
        self.assertEqual(len(self.store.rows()), 0)
    def test_nonfinite_and_negative(self):
        for value in ('NaN', 'Infinity', '-2'):
            with self.assertRaises(ValueError): money(value)
    def test_duplicate_does_not_spend_twice(self):
        self.store.ingest([self.item, self.item])
        self.store.buy('test:1', 2500, DEFAULT)
        with self.assertRaises(ValueError): self.store.buy('test:1', 2500, DEFAULT)
        self.assertEqual(self.store.cash(100), 7500)
    def test_cash_only_when_paid(self):
        self.store.ingest([self.item])
        self.store.buy('test:1', 2500, DEFAULT)
        self.store.sell('test:1', 6000)
        self.assertEqual(self.store.cash(100), 13500)
        with self.assertRaises(ValueError): self.store.sell('test:1', 6000)
    def test_budget_and_defects(self):
        item = dict(self.item, description='pour pièces')
        self.assertNotEqual(evaluate(item, self.ref, DEFAULT, 10000)['status'], 'Alerte')
        self.assertNotEqual(evaluate(self.item, self.ref, DEFAULT, 1000)['status'], 'Alerte')
    def test_stale_reference(self):
        self.ref[0]['checked_on'] = '2020-01-01'
        self.assertNotEqual(evaluate(self.item, self.ref, DEFAULT, 10000)['status'], 'Alerte')
    def test_bought_payload_frozen(self):
        self.store.ingest([self.item])
        self.store.buy('test:1', 2500, DEFAULT)
        self.store.ingest([dict(self.item, price='999')])
        self.assertIn('"price": "20"', self.store.rows()[0]['payload'])
    def test_different_model_no_alert(self):
        item = dict(self.item, title='New 3DS standard')
        self.assertNotEqual(evaluate(item, self.ref, DEFAULT, 10000)['status'], 'Alerte')

if __name__ == '__main__': unittest.main()
