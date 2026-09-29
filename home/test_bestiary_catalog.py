from django.test import TestCase
from django.urls import reverse

from .bestiary_catalog import cr_classification, size_keys, type_key, type_keys
from .models import TbBestiario


class BestiaryCatalogClassificationTests(TestCase):
    def test_explicit_aliases_and_special_values(self):
        self.assertEqual(type_key('Besta (Dinossauro)'), 'besta')
        self.assertEqual(type_key('swarm of Tiny Beasts'), 'besta')
        self.assertIsNone(type_key('Celestial, Fey, or Fiend'))
        self.assertEqual(type_keys('Celestial, Fey, or Fiend'),
                         ('celestial', 'feerico', 'corruptor'))
        self.assertEqual(type_keys('celestial ou corruptor (Tit\ufffd)'),
                         ('celestial', 'corruptor'))
        self.assertEqual(type_keys('enxame de mortos-vivos mi\ufffddos'), ('morto-vivo',))
        self.assertEqual(size_keys('Small or Medium'), ('S', 'M'))
        self.assertEqual(size_keys('Huge or Gargantuan'), ('H', 'G'))
        self.assertEqual(cr_classification('1/4 (XP 50; PB +2)')[:2], ('nd:1/4', 0.25))
        self.assertEqual(cr_classification('2 (XP 450; PB +2)')[:2], ('nd:2', 2.0))
        self.assertEqual(cr_classification('None (XP 0; PB equals your bonus)')[1], float('inf'))

    def test_combined_filters_and_nd_order_share_the_same_projection(self):
        for slug, nome, kind, size, nd in (
            ('beast-multi', 'Besta múltipla', 'Besta (Dinossauro)', 'Small or Medium', '1/4 (XP 50; PB +2)'),
            ('beast-small', 'Besta pequena', 'Besta', 'Pequeno', '1/4 (XP 60; PB +2)'),
            ('fiend-large', 'Corruptor grande', 'Corruptor (Demônio)', 'L', '2 (XP 450; PB +2)'),
            ('variable', 'Tipo variável', 'Celestial, Fey, or Fiend', None,
             'None (XP 0; PB equals your bonus)'),
        ):
            TbBestiario.objects.create(slug=slug, nome=nome, tipo=kind,
                                       tamanho=size, nd=nd, statblock_json={})
        url = reverse('bestiario')
        response = self.client.get(url, {'tipo': 'besta', 'tam': 'S', 'nd': 'nd:1/4'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual({c['slug'] for c in response.context['criaturas']},
                         {'beast-multi', 'beast-small'})
        self.assertEqual(next(c['tamanho'] for c in response.context['criaturas']
                              if c['slug'] == 'beast-multi'), 'Pequeno / Médio')
        self.assertIn('id="bz-count">2</span>', response.content.decode())
        old_link = self.client.get(url, {'tipo': 'Besta', 'tam': 'Pequeno',
                                         'nd': '1/4 (XP 50; PB +2)'})
        self.assertEqual({c['slug'] for c in old_link.context['criaturas']},
                         {'beast-multi', 'beast-small'})
        medium = self.client.get(url, {'tam': 'M'})
        self.assertEqual([c['slug'] for c in medium.context['criaturas']], ['beast-multi'])
        pending = self.client.get(url, {'tipo': 'pending', 'tam': 'pending'})
        self.assertEqual([c['slug'] for c in pending.context['criaturas']], [])
        for kind in ('celestial', 'feerico', 'corruptor'):
            filtered = self.client.get(url, {'tipo': kind})
            self.assertIn('variable', [c['slug'] for c in filtered.context['criaturas']])
        descending = self.client.get(url, {'ord': 'nd_desc'})
        self.assertEqual([c['slug'] for c in descending.context['criaturas']],
                         ['fiend-large', 'beast-multi', 'beast-small', 'variable'])
