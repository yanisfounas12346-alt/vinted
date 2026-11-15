import unittest
from desktop import Dashboard
from engine import evaluate
from pricing import DEFAULT_PROFILE
import tempfile

class ProductIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.dashboard=Dashboard(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def analyze(self,title,description=''):
        return evaluate(dict(title=title,description=description,price=5,shipping=None,buyer_fee=None),self.dashboard.references(),self.dashboard.config,10000,DEFAULT_PROFILE)
    def test_user_poster_does_not_inherit_game_price(self):
        result=self.analyze('Poster The Legend of Zelda : Breath of the Wild – Link (Grand format), Marque: Zelda, État: Bon état, 5.00 €, 5.95 €')
        self.assertEqual(result['status'],'Exclu')
        self.assertEqual(result['floor'],0)
        self.assertIsNone(result['margin'])
        self.assertNotIn('forecast',result)
        self.assertFalse(result['candidate'])
    def test_derivatives_with_game_names_are_not_games(self):
        for title in ['Guide Zelda Breath of the Wild Switch','Affiche du jeu Zelda Breath of the Wild','Amiibo Link Breath of the Wild','T-shirt Super Mario Odyssey Switch','Stickers Animal Crossing New Horizons']:
            with self.subTest(title=title): self.assertEqual(self.analyze(title)['status'],'Exclu')
    def test_real_game_still_has_forecast(self):
        result=self.analyze('Jeu Zelda Breath of the Wild Nintendo Switch complet')
        self.assertIn('forecast',result)
        self.assertEqual(result['floor'],2600)
    def test_game_with_explicit_bonus_is_not_rejected(self):
        result=self.analyze('Jeu Zelda Breath of the Wild Switch avec poster inclus')
        self.assertIn('forecast',result)
    def test_description_identifying_poster_blocks_ambiguous_title(self):
        result=self.analyze('Zelda Breath of the Wild','Poster grand format, pas de jeu')
        self.assertEqual(result['status'],'Exclu')

if __name__=='__main__':unittest.main()
