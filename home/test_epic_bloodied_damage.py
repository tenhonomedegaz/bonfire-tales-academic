"""Focused sheet flow for the bloodied once-per-turn damage tag."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_bloodied_damage import bloodied_attack_state
from home.epic_battle_accuracy import FORTUNE_TAG, attack_accuracy_state
from home.epic_talent_catalog import ATTRIBUTE_TAGS, VERIFIED_EFFECTS, epic_candidates
from home.models import (TbItemMundano, TbOperacaoRecurso, TbPersonagem,
                         TbPersonagemItem, TbPersonagemTalento, TbTalento)
from home.tag_engine.library import Library
from home.tag_engine.validator import validate_tags_json


BONUS_TAG = VERIFIED_EFFECTS['dadiva-da-carnificina'][1]
CRITICAL_TAG = VERIFIED_EFFECTS['dadiva-da-carnificina'][2]


class BloodiedDamageSheetTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='bloodied-owner')
        self.other = get_user_model().objects.create_user(username='bloodied-other')
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome='Combatente', nivel=10,
            pv_maximo=100, pv_atual=40)
        weapon = TbItemMundano.objects.create(
            nome='Espada de teste', slug='espada-bloodied', categoria='arma',
            subcategoria='arma_marcial', tags_json=['dmg:1d8(cortante)'])
        TbPersonagemItem.objects.create(
            id_personagem=self.person, id_item_mundano=weapon,
            nome=weapon.nome, equipado=True, tags_json=weapon.tags_json)
        self.talent = TbTalento.objects.create(
            nome='Fonte sintética', slug='fonte-bloodied-teste', tipo='geral',
            tags_json=ATTRIBUTE_TAGS + [BONUS_TAG])
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes='talent_attr:FOR')
        self.url = reverse('personagem_usar_dano_sangrando', args=[self.person.pk])
        self.turn_url = reverse('personagem_iniciar_turno_dano_sangrando',
                                args=[self.person.pk])
        self.sheet = reverse('ficha_detail', args=[self.person.pk])
        self.profile_index = bloodied_attack_state(self.person)['profiles'][0]['index']
        self.client.force_login(self.owner)

    def payload(self, **changes):
        return dict({'operation_id': str(uuid.uuid4()),
                     'profile_index': str(self.profile_index), 'hit_confirmed': 'on'},
                    **changes)

    def test_tag_sheet_hit_receipt_and_next_turn(self):
        self.assertEqual(validate_tags_json([BONUS_TAG], Library()), [])
        self.assertContains(self.client.get(self.sheet), 'Aplicar +10 de dano')
        payload = self.payload()
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        receipt = TbOperacaoRecurso.objects.get(operation_id=payload['operation_id'])
        self.assertEqual(receipt.resposta['bonus_damage'], 10)
        self.assertEqual(receipt.resposta['damage_type'], 'cortante')
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.filter(
            operation_id=payload['operation_id']).count(), 1)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 400)
        self.assertContains(self.client.get(self.sheet), 'O bônus já foi usado')
        turn = {'operation_id': str(uuid.uuid4()), 'turn_ref': 'turno-2',
                'confirmed': 'on'}
        self.assertEqual(self.client.post(self.turn_url, turn).status_code, 302)
        self.assertEqual(self.client.post(self.turn_url, turn).status_code, 302)
        self.assertEqual(self.client.post(self.turn_url, {
            'operation_id': str(uuid.uuid4()), 'turn_ref': 'turno-2',
            'confirmed': 'on'}).status_code, 400)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 302)

    def test_bloodied_gate_choice_removal_and_other_owner(self):
        self.person.pv_atual = 70
        self.person.save(update_fields=['pv_atual'])
        self.assertIsNone(bloodied_attack_state(self.person))
        self.assertNotContains(self.client.get(self.sheet), 'Aplicar +10 de dano')
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 400)
        self.person.pv_atual = 40
        self.person.save(update_fields=['pv_atual'])
        payload = self.payload()
        self.assertEqual(self.client.post(self.url, dict(
            payload, hit_confirmed='')).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, payload).status_code, 404)
        self.client.force_login(self.owner)
        self.grant.detalhes = ''
        self.grant.save(update_fields=['detalhes'])
        self.assertIsNone(bloodied_attack_state(self.person))
        self.assertEqual(self.client.post(self.url, payload).status_code, 400)
        self.grant.detalhes = 'talent_attr:FOR'
        self.grant.save(update_fields=['detalhes'])
        self.grant.delete()
        self.assertEqual(self.client.post(self.url, payload).status_code, 400)

    def test_bonus_coexists_with_another_source(self):
        other_tag = ('while_active{requires:self{sangrando}, 1/turn, '
                     'instant{trigger=hit, dmg:+5}}')
        extra = TbTalento.objects.create(
            nome='Outra fonte', slug='outra-fonte-bloodied', tipo='geral',
            tags_json=[other_tag])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=extra, nome=extra.nome)
        state = bloodied_attack_state(self.person)
        self.assertEqual(state['bonus'], 15)
        payload = self.payload()
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.get(
            operation_id=payload['operation_id']).resposta['bonus_damage'], 15)

    def test_unrelated_damage_tag_does_not_join_bloodied_attack(self):
        unrelated = TbTalento.objects.create(
            nome='Dano de outra ocasião', slug='outra-ocasiao-bloodied', tipo='geral',
            tags_json=['while_active{1/turn, instant{trigger=hit, dmg:+5}}'])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=unrelated, nome=unrelated.nome)
        self.assertEqual(bloodied_attack_state(self.person)['bonus'], 10)

    def test_bloodied_critical_margin_roll_and_source_lifecycle(self):
        self.talent.tags_json = ATTRIBUTE_TAGS + [BONUS_TAG, CRITICAL_TAG]
        self.talent.save(update_fields=['tags_json'])
        self.assertEqual(validate_tags_json([CRITICAL_TAG], Library()), [])
        self.assertEqual(attack_accuracy_state(self.person)['critical_threshold'], 19)
        another = TbTalento.objects.create(
            nome='Outra margem global', slug='outra-margem-bloodied', tipo='geral',
            tags_json=['crit_range:+1'])
        other_grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=another, nome=another.nome)
        self.assertEqual(attack_accuracy_state(self.person)['critical_threshold'], 18)
        other_grant.delete()
        self.assertContains(self.client.get(self.sheet), 'Crítico em 19–20')
        roll_url = reverse('personagem_rolar_ataque_epico', args=[self.person.pk])
        operation = uuid.uuid4()
        with patch('home.epic_battle_accuracy.secrets.randbelow', return_value=18) as dice:
            self.assertEqual(self.client.post(roll_url, {
                'operation_id': str(operation)}).status_code, 302)
        dice.assert_called_once_with(20)
        receipt = TbOperacaoRecurso.objects.get(operation_id=operation).resposta
        self.assertEqual((receipt['applied_d20'], receipt['critical_threshold'],
                          receipt['critical_on_hit']), (19, 19, True))
        with patch('home.epic_battle_accuracy.secrets.randbelow',
                   side_effect=AssertionError('replay rolled again')):
            self.assertEqual(self.client.post(roll_url, {
                'operation_id': str(operation)}).status_code, 302)
        self.person.pv_atual = 70
        self.person.save(update_fields=['pv_atual'])
        self.assertIsNone(attack_accuracy_state(self.person))
        self.assertEqual(self.client.post(roll_url, {
            'operation_id': str(uuid.uuid4())}).status_code, 400)
        self.person.pv_atual = 40
        self.person.save(update_fields=['pv_atual'])
        self.grant.detalhes = ''
        self.grant.save(update_fields=['detalhes'])
        self.assertIsNone(attack_accuracy_state(self.person))
        self.grant.delete()
        self.assertIsNone(attack_accuracy_state(self.person))

    def test_visible_zero_grants_next_attack_and_consumes_once(self):
        self.talent.tags_json = ATTRIBUTE_TAGS + [BONUS_TAG, CRITICAL_TAG, FORTUNE_TAG]
        self.talent.save(update_fields=['tags_json'])
        self.assertEqual(validate_tags_json([FORTUNE_TAG], Library()), [])
        event_url = reverse('personagem_registrar_criatura_a_zero', args=[self.person.pk])
        roll_url = reverse('personagem_rolar_ataque_epico', args=[self.person.pk])
        event = {'operation_id': str(uuid.uuid4()), 'event_ref': 'queda-1',
                 'creature_ref': 'criatura-a', 'visible_confirmed': 'on',
                 'zero_confirmed': 'on'}
        self.assertEqual(self.client.post(event_url, event).status_code, 302)
        self.assertEqual(self.client.post(event_url, event).status_code, 302)
        self.assertEqual(self.client.post(event_url, dict(
            event, operation_id=str(uuid.uuid4()))).status_code, 400)
        self.assertTrue(attack_accuracy_state(self.person)['fortune_pending'])
        operation = uuid.uuid4()
        with patch('home.epic_battle_accuracy.secrets.randbelow', side_effect=[3, 18]) as dice:
            self.assertEqual(self.client.post(roll_url, {
                'operation_id': str(operation), 'disadvantage': 'on'}).status_code, 302)
        dice.assert_called_once_with(20)
        receipt = TbOperacaoRecurso.objects.get(operation_id=operation).resposta
        self.assertEqual(receipt['mode'], 'normal')
        self.assertTrue(receipt['fortune_consumed'])
        self.assertFalse(attack_accuracy_state(self.person)['fortune_pending'])
        with patch('home.epic_battle_accuracy.secrets.randbelow',
                   side_effect=AssertionError('replay rolled again')):
            self.assertEqual(self.client.post(roll_url, {
                'operation_id': str(operation), 'disadvantage': 'on'}).status_code, 302)
        self.assertEqual(self.client.post(event_url, dict(
            event, operation_id=str(uuid.uuid4()), event_ref='queda-1b')).status_code, 302)
        with patch('home.epic_battle_accuracy.secrets.randbelow', side_effect=[3, 18]) as dice:
            second = uuid.uuid4()
            self.assertEqual(self.client.post(roll_url, {
                'operation_id': str(second)}).status_code, 302)
        self.assertEqual(dice.call_count, 2)
        self.assertEqual(TbOperacaoRecurso.objects.get(
            operation_id=second).resposta['mode'], 'advantage')
        self.assertEqual(self.client.post(event_url, dict(
            event, operation_id=str(uuid.uuid4()), event_ref='queda-1c')).status_code, 302)
        self.grant.delete()
        self.assertIsNone(attack_accuracy_state(self.person))
        self.assertEqual(self.client.post(roll_url, {
            'operation_id': str(uuid.uuid4())}).status_code, 400)

    def test_fortune_expires_at_next_turn_end_and_choice_gates_event(self):
        self.talent.tags_json = ATTRIBUTE_TAGS + [FORTUNE_TAG]
        self.talent.save(update_fields=['tags_json'])
        event_url = reverse('personagem_registrar_criatura_a_zero', args=[self.person.pk])
        turn_url = reverse('personagem_encerrar_turno_fortuna', args=[self.person.pk])
        event = {'operation_id': str(uuid.uuid4()), 'event_ref': 'queda-2',
                 'creature_ref': 'criatura-b', 'visible_confirmed': 'on',
                 'zero_confirmed': 'on', 'during_own_turn': 'on'}
        self.assertEqual(self.client.post(event_url, dict(
            event, zero_confirmed='')).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(event_url, event).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(event_url, event).status_code, 302)
        self.assertTrue(attack_accuracy_state(self.person)['fortune_pending'])
        first = {'operation_id': str(uuid.uuid4()), 'turn_ref': 'turno-1',
                 'confirmed': 'on'}
        self.assertEqual(self.client.post(turn_url, first).status_code, 302)
        self.assertEqual(self.client.post(turn_url, first).status_code, 302)
        self.assertTrue(attack_accuracy_state(self.person)['fortune_pending'])
        self.assertEqual(self.client.post(turn_url, dict(
            first, operation_id=str(uuid.uuid4()))).status_code, 400)
        self.assertEqual(self.client.post(turn_url, {
            'operation_id': str(uuid.uuid4()), 'turn_ref': 'turno-2',
            'confirmed': 'on'}).status_code, 302)
        self.assertFalse(attack_accuracy_state(self.person)['fortune_pending'])
        self.grant.detalhes = ''
        self.grant.save(update_fields=['detalhes'])
        self.assertIsNone(attack_accuracy_state(self.person))
        self.assertEqual(self.client.post(event_url, dict(
            event, operation_id=str(uuid.uuid4()), event_ref='queda-3')).status_code, 400)

    def test_complete_candidate_retains_source_markdown_and_existing_requirements(self):
        candidate = next(row for row in epic_candidates()
                         if row['slug'] == 'dadiva-da-carnificina')
        self.assertEqual(candidate['tags_json'], ATTRIBUTE_TAGS +
                         VERIFIED_EFFECTS['dadiva-da-carnificina'])
        self.assertEqual(candidate['pre_requisito'], '')
        self.assertIn('Fortuna do Assassino', candidate['descricao'])
        self.assertIn('Momento de Violência', candidate['descricao'])
        self.assertIn('Sede de Sangue', candidate['descricao'])
        self.assertEqual(validate_tags_json(candidate['tags_json'], Library()), [])
