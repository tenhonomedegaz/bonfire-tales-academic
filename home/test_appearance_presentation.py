"""Regressions for rank cards and the shared profile/sheet media contract."""
from pathlib import Path
import json

from bs4 import BeautifulSoup
from PIL import Image
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from .cosmetics import invalidate_cosmetic_cache
from .models import TbCosmetico, TbPersonagem
from .ranks import character_rank
from .views import _personagem_card


class AppearancePresentationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('appearance-owner')
        self.character = TbPersonagem.objects.create(
            dono=self.owner, nome='Guarda de Cristal', aventuras=59, publico=True,
            foto_url='/static/brand/human.webp', banner_url='/static/brand/world.webp',
            ficha_theme='arcane', foto_frame='arcane-pulse')
        for slug, kind, css in (
            ('tema-arcane','tema','theme-arcane'),
            ('moldura-arcane-pulse','moldura','frame-arcane-pulse')):
            TbCosmetico.objects.create(slug=slug,tipo=kind,nome=slug,
                css_class=css,escopo='ambos',origem='livre')
        invalidate_cosmetic_cache()

    def tearDown(self):
        invalidate_cosmetic_cache()

    def test_character_card_has_its_own_rank_and_no_empty_image(self):
        card = _personagem_card(self.character)
        self.assertEqual(card['rank']['nome'], 'Esmeralda')
        html = render_to_string('home/partials/personagem_card.html', {'c':card})
        images = BeautifulSoup(html, 'html.parser').select('img')
        self.assertTrue(images)
        self.assertTrue(all(image.get('src') for image in images))
        self.assertIn('rank-esmeralda-v3.webp', html)

    def test_anonymous_sheet_uses_owner_packages_and_real_banner(self):
        response = self.client.get(reverse('ficha_publica',args=[self.character.pk]))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['character_owner'],self.owner)
        self.assertContains(response,'/static/cosmetics/arcane-ring.svg')
        self.assertContains(response,'/static/brand/world.webp')
        self.assertContains(response,'cosmetic-has-banner')

    def test_private_sheet_banner_uses_same_package_assets(self):
        context = {'p':self.character,'appearance':{
            'theme_key':'arcane','frame_key':'arcane-pulse','effect_key':'none',
            'frame_class':'frame-arcane-pulse'},'ficha':{'classes':[],
                'nivel_total':1,'progressao':{'nivel_aventuras':1}}}
        html = render_to_string('home/partials/_ficha_banner.html',context)
        self.assertIn('/static/cosmetics/arcane-ring.svg',html)
        self.assertIn('/static/cosmetics/arcane-banner.svg',html)
        self.assertIn('is-packaged',html)

    def test_all_existing_ranks_have_local_icon_and_frame_assets(self):
        static = Path(__file__).resolve().parent/'static'
        covered = set()
        for adventures in (0,9,28,59,102,140,160,200):
            self.character.aventuras = adventures
            rank = character_rank(self.character)
            covered.add(rank['key'])
            self.assertTrue(rank['nome'])
            self.assertTrue((static/rank['icone_url'].removeprefix('/static/')).is_file())
            self.assertTrue((static/rank['helmet_url'].removeprefix('/static/')).is_file())
            self.assertTrue(rank['art_url'])
            self.assertTrue((static/rank['art_url'].removeprefix('/static/')).is_file())
        self.assertEqual(len(covered),7)

    def test_unconfigured_rank_badge_omits_broken_image_instead_of_empty_src(self):
        self.assertNotIn('<img',render_to_string('home/partials/rank_badge.html',{}))

    def test_each_rank_has_distinct_cartoon_pair_with_transparent_opening(self):
        static = Path(__file__).resolve().parent/'static'
        catalog = json.loads((static/'icons/ranks/art.json').read_text(encoding='utf-8'))
        self.assertEqual(len(catalog),7)
        self.assertEqual(len(set(catalog.values())),7)
        for key,filename in catalog.items():
            with self.subTest(rank=key), Image.open(static/'cosmetics'/filename) as image:
                self.assertEqual(image.mode,'RGBA')
                self.assertEqual(image.width,2*image.height)
                self.assertLessEqual(image.getpixel((image.width//4,image.height//2))[3],2)
                self.assertLessEqual(image.getpixel((3*image.width//4,int(image.height*.65)))[3],2)
