import json
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from desktop import Dashboard, make_server

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dashboard = Dashboard(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_modes_and_ledger_are_isolated(self):
        self.assertEqual(self.dashboard.dispatch('state', {})['rows'], [])
        demo = self.dashboard.dispatch('mode', {'demo': True})
        self.assertEqual(len(demo['rows']), 6)
        self.dashboard.dispatch('buy', {'id':'demo:1', 'amount':'25'})
        self.assertEqual(self.dashboard.dispatch('state', {})['cash'], 7500)
        real = self.dashboard.dispatch('mode', {'demo': False})
        self.assertEqual(real['cash'], 10000)
        self.assertEqual(real['rows'], [])
    def test_bad_settings_do_not_persist(self):
        values = dict(self.dashboard.config, sale_fee_rate=.9, turnover_reserve_rate=.9)
        with self.assertRaises(ValueError): self.dashboard.dispatch('settings', values)
        self.assertEqual(self.dashboard.config['sale_fee_rate'], 0)
    def test_server_requires_local_token_and_blocks_unknown_paths(self):
        server=make_server(self.dashboard)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            page=urlopen(base).read().decode()
            token=page.split('name="session-token" content="')[1].split('"')[0]
            req=Request(base+'/api/state',data=b'{}',headers={'X-Session-Token':token,'Content-Type':'application/json'})
            self.assertEqual(json.load(urlopen(req))['cash'],10000)
            with self.assertRaises(HTTPError) as caught: urlopen(Request(base+'/api/buy',data=b'{}'))
            self.assertEqual(caught.exception.code,403)
            with self.assertRaises(HTTPError) as caught: urlopen(base+'/engine.py')
            self.assertEqual(caught.exception.code,404)
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_extension_token_only_allows_bridge(self):
        server=make_server(self.dashboard)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        headers={'Content-Type':'application/json','X-Bridge-Token':self.dashboard.bridge_token,'Origin':'chrome-extension://local-test'}
        try:
            body=json.dumps({'rows':[dict(id='vinted:1',title='New 3DS XL',price=20,url='https://www.vinted.fr/items/1-test')]}).encode()
            result=json.load(urlopen(Request(base+'/api/bridge',data=body,headers=headers)))
            self.assertEqual(result['new'],1)
            with self.assertRaises(HTTPError) as caught:urlopen(Request(base+'/api/settings',data=b'{}',headers=headers))
            self.assertEqual(caught.exception.code,403)
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
