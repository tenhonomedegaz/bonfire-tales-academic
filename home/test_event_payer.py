"""Character payer UI preserves event POST and has no selection-side transaction."""
from contextlib import ExitStack
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings

from home.models import TbPersonagem
from home.test_cosmetic_shop_ui import fixture_offers
from home.views import event_cosmetic_shop


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inputs = []
        self.images = []
        self.event_inputs = []
        self.in_event_form = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            self.in_event_form = 'data-purchase-review' in dict(attrs)
        if tag == 'input':
            self.inputs.append(dict(attrs))
            if self.in_event_form:
                self.event_inputs.append(dict(attrs))
        if tag == 'img':
            self.images.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.in_event_form = False


def characters_fixture():
    return [SimpleNamespace(pk=7, nome='Lara do Vale Distante', braseiros=30,
                            payer_avatar_url='/static/brand/icon.png'),
            SimpleNamespace(pk=8, nome='Darian das Montanhas do Norte', braseiros=50,
                            payer_avatar_url='')]


def browser_fixture(mode='events'):
    user = SimpleNamespace(pk=1, username='QA', is_authenticated=True,
                           is_staff=False, is_superuser=False)
    with override_settings(STATIC_URL='https://payer.invalid/static/'):
        if mode != 'events':
            template = Template("""{% load static %}<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<body class="bft-commerce"><form id="legacy" action="/legacy/" method="post" data-purchase-review data-product="Legacy" data-amount="10 braseiros" data-mode="Resgate de evento" data-note="Resgate legado."><input name="offer" value="91" type="hidden"><select name="character" required><option value="7">Lara · 30 braseiros</option><option value="8">Darian · 50 braseiros</option></select><button type="submit">Resgatar legado</button></form>
<form id="cash" action="/cash/" method="post" data-purchase-review data-product="Oferta" data-amount="R$ 12,34" data-mode="Pagamento único"><input name="slug" value="moldura-exemplo" type="hidden"><button type="submit">Comprar</button></form>
<form id="readonly" action="/readonly/" method="post" data-purchase-review data-co-readonly data-product="Demonstração" data-amount="Exemplo" data-mode="Resgate de evento"><button type="submit">Ver demonstração</button></form>
{% include 'home/partials/commerce_review.html' %}<script src="{% static 'js/commerce.js' %}" defer></script></body></html>""")
            return template.render(Context({'user': user}))
        request = RequestFactory().get('/cosmeticos/eventos/')
        request.user = user
        characters = characters_fixture()
        cards = []
        for index, offer in enumerate(fixture_offers()[:4]):
            offer.pk = index + 1
            offer.cost_braseiros = 10 if index < 2 else 0 if index == 2 else 100
            offer.event_key = 'QA-local'
            cards.append({'offer': offer, 'owned': False, 'request_id': uuid4(),
                          'eligible_characters': characters if offer.cost_braseiros <= 30 else [],
                          'shop_preview': offer.shop_preview})
        return render_to_string('home/pages/event_cosmetic_shop.html', {
            'user': user, 'request': request, 'cards': cards, 'characters': characters,
            'redemption_history': [], 'has_unowned_paid_offer': True, 'csrf_token': 'x' * 32,
        })


class EventPayerTests(SimpleTestCase):
    def test_native_required_radios_keep_first_selection_labels_balance_and_ids(self):
        html = render_to_string('home/includes/event_payer.html',
                                {'characters': characters_fixture(), 'offer_id': 21})
        inputs = Inputs(html).inputs
        self.assertEqual([value['name'] for value in inputs], ['character', 'character'])
        self.assertEqual([value['value'] for value in inputs], ['7', '8'])
        self.assertTrue(all(value['type'] == 'radio' and 'required' in value for value in inputs))
        self.assertIn('checked', inputs[0])
        self.assertNotIn('checked', inputs[1])
        self.assertEqual(inputs[1]['data-payer-label'], 'Darian das Montanhas do Norte · 50 braseiros')
        self.assertEqual([value['id'] for value in inputs], ['payer-21-7', 'payer-21-8'])
        self.assertNotIn('<select', html)
        self.assertNotIn('<form', html)

    def test_labels_are_escaped_and_avatars_have_initial_fallback(self):
        character = SimpleNamespace(pk=7, nome='<script>alert(1)</script>', braseiros=30,
                                    payer_avatar_url='')
        html = render_to_string('home/includes/event_payer.html', {'characters': [character], 'offer_id': 1})
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertEqual(Inputs(html).images, [])
        self.assertIn('event-payer-avatar', html)

    def test_paid_and_free_offer_post_contracts_and_insufficient_balance(self):
        html = browser_fixture()
        inputs = Inputs(html).event_inputs
        self.assertEqual(len([value for value in inputs if value.get('name') == 'character']), 4)
        self.assertEqual(len({value['id'] for value in inputs if value.get('name') == 'character'}), 4)
        for name in ('offer', 'request_id', 'quoted_cost', 'csrfmiddlewaretoken'):
            self.assertEqual(len([value for value in inputs if value.get('name') == name]), 3)
        self.assertIn('Nenhum personagem tem 100 braseiros', html)
        self.assertIn('Resgatar gratuitamente', html)

    def test_get_loads_avatar_in_same_character_query_and_sanitizes_once(self):
        characters = [TbPersonagem(id_personagem=7, nome='Lara', braseiros=30,
                                  foto_url='/static/brand/icon.png'),
                      TbPersonagem(id_personagem=8, nome='Darian', braseiros=50,
                                  foto_url='javascript:alert(1)')]
        request = RequestFactory().get('/cosmeticos/eventos/')
        request.user = SimpleNamespace(pk=1, is_authenticated=True)
        with ExitStack() as stack:
            managers = {name: stack.enter_context(patch('home.models.' + name + '.objects'))
                        for name in ('TbPersonagem', 'EventCosmeticOffer', 'TbUsuarioCosmetico',
                                     'CosmeticCheckoutPurchase', 'EventCosmeticRedemption')}
            managers['TbPersonagem'].filter.return_value.only.return_value = characters
            managers['EventCosmeticOffer'].select_related.return_value.filter.return_value = []
            managers['TbUsuarioCosmetico'].filter.return_value.exclude.return_value.only.return_value = []
            managers['CosmeticCheckoutPurchase'].filter.return_value.values_list.return_value = []
            managers['EventCosmeticRedemption'].filter.return_value.values_list.return_value = []
            stack.enter_context(patch('django.core.paginator.Paginator')).return_value.get_page.return_value = []
            stack.enter_context(patch('home.views.render', side_effect=lambda req, template, context, **kwargs: context))
            context = event_cosmetic_shop(request)
            managers['TbPersonagem'].filter.assert_called_once_with(dono=request.user, arquivado=False)
            managers['TbPersonagem'].filter.return_value.only.assert_called_once_with(
                'pk', 'nome', 'braseiros', 'foto_url')
            self.assertEqual(context['characters'][0].payer_avatar_url, '/static/brand/icon.png')
            self.assertEqual(context['characters'][1].payer_avatar_url, '')
