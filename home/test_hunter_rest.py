from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from .models import TbRecursoclasse, TbItemMundano


class HunterPinnedRestTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind=HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.resource=TbRecursoclasse.objects.create(id_classe=self.cl,nome='Frozen pool',
            slug='frozen-pool',tipo='consumable',nivel=1,valor='3',reset='long_rest')
        self.item=TbItemMundano.objects.create(nome='Frozen charges',slug='frozen-charges',
            categoria='equipamento',tags_json=['charges:4(reset:long_rest)'])
        self.person.inventario.create(nome=self.item.nome,id_item_mundano=self.item)
        self.bind(self.data)
        self.url=reverse('personagem_descansar',args=[self.person.pk])

    def test_rest_uses_frozen_class_and_item_contracts(self):
        self.resource.valor='99';self.resource.reset='short_rest';self.resource.save()
        self.item.tags_json=['charges:99(reset:short_rest)'];self.item.save()
        self.assertEqual(self.client.post(self.url,{'tipo':'longo'}).status_code,302)
        pool=self.person.recursos.get(nome='Frozen pool')
        charge=self.person.recursos.get(chave__startswith='item:')
        self.assertEqual((pool.maximo,pool.atual),(3,3))
        self.assertEqual((charge.maximo,charge.atual),(4,4))
        self.person.recursos.update(atual=0)
        self.assertEqual(self.client.post(self.url,{'tipo':'curto'}).status_code,302)
        pool.refresh_from_db();charge.refresh_from_db()
        self.assertEqual((pool.atual,charge.atual),(0,0))
        self.assertEqual(self.client.post(self.url,{'tipo':'longo'}).status_code,302)
        pool.refresh_from_db();charge.refresh_from_db()
        self.assertEqual((pool.atual,charge.atual),(3,4))

    def test_late_failure_rolls_back_all_materialization_and_resets(self):
        self.assertEqual(self.person.recursos.count(),0)
        with patch('home.resource_engine.end_states_on',side_effect=ValueError('invalid')):
            response=self.client.post(self.url,{'tipo':'longo'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.person.recursos.count(),0)
        self.assertFalse(self.person.escolhas.filter(tipo='hunter-mastery-rest').exists())

    def test_unlinked_character_keeps_live_contract_and_other_user_cannot_rest(self):
        self.profile.delete()
        self.resource.valor='7';self.resource.save()
        self.assertEqual(self.client.post(self.url,{'tipo':'longo'}).status_code,302)
        self.assertEqual(self.person.recursos.get(nome='Frozen pool').maximo,7)
        self.person.recursos.update(atual=0)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url,{'tipo':'longo'}).status_code,404)
        self.assertFalse(self.person.recursos.filter(atual__gt=0).exists())

    def test_ajax_rest_and_resource_use_keep_frozen_limits(self):
        self.resource.valor = '99'
        self.resource.save()
        self.item.tags_json = ['charges:99(reset:short_rest, destroy_on_zero)']
        self.item.save()
        ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        response = self.client.post(self.url, {'tipo': 'longo'}, **ajax)
        self.assertEqual(response.status_code, 200)
        pool = self.person.recursos.get(nome='Frozen pool')
        charge = self.person.recursos.get(chave__startswith='item:')
        snapshot = {row['key']: row for row in response.json()['recursos']}
        self.assertEqual(snapshot[pool.chave]['maximo'], 3)
        self.assertEqual(snapshot[charge.chave]['maximo'], 4)
        use = reverse('personagem_usar_recurso', args=[self.person.pk])
        response = self.client.post(use, {'recurso': pool.chave}, **ajax)
        self.assertEqual(response.status_code, 200)
        pool.refresh_from_db()
        self.assertEqual((pool.atual, pool.maximo), (2, 3))
        for _ in range(4):
            self.assertEqual(self.client.post(use, {'recurso': charge.chave}, **ajax).status_code, 200)
        charge.refresh_from_db()
        self.assertEqual((charge.atual, charge.maximo), (0, 4))
        self.assertTrue(self.person.inventario.exists())
        self.client.post(self.url, {'tipo': 'curto'}, **ajax)
        charge.refresh_from_db()
        self.assertEqual(charge.atual, 0)
        self.client.post(self.url, {'tipo': 'longo'}, **ajax)
        charge.refresh_from_db()
        self.assertEqual(charge.atual, 4)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(use, {'recurso': charge.chave}, **ajax).status_code, 404)
        charge.refresh_from_db()
        self.assertEqual(charge.atual, 4)

    def test_ajax_failure_rolls_back_resource_use(self):
        self.client.post(self.url, {'tipo': 'longo'})
        pool = self.person.recursos.get(nome='Frozen pool')
        use = reverse('personagem_usar_recurso', args=[self.person.pk])
        with patch('home.views._recursos_ajax_payload', side_effect=ValueError('invalid')):
            response = self.client.post(use, {'recurso': pool.chave},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 409)
        pool.refresh_from_db()
        self.assertEqual(pool.atual, 3)

    def test_frozen_destroy_on_zero_is_not_removed_by_live_catalog(self):
        self.item.tags_json = ['charges:1(destroy_on_zero)']
        self.item.save()
        self.bind(self.data)
        self.item.tags_json = ['charges:99']
        self.item.save()
        self.client.post(self.url, {'tipo': 'longo'})
        charge = self.person.recursos.get(chave__startswith='item:')
        response = self.client.post(reverse('personagem_usar_recurso', args=[self.person.pk]),
            {'recurso': charge.chave}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.person.inventario.exists())
