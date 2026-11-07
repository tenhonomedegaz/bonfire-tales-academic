"""New artwork replaces presentation only, not progression or entitlements."""
import json
from pathlib import Path
from types import SimpleNamespace
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from .character_engine import rank_icone_url, rank_por_nivel
from .cosmetic_packages import load_package
from .ranks import character_rank

ROOT=Path(__file__).resolve().parents[1]

class RankMetalPresentationTests(SimpleTestCase):
    def test_each_rank_has_own_real_raster_assets_and_registered_aperture(self):
        from PIL import Image
        rows=json.loads((ROOT/'docs/cosmetics/rank-metal-catalog.json').read_text())['cosmetics']
        self.assertEqual(len(rows),7)
        self.assertEqual(len({r['theme_asset'] for r in rows}),7)
        for row in rows:
            key=row['slug'].removeprefix('tema-rank-')
            with self.subTest(rank=key):
                opened=load_package('moldura',f'elo-{key}-aberta')['avatar'][0]
                closed_layers=load_package('moldura',f'elo-{key}-fechada')['avatar']
                closed=closed_layers[0]
                self.assertEqual(opened['aperture'],closed['aperture'])
                self.assertEqual(opened['motion'],'none')
                self.assertEqual(closed,opened)
                self.assertEqual(len(closed_layers),4)
                self.assertTrue(all(part['motion']=='retract' for part in closed_layers[1:]))
                self.assertIn('-open-base-v1.webp',opened['url'])
                self.assertEqual(opened['sprite'],'full')
                self.assertGreater(opened['aperture']['diameter'],45)
                self.assertLess(opened['aperture']['diameter'],80)
                with Image.open(ROOT/'home/static/cosmetics'/row['theme_asset']) as image:
                    self.assertEqual(image.size,(1024,1024))
                    self.assertEqual(image.mode,'RGBA')
                with Image.open(ROOT/'home/static/cosmetics'/row['frame_asset']) as image:
                    self.assertEqual(image.size,(1024,512))

    def test_all_visors_preserve_source_pixels_and_transparent_eye_openings(self):
        from PIL import Image, ImageChops
        assets=ROOT/'home/static/cosmetics'
        config=json.loads((ROOT/'docs/cosmetics/rank-visor-rigs.json').read_text())
        total=0
        for rig in config['ranks']:
            rank=rig['rank']
            with self.subTest(rank=rank):
                package=load_package('moldura',f'elo-{rank}-fechada')
                self.assertIsNotNone(package)
                base_file=package['avatar'][0]['url'].rsplit('/',1)[-1]
                original=Image.open(assets/rig['source']).convert('RGBA')
                self.assertEqual(Image.open(assets/base_file).convert('RGBA').tobytes(),original.crop((0,0,512,512)).tobytes())
                parts=package['avatar'][1:]
                self.assertEqual(len(parts),3)
                self.assertEqual(parts[0]['retract']['x'],0)
                self.assertLess(parts[0]['retract']['y'],0)
                self.assertLess(parts[1]['retract']['x'],0)
                self.assertGreater(parts[2]['retract']['x'],0)
                mask_file=f'rank-{rank}-visor-parts-v1-aperture.webp'
                opening=Image.open(assets/mask_file).getchannel('A')
                source=original.crop((512,0,1024,512))
                expected=ImageChops.multiply(source.getchannel('A'),opening)
                accumulated=Image.new('L',(512,512))
                occupied=Image.new('L',(512,512))
                for part in parts:
                    filename=part['url'].rsplit('/',1)[-1]
                    image=Image.open(assets/filename).convert('RGBA')
                    self.assertEqual(image.size,(512,512))
                    self.assertEqual(part['retract_mask_url'].rsplit('/',1)[-1],mask_file)
                    alpha=image.getchannel('A')
                    self.assertIsNone(ImageChops.multiply(occupied,alpha).getbbox())
                    occupied=ImageChops.lighter(occupied,alpha)
                    accumulated=ImageChops.add(accumulated,alpha)
                    difference=ImageChops.difference(image.convert('RGB'),source.convert('RGB'))
                    self.assertIsNone(ImageChops.multiply(difference,Image.merge('RGB',(alpha,alpha,alpha))).getbbox())
                    total+=(assets/filename).stat().st_size
                    self.assertEqual(image.tobytes(),Image.open(assets/filename.replace('.webp','.png')).convert('RGBA').tobytes())
                self.assertIsNone(ImageChops.difference(accumulated,expected).getbbox())
        self.assertLess(total,3_000_000)

    def test_supplied_eight_insignias_are_local_and_retina_sized(self):
        from PIL import Image
        for name in ['Obsidiana','Ametista','Topázio','Esmeralda','Âmbar','Rubi','Diamante','Lenda']:
            url=rank_icone_url(name)
            self.assertTrue(url.startswith('/static/icons/ranks/'))
            self.assertIn('-metal-v1.png',url)
            with Image.open(ROOT/'home'/url.removeprefix('/')) as image:
                self.assertEqual(image.size,(128,128))
        self.assertEqual(rank_icone_url('inventado'),'')

    def test_badge_uses_insignia_not_helmet_atlas_or_color_filter(self):
        rank=character_rank(SimpleNamespace(aventuras=0,pk=1))
        html=render_to_string('home/partials/rank_badge.html',{'rank':rank})
        self.assertIn('obsidiana-metal-v1.png',html)
        self.assertNotIn('rank-art-pair',html)
        self.assertNotIn('knight-closed-helm',html)

    def test_legend_art_does_not_create_another_cosmetic_rank(self):
        rank=character_rank(SimpleNamespace(aventuras=200,pk=1))
        self.assertEqual(rank['nome'],'Diamante')
        self.assertEqual(rank['open_frame_key'],'elo-diamante-aberta')
        self.assertIn('lenda-metal-v1.png',rank['icone_url'])
        self.assertTrue(rank['is_lenda'])
        self.assertEqual(rank_por_nivel(21),'Diamante')
        self.assertEqual(rank_por_nivel(22),'Lenda')

    def test_admin_catalog_sanitization_keeps_valid_unlock_but_not_css_injection(self):
        from .cosmetics import sanitize_catalog_theme_definition, sanitize_definicao_tema
        unlock={'schema_version':1,'metric':'rank_reached','rank':'Obsidiana',
                'min_level':1,'min_adventures':0,'permanent':True}
        raw={'accent':'url(javascript:bad)','desbloqueio':unlock,'arbitrary':'bad'}
        clean=sanitize_catalog_theme_definition(raw)
        self.assertEqual(clean['desbloqueio'],unlock)
        self.assertNotIn('arbitrary',clean)
        self.assertNotIn('url(',clean['accent'])
        self.assertNotIn('desbloqueio',sanitize_definicao_tema(raw))

    def test_invalid_unlock_is_rejected_instead_of_silently_discarded(self):
        from django.core.exceptions import ValidationError
        from .cosmetics import sanitize_catalog_theme_definition
        with self.assertRaises(ValidationError):
            sanitize_catalog_theme_definition({'desbloqueio':{'rank':'Inventado'}})
