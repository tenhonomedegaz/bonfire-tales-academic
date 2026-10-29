"""Bounded presentation rigs, independent of shipped art and catalog grants."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.template.loader import get_template
from django.test import SimpleTestCase

from .cosmetic_packages import load_package, parse_package


def sequence(columns=1, rows=None, count=24):
  result = {'columns': columns, 'duration': 18, 'delay': -3, 'backdrop': 0,
            'frames': [{'at': i / (count - 1), 'frame': i % (columns * (rows or 1)),
                        'opacity': 1} for i in range(count)]}
  if rows is not None:
    result['rows'] = rows
  return result


def rig_manifest():
  part = {'slot': 'banner', 'file': 'arcane-banner.svg', 'fallback': 'arcane-banner.svg',
          'width': 400, 'height': 300, 'motion': 'none',
          'placement': {'x': 50, 'y': 12, 'width': 30}, 'pivot': {'x': 50, 'y': 90},
          'sequence': sequence(4, 3, 13)}
  body = dict(deepcopy(part), width=400, height=600, motion='float',
              sequence=sequence(), parts=[part], opacity=.6)
  return {'version': 1, 'slug': 'efeito-rig-test', 'type': 'efeito', 'scope': 'ambos',
          'overlay': True, 'layers': [body]}


def parse(raw):
  return parse_package(raw, raw['slug'], raw['type'])


class ImageAttributes(HTMLParser):
  def __init__(self):
    super().__init__()
    self.images = []

  def handle_starttag(self, tag, attrs):
    if tag == 'img':
      self.images.append(dict(attrs))


class CosmeticRigTests(SimpleTestCase):
  def test_fixed_body_and_grid_parts_are_serialized_without_mutation(self):
    raw = rig_manifest()
    before = deepcopy(raw)
    package = parse(raw)
    body = package['banner'][0]
    self.assertEqual(body['sequence']['columns'], 1)
    self.assertNotIn('rows', body['sequence'])
    self.assertEqual(len(body['sequence']['frames']), 24)
    self.assertEqual(body['parts'][0]['sequence']['rows'], 3)
    self.assertEqual(json.loads(body['parts_json']), body['parts'])
    self.assertEqual(before, raw)
    self.assertEqual(package, parse_package(raw, raw['slug'], raw['type'], 'ficha'))

  def test_template_escapes_parts_and_round_trips_validated_metadata(self):
    body = parse(rig_manifest())['banner'][0]
    html = get_template('home/partials/_cosmetic_preview.html').render({'layers': [body], 'slot': 'banner'})
    self.assertIn('data-cosmetic-parts="[{&quot;', html)
    self.assertNotIn('data-cosmetic-parts="[{"', html)
    parser = ImageAttributes()
    parser.feed(html)
    self.assertEqual(len(parser.images), 1)
    self.assertEqual(json.loads(parser.images[0]['data-cosmetic-parts']), body['parts'])

  def test_all_pose_bounds_are_optional_finite_numbers(self):
    for key, low, high in [('x', -100, 100), ('y', -100, 100), ('rotate', -15, 15),
                           ('scaleX', .8, 1.2), ('scaleY', .8, 1.2), ('shift', -25, 25)]:
      for value in [low, high, (low + high) / 2]:
        raw = rig_manifest()
        raw['layers'][0]['sequence']['frames'][1][key] = value
        with self.subTest(key=key, value=value):
          self.assertIsNotNone(parse(raw))
      for value in [low - .01, high + .01, True, None, '1', float('nan'), float('inf'), 10**400]:
        raw = rig_manifest()
        raw['layers'][0]['parts'][0]['sequence']['frames'][1][key] = value
        with self.subTest(key=key, value=value):
          self.assertIsNone(parse(raw))

  def test_grid_and_timeline_limits_and_legacy_horizontal_atlases(self):
    for columns, rows, count in [(1, None, 4), (7, None, 24), (4, 3, 13), (8, 8, 64)]:
      raw = rig_manifest()
      raw['layers'][0].pop('parts')
      raw['layers'][0]['sequence'] = sequence(columns, rows, count)
      self.assertIsNotNone(parse(raw))
    for key, value in [('columns', 0), ('columns', 9), ('columns', True), ('rows', 0),
                       ('rows', 9), ('rows', True), ('rows', 1.0), ('rows', None),
                       ('frames', sequence(count=65)['frames']), ('frames', sequence(count=3)['frames'])]:
      raw = rig_manifest()
      raw['layers'][0]['sequence'][key] = value
      with self.subTest(key=key, value=value):
        self.assertIsNone(parse(raw))

  def test_frame_index_is_integer_within_actual_grid(self):
    for value in [-1, 12, True, 2.0, float('nan')]:
      raw = rig_manifest()
      raw['layers'][0]['parts'][0]['sequence']['frames'][1]['frame'] = value
      self.assertIsNone(parse(raw))
    raw = rig_manifest()
    raw['layers'][0]['parts'][0]['sequence']['frames'][1]['frame'] = 11
    self.assertIsNotNone(parse(raw))

  def test_parts_require_fixed_single_cell_root_and_one_level(self):
    for change in [{'columns': 2}, {'rows': 2}]:
      raw = rig_manifest()
      raw['layers'][0]['sequence'].update(change)
      self.assertIsNone(parse(raw))
    raw = rig_manifest()
    del raw['layers'][0]['sequence']
    self.assertIsNone(parse(raw))
    raw = rig_manifest()
    raw['layers'][0]['parts'][0]['parts'] = [deepcopy(raw['layers'][0]['parts'][0])]
    self.assertIsNone(parse(raw))

  def test_parts_limits_do_not_raise_root_layer_limit(self):
    for count in [1, 6]:
      raw = rig_manifest()
      raw['layers'][0]['parts'] *= count
      raw['layers'] *= 8
      self.assertIsNotNone(parse(raw))
    for parts in [None, {}, [], rig_manifest()['layers'][0]['parts'] * 7]:
      raw = rig_manifest()
      raw['layers'][0]['parts'] = parts
      self.assertIsNone(parse(raw))
    raw = rig_manifest()
    raw['layers'] *= 9
    self.assertIsNone(parse(raw))

  def test_child_uses_existing_asset_placement_pivot_and_sequence_validation(self):
    for change in [{'file': '../unsafe.svg'}, {'fallback': 'missing.svg'}, {'slot': 'avatar'},
                   {'placement': {}}, {'pivot': {'x': 101, 'y': 50}}, {'width': True},
                   {'height': 4097}, {'sequence': None}, {'motion': 'drift'}]:
      raw = rig_manifest()
      raw['layers'][0]['parts'][0].update(change)
      with self.subTest(change=change):
        self.assertIsNone(parse(raw))
    raw = rig_manifest()
    del raw['layers'][0]['parts'][0]['placement']
    self.assertIsNone(parse(raw))
    raw = rig_manifest()
    raw['layers'][0]['parts'][0]['sequence']['backdrop'] = .1
    self.assertIsNone(parse(raw))

  def test_mobile_is_optional_and_retains_validated_child_metadata(self):
    raw = rig_manifest()
    self.assertNotIn('mobile', parse(raw)['banner'][0]['parts'][0])
    mobile = {'x': 25, 'y': 80, 'width': 35}
    raw['layers'][0]['parts'][0]['mobile'] = mobile
    self.assertEqual(parse(raw)['banner'][0]['parts'][0]['mobile'], mobile)

  def test_pose_schema_does_not_relax_timeline_validation(self):
    for change in [{'at': .5}, {'opacity': float('inf')}, {'unknown': 1}]:
      raw = rig_manifest()
      raw['layers'][0]['sequence']['frames'][0].update(change)
      self.assertIsNone(parse(raw))

  def test_manifest_byte_cap_is_64_kib(self):
    raw = rig_manifest()
    with TemporaryDirectory() as directory:
      root = Path(directory)
      path = root / (raw['slug'] + '.json')
      content = json.dumps(raw)
      with patch('home.cosmetic_packages.PACKAGE_ROOT', root), patch('home.cosmetic_packages._asset_url', return_value='/static/cosmetics/valid.svg'):
        path.write_text(content + ' ' * (64 * 1024 - len(content)), encoding='utf-8')
        self.assertIsNotNone(load_package('efeito', 'rig-test'))
        path.write_text(content + ' ' * (64 * 1024 + 1 - len(content)), encoding='utf-8')
        self.assertIsNone(load_package('efeito', 'rig-test'))
