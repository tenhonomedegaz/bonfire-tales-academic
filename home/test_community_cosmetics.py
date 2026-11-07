"""Community media release: static presentation, not a new grant mechanism."""
import json
import ast
from pathlib import Path
from django.test import SimpleTestCase
from PIL import Image
from .cosmetic_packages import load_package
from .cosmetic_picker import _presentation_metadata

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'home/static/cosmetics'

class CommunityCosmeticTests(SimpleTestCase):
  def test_profile_does_not_build_the_removed_eager_public_preview(self):
    tree=ast.parse((ROOT/'home/views.py').read_text(encoding='utf-8-sig'))
    profile=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='profile_view')
    keys={node.value for node in ast.walk(profile) if isinstance(node,ast.Constant) and isinstance(node.value,str)}
    self.assertTrue({'preview_personagens','preview_badges','preview_conquistas','preview_appearance'}.isdisjoint(keys))
    calls=[node for node in ast.walk(profile) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)]
    self.assertFalse(any(node.func.id=='_perfil_personagens' for node in calls))
    template=(ROOT/'home/templates/home/pages/perfil.html').read_text(encoding='utf-8')
    self.assertNotIn("{% cosmetic_package '",template)
    self.assertNotIn("layers=effect_package",template)

  def test_six_frames_have_readable_real_art_and_transparent_calibrated_centers(self):
    keys=['ember-ring','arcane-pulse','gold-trim','frost','verdant','guardiao-da-fogueira']
    for key in keys:
      with self.subTest(key=key):
        package=load_package('moldura',key)
        self.assertIsNotNone(package)
        self.assertEqual(package,load_package('moldura',key,'ficha'))
        layer=package['avatar'][0]
        self.assertIn('community-frame-',layer['url'])
        self.assertEqual(layer['motion'],'none')
        opening=layer['aperture']
        self.assertTrue(45<opening['cx']<55 and 45<opening['cy']<55)
        self.assertTrue(50<opening['diameter']<90)
        image=Image.open(ASSETS/layer['fallback'].rsplit('/',1)[-1]).convert('RGBA')
        self.assertEqual(image.size,(512,512))
        self.assertEqual(image.getpixel((256,256))[3],0)
        self.assertTrue(any(pixel[3]>100 for pixel in image.getdata()))

  def test_simple_effects_are_transparent_overlays_with_bounded_existing_motion(self):
    for key in ('folhas-da-trilha','faiscas-da-forja','fogueira-partilhada'):
      package=load_package('efeito',key)
      self.assertTrue(package['overlay'])
      layer=package['banner'][0]
      self.assertIn(layer['motion'],('drift','float'))
      image=Image.open(ASSETS/layer['fallback'].rsplit('/',1)[-1]).convert('RGBA')
      self.assertEqual(image.size,(1200,400))
      center=image.getchannel('A').crop((480,0,720,400))
      # Ignore isolated subpixel specks from the painted source, not ornaments.
      visible=sum(alpha>32 for alpha in center.getdata())
      self.assertLess(visible,center.width*center.height*.001)

  def test_release_keeps_existing_access_and_colab_uses_existing_minimum_tier(self):
    data=json.loads((ROOT/'docs/cosmetics/community-catalog-release.json').read_text(encoding='utf-8'))
    self.assertEqual(data['status'],'prepared-not-applied')
    for item in data['updates']:
      self.assertEqual(set(item),{'slug','descricao'})
    rows=data['create_if_missing']
    self.assertEqual(len(rows),5)
    self.assertEqual(len({r['slug'] for r in rows}),5)
    colab=[r for r in rows if r['origem']=='colaborador']
    self.assertEqual({r['tipo'] for r in colab},{'tema','moldura','efeito'})
    self.assertTrue(all(r['requer_plano']=='conde' for r in colab))
    self.assertFalse(any(r['origem']=='livre' and r['tipo']=='tema' for r in rows))
    theme=next(r for r in colab if r['tipo']=='tema')
    self.assertEqual(theme['definicao_json']['categoria'],'especial')
    self.assertIn('skin-illustrated',theme['css_class'])

  def test_picker_thumbnails_are_small_real_files_not_live_packages(self):
    registry=_presentation_metadata()
    self.assertGreater(len(registry),35)
    for key,metadata in registry.items():
      with self.subTest(key=key):
        filename=ROOT/'home/static'/metadata['thumbnail']
        self.assertTrue(filename.is_file())
        self.assertLess(filename.stat().st_size,50000)
        with Image.open(filename) as image:
          self.assertEqual(image.size,(112,112))
