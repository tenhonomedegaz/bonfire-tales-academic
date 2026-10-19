"""Aceite regional dos direitos de progressão vinculados à ficha."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from .conquistas import (conceder_direitos_marco, confirmar_consumo_token,
                         direitos_ficha, solicitar_token_ficha)
from .models import TbEventoConquista, TbPersonagem, TbPersonagemAventura, TbPersonagemRevisao
from .permissions import limite_detalhe


class CharacterMilestoneTokenTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user('token-owner')
        self.staff = users.objects.create_user('token-staff', is_staff=True)
        self.one = TbPersonagem.objects.create(dono=self.owner, nome='Uma', nivel=13)
        self.two = TbPersonagem.objects.create(dono=self.owner, nome='Duas', nivel=13)

    def grant(self, character, level):
        revision = TbPersonagemRevisao.objects.create(
            id_personagem=character, tipo='level_up', nivel_antes=level - 1,
            nivel_depois=level)
        fact = TbEventoConquista.objects.create(
            origem='site', chave_origem=f'test-level:{revision.pk}',
            tipo='character_level_up', conta=self.owner, personagem=character,
            agregado_id=revision.pk, ocorrido_em=timezone.now())
        conceder_direitos_marco(revision, fact)
        return revision

    def test_new_grants_are_per_character_and_replay_is_idempotent(self):
        revision = self.grant(self.one, 13)
        self.grant(self.two, 13)
        fact = TbEventoConquista.objects.get(chave_origem=f'test-level:{revision.pk}')
        conceder_direitos_marco(revision, fact)
        self.assertEqual(len(direitos_ficha(self.one)), 2)
        self.assertEqual(len(direitos_ficha(self.two)), 2)
        with (patch('home.permissions.is_rank_esmeralda', return_value=True),
              patch('home.permissions.is_colaborador', return_value=False),
              patch('home.permissions.is_mestre_ouro', return_value=False)):
            self.assertEqual(limite_detalhe(self.owner)['total'], 3)
        revision.revertida = True
        revision.revertida_em = timezone.now()
        revision.save(update_fields=['revertida', 'revertida_em'])
        self.assertEqual(direitos_ficha(self.one), [])
        with (patch('home.permissions.is_rank_esmeralda', return_value=True),
              patch('home.permissions.is_colaborador', return_value=False),
              patch('home.permissions.is_mestre_ouro', return_value=False)):
            self.assertEqual(limite_detalhe(self.owner)['total'], 2)
        self.grant(self.one, 13)
        self.assertEqual(len(direitos_ficha(self.one)), 2)
        self.assertEqual(TbEventoConquista.objects.filter(
            tipo='character_milestone_granted', personagem=self.one).count(), 2)
        self.assertEqual(TbEventoConquista.objects.filter(
            tipo='character_milestone_restored', personagem=self.one).count(), 2)

    def test_request_and_staff_consumption_require_mission_of_same_character(self):
        self.grant(self.one, 9)
        self.grant(self.two, 9)
        grant = direitos_ficha(self.one)[0]['grant']
        other_grant = direitos_ficha(self.two)[0]['grant']
        with self.assertRaises(ValueError):
            solicitar_token_ficha(self.two.pk, grant.pk, self.owner)
        request = solicitar_token_ficha(self.one.pk, grant.pk, self.owner)
        self.assertEqual(solicitar_token_ficha(self.one.pk, grant.pk, self.owner).pk,
                         request.pk)
        with self.assertRaises(ValueError):
            confirmar_consumo_token(self.one.pk, grant.pk, 99999, self.staff)
        wrong = TbPersonagemAventura.objects.create(
            id_personagem=self.two, nome_aventura='Outra',
            detalhes_json={'bot_quest_id': 'q-other', 'bot_quest_proof': {'ok': True},
                           'quest_category': 'item_rare',
                           'quest_confirmed_by': self.staff.pk})
        with self.assertRaises(ValueError):
            confirmar_consumo_token(self.one.pk, grant.pk, wrong.pk, self.staff)
        mission = TbPersonagemAventura.objects.create(
            id_personagem=self.one, nome_aventura='Missão confirmada',
            detalhes_json={'bot_quest_id': 'q-one', 'bot_quest_proof': {'ok': True},
                           'quest_category': 'item_rare',
                           'quest_confirmed_by': self.staff.pk})
        consumed = confirmar_consumo_token(self.one.pk, grant.pk, mission.pk, self.staff)
        self.assertEqual(consumed.payload_json['confirmed_by'], self.staff.pk)
        self.assertEqual(consumed.payload_json['bot_quest_id'], 'q-one')
        self.assertEqual(confirmar_consumo_token(self.one.pk, grant.pk, mission.pk,
                                                self.staff).pk, consumed.pk)
        with self.assertRaises(ValueError):
            confirmar_consumo_token(self.one.pk, grant.pk, wrong.pk, self.staff)
        solicitar_token_ficha(self.two.pk, other_grant.pk, self.owner)
        with self.assertRaises(ValueError):
            confirmar_consumo_token(self.two.pk, other_grant.pk, mission.pk, self.staff)

    def test_missing_reference_no_item_and_deletion_keep_audit(self):
        self.grant(self.one, 13)
        grant = next(row['grant'] for row in direitos_ficha(self.one)
                     if row['benefit'] == 'item_very_rare')
        solicitar_token_ficha(self.one.pk, grant.pk, self.owner)
        mission = TbPersonagemAventura.objects.create(
            id_personagem=self.one, nome_aventura='Sem referência')
        with self.assertRaises(ValueError):
            confirmar_consumo_token(self.one.pk, grant.pk, mission.pk, self.staff)
        self.assertEqual(self.one.inventario.count(), 0)
        grant_id = grant.pk
        self.one.delete()
        grant.refresh_from_db()
        self.assertIsNone(grant.personagem_id)
        with self.assertRaises(TbPersonagem.DoesNotExist):
            solicitar_token_ficha(self.one.pk, grant_id, self.owner)

    def test_routes_keep_owner_and_staff_boundaries(self):
        self.grant(self.one, 5)
        grant = direitos_ficha(self.one)[0]['grant']
        request_url = reverse('request_character_token', args=[self.one.pk, grant.pk])
        confirm_url = reverse('confirm_character_token', args=[self.one.pk, grant.pk])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(request_url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(request_url).status_code, 302)
        self.assertEqual(self.client.post(confirm_url, {'mission_ledger_id': 1}).status_code,
                         404)

    def test_historical_reprocessing_does_not_create_new_rights(self):
        from .conquistas import registrar_fato_level_up

        revision = TbPersonagemRevisao.objects.create(
            id_personagem=self.one, tipo='level_up', nivel_antes=12, nivel_depois=13,
            snapshot_json={'personagem': {'nivel': 12}, 'classes': [
                {'id_classe_id': 1, 'nivel': 12, 'principal': True}]})
        following = TbPersonagemRevisao.objects.create(
            id_personagem=self.one, tipo='nivel_1', nivel_antes=13, nivel_depois=13,
            snapshot_json={'personagem': {'nivel': 13}, 'classes': [
                {'id_classe_id': 1, 'nivel': 13, 'principal': True}]})
        with (patch('home.event_deliveries.enqueue_level_event'),
              patch('home.conquistas.avaliar_nivel_personagem')):
            registrar_fato_level_up(revision, proxima_revisao=following,
                                    novos_direitos=False)
        self.assertFalse(TbEventoConquista.objects.filter(
            tipo='character_milestone_granted').exists())


class ConcurrentTokenRequestTests(TransactionTestCase):
    def test_two_requests_share_one_receipt(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections

        owner = get_user_model().objects.create_user('concurrent-token-owner')
        character = TbPersonagem.objects.create(dono=owner, nome='Concorrente', nivel=5)
        revision = TbPersonagemRevisao.objects.create(
            id_personagem=character, tipo='level_up', nivel_antes=4, nivel_depois=5)
        fact = TbEventoConquista.objects.create(
            origem='site', chave_origem='concurrent-level', tipo='character_level_up',
            conta=owner, personagem=character, agregado_id=revision.pk,
            ocorrido_em=timezone.now())
        conceder_direitos_marco(revision, fact)
        grant = direitos_ficha(character)[0]['grant']
        barrier = Barrier(2)

        def ask():
            try:
                barrier.wait(timeout=5)
                return solicitar_token_ficha(character.pk, grant.pk, owner).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(lambda _: ask(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(TbEventoConquista.objects.filter(
            tipo='character_token_requested').count(), 1)
