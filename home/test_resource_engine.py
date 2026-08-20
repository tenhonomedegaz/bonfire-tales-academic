from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from home.models import (
    TbPersonagem, TbPersonagemEstado, TbPersonagemItem, TbPersonagemRecurso,
)
from home.resource_engine import (
    activate_state, end_states_on, ensure_resource, mutate_resource,
    reset_resources, sync_item_charges,
)


class ResourceEngineTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='resource-engine', password='test')
        self.character = TbPersonagem.objects.create(
            dono=user, nome='Ledger de teste')

    def test_charges_are_persistent_aggregate_and_recover_at_dawn(self):
        item = TbPersonagemItem.objects.create(
            id_personagem=self.character, nome='Kit carregado', qtd=2,
            tags_json=['charges:3(reset:dawn, amount:1d4)'])
        contract = sync_item_charges(self.character)[0]
        self.assertEqual(contract['maximum'], 6)

        snapshot = mutate_resource(self.character, contract, -2)
        self.assertEqual(snapshot['current'], 4)
        self.assertTrue(TbPersonagemItem.objects.filter(pk=item.pk).exists())

        with patch('home.resource_engine.secrets.randbelow', return_value=0):
            changed = reset_resources(self.character, 'dawn')
        self.assertEqual(changed[0]['current'], 5)

    def test_syncing_one_item_does_not_delete_other_item_counters(self):
        first = TbPersonagemItem.objects.create(
            id_personagem=self.character, nome='Primeiro',
            tags_json=['charges:2(reset:dawn)'])
        second = TbPersonagemItem.objects.create(
            id_personagem=self.character, nome='Segundo',
            tags_json=['charges:4(reset:long_rest)'])
        sync_item_charges(self.character)

        sync_item_charges(self.character, [first])

        self.assertEqual(
            TbPersonagemRecurso.objects.filter(
                id_personagem=self.character, id_item=second).count(), 1)

    def test_destroy_on_zero_is_declarative(self):
        item = TbPersonagemItem.objects.create(
            id_personagem=self.character, nome='Uso único',
            tags_json=['charges:1(destroy_on_zero)'])
        contract = sync_item_charges(self.character)[0]
        snapshot = mutate_resource(self.character, contract, -1)
        self.assertTrue(snapshot['destroyed'])
        self.assertFalse(TbPersonagemItem.objects.filter(pk=item.pk).exists())

    def test_legacy_resource_is_promoted_without_refilling_spent_uses(self):
        legacy = TbPersonagemRecurso.objects.create(
            id_personagem=self.character, nome='Fúrias', atual=1, maximo=2)
        resource = ensure_resource(self.character, {
            'key': 'class:1:0:furias', 'legacy_name': 'Fúrias',
            'name': 'Fúrias', 'maximum': 3, 'reset': 'long_rest',
            'origin': 'classe:barbaro',
        })
        self.assertEqual(resource.pk, legacy.pk)
        self.assertEqual(resource.atual, 2)
        self.assertEqual(resource.chave, 'class:1:0:furias')

    def test_persistent_state_has_declarative_lifecycle(self):
        state = activate_state(
            self.character, 'spell:42', origin='magia:encontrar_familiar',
            payload={'spell_name': 'Encontrar Familiar'},
            ends_on=['dismissed', 'long_rest'])
        self.assertTrue(state.ativo)
        self.assertEqual(end_states_on(self.character, 'short_rest'), [])
        self.assertEqual(end_states_on(self.character, 'long_rest'), ['spell:42'])
        self.assertFalse(TbPersonagemEstado.objects.get(pk=state.pk).ativo)
