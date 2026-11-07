"""Versioned, static media packages for cosmetics already present in TbCosmetico.

Packages are presentation data. Eligibility remains in ``cosmetic_allowed`` and
the profile view; this module never grants a cosmetic to a user.
"""

import json
import math
import re
from pathlib import Path

from django.templatetags.static import static

from .cosmetics import cosmetic_allowed


PACKAGE_ROOT = Path(__file__).resolve().parent / 'static' / 'cosmetics'
_SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
_ASSET = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*\.(?:png|webp|gif|svg)$')
_TYPES = {'tema', 'moldura', 'efeito', 'banner_preset'}
_SLOTS = {'banner', 'ornament', 'avatar'}
_ANCHORS = {'center', 'left', 'right'}
_MOTIONS = {'none', 'float', 'pulse', 'helmet', 'breeze', 'drift', 'retract'}
_SPRITES = {'full', 'open', 'closed'}
_MAX_ASSET_BYTES = 4 * 1024 * 1024
_RETRACT_BOUNDS = {'x': (-100, 100), 'y': (-100, 100), 'rotate': (-45, 45),
                   'duration': (100, 1500), 'delay': (0, 500)}


def _retract_layer(layer, output):
  """Slide a full avatar image inside an optional stationary opening mask."""
  if output['motion'] != 'retract':
    return not any(key in layer for key in ('retract', 'retract_mask'))
  if (layer['slot'] != 'avatar' or output['sprite'] != 'full'
      or any(key in layer for key in ('sequence', 'parts', 'placement'))
      or not _numeric_schema(layer.get('retract'), _RETRACT_BOUNDS)):
    return False
  output['retract'] = dict(layer['retract'])
  units = {'x': '%', 'y': '%', 'rotate': 'deg', 'duration': 'ms', 'delay': 'ms'}
  output['retract_style'] = ';'.join(
    f'--cosmetic-retract-{key}:{output["retract"][key]}{unit}' for key, unit in units.items())
  if 'retract_mask' in layer:
    mask_url = _asset_url(layer['retract_mask'])
    if not mask_url:
      return False
    output['retract_mask_url'] = mask_url
    output['retract_mask_style'] = (
      f'mask-image:url({json.dumps(mask_url)});-webkit-mask-image:url({json.dumps(mask_url)})')
  return True


def _numeric_schema(value, bounds):
  return (isinstance(value, dict) and value.keys() == bounds.keys()
          and all(type(value[key]) in (int, float)
                  and low <= value[key] <= high and math.isfinite(value[key])
                  for key, (low, high) in bounds.items()))


def _position_layer(layer, output):
  """Keep layout separate from image motion, including reduced-motion centering."""
  bounds = {'x': (0, 100), 'y': (0, 100), 'width': (1, 200)}
  placement = layer.get('placement')
  if 'placement' not in layer:
    return not any(key in layer for key in ('mobile', 'motion_params', 'pivot')) and output['motion'] != 'drift'
  if (layer['slot'] != 'banner' or output['sprite'] != 'full'
      or output['motion'] == 'breeze' or not _numeric_schema(placement, bounds)):
    return False
  output['placement'] = dict(placement)
  properties = [(f'--cosmetic-{key}', value, '%') for key, value in placement.items()]
  if 'pivot' in layer:
    if not _numeric_schema(layer['pivot'], {'x': (0, 100), 'y': (0, 100)}):
      return False
    output['pivot'] = dict(layer['pivot'])
    properties.extend((f'--cosmetic-pivot-{key}', value, '%') for key, value in layer['pivot'].items())
  if 'mobile' in layer:
    if not _numeric_schema(layer['mobile'], bounds):
      return False
    output['mobile'] = dict(layer['mobile'])
    properties.extend((f'--cosmetic-mobile-{key}', value, '%') for key, value in layer['mobile'].items())
  if output['motion'] == 'drift':
    params = {'distance': 40, 'duration': 60, 'delay': -30}
    supplied = layer.get('motion_params', {})
    if not isinstance(supplied, dict) or supplied.keys() - params.keys():
      return False
    params.update(supplied)
    if not _numeric_schema(params, {'distance': (1, 150), 'duration': (20, 180), 'delay': (-180, 0)}):
      return False
    output['motion_params'] = params
    properties.extend((f'--cosmetic-drift-{key}', value, '%' if key == 'distance' else 's')
                      for key, value in params.items())
  elif 'motion_params' in layer:
    return False
  output['placement_style'] = ';'.join(f'{key}:{value}{unit}' for key, value, unit in properties)
  return True


