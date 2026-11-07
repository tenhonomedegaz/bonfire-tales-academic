from html.parser import HTMLParser
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class Controls(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inputs = []
        self.selects = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            self.inputs.append(dict(attrs))
        elif tag == 'select':
            self.selects.append(dict(attrs))


class MarketCharacterPickerTests(SimpleTestCase):
    def test_native_fallback_and_cards_preserve_single_submission(self):
        active = SimpleNamespace(id_personagem=7, nome='<Guarda>', market_picker_wallet='12 PO')
        other = SimpleNamespace(id_personagem=8, nome='Outra ficha', market_picker_wallet='9 PO')
        html = render_to_string('home/partials/_mercado_balcao.html', {
            'mercado_logado': True, 'mercado_personagens': [active, other],
            'mercado_ativo': active, 'mercado_carteira': '12 PO',
        })
        controls = Controls(html)
        self.assertEqual(controls.selects[0]['name'], 'personagem')
        self.assertNotIn('disabled', controls.selects[0])
        radios = controls.inputs
        self.assertEqual([radio['value'] for radio in radios], ['7', '8'])
        self.assertTrue(all('disabled' in radio for radio in radios))
        self.assertIn('checked', radios[0])
        self.assertNotIn('checked', radios[1])
        self.assertIn('&lt;Guarda&gt;', html)
        self.assertIn('12 PO', html)
        self.assertIn('9 PO', html)
        self.assertNotIn('method="post"', html)

    def test_anonymous_and_empty_states_do_not_offer_a_payer(self):
        for context in ({}, {'mercado_logado': True, 'mercado_personagens': []}):
            html = render_to_string('home/partials/_mercado_balcao.html', context)
            self.assertEqual(Controls(html).inputs, [])
            self.assertNotIn('data-market-characters', html)
