"""Separate approved artwork into registered plates; never redraw or recolor it.

Run with the project's Python (Pillow required). Geometry is authoring data in
rank-visor-rigs.json; runtime animation parameters live in each manifest.
"""
import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'home/static/cosmetics'
CONFIG = Path(__file__).with_name('rank-visor-rigs.json')


def aperture_mask(opened):
  alpha = opened.getchannel('A')
  pixels = alpha.load()
  visited = {(256, 256)}
  queue = deque(visited)
  while queue:
    x, y = queue.popleft()
    for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
      px, py = point
      if 0 <= px < 512 and 0 <= py < 512 and point not in visited and pixels[px, py] < 32:
        visited.add(point)
        queue.append(point)
  assert len(visited) > 35000, 'Missing transparent portrait aperture'
  assert all(0 < x < 511 and 0 < y < 511 for x, y in visited), 'Open frame aperture leaks to exterior'
  interior = Image.new('L', (512, 512))
  interior.putdata([255 if (x, y) in visited else 0 for y in range(512) for x in range(512)])
  # Include antialiased inner edges without exposing any exterior of the rim.
  return ImageChops.multiply(interior.filter(ImageFilter.MaxFilter(7)), ImageChops.invert(alpha))


def polygon_mask(points):
  mask = Image.new('L', (512, 512))
  ImageDraw.Draw(mask).polygon(points, fill=255)
  return mask


def split_masks(row):
  left = polygon_mask(row['left_joint'] + [[row['left_joint'][-1][0], 512], [0, 512]])
  right = polygon_mask(row['right_joint'] + [[row['right_joint'][-1][0], 512], [512, 512]])
  # Resolve the shared chin seam once, so no pixel is drawn by two plates.
  right = ImageChops.subtract(right, left)
  upper = ImageChops.invert(ImageChops.lighter(left, right))
  return {'upper': upper, 'left': left, 'right': right}


def save_pair(image, stem):
  image.save(ASSETS / (stem + '.png'), optimize=True)
  image.save(ASSETS / (stem + '.webp'), lossless=True, method=6, exact=True)


def build(row):
  rank = row['rank']
  open_raw = json.loads((ASSETS / f'moldura-elo-{rank}-aberta.json').read_text(encoding='utf-8'))
  base = open_raw['layers'][0]
  atlas = Image.open(ASSETS / row['source']).convert('RGBA')
  assert atlas.size == (1024, 512)
  opened = atlas.crop((0, 0, 512, 512))
  closed = atlas.crop((512, 0, 1024, 512))
  base_name = f'rank-{rank}-open-base-v1'
  save_pair(opened, base_name)
  base = dict(base, file=base_name + '.webp', fallback=base_name + '.png',
              width=512, height=512, sprite='full', motion='none')
  open_raw['layers'] = [base]
  (ASSETS / (open_raw['slug'] + '.json')).write_text(json.dumps(open_raw, indent=2) + '\n', encoding='utf-8')
  aperture = aperture_mask(opened)
  prefix = f'rank-{rank}-visor-parts-v1'
  mask_name = prefix + '-aperture'
  white = Image.new('RGBA', (512, 512), 'white')
  white.putalpha(aperture)
  save_pair(white, mask_name)
  clipped_alpha = ImageChops.multiply(closed.getchannel('A'), aperture)
  alpha_sum = Image.new('L', (512, 512))
  layers = [dict(base)]
  for part, mask in split_masks(row).items():
    plate = closed.copy()
    plate_alpha = ImageChops.multiply(clipped_alpha, mask)
    assert plate_alpha.getbbox() is not None
    plate.putalpha(plate_alpha)
    # Remove invisible RGB to keep the transparent derivatives compact.
    clean = Image.new('RGBA', plate.size)
    clean.paste(plate, mask=plate_alpha.point(lambda a: 255 if a else 0))
    stem = prefix + '-' + part
    save_pair(clean, stem)
    alpha_sum = ImageChops.add(alpha_sum, plate_alpha)
    upper = part == 'upper'
    direction = -1 if part == 'left' else 1
    layers.append({
      'slot': 'avatar', 'file': stem + '.webp', 'fallback': stem + '.png',
      'width': 512, 'height': 512, 'sprite': 'full', 'motion': 'retract',
      'retract_mask': mask_name + '.webp',
      'retract': {'x': 0 if upper else direction * row['travel'],
                  'y': -32 if upper else 2, 'rotate': 0 if upper else direction * 4,
                  'duration': 580 if upper else 540, 'delay': 0 if upper else 45},
    })
  assert ImageChops.difference(alpha_sum, clipped_alpha).getbbox() is None, 'Lost or duplicated plate pixels'
  manifest = dict(open_raw, slug=f'moldura-elo-{rank}-fechada', layers=layers)
  (ASSETS / (manifest['slug'] + '.json')).write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
  print(rank + ': stationary open frame + upper / left / right; pixel-conserving split')


if __name__ == '__main__':
  config = json.loads(CONFIG.read_text(encoding='utf-8'))
  assert config['schema'] == 1 and config['canvas'] == 512
  for rank_row in config['ranks']:
    build(rank_row)
