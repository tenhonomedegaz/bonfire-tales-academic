"""Versioned, static media packages for cosmetics already present in TbCosmetico.

Packages are presentation data. Eligibility remains in ``cosmetic_allowed`` and
the profile view; this module never grants a cosmetic to a user.
"""

import json
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
_MOTIONS = {'none', 'float', 'pulse', 'helmet'}
_SPRITES = {'full', 'open', 'closed'}
_MAX_ASSET_BYTES = 4 * 1024 * 1024


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


def parse_package(raw, slug, tipo, escopo='perfil'):
  """Validate a manifest and return template ready layers, or no package."""
  if not isinstance(raw, dict) or raw.get('version') != 1:
    return None
  if raw.get('slug') != slug or raw.get('type') != tipo:
    return None
  if escopo not in ('perfil', 'ficha') or raw.get('scope') not in (escopo, 'ambos'):
    return None
  layers = raw.get('layers')
  if not isinstance(layers, list) or not 1 <= len(layers) <= 8:
    return None
  result = {
    'slug': slug, 'type': tipo, 'version': 1,
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
      or type(width) is not int or type(height) is not int
      or not 32 <= width <= 4096 or not 32 <= height <= 4096
      or not source or not fallback
    ):
      return None
    result[slot].append({
      'url': source, 'fallback': fallback, 'anchor': anchor,
      'motion': motion, 'width': width, 'height': height,
      'sprite': sprite,
    })
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
    if path.stat().st_size > 16 * 1024:
      return None
    with path.open(encoding='utf-8') as source:
      raw = json.load(source)
  except (OSError, ValueError):
    return None
  return parse_package(raw, slug, tipo, escopo)
