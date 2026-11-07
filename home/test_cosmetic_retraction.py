"""Generic retractable avatar pieces, with no database or production settings."""
from copy import deepcopy
from html.parser import HTMLParser

from django.template.loader import get_template
from django.test import SimpleTestCase, override_settings

from home.cosmetic_packages import parse_package


def retraction_manifest(mask=True):
  base = {
    'slot': 'avatar', 'file': 'ember-ring.svg', 'fallback': 'ember-ring.svg',
    'width': 1024, 'height': 512, 'sprite': 'open', 'motion': 'none',
    'aperture': {'cx': 50, 'cy': 48, 'diameter': 44},
  }
  pieces = []
  for x, y, rotate, delay in ((-28, 0, -6, 30), (28, 0, 6, 60), (0, 24, 0, 90)):
    piece = {
      'slot': 'avatar', 'file': 'arcane-ring.svg', 'fallback': 'arcane-ring.svg',
      'width': 512, 'height': 512, 'sprite': 'full', 'motion': 'retract',
      'retract': {'x': x, 'y': y, 'rotate': rotate, 'duration': 540, 'delay': delay},
    }
    if mask:
      piece['retract_mask'] = 'ember-ring.svg'
    pieces.append(piece)
  return {'version': 1, 'slug': 'moldura-retraction-test', 'type': 'moldura',
          'scope': 'ambos', 'layers': [base] + pieces}


def parse_retraction(raw, scope='perfil'):
  return parse_package(raw, raw['slug'], raw['type'], scope)


class ImageMarkup(HTMLParser):
  def __init__(self):
    super().__init__()
    self.images = []
    self.viewports = []

  def handle_starttag(self, tag, attrs):
    attrs = dict(attrs)
    if tag == 'img':
      self.images.append(attrs)
    if tag == 'span' and attrs.get('class') == 'cosmetic-retract-viewport':
      self.viewports.append(attrs)


