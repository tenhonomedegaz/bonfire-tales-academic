import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from .bestiary_catalog import is_statblock_placeholder
from .models import TbBestiario
from .views import _render_creature_statblock_full


class DemonSelectorPreviewTests(TestCase):
    def test_demon_selectors_link_to_existing_statblocks_in_both_previews(self):
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        bestiary = {r['pk']: r['fields'] for r in records
                    if r['model'] == 'home.tbbestiario'}
        spells = {r['pk']: r['fields'] for r in records
                  if r['model'] == 'home.tbmagia'}
        for selector_pk, spell_pk, example_pks in (
            (45, 496, (564, 315, 574, 683)),
            (54, 495, (730, 157)),
        ):
            selector = bestiary[selector_pk]
            refs = selector['statblock_json']['variant_refs']
            self.assertEqual([ref['slug'] for ref in refs],
                             [bestiary[pk]['slug'] for pk in example_pks])
            self.assertIn(selector['slug'], spells[spell_pk]['descricao'])
            self.assertFalse(is_statblock_placeholder(selector['statblock_json']))
            self.assertIsNone(selector['nd'])
            for pk in example_pks:
                self.assertFalse(is_statblock_placeholder(
                    bestiary[pk]['statblock_json']))
                self.assertIn('Dem', bestiary[pk]['tipo'])
            TbBestiario.objects.create(**{
                key: selector[key] for key in ('nome', 'slug', 'tipo', 'tamanho',
                                               'ca', 'pv', 'nd', 'statblock_json')
            })
            creature = self.client.get('/api/creature/', {'slug': selector['slug']})
            card = self.client.get('/api/card-preview/', {
                'table': 'bestiario', 'args': selector['slug'],
            })
            self.assertEqual((creature.status_code, card.status_code), (200, 200))
            self.assertFalse(creature.json()['statblock_incompleto'])
            for html in (creature.json()['statblock_html'], card.json()['card_html']):
                self.assertIn('Ficha variavel', html)
                self.assertNotIn('Statblock incompleto', html)
                for ref in refs:
                    self.assertIn('data-args="%s"' % ref['slug'], html)
                    self.assertIn('(ND %s)' % ref['cr'], html)

        infernal = spells[286]
        self.assertNotIn('dem\u00f4nio', infernal['descricao'].lower())
        self.assertIn('diabo', infernal['descricao'].lower())
        self.assertNotIn('summon:bestiary{demonio}', infernal['tags_json'])
        for pk in (154, 160):
            self.assertIn(bestiary[pk]['slug'], infernal['descricao'])
            self.assertIn('Diabo', bestiary[pk]['tipo'])

    def test_invalid_selector_is_incomplete_and_html_is_escaped(self):
        self.assertTrue(is_statblock_placeholder({
            'name': 'selector', 'variant_refs': [{'slug': 'valid', 'name': 'Valid'}]
        }))
        self.assertTrue(is_statblock_placeholder({
            'selection_note': 'note', 'variant_refs': [{'slug': '<script>', 'name': 'Bad'}]
        }))
        sb = {'selection_note': '<script>alert(1)</script>',
              'variant_refs': [{'slug': 'valid', 'name': '<b>Bad</b>', 'cr': '<1>'}]}
        creature = TbBestiario(nome='Selector', tipo='demonio', tamanho='',
                               statblock_json=sb)
        html = _render_creature_statblock_full(creature)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<b>Bad</b>', html)
        self.assertNotIn('<1>', html)
