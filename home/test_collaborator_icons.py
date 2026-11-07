"""Catalog artwork renders without database access or checkout changes."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.template import Context, Engine
from django.test import SimpleTestCase, override_settings

from home.templatetags.commerce_presentation import collaborator_icon
from home.views import COLABORADOR_TIERS, COLABORADOR_TOKENS


@override_settings(STATIC_URL='/static/')
class CollaboratorIconTests(SimpleTestCase):
    expected = {
        'colaborador-conde-1m': 'conde-condessa.png',
        'colaborador-marques-1m': 'marques-marquesa.png',
        'colaborador-duque-1m': 'duque-duquesa.png',
        'token-missao': 'missao-especial.png',
        'token-boost': 'boost.png',
        'token-superboost': 'superboost.png',
    }

    def test_six_exact_assets_have_retina_dimensions(self):
        from PIL import Image
        root = Path(__file__).parent / 'static'
        products = COLABORADOR_TIERS + COLABORADOR_TOKENS
        self.assertEqual({item['product_code'] for item in products}, set(self.expected))
        for code, filename in self.expected.items():
            with self.subTest(product=code):
                self.assertEqual(collaborator_icon(code), '/static/icons/collaborator/' + filename)
                with Image.open(root / 'icons' / 'collaborator' / filename) as image:
                    self.assertEqual(image.size, (128, 128))
                    self.assertIn('A', image.getbands())
                    self.assertGreater(image.getchannel('A').getextrema()[1], 0)

    def test_unknown_products_do_not_create_asset_paths(self):
        for code in ('unknown', '../boost', 'https://example.test/icon', '', None):
            self.assertEqual(collaborator_icon(code), '')

    def render_page(self, ready, tiers=None, tokens=None):
        engine = Engine(
            dirs=[str(Path(__file__).parent / 'templates')],
            loaders=[('django.template.loaders.locmem.Loader', {
                'home/base.html': '{% block extra_head %}{% endblock %}{% block content %}{% endblock %}',
            }), 'django.template.loaders.filesystem.Loader'],
            libraries={
                'static': 'django.templatetags.static',
                'commerce_presentation': 'home.templatetags.commerce_presentation',
            },
        )
        context = Context({
            'tiers': COLABORADOR_TIERS if tiers is None else tiers,
            'tokens': COLABORADOR_TOKENS if tokens is None else tokens,
            'user': SimpleNamespace(is_authenticated=ready, email=''),
            'checkout_account_ready': ready,
            'csrf_token': 'test-csrf-token',
        })
        with patch('django.urls.reverse', side_effect=lambda name, **kw: '/' + name + '/'):
            return engine.get_template('home/pages/colaborador.html').render(context)

    def test_render_preserves_prices_products_and_account_gates(self):
        before = deepcopy((COLABORADOR_TIERS, COLABORADOR_TOKENS))
        for ready in (False, True):
            with self.subTest(account_ready=ready):
                html = self.render_page(ready)
                self.assertEqual(html.count('class="co-collaborator-icon"'), 6)
                self.assertEqual(html.count('width="64" height="64" alt=""'), 6)
                for filename in self.expected.values():
                    self.assertEqual(html.count('/static/icons/collaborator/' + filename), 1)
                for product in COLABORADOR_TIERS + COLABORADOR_TOKENS:
                    self.assertIn(product.get('preco_mes', product.get('preco')), html)
                self.assertEqual(html.count('<form '), 18 if ready else 0)
                if ready:
                    for tier in COLABORADOR_TIERS:
                        self.assertIn('value="' + tier['product_code'] + '"', html)
                        for plan in tier['planos']:
                            self.assertIn('value="' + plan['product_code'] + '"', html)
                            self.assertIn(plan['preco'], html)
                    for token in COLABORADOR_TOKENS:
                        self.assertIn('value="' + token['product_code'] + '"', html)
                    self.assertEqual(html.count('value="recurring"'), 3)
                    self.assertEqual(html.count('value="single"'), 15)
        self.assertEqual((COLABORADOR_TIERS, COLABORADOR_TOKENS), before)

    def test_unknown_product_keeps_symbol_fallback(self):
        tiers = [dict(COLABORADOR_TIERS[0], product_code='unknown')]
        html = self.render_page(False, tiers=tiers, tokens=[])
        self.assertNotIn('co-collaborator-icon', html)
        self.assertNotIn('src=""', html)
        self.assertIn('<svg', html)
