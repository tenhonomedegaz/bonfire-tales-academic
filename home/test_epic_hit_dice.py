"""Recovery Superior uses class Hit Dice in the real sheet ledger."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_hit_dice import HIT_DICE_MAX_TAG, hit_dice_state, spend_hit_dice
from home.epic_talent_catalog import ATTRIBUTE_TAGS, epic_candidates
from home.models import (
    TbClasse, TbPersonagem, TbPersonagemClasse, TbPersonagemTalento, TbTalento,
)
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class EpicHitDiceTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username='hit-dice-owner')
        self.other = users.objects.create_user(username='hit-dice-other')
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome='Recuperação Superior', nivel=3,
            constituicao=16, pv_maximo=60, pv_atual=10)
        cls = TbClasse.objects.create(
            nome='Classe de dados', slug='classe-dados-epicos', dado_vida='1d8')
        TbPersonagemClasse.objects.create(
            id_personagem=self.person, id_classe=cls, nivel=3, principal=True)
        self.talent = TbTalento.objects.create(
            nome='Fonte de saúde', slug='saude-dados-teste', tipo='geral',
            tags_json=ATTRIBUTE_TAGS + [
                'always_active{temp_hp:+5}', HIT_DICE_MAX_TAG])
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes='talent_attr:CON')
        self.url = reverse('personagem_gastar_dados_vida', args=[self.person.pk])
        self.sheet = reverse('ficha_detail', args=[self.person.pk])

    def payload(self, operation_id=None, count='2'):
        return {'operation_id': str(operation_id or uuid.uuid4()),
                'die': '8', 'count': count, 'maximize': 'on', 'confirmed': 'on'}

    def test_maximum_spend_replay_exhaustion_and_long_rest(self):
        self.assertEqual([row['available'] for row in hit_dice_state(self.person)], [3])
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.sheet), 'Recuperação Superior')
        data = self.payload()
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 34)  # 2 * (d8 máximo + CON 4)
        self.assertEqual([row['available'] for row in hit_dice_state(self.person)], [1])
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 34)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 400)
        self.assertEqual(self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                          {'tipo': 'longo'}).status_code, 302)
        self.assertEqual([row['available'] for row in hit_dice_state(self.person)], [3])

    def test_choice_source_gate_owner_and_other_healing_tag(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 404)
        self.client.force_login(self.owner)
        self.grant.detalhes = ''
        self.grant.save(update_fields=['detalhes'])
        self.assertIsNone(hit_dice_state(self.person))
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 400)
        self.grant.detalhes = 'talent_attr:CON'
        self.grant.save(update_fields=['detalhes'])
        other = TbTalento.objects.create(
            nome='Outra cura', slug='outra-cura-dados-epicos', tipo='geral',
            tags_json=['always_active{trigger=healing, instant{heal:+2}}'])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=other, nome=other.nome)
        result = spend_hit_dice(self.person, operation_id=uuid.uuid4(),
                                die=8, count=1, maximize=True, confirmed=True)
        self.assertEqual((result['healed'], result['remaining']), (14, 2))
        self.grant.delete()
        self.assertIsNone(hit_dice_state(self.person))
        self.assertNotContains(self.client.get(self.sheet), 'Gastar Dados de Vida')
        self.assertEqual(self.client.post(self.url, self.payload(count='1')).status_code, 400)

    def test_tag_is_valid(self):
        candidate = next(row for row in epic_candidates()
                         if row['slug'] == 'dadiva-da-saude-abundante')
        self.assertIn(HIT_DICE_MAX_TAG, candidate['tags_json'])
        self.assertEqual([issue for issue in validate_tags_json(
            candidate['tags_json'], Library())
            if issue.level == ERROR], [])

    def test_optional_normal_roll_stays_on_server_and_replays(self):
        operation_id = uuid.uuid4()
        with patch('home.epic_hit_dice.secrets.randbelow', return_value=1):
            first = spend_hit_dice(self.person, operation_id=operation_id,
                                   die=8, count=1, maximize=False, confirmed=True)
        self.assertEqual((first['dice_values'], first['healed']), ([2], 6))
        with patch('home.epic_hit_dice.secrets.randbelow',
                   side_effect=AssertionError('replay must not roll')):
            replay = spend_hit_dice(self.person, operation_id=operation_id,
                                    die=8, count=1, maximize=False, confirmed=True)
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['dice_values'], [2])
        with self.assertRaises(ValueError):
            spend_hit_dice(self.person, operation_id=operation_id,
                           die=8, count=1, maximize=True, confirmed=True)
