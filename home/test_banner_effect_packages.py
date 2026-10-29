from unittest.mock import patch

from django.test import SimpleTestCase

from home.cosmetic_packages import get_package, load_package
from home.views import _appearance_context


class BannerEffectPackageTests(SimpleTestCase):
  def test_reclassified_effects_keep_art_and_responsive_layout(self):
    for key in ('lua-vermelha', 'lua-negra', 'lua-cristal', 'vigilia-das-lanternas'):
      for scope in ('perfil', 'ficha'):
        with self.subTest(key=key, scope=scope):
          old = load_package('tema', key, scope)
          new = load_package('efeito', key, scope)
          self.assertIsNotNone(new)
          for slot in ('banner', 'ornament', 'avatar'):
            self.assertEqual(old[slot], new[slot])
          self.assertEqual(new['type'], 'efeito')

  @patch('home.cosmetic_packages.cosmetic_allowed')
  def test_effect_access_is_checked_independently_from_palette(self, allowed):
    owner = object()
    allowed.return_value = False
    self.assertIsNone(get_package(owner, 'efeito', 'lua-vermelha'))
    allowed.return_value = True
    self.assertTrue(get_package(owner, 'efeito', 'lua-vermelha')['banner'])
    allowed.assert_called_with(owner, 'efeito', 'lua-vermelha', 'perfil')

  def test_effect_does_not_select_a_theme_or_change_palette(self):
    catalogs = {
      'theme': {'bonfire': {'class': 'theme-bonfire', 'origem': 'livre', 'label': 'Bonfire'}},
      'frame': {'none': {'class': '', 'origem': 'livre'}},
      'effect': {'lua-vermelha': {'class': '', 'origem': 'staff'},
                 'none': {'class': '', 'origem': 'livre'}},
    }
    with patch('home.views._appearance_catalog', side_effect=catalogs.__getitem__), \
         patch('home.views._cosmetic_allowed', return_value=True):
      appearance = _appearance_context('bonfire', 'none', 'lua-vermelha', user=object())
    self.assertEqual(appearance['theme_key'], 'bonfire')
    self.assertEqual(appearance['theme_class'], 'theme-bonfire')
    self.assertEqual(appearance['effect_key'], 'lua-vermelha')
    self.assertEqual(appearance['custom_style'], '')
