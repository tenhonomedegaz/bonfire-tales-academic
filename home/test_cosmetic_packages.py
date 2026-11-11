"""Focused contract tests for the static cosmetic renderer, without a database."""

import json
from unittest.mock import patch

from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase

from home.cosmetic_packages import PACKAGE_ROOT, get_package, parse_package
from home.templatetags.cosmetic_packages import cosmetic_media_options


class CosmeticPackageTests(SimpleTestCase):
  def test_shipped_manifests_and_assets_are_valid(self):
    paths = [path for path in PACKAGE_ROOT.glob('*.json')
             if path.stem.partition('-')[0] in {'tema', 'moldura', 'efeito', 'banner_preset'}]
    self.assertTrue(paths)
    for path in sorted(paths):
      with self.subTest(path=path.name):
        raw = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(path.stem, raw['slug'])
        package = parse_package(raw, raw['slug'], raw['type'])
        self.assertIsNotNone(package)
        self.assertTrue(any(package[slot] for slot in ('banner', 'ornament', 'avatar')))

  def test_paths_and_untrusted_fields_are_rejected(self):
    raw = json.loads((PACKAGE_ROOT / 'moldura-ember-ring.json').read_text(encoding='utf-8'))
    for change in (
      {'file': '../renderer.js'},
      {'file': 'renderer.js'},
      {'file': 'missing.svg'},
      {'fallback': 'https://other.invalid/fallback.svg'},
      {'anchor': 'left;position:fixed'},
      {'motion': 'javascript:alert(1)'},
      {'sprite':'other'},
      {'motion':'helmet','sprite':'full'},
      {'width': True},
      {'aperture': {'cx': '50;display:none', 'cy': 50, 'diameter': 50}},
      {'aperture': {'cx': 50, 'cy': 50, 'diameter': float('nan')}},
      {'aperture': {'cx': 50, 'cy': 50, 'diameter': True}},
    ):
      with self.subTest(change=change):
        candidate = json.loads(json.dumps(raw))
        candidate['layers'][0].update(change)
        self.assertIsNone(parse_package(candidate, candidate['slug'], candidate['type']))
    self.assertIsNone(parse_package(raw, raw['slug'], 'tema'))

  def test_breeze_is_generic_banner_motion_only(self):
    raw = {
      'version': 1, 'slug': 'tema-motion-test', 'type': 'tema', 'scope': 'ambos',
      'layers': [{'slot': 'banner', 'file': 'arcane-banner.svg',
                  'fallback': 'arcane-banner.svg', 'width': 1200, 'height': 340,
                  'motion': 'breeze'}],
    }
    for scope in ('perfil', 'ficha'):
      parsed = parse_package(raw, raw['slug'], raw['type'], scope)
      self.assertEqual(parsed['banner'][0]['motion'], 'breeze')
    raw['layers'][0]['slot'] = 'avatar'
    self.assertIsNone(parse_package(raw, raw['slug'], raw['type']))

  def test_scope_is_enforced_by_manifest_as_well_as_catalog(self):
    raw = json.loads((PACKAGE_ROOT / 'moldura-ember-ring.json').read_text(encoding='utf-8'))
    raw['scope'] = 'perfil'
    self.assertIsNone(parse_package(raw, raw['slug'], raw['type'], 'ficha'))
    raw['scope'] = 'ficha'
    self.assertIsNone(parse_package(raw, raw['slug'], raw['type'], 'perfil'))
    self.assertIsNotNone(parse_package(raw, raw['slug'], raw['type'], 'ficha'))
    raw['scope'] = 'ambos'
    for scope in ('ficha', 'perfil'):
      self.assertIsNotNone(parse_package(raw, raw['slug'], raw['type'], scope))

  def test_rank_pairs_share_a_calibrated_portrait_aperture(self):
    for rank in ('obsidiana', 'ametista', 'topazio', 'esmeralda', 'ambar', 'rubi', 'diamante'):
      pairs = []
      for form in ('aberta', 'fechada'):
        raw = json.loads((PACKAGE_ROOT / f'moldura-elo-{rank}-{form}.json').read_text())
        parsed = parse_package(raw, raw['slug'], raw['type'])
        pairs.append(parsed['avatar'][0]['aperture'])
      self.assertEqual(*pairs)
      self.assertTrue(25 < pairs[0]['diameter'] < 65)

  def test_rank_delivery_uses_small_derivatives_with_original_fallback(self):
    total = 0
    for rank in ('obsidiana', 'ametista', 'topazio', 'esmeralda', 'ambar', 'rubi', 'diamante'):
      source = PACKAGE_ROOT / f'rank-{rank}-v3.webp'
      total += source.stat().st_size
      self.assertEqual(source.read_bytes()[8:12], b'WEBP')
      for form in ('aberta', 'fechada'):
        raw = json.loads((PACKAGE_ROOT / f'moldura-elo-{rank}-{form}.json').read_text())
        self.assertEqual(raw['layers'][0]['file'], source.name)
        self.assertEqual(raw['layers'][0]['fallback'], f'rank-{rank}-v3.png')
    self.assertLess(total, 1_500_000)

  def test_live_preview_media_excludes_locked_options(self):
    media = cosmetic_media_options([], [
      {'key':'lua-cristal','locked':False},
      {'key':'lua-vermelha','locked':True}], [])
    self.assertIn('lua-cristal',media['moldura'])
    self.assertNotIn('lua-vermelha',media['moldura'])
    self.assertTrue(media['moldura']['lua-cristal']['avatar'])

  @patch('home.cosmetic_packages.cosmetic_allowed', return_value=True)
  def test_sheet_uses_same_assets_and_explicit_owner_scope(self, allowed):
    owner = object()
    profile = get_package(owner, 'moldura', 'arcane-pulse')
    sheet = get_package(owner, 'moldura', 'arcane-pulse', 'ficha')
    self.assertEqual(profile, sheet)
    allowed.assert_called_with(owner, 'moldura', 'arcane-pulse', 'ficha')

  @patch('home.cosmetic_packages.cosmetic_allowed')
  def test_only_eligible_catalog_values_load(self, allowed):
    allowed.return_value = False
    self.assertIsNone(get_package(object(), 'moldura', 'ember-ring'))
    allowed.return_value = True
    package = get_package(object(), 'moldura', 'ember-ring')
    self.assertEqual(package['avatar'][0]['url'], '/static/cosmetics/ember-ring.svg')
    self.assertIsNone(get_package(object(), 'moldura', '../ember-ring'))
    self.assertIsNone(get_package(object(), 'moldura', 'missing'))

  @patch('home.cosmetic_packages.cosmetic_allowed', return_value=True)
  def test_template_tag_renders_only_validated_layers(self, _allowed):
    template = Template(
      "{% load cosmetic_packages %}"
      "{% cosmetic_package 'moldura' 'arcane-pulse' user as package %}"
      "{% include 'home/partials/_cosmetic_preview.html' with layers=package.avatar slot='avatar' %}"
    )
    html = template.render(Context({'user': object()}))
    self.assertIn('cosmetic-layers--avatar', html)
    self.assertIn('arcane-ring.svg', html)
    self.assertIn('aria-hidden="true"', html)

  def test_profile_pages_and_shared_preview_compile(self):
    for name in (
      'home/pages/perfil.html',
      'home/pages/perfil_publico.html',
      'home/partials/_perfil_publico_hero.html',
      'home/partials/_ficha_banner.html',
      'home/pages/ficha_publica.html',
    ):
      with self.subTest(name=name):
        self.assertIsNotNone(get_template(name))

  @patch('home.cosmetic_packages.cosmetic_allowed',return_value=True)
  def test_closed_rank_is_articulated_and_open_rank_is_static(self,_allowed):
    owner = object()
    closed = get_package(owner,'moldura','elo-esmeralda-fechada','ficha')
    opened = get_package(owner,'moldura','elo-esmeralda-aberta','ficha')
    self.assertEqual(closed['avatar'][0]['motion'],'helmet')
    self.assertEqual(opened['avatar'][0]['sprite'],'open')
    template = Template("{% include 'home/partials/_cosmetic_preview.html' with layers=layers slot='avatar' %}")
    html = template.render(Context({'layers':closed['avatar']}))
    for part in ('open','brow','left','right','chin'):
      self.assertIn('cosmetic-helmet-'+part,html)
    self.assertEqual(html.count('<img '),5)
