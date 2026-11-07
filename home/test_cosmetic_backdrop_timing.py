"""Independent backdrop timing is bounded presentation data, not a face timeline."""
from copy import deepcopy
from html.parser import HTMLParser
import json

from django.template.loader import get_template
from django.test import SimpleTestCase

from .cosmetic_packages import parse_package


def manifest():
  return {
    'version': 1, 'slug': 'efeito-backdrop-test', 'type': 'efeito', 'scope': 'ambos',
    'layers': [{
      'slot': 'banner', 'file': 'arcane-banner.svg', 'fallback': 'arcane-banner.svg',
      'width': 400, 'height': 400, 'motion': 'none',
      'placement': {'x': 50, 'y': 50, 'width': 30},
      'sequence': {'columns': 1, 'duration': 16, 'delay': -2, 'backdrop': .7,
                   'frames': [{'at': 0, 'frame': 0, 'opacity': 0, 'x': 0},
                              {'at': .1, 'frame': 0, 'opacity': 1, 'x': 2},
                              {'at': .8, 'frame': 0, 'opacity': 1, 'x': -2},
                              {'at': 1, 'frame': 0, 'opacity': 0, 'x': 0}]},
    }],
  }


def backdrop_frames():
  return [{'at': 0, 'opacity': 0}, {'at': .3 / 16, 'opacity': 1},
          {'at': .95, 'opacity': 1}, {'at': 1, 'opacity': 0}]


def parse(raw):
  return parse_package(raw, raw['slug'], raw['type'])


class Attributes(HTMLParser):
  def __init__(self):
    super().__init__()
    self.sequence = None

  def handle_starttag(self, tag, attrs):
    values = dict(attrs)
    if tag == 'img' and 'data-cosmetic-sequence' in values:
      self.sequence = json.loads(values['data-cosmetic-sequence'])


class CosmeticBackdropTimingTests(SimpleTestCase):
  def test_separate_timeline_round_trips_without_changing_face_or_input(self):
    raw = manifest()
    raw['layers'][0]['sequence']['backdropFrames'] = backdrop_frames()
    before = deepcopy(raw)
    layer = parse(raw)['banner'][0]
    self.assertEqual(layer['sequence'], raw['layers'][0]['sequence'])
    self.assertEqual(layer['sequence']['frames'], manifest()['layers'][0]['sequence']['frames'])
    self.assertEqual(json.loads(layer['sequence_json']), layer['sequence'])
    self.assertEqual(before, raw)
    self.assertEqual(parse(raw), parse_package(raw, raw['slug'], raw['type'], 'ficha'))

  def test_template_escapes_and_round_trips_both_timelines(self):
    raw = manifest()
    raw['layers'][0]['sequence']['backdropFrames'] = backdrop_frames()
    layer = parse(raw)['banner'][0]
    html = get_template('home/partials/_cosmetic_preview.html').render({'layers': [layer], 'slot': 'banner'})
    self.assertIn('&quot;backdropFrames&quot;', html)
    self.assertNotIn('data-cosmetic-sequence="{"', html)
    parser = Attributes()
    parser.feed(html)
    self.assertEqual(parser.sequence, raw['layers'][0]['sequence'])

  def test_omitted_timeline_keeps_exact_legacy_fallback_data(self):
    raw = manifest()
    expected = deepcopy(raw['layers'][0]['sequence'])
    layer = parse(raw)['banner'][0]
    self.assertNotIn('backdropFrames', layer['sequence'])
    self.assertEqual(json.loads(layer['sequence_json']), expected)
    self.assertEqual(layer['sequence'].get('backdropFrames', layer['sequence']['frames']), expected['frames'])

  def test_timeline_length_limits_are_independent_from_face_frames(self):
    for count in [4, 64]:
      raw = manifest()
      raw['layers'][0]['sequence']['backdropFrames'] = [{'at': i / (count - 1), 'opacity': i % 2} for i in range(count)]
      self.assertIsNotNone(parse(raw))
    for value in [None, True, {}, '', [], backdrop_frames()[:3],
                  [{'at': i / 64, 'opacity': 1} for i in range(65)]]:
      raw = manifest()
      raw['layers'][0]['sequence']['backdropFrames'] = value
      with self.subTest(value=value):
        self.assertIsNone(parse(raw))

  def test_frames_require_exact_numeric_finite_schema(self):
    for field in ['at', 'opacity']:
      for value in [True, False, None, '0.5', -.01, 1.01, float('nan'), float('inf'), float('-inf'), 10**400]:
        raw = manifest()
        frames = backdrop_frames()
        frames[1][field] = value
        raw['layers'][0]['sequence']['backdropFrames'] = frames
        with self.subTest(field=field, value=value):
          self.assertIsNone(parse(raw))
    for value in [None, [], {}, {'at': .5}, {'opacity': 1},
                  {'at': .5, 'opacity': 1, 'frame': 0}, {'at': .5, 'opacity': 1, 'extra': 0}]:
      raw = manifest()
      raw['layers'][0]['sequence']['backdropFrames'] = [backdrop_frames()[0], value, *backdrop_frames()[2:]]
      self.assertIsNone(parse(raw))

  def test_offsets_must_increase_strictly_and_cover_exact_cycle(self):
    for offsets in [[.01, .1, .8, 1], [0, .1, .8, .99], [0, .1, .1, 1], [0, .8, .1, 1]]:
      raw = manifest()
      raw['layers'][0]['sequence']['backdropFrames'] = [{'at': at, 'opacity': 1} for at in offsets]
      with self.subTest(offsets=offsets):
        self.assertIsNone(parse(raw))

  def test_separate_timeline_requires_nonzero_backdrop(self):
    raw = manifest()
    raw['layers'][0]['sequence']['backdrop'] = 0
    self.assertIsNotNone(parse(raw))
    raw['layers'][0]['sequence']['backdropFrames'] = backdrop_frames()
    self.assertIsNone(parse(raw))

  def test_child_parts_cannot_add_backdrop_or_backdrop_timeline(self):
    raw = manifest()
    child = deepcopy(raw['layers'][0])
    child['sequence']['backdrop'] = 0
    raw['layers'][0]['parts'] = [child]
    self.assertIsNotNone(parse(raw))
    child['sequence']['backdropFrames'] = backdrop_frames()
    self.assertIsNone(parse(raw))
    child['sequence']['backdrop'] = .2
    self.assertIsNone(parse(raw))
