"""Optional local alpha masks remain bounded presentation-only data."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from unittest.mock import patch

from django.template.loader import get_template
from django.test import SimpleTestCase

from .cosmetic_packages import parse_package


def masked_manifest():
  return {
    'version': 1, 'slug': 'efeito-mask-test', 'type': 'efeito', 'scope': 'ambos',
    'layers': [{
      'slot': 'banner', 'file': 'arcane-banner.svg', 'fallback': 'arcane-banner.svg',
      'width': 400, 'height': 400, 'motion': 'float', 'opacity': .6,
      'placement': {'x': 50, 'y': 50, 'width': 30},
      'sequence': {'columns': 1, 'duration': 18, 'delay': -3, 'backdrop': 0,
                   'frames': [{'at': at, 'frame': 0, 'opacity': 1}
                              for at in [0, .3, .6, 1]]},
      'mask': {'file': 'arcane-banner.svg'},
    }],
  }


def parse(raw):
  return parse_package(raw, raw['slug'], raw['type'])


class Attributes(HTMLParser):
  def __init__(self):
    super().__init__()
    self.images = []

  def handle_starttag(self, tag, attrs):
    if tag == 'img':
      self.images.append(dict(attrs))


class CosmeticMaskTests(SimpleTestCase):
  def test_optional_local_mask_is_resolved_without_mutating_input(self):
    raw = masked_manifest()
    before = deepcopy(raw)
    output = parse(raw)['banner'][0]
    self.assertEqual(output['mask_url'], '/static/cosmetics/arcane-banner.svg')
    self.assertNotIn('mask', output)
    self.assertEqual(output['opacity'], .6)
    self.assertEqual(raw, before)
    self.assertEqual(parse(raw), parse_package(raw, raw['slug'], raw['type'], 'ficha'))

  def test_omitted_mask_does_not_change_legacy_output_or_markup(self):
    raw = masked_manifest()
    del raw['layers'][0]['mask']
    output = parse(raw)['banner'][0]
    self.assertNotIn('mask_url', output)
    html = get_template('home/partials/_cosmetic_preview.html').render({'layers': [output], 'slot': 'banner'})
    self.assertNotIn('data-cosmetic-mask', html)

  def test_mask_requires_exactly_one_file_field(self):
    for value in [None, True, 0, [], 'arcane-banner.svg', {},
                  {'url': 'arcane-banner.svg'}, {'file': 'arcane-banner.svg', 'extra': 1}]:
      raw = masked_manifest()
      raw['layers'][0]['mask'] = value
      with self.subTest(mask=value):
        self.assertIsNone(parse(raw))

  def test_mask_reuses_existing_flat_local_asset_validation(self):
    for filename in [None, True, 7, [], {}, '', 'missing-mask.svg', '../arcane-banner.svg',
                     '/arcane-banner.svg', 'nested/arcane-banner.svg', 'renderer.js',
                     'https://example.com/mask.webp', 'data:image/svg+xml,test',
                     'arcane-banner.svg?x=1', 'arcane-banner.svg" onload="x']:
      raw = masked_manifest()
      raw['layers'][0]['mask']['file'] = filename
      with self.subTest(file=filename):
        self.assertIsNone(parse(raw))
    raw = masked_manifest()
    with patch('home.cosmetic_packages._asset_url', side_effect=['/base.svg', '/fallback.svg', '']) as resolve:
      self.assertIsNone(parse(raw))
      self.assertEqual(resolve.call_args.args, ('arcane-banner.svg',))

  def test_mask_requires_single_cell_sequence(self):
    for change in [{'columns': 2}, {'rows': 2}, {'columns': 8, 'rows': 8}]:
      raw = masked_manifest()
      raw['layers'][0]['sequence'].update(change)
      with self.subTest(change=change):
        self.assertIsNone(parse(raw))
    raw = masked_manifest()
    raw['layers'][0]['sequence']['rows'] = 1
    self.assertIsNotNone(parse(raw))
    del raw['layers'][0]['sequence']
    self.assertIsNone(parse(raw))

  def test_mask_cannot_bypass_banner_and_sequence_contract(self):
    for change in [{'slot': 'avatar'}, {'slot': 'ornament'}, {'motion': 'pulse'},
                   {'sprite': 'open'}, {'sequence': None}, {'placement': {}}]:
      raw = masked_manifest()
      raw['layers'][0].update(change)
      with self.subTest(change=change):
        self.assertIsNone(parse(raw))

  def test_mask_url_is_escaped_in_server_partial(self):
    raw = masked_manifest()
    escaped_url = '/static/cosmetics/arcane-banner.svg?x="test"&y=<value>'
    with patch('home.cosmetic_packages.static', return_value=escaped_url):
      output = parse(raw)['banner'][0]
    html = get_template('home/partials/_cosmetic_preview.html').render({'layers': [output], 'slot': 'banner'})
    self.assertIn('data-cosmetic-mask="/static/cosmetics/arcane-banner.svg?x=&quot;test&quot;&amp;y=&lt;value&gt;"', html)
    attrs = Attributes()
    attrs.feed(html)
    self.assertEqual(len(attrs.images), 1)
    self.assertEqual(attrs.images[0]['data-cosmetic-mask'], escaped_url)

  def test_masked_parent_preserves_parts_and_child_mask_metadata(self):
    raw = masked_manifest()
    child = deepcopy(raw['layers'][0])
    child['motion'] = 'none'
    child['opacity'] = .4
    raw['layers'][0]['parts'] = [child]
    body = parse(raw)['banner'][0]
    self.assertEqual(body['mask_url'], body['parts'][0]['mask_url'])
    self.assertEqual(body['parts'][0]['opacity'], .4)
    self.assertEqual(json.loads(body['parts_json'])[0]['mask_url'], body['mask_url'])
    raw['layers'][0]['parts'][0]['sequence']['columns'] = 2
    self.assertIsNone(parse(raw))

  def test_mask_with_grid_children_is_valid_and_does_not_mask_each_child(self):
    raw = masked_manifest()
    child = deepcopy(raw['layers'][0])
    del child['mask']
    child['sequence'].update(columns=4, rows=3)
    child['sequence']['frames'][1]['frame'] = 11
    raw['layers'][0]['parts'] = [child]
    body = parse(raw)['banner'][0]
    self.assertIn('mask_url', body)
    self.assertNotIn('mask_url', body['parts'][0])
