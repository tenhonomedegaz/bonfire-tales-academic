"""Storefront routing, display and original form contracts without SQL."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse

from home.models import TbCosmetico
from home.views import _cosmetic_shop_preview, cosmetic_checkout, cosmetic_shop


def fixture_offers():
    definitions = [
        ('moldura', 'ember-ring', 'Anel de brasas', 'frame-ember-ring'),
        ('moldura', 'elo-diamante-fechada', 'Elmo de Diamante', ''),
        ('efeito', 'aurora', 'Aurora', 'effect-aurora'),
        ('tema', 'arcane', 'Tema arcano', 'theme-arcane'),
        ('titulo', 'cronista', 'Cronista de Cineria', ''),
        ('badge', 'estrela', 'Insignia estelar', ''),
    ]
    offers = []
    for index, (kind, key, name, css) in enumerate(definitions):
        cosmetic = TbCosmetico(slug=kind + '-' + key, tipo=kind, nome=name,
                              css_class=css, escopo='ambos', descricao='Uma identidade de Cineria.',
                              asset_url='*' if kind == 'badge' else '')
        offer = SimpleNamespace(pk=index + 1, cosmetico=cosmetic, amount=Decimal('12.34'),
                                owned=index == 4, demonstration=False, borrowed=False)
        offer.shop_preview = _cosmetic_shop_preview(cosmetic)
        offers.append(offer)
    return offers


def browser_fixture(mode='shop'):
    request = RequestFactory().get('/cosmeticos/' if mode == 'shop' else '/cosmeticos/eventos/')
    request.user = SimpleNamespace(username='QA', is_authenticated=True, is_staff=False,
                                   is_superuser=False, pk=1)
    with override_settings(STATIC_URL='https://store.invalid/static/'):
        offers = fixture_offers()
        context = {'user': request.user, 'request': request, 'csrf_token': 'x' * 32,
                   'offers': offers, 'cards': [], 'characters': [], 'redemption_history': [],
                   'site_origin': 'https://store.invalid', 'commerce_preview': True}
        template = 'home/pages/cosmetic_checkout.html'
        if mode == 'events':
            character = SimpleNamespace(pk=7, nome='Aventureira', braseiros=30)
            context['characters'] = [character]
            for index, offer in enumerate(offers[:3]):
                offer.cost_braseiros = 10 if index == 1 else 0
                offer.event_key = 'QA-local'
                context['cards'].append({'offer': offer, 'owned': index == 2,
                    'ownership_sources': ['Resgate de evento'] if index == 2 else [],
                    'request_id': uuid4(), 'eligible_characters': [character],
                    'shop_preview': offer.shop_preview})
            template = 'home/pages/event_cosmetic_shop.html'
        elif mode == 'empty':
            context['offers'] = []
        elif mode == 'status':
            context['purchase'] = SimpleNamespace(name=offers[0].cosmetico.nome,
                                                  cosmetico=offers[0].cosmetico, granted_at=None)
            context['order'] = SimpleNamespace(id=uuid4(), status='pending', amount=Decimal('12.34'),
                get_status_display='Aguardando pagamento', asaas_checkout_url='')
        return render_to_string(template, context)


class CosmeticShopUITests(SimpleTestCase):
    def request(self, method='get', authenticated=True):
        request = getattr(RequestFactory(), method)('/cosmeticos/')
        request.user = (SimpleNamespace(is_authenticated=True, pk=1) if authenticated
                        else AnonymousUser())
        return request

    def test_canonical_route_is_get_only_and_preserves_login(self):
        self.assertEqual(reverse('cosmetic_shop'), '/cosmeticos/')
        self.assertIs(resolve('/cosmeticos/').func, cosmetic_shop)
        self.assertEqual(cosmetic_shop(self.request(authenticated=False)).status_code, 302)
        self.assertEqual(cosmetic_shop(self.request('post')).status_code, 405)
        with patch('home.views.cosmetic_checkout', return_value='shop') as existing:
            self.assertEqual(cosmetic_shop(self.request()), 'shop')
            existing.assert_called_once()

    def test_get_adds_only_presentation_and_verified_ownership(self):
        offers = fixture_offers()
        manager = Mock()
        manager.select_related.return_value.filter.return_value.exclude.return_value.exclude.return_value = offers
        with patch('home.models.CosmeticCheckoutOffer.objects', manager), patch(
            'home.cosmetic_entitlements.permanent_cosmetic_slugs', return_value={offers[0].cosmetico.slug}
        ), patch('home.views.render', side_effect=lambda req, template, context: context):
            context = cosmetic_checkout(self.request())
        self.assertTrue(context['offers'][0].owned)
        self.assertFalse(context['offers'][1].owned)
        self.assertTrue(context['offers'][0].shop_preview['package']['avatar'])
        self.assertTrue(all(offer.amount == Decimal('12.34') for offer in context['offers']))
        manager.select_related.return_value.filter.assert_called_once_with(
            active=True, demonstration=False, cosmetico__ativo=True, amount__gt=0)

    def test_catalog_forms_keep_checkout_csrf_and_slug(self):
        html = browser_fixture()
        self.assertIn('action="/cosmeticos/checkout/"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn('name="slug" value="moldura-ember-ring"', html)
        self.assertIn('cosmetic-shop.css', html)
        self.assertIn('data-cosmetic-helmet', html)
        self.assertNotIn('name="slug" value="titulo-cronista"', html)
        self.assertRegex(html, r'R\$ 12[,.]34')

    def test_event_forms_keep_quoted_cost_request_id_and_character(self):
        html = browser_fixture('events')
        for name in ('offer', 'quoted_cost', 'request_id', 'character', 'csrfmiddlewaretoken'):
            self.assertIn('name="' + name + '"', html)
        self.assertIn('value="10"', html)
        self.assertIn('Você já possui', html)

    def test_empty_and_status_templates_render(self):
        self.assertIn('Nenhuma oferta paga', browser_fixture('empty'))
        status = browser_fixture('status')
        self.assertIn('Checkout em conciliação', status)
        self.assertNotIn('name="slug"', status)

    def test_preview_rejects_untrusted_image_and_theme_colors(self):
        cosmetic = TbCosmetico(tipo='tema', slug='tema-x', escopo='perfil',
                              asset_url='javascript:alert(1)',
                              definicao_json={'accent': 'red;background:url(https://bad.invalid)'})
        preview = _cosmetic_shop_preview(cosmetic)
        self.assertFalse(preview['image'])
        self.assertNotIn('bad.invalid', preview['theme_style'])
