"""A real sheet action resolves both relentless weapon damage effects."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_talent_catalog import ATTRIBUTE_TAGS, VERIFIED_EFFECTS
from home.models import (TbItemMundano, TbOperacaoRecurso, TbPersonagem,
                         TbPersonagemItem, TbPersonagemTalento, TbTalento)


class RelentlessDamageViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='relentless-owner')
        self.other = get_user_model().objects.create_user(username='relentless-other')
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome='Guerreiro', forca=16)
        weapon = TbItemMundano.objects.create(
            nome='Espada de teste', slug='espada-relentless', categoria='arma',
            subcategoria='arma_marcial', tags_json=['dmg:1d8(cortante)'])
        TbPersonagemItem.objects.create(
            id_personagem=self.person, id_item_mundano=weapon,
            nome=weapon.nome, equipado=True, tags_json=weapon.tags_json)
        talent = TbTalento.objects.create(
            nome='Fonte sintética', slug='relentless-source', tipo='geral',
            tags_json=ATTRIBUTE_TAGS + VERIFIED_EFFECTS['dadiva-do-ataque-implacavel'])
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=talent,
            nome=talent.nome, detalhes='talent_attr:FOR')
        self.url = reverse('personagem_resolver_dano_arma', args=[self.person.pk])
        self.sheet = reverse('ficha_detail', args=[self.person.pk])
        self.client.force_login(self.owner)

    def _payload(self, **changes):
        from home.epic_relentless_damage import relentless_profiles
        index = relentless_profiles(self.person)[0]['index']
        return dict({'operation_id': str(uuid.uuid4()), 'profile_index': str(index),
                     'rolled_damage': '10', 'critical': 'on',
                     'target_defense': 'resist', 'confirmed': 'on'}, **changes)

    def test_critical_resistance_replay_and_coexistence(self):
        self.assertContains(self.client.get(self.sheet), 'Resolver dano')
        payload = self._payload()
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        receipt = TbOperacaoRecurso.objects.get(operation_id=payload['operation_id'])
        self.assertEqual(receipt.resposta['critical_bonus'], 18)
        self.assertEqual(receipt.resposta['final_damage'], 28)
        self.assertTrue(receipt.resposta['ignored_resistance'])
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.filter(
            operation_id=payload['operation_id']).count(), 1)
        self.assertEqual(self.client.post(self.url, dict(
            payload, rolled_damage='11')).status_code, 400)
        immune = self._payload(target_defense='immune')
        self.assertEqual(self.client.post(self.url, immune).status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.get(
            operation_id=immune['operation_id']).resposta['final_damage'], 0)

    def test_choice_and_source_removal_disable_action(self):
        payload = self._payload()
        self.grant.detalhes = ''
        self.grant.save(update_fields=['detalhes'])
        self.assertNotContains(self.client.get(self.sheet), 'Resolver dano')
        self.assertEqual(self.client.post(self.url, payload).status_code, 400)
        self.grant.detalhes = 'talent_attr:FOR'
        self.grant.save(update_fields=['detalhes'])
        self.grant.delete()
        self.assertEqual(self.client.post(self.url, payload).status_code, 400)

    def test_high_existing_attribute_and_noncritical_damage(self):
        self.person.destreza = 31
        self.person.save(update_fields=['destreza'])
        self.grant.detalhes = 'talent_attr:DES'
        self.grant.save(update_fields=['detalhes'])
        critical = self._payload(target_defense='none')
        self.assertEqual(self.client.post(self.url, critical).status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.get(
            operation_id=critical['operation_id']).resposta['final_damage'], 41)
        normal = self._payload(critical='', target_defense='resist')
        self.assertEqual(self.client.post(self.url, normal).status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.get(
            operation_id=normal['operation_id']).resposta['final_damage'], 10)

    def test_other_account_and_unconfirmed_hit_cannot_resolve(self):
        payload = self._payload()
        self.assertEqual(self.client.post(self.url, dict(
            payload, confirmed='')).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, payload).status_code, 404)