def _asset_url(filename):
  """Return only URLs for present, flat files under the cosmetics directory."""
  if not isinstance(filename, str) or not _ASSET.fullmatch(filename):
    return ''
  path = PACKAGE_ROOT / filename
  try:
    if path.resolve().parent != PACKAGE_ROOT.resolve():
      return ''
    if not path.is_file() or path.stat().st_size > _MAX_ASSET_BYTES:
      return ''
  except OSError:
    return ''
  return static('cosmetics/' + filename)


def _sequence_layer(layer, output):
  """Optional bounded atlas timeline; numeric presentation data, never code."""
  if 'sequence' not in layer:
    return True
  seq = layer['sequence']
  if (output['motion'] not in ('none', 'float') or output['sprite'] != 'full'
      or layer['slot'] != 'banner' or 'placement' not in output
      or not isinstance(seq, dict)
      or seq.keys() - {'columns', 'rows', 'duration', 'delay', 'backdrop', 'frames', 'backdropFrames'}
      or not {'columns', 'duration', 'delay', 'backdrop', 'frames'} <= seq.keys()):
    return False
  columns = seq['columns']
  rows = seq.get('rows', 1)
  if (type(columns) is not int or not 1 <= columns <= 8
      or type(rows) is not int or not 1 <= rows <= 8
      or not _numeric_schema({key: seq[key] for key in ('duration', 'delay', 'backdrop')},
                            {'duration': (1, 120), 'delay': (-120, 0), 'backdrop': (0, .85)})
      or not isinstance(seq['frames'], list) or not 4 <= len(seq['frames']) <= 64):
    return False
  previous = -1
  for frame in seq['frames']:
    bounds = {'at': (0, 1), 'frame': (0, columns * rows - 1), 'opacity': (0, 1)}
    for key, limits in {'shift': (-25, 25), 'x': (-100, 100), 'y': (-100, 100),
                        'rotate': (-15, 15), 'scaleX': (.8, 1.2), 'scaleY': (.8, 1.2)}.items():
      if isinstance(frame, dict) and key in frame:
        bounds[key] = limits
    if (not _numeric_schema(frame, bounds)
        or type(frame['frame']) is not int or frame['at'] <= previous):
      return False
    previous = frame['at']
  if seq['frames'][0]['at'] != 0 or seq['frames'][-1]['at'] != 1:
    return False
  if 'backdropFrames' in seq:
    backdrop_frames = seq['backdropFrames']
    if (seq['backdrop'] <= 0 or not isinstance(backdrop_frames, list)
        or not 4 <= len(backdrop_frames) <= 64):
      return False
    previous = -1
    for frame in backdrop_frames:
      if (not _numeric_schema(frame, {'at': (0, 1), 'opacity': (0, 1)})
          or frame['at'] <= previous):
        return False
      previous = frame['at']
    if backdrop_frames[0]['at'] != 0 or backdrop_frames[-1]['at'] != 1:
      return False
  output['sequence'] = seq
  output['sequence_json'] = json.dumps(seq, separators=(',', ':'), allow_nan=False)
  return True


