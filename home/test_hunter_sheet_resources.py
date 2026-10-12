from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import TbItemMundano, TbRecursoclasse


class HunterSheetResourceTests(TestCase):
    def setUp(self):
        from .test_hunter_slots import HunterPinnedSlotTests
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterPinnedSlotTests.setUp(self)
        self.pool = TbRecursoclasse.objects.create(id_classe=self.cl,
            nome='Reserva de teste', slug='test-pool', tipo='consumable',
            nivel=1, valor='3', reset='long_rest')
        self.item = TbItemMundano.objects.create(nome='Cajado de teste',
            slug='test-staff', categoria='equipamento', tags_json=['charges:4(reset:long_rest)'])
        self.possession = self.person.inventario.create(nome=self.item.nome, id_item_mundano=self.item)
        self.bind(self.data)
        self.use_resource = reverse('personagem_usar_recurso', args=[self.person.pk])
        self.rest = reverse('personagem_descansar', args=[self.person.pk])

    def read_sheet(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.sheet_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(
            ('INSERT ', 'UPDATE ', 'DELETE '))], [])
        return response

    def test_read_spend_return_and_rest_with_frozen_class_and_charges(self):
        self.pool.valor = '99'
        self.pool.save()
        self.item.tags_json = ['charges:99(reset:short_rest)']
        self.item.save()
        response = self.read_sheet()
        self.assertContains(response, 'Gastar uso de Reserva de teste')
        self.assertContains(response, 'Gastar espaço de nível 1')
        self.assertEqual(self.person.recursos.count(), 0)
        cards = response.context['resource_cards']
        self.assertEqual(sorted(card['maximo'] for card in cards), [3, 4])
        for card in cards:
            response = self.client.post(self.use_resource,
                {'recurso': card['id'], 'acao': 'gastar', 'next': self.sheet_url}, follow=True)
            self.assertRedirects(response, self.sheet_url)
            updated = next(c for c in response.context['resource_cards'] if c['id'] == card['id'])
            self.assertEqual(updated['atual'], card['maximo'] - 1)
        self.read_sheet()
        self.client.post(self.rest, {'tipo': 'longo', 'next': self.sheet_url})
        self.assertTrue(all(c['atual'] == c['maximo']
            for c in self.read_sheet().context['resource_cards']))

    def test_projection_preserves_spent_without_rewriting_legacy_rows(self):
        legacy = self.person.recursos.create(nome='Reserva de teste', chave='', maximo=5, atual=3)
        response = self.read_sheet()
        pool = next(c for c in response.context['resource_cards'] if c['grupo'] == 'habilidade')
        self.assertEqual((pool['atual'], pool['maximo']), (1, 3))
        legacy.refresh_from_db()
        self.assertEqual((legacy.chave, legacy.atual, legacy.maximo), ('', 3, 5))
        self.client.post(self.use_resource, {'recurso': pool['id'], 'acao': 'gastar'})
        legacy.refresh_from_db()
        self.assertEqual((legacy.atual, legacy.maximo), (0, 3))
        self.assertNotEqual(legacy.chave, '')
        self.assertEqual(self.person.recursos.filter(nome='Reserva de teste').count(), 1)

    def test_public_and_archived_sheets_have_no_resource_controls(self):
        self.person.publico = True
        self.person.save()
        self.client.force_login(self.other)
        response = self.client.get(self.sheet_url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.post(self.use_resource, {'recurso': 'test-pool'}).status_code, 404)
        self.client.force_login(self.person.dono)
        self.person.arquivado = True
        self.person.save()
        self.assertNotContains(self.read_sheet(), self.use_resource)
