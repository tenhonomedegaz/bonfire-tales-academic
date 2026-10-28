"""Static layer layout contract. These tests never access a database."""

from copy import deepcopy

from django.template.loader import get_template
from django.test import SimpleTestCase

from home.cosmetic_packages import parse_package


def layout_manifest():
  return {
    'version': 1, 'slug': 'tema-layout-test', 'type': 'tema', 'scope': 'ambos',
    'layers': [{
      'slot': 'banner', 'file': 'arcane-banner.svg', 'fallback': 'arcane-banner.svg',
      'width': 1200, 'height': 340, 'motion': 'drift',
      'placement': {'x': 45, 'y': 30, 'width': 120},
      'mobile': {'x': 55, 'y': 25, 'width': 180},
      'motion_params': {'distance': 40, 'duration': 60, 'delay': -30},
    }],
  }


def parse_layout(raw):
  return parse_package(raw, raw['slug'], raw['type'])


class CosmeticLayerLayoutTests(SimpleTestCase):
  def test_same_layout_and_template_for_profile_and_sheet(self):
    raw = layout_manifest()
    profile = parse_layout(raw)
    self.assertEqual(profile, parse_package(raw, raw['slug'], raw['type'], 'ficha'))
    layer = profile['banner'][0]
    self.assertEqual(layer['placement'], raw['layers'][0]['placement'])
    self.assertEqual(layer['mobile'], raw['layers'][0]['mobile'])
    html = get_template('home/partials/_cosmetic_preview.html').render({'layers': profile['banner'], 'slot': 'banner'})
    self.assertIn('class="cosmetic-positioned"', html)
    self.assertIn('style="' + layer['placement_style'] + '"', html)
    self.assertIn('cosmetic-layer--drift', html)
    self.assertIn('width="1200" height="340"', html)
    self.assertEqual(html.count('<img '), 1)

  def test_legacy_cover_has_no_position_wrapper_or_new_defaults(self):
    raw = layout_manifest()
    raw['layers'][0] = {key: value for key, value in raw['layers'][0].items()
                        if key not in ('placement', 'mobile', 'motion_params')}
    raw['layers'][0]['motion'] = 'none'
    layer = parse_layout(raw)['banner'][0]
    self.assertNotIn('placement', layer)
    html = get_template('home/partials/_cosmetic_preview.html').render({'layers': [layer], 'slot': 'banner'})
    self.assertNotIn('cosmetic-positioned', html)
    self.assertIn('cosmetic-layer--none', html)

  def test_partial_motion_params_use_safe_defaults_without_mutating_input(self):
    raw = layout_manifest()
    raw['layers'][0]['motion_params'] = {'duration': 90}
    before = deepcopy(raw)
    self.assertEqual(parse_layout(raw)['banner'][0]['motion_params'], {'distance': 40, 'duration': 90, 'delay': -30})
    self.assertEqual(before, raw)
    del raw['layers'][0]['motion_params']
    self.assertEqual(parse_layout(raw)['banner'][0]['motion_params']['delay'], -30)

  def test_numeric_layout_rejects_injection_nonfinite_and_invalid_shapes(self):
    for field in ('placement', 'mobile'):
      for value in (None, [], {}, {'x': 50, 'y': 50}, {'x': 50, 'y': 50, 'width': 100, 'extra': 1}):
        with self.subTest(field=field, value=value):
          raw = layout_manifest()
          raw['layers'][0][field] = value
          self.assertIsNone(parse_layout(raw))
      for key, values in {
        'x': [-1, 101, True, '50;position:fixed', float('nan'), float('inf'), 10**400],
        'y': [-1, 101, False, None, float('-inf')],
        'width': [0, 201, True, '120', float('nan')],
      }.items():
        for value in values:
          with self.subTest(field=field, key=key, value=value):
            raw = layout_manifest()
            raw['layers'][0][field][key] = value
            self.assertIsNone(parse_layout(raw))

  def test_numeric_boundaries_and_fractional_percentages(self):
    raw = layout_manifest()
    raw['layers'][0]['placement'] = {'x': 0, 'y': 100, 'width': 1}
    raw['layers'][0]['mobile'] = {'x': 100, 'y': 0.125, 'width': 200}
    raw['layers'][0]['motion_params'] = {'distance': 1, 'duration': 20, 'delay': -180}
    self.assertIsNotNone(parse_layout(raw))
    raw['layers'][0]['motion_params'] = {'distance': 150, 'duration': 180, 'delay': 0}
    self.assertIsNotNone(parse_layout(raw))

  def test_opacity_is_optional_finite_numeric_and_template_safe(self):
    for value in (0, 0.55, 1):
      raw = layout_manifest()
      raw['layers'][0]['opacity'] = value
      layer = parse_layout(raw)['banner'][0]
      self.assertEqual(layer['opacity'], value)
      html = get_template('home/partials/_cosmetic_preview.html').render({'layers': [layer], 'slot': 'banner'})
      self.assertIn(f'--cosmetic-opacity:{value}', html)
    for value in (-0.1, 1.1, True, '0.5', None, float('nan'), float('inf')):
      raw = layout_manifest()
      raw['layers'][0]['opacity'] = value
      self.assertIsNone(parse_layout(raw))

  def test_motion_params_reject_invalid_and_nonfinite_values(self):
    for params in (None, [], {'extra': 10}, {'distance': 0}, {'distance': 151},
                   {'duration': 19}, {'duration': 181}, {'delay': 1}, {'delay': -181},
                   {'distance': True}, {'duration': '60'}, {'delay': float('nan')},
                   {'distance': float('inf')}, {'duration': 10**400}):
      with self.subTest(params=params):
        raw = layout_manifest()
        raw['layers'][0]['motion_params'] = params
        self.assertIsNone(parse_layout(raw))

  def test_drift_requires_positioned_full_banner(self):
    for change in ({'slot': 'avatar'}, {'slot': 'ornament'}, {'sprite': 'open'}, {'motion': 'breeze'}):
      raw = layout_manifest()
      raw['layers'][0].update(change)
      self.assertIsNone(parse_layout(raw))
    raw = layout_manifest()
    for key in ('placement', 'mobile', 'motion_params'):
      raw['layers'][0].pop(key)
    self.assertIsNone(parse_layout(raw))

  def test_mobile_and_motion_params_cannot_be_orphaned(self):
    for key in ('mobile', 'motion_params'):
      raw = layout_manifest()
      layer = raw['layers'][0]
      layer['motion'] = 'none'
      layer.pop('placement')
      layer.pop('mobile' if key == 'motion_params' else 'motion_params')
      self.assertIsNone(parse_layout(raw))
    raw = layout_manifest()
    raw['layers'][0]['motion'] = 'none'
    self.assertIsNone(parse_layout(raw))

  def test_static_placements_and_repeated_asset_layers_preserve_order(self):
    raw = layout_manifest()
    raw['layers'][0].pop('mobile')
    raw['layers'][0].pop('motion_params')
    raw['layers'][0]['motion'] = 'none'
    raw['layers'] *= 7
    package = parse_layout(raw)
    self.assertEqual(len(package['banner']), 7)
    self.assertEqual([layer['motion'] for layer in package['banner']], ['none'] * 7)
    self.assertNotIn('mobile', package['banner'][0])