def parse_package(raw, slug, tipo, escopo='perfil', *, _depth=0):
  """Validate a manifest and return template ready layers, or no package."""
  if not isinstance(raw, dict) or raw.get('version') != 1:
    return None
  if raw.get('slug') != slug or raw.get('type') != tipo:
    return None
  if escopo not in ('perfil', 'ficha') or raw.get('scope') not in (escopo, 'ambos'):
    return None
  overlay = raw.get('overlay', False)
  if type(overlay) is not bool:
    return None
  layers = raw.get('layers')
  if not isinstance(layers, list) or not 1 <= len(layers) <= 8:
    return None
  result = {
    'slug': slug, 'type': tipo, 'version': 1, 'overlay': overlay,
    'banner': [], 'ornament': [], 'avatar': [],
  }
  for layer in layers:
    if not isinstance(layer, dict):
      return None
    slot = layer.get('slot')
    anchor = layer.get('anchor', 'center')
    motion = layer.get('motion', 'none')
    sprite = layer.get('sprite', 'full')
    width, height = layer.get('width'), layer.get('height')
    source = _asset_url(layer.get('file'))
    fallback = _asset_url(layer.get('fallback'))
    if (
      slot not in _SLOTS or anchor not in _ANCHORS or motion not in _MOTIONS
      or sprite not in _SPRITES or (motion == 'helmet' and (sprite != 'closed' or slot != 'avatar'))
      or (motion == 'breeze' and (slot != 'banner' or sprite != 'full'))
      or type(width) is not int or type(height) is not int
      or not 32 <= width <= 4096 or not 32 <= height <= 4096
      or not source or not fallback
    ):
      return None
    result[slot].append({
      'url': source, 'fallback': fallback, 'anchor': anchor,
      'motion': motion, 'width': width, 'height': height,
      'sprite': sprite, 'overlay': overlay,
    })
    if not _retract_layer(layer, result[slot][-1]):
      return None
    if 'opacity' in layer:
      if not _numeric_schema({'opacity': layer['opacity']}, {'opacity': (0, 1)}):
        return None
      result[slot][-1]['opacity'] = layer['opacity']
      result[slot][-1]['opacity_style'] = f"--cosmetic-opacity:{layer['opacity']}"
    if not _position_layer(layer, result[slot][-1]):
      return None
    if not _sequence_layer(layer, result[slot][-1]):
      return None
    if 'mask' in layer:
      mask = layer['mask']
      sequence = result[slot][-1].get('sequence', {})
      if (not isinstance(mask, dict) or mask.keys() != {'file'}
          or sequence.get('columns') != 1 or sequence.get('rows', 1) != 1):
        return None
      mask_url = _asset_url(mask['file'])
      if not mask_url:
        return None
      result[slot][-1]['mask_url'] = mask_url
    if 'parts' in layer:
      parts = layer['parts']
      sequence = result[slot][-1].get('sequence', {})
      if (_depth or not isinstance(parts, list) or not 1 <= len(parts) <= 6
          or sequence.get('columns') != 1 or sequence.get('rows', 1) != 1):
        return None
      for part in parts:
        if (not isinstance(part, dict) or part.get('slot') != 'banner'
            or 'placement' not in part or not isinstance(part.get('sequence'), dict)
            or part['sequence'].get('backdrop') != 0):
          return None
      children = parse_package(dict(raw, layers=parts), slug, tipo, escopo, _depth=1)
      if children is None:
        return None
      result[slot][-1]['parts'] = children['banner']
      result[slot][-1]['parts_json'] = json.dumps(children['banner'], separators=(',', ':'), allow_nan=False)
    aperture = layer.get('aperture')
    if aperture is not None:
      if (slot != 'avatar' or not isinstance(aperture, dict)
          or any(type(aperture.get(key)) not in (int, float) for key in ('cx', 'cy', 'diameter'))
          or not all(0 < aperture[key] < 100 for key in ('cx', 'cy', 'diameter'))):
        return None
      result[slot][-1]['aperture'] = {key: aperture[key] for key in ('cx', 'cy', 'diameter')}
  return result


def get_package(user, tipo, value, escopo='perfil'):
  """Load media for an eligible catalog item, never from a client supplied path."""
  if tipo not in _TYPES or not isinstance(value, str) or not _SLUG.fullmatch(value):
    return None
  if not cosmetic_allowed(user, tipo, value, escopo):
    return None
  return load_package(tipo, value, escopo)


def load_package(tipo, value, escopo='perfil'):
  """Read only static media; caller must already have checked catalog access."""
  if tipo not in _TYPES or not isinstance(value, str) or not _SLUG.fullmatch(value):
    return None
  slug = tipo + '-' + value
  path = PACKAGE_ROOT / (slug + '.json')
  try:
    if path.stat().st_size > 64 * 1024:
      return None
    with path.open(encoding='utf-8') as source:
      raw = json.load(source)
  except (OSError, ValueError):
    return None
  return parse_package(raw, slug, tipo, escopo)