@override_settings(STATIC_URL='/static/')
class CosmeticRetractionTests(SimpleTestCase):
  def test_version_one_preserves_base_aperture_order_and_input(self):
    raw = retraction_manifest()
    before = deepcopy(raw)
    package = parse_retraction(raw)
    self.assertIsNotNone(package)
    self.assertEqual(package, parse_retraction(raw, 'ficha'))
    self.assertEqual(package['version'], 1)
    self.assertEqual(raw, before)
    base, *pieces = package['avatar']
    self.assertEqual(base['motion'], 'none')
    self.assertEqual(base['sprite'], 'open')
    self.assertEqual(base['url'], '/static/cosmetics/ember-ring.svg')
    self.assertEqual(base['aperture'], raw['layers'][0]['aperture'])
    self.assertNotIn('retract', base)
    self.assertEqual(len(pieces), 3)
    for layer, original in zip(pieces, raw['layers'][1:]):
      self.assertEqual(layer['retract'], original['retract'])
      self.assertIsNot(layer['retract'], original['retract'])
    self.assertEqual(pieces[0]['retract_style'],
        '--cosmetic-retract-x:-28%;--cosmetic-retract-y:0%;--cosmetic-retract-rotate:-6deg;'
        '--cosmetic-retract-duration:540ms;--cosmetic-retract-delay:30ms')

  def test_finite_bounds_and_fractional_values_are_allowed(self):
    for values in (
        {'x': -100, 'y': 100, 'rotate': -45, 'duration': 100, 'delay': 0},
        {'x': 100, 'y': -100, 'rotate': 45, 'duration': 1500, 'delay': 500},
        {'x': -28.5, 'y': 0.25, 'rotate': -6.5, 'duration': 540.5, 'delay': 30.5}):
      raw = retraction_manifest()
      raw['layers'][1]['retract'] = values
      self.assertIsNotNone(parse_retraction(raw))

  def test_rejects_bool_nonfinite_text_and_out_of_bounds_for_each_key(self):
    bounds = {'x': (-100, 100), 'y': (-100, 100), 'rotate': (-45, 45),
              'duration': (100, 1500), 'delay': (0, 500)}
    for key, (low, high) in bounds.items():
      for value in (True, False, None, '30', '0;position:fixed', [], {},
                    float('nan'), float('inf'), float('-inf'), 10**400, low - .01, high + .01):
        with self.subTest(key=key, value=value):
          raw = retraction_manifest()
          raw['layers'][1]['retract'][key] = value
          self.assertIsNone(parse_retraction(raw))

  def test_requires_exact_five_key_object(self):
    valid = retraction_manifest()['layers'][1]['retract']
    malformed = [None, [], '', True, {}, dict(valid, extra=1)]
    malformed.extend({key: value for key, value in valid.items() if key != missing} for missing in valid)
    for value in malformed:
      with self.subTest(value=value):
        raw = retraction_manifest()
        raw['layers'][1]['retract'] = value
        self.assertIsNone(parse_retraction(raw))
    raw = retraction_manifest()
    del raw['layers'][1]['retract']
    self.assertIsNone(parse_retraction(raw))

  def test_retract_requires_full_avatar_without_other_layer_engines(self):
    changes = [{'slot': slot} for slot in ('banner', 'ornament')]
    changes += [{'sprite': sprite} for sprite in ('open', 'closed')]
    changes += [{key: None} for key in ('sequence', 'parts', 'placement', 'mobile', 'pivot', 'motion_params')]
    for change in changes:
      with self.subTest(change=change):
        raw = retraction_manifest()
        raw['layers'][1].update(change)
        self.assertIsNone(parse_retraction(raw))

  def test_retract_and_masks_are_forbidden_on_other_motions(self):
    for motion in ('none', 'float', 'pulse', 'helmet', 'breeze', 'drift'):
      for key, value in (('retract', retraction_manifest()['layers'][1]['retract']),
                         ('retract_mask', 'ember-ring.svg')):
        raw = retraction_manifest()
        layer = raw['layers'][0]
        layer.update(motion=motion)
        if motion == 'helmet':
          layer['sprite'] = 'closed'
        layer[key] = value
        self.assertIsNone(parse_retraction(raw))

  def test_optional_mask_resolves_to_safe_static_style(self):
    for layer in parse_retraction(retraction_manifest())['avatar'][1:]:
      self.assertEqual(layer['retract_mask_url'], '/static/cosmetics/ember-ring.svg')
      self.assertEqual(layer['retract_mask_style'],
          'mask-image:url("/static/cosmetics/ember-ring.svg");'
          '-webkit-mask-image:url("/static/cosmetics/ember-ring.svg")')
    for layer in parse_retraction(retraction_manifest(mask=False))['avatar'][1:]:
      self.assertNotIn('retract_mask_url', layer)
      self.assertNotIn('retract_mask_style', layer)

  def test_mask_rejects_missing_assets_path_traversal_and_malformed_values(self):
    for value in ('missing-retraction-mask.webp', '../ember-ring.svg',
                  '/static/cosmetics/ember-ring.svg', 'https://example.test/mask.png',
                  'data:image/png;base64,x', 'ember-ring.svg);display:none',
                  None, True, 1, {}, [], ''):
      with self.subTest(value=value):
        raw = retraction_manifest()
        raw['layers'][1]['retract_mask'] = value
        self.assertIsNone(parse_retraction(raw))

  def test_server_renders_three_separate_images_inside_fixed_mask_viewports(self):
    for masked in (True, False):
      package = parse_retraction(retraction_manifest(mask=masked))
      rendered = get_template('home/partials/_cosmetic_preview.html').render({
          'layers': package['avatar'], 'slot': 'avatar'})
      markup = ImageMarkup()
      markup.feed(rendered)
      self.assertEqual(len(markup.images), 4)
      self.assertEqual(len(markup.viewports), 3)
      self.assertIn('cosmetic-sprite--open', rendered)
      self.assertIn('data-aperture-x="50.000"', rendered)
      self.assertNotIn('cosmetic-helmet', rendered)
      for img, layer, viewport in zip(markup.images[1:], package['avatar'][1:], markup.viewports):
        self.assertIn('cosmetic-layer--retract', img['class'])
        self.assertEqual((img['width'], img['height']), ('512', '512'))
        self.assertEqual(img['src'], layer['url'])
        self.assertEqual(img['data-fallback'], layer['fallback'])
        self.assertIn(layer['retract_style'], img['style'])
        self.assertEqual(viewport['style'], layer.get('retract_mask_style', ''))
        self.assertNotIn('retract-x', viewport['style'])
        self.assertNotIn('mask-image', img['style'])

  def test_legacy_helmet_reader_and_markup_are_unchanged(self):
    raw = retraction_manifest()
    raw['layers'] = [dict(raw['layers'][0], motion='helmet', sprite='closed')]
    package = parse_retraction(raw)
    self.assertIsNotNone(package)
    self.assertNotIn('retract', package['avatar'][0])
    html = get_template('home/partials/_cosmetic_preview.html').render({
        'layers': package['avatar'], 'slot': 'avatar'})
    self.assertEqual(html.count('<img '), 5)
    self.assertIn('data-cosmetic-helmet', html)
    self.assertNotIn('cosmetic-retract-viewport', html)
