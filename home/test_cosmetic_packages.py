"""Focused contract tests for the static cosmetic renderer, without a database."""

import json
from unittest.mock import patch

from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase

from home.cosmetic_packages import PACKAGE_ROOT, get_package, parse_package


class CosmeticPackageTests(SimpleTestCase):
  def test_shipped_manifests_and_assets_are_valid(self):
    for path in sorted(PACKAGE_ROOT.glob('*.json')):
      with self.subTest(path=path.name):
        raw = json.loads(path.read_text(encoding='utf-8'))
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
      {'width': True},
    ):
      with self.subTest(change=change):
        candidate = json.loads(json.dumps(raw))
        candidate['layers'][0].update(change)
        self.assertIsNone(parse_package(candidate, candidate['slug'], candidate['type']))
    self.assertIsNone(parse_package(raw, raw['slug'], 'tema'))

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
    ):
      with self.subTest(name=name):
        self.assertIsNotNone(get_template(name))
