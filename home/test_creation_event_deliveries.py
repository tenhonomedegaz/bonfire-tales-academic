from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone

from home.event_deliveries import (CREATION_CONSUMER, enqueue_creation_event,
                                   process_creation_delivery, reserve_creation_delivery)
from home.models import (TbConquista, TbCosmetico, TbEntregaEventoConquista,
                         TbEventoConquista, TbUsuarioConquista, TbUsuarioCosmetico)
from home.test_criador import _CriadorBase


class CreationDeliveryFlowTests(_CriadorBase):
    def setUp(self):
        super().setUp()
        self.user = self._novo_usuario('delivery-creation-owner', staff=True)
        created = self._post_criar(self.user, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        self.event = TbEventoConquista.objects.get(conta=self.user)
        self.delivery = TbEntregaEventoConquista.objects.get(
            evento=self.event, consumidor=CREATION_CONSUMER)
        self.badge = TbCosmetico.objects.create(
            slug='badge-creation-delivery', nome='Marco de criação',
            tipo='badge', origem='conquista')
        self.first_rule = TbConquista.objects.create(
            slug='first-delivery-test', nome='Primeira ficha', criterio='automatico',
            criterio_json={'schema_version': 1, 'metric': 'characters_created',
                           'scope': 'account', 'operator': 'gte', 'target': 1},
            recompensa=self.badge)
        self.class_rule = TbConquista.objects.create(
            slug='class-delivery-test', nome='Primeira classe', criterio='automatico',
            criterio_json={'schema_version': 1, 'metric': 'class_started',
                           'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                           'operator': 'gte', 'target': 1})

    def test_creation_delivery_replays_later_rules_and_deduplicates_right(self):
        self.assertEqual(self.delivery.estado, 'pendente')
        output = StringIO()
        call_command('processar_entregas_criacao', user_id=self.user.pk, stdout=output)
        self.assertIn('fatos=1 entregas=1', output.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.user).exists())

        call_command('processar_entregas_criacao', apply=True, user_id=self.user.pk,
                     stdout=StringIO())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'concluida')
        self.assertEqual(self.delivery.tentativas, 1)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=self.user).count(), 2)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(user=self.user,
                                                          cosmetico=self.badge).count(), 1)
        call_command('processar_entregas_criacao', apply=True, user_id=self.user.pk,
                     stdout=StringIO())
        self.assertEqual(TbUsuarioConquista.objects.filter(user=self.user).count(), 2)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(user=self.user,
                                                          cosmetico=self.badge).count(), 1)

    def test_failed_effect_returns_to_queue_without_partial_grants(self):
        with patch('home.event_deliveries.avaliar_primeira_ficha_evento',
                   side_effect=RuntimeError('simulated failure')):
            call_command('processar_entregas_criacao', apply=True, user_id=self.user.pk,
                         stdout=StringIO())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'pendente')
        self.assertEqual(self.delivery.tentativas, 1)
        self.assertEqual(self.delivery.ultimo_erro, 'RuntimeError')
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.user).exists())
        TbEntregaEventoConquista.objects.filter(pk=self.delivery.pk).update(
            proxima_tentativa_em=timezone.now() - timedelta(seconds=1))
        call_command('processar_entregas_criacao', apply=True, user_id=self.user.pk,
                     stdout=StringIO())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'concluida')
        self.assertEqual(self.delivery.tentativas, 2)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=self.user).count(), 2)

    def test_expired_reservation_rejects_stale_worker(self):
        first = reserve_creation_delivery(user_id=self.user.pk)
        self.assertIsNotNone(first)
        TbEntregaEventoConquista.objects.filter(pk=self.delivery.pk).update(
            reserva_ate=timezone.now() - timedelta(seconds=1))
        second = reserve_creation_delivery(user_id=self.user.pk)
        self.assertNotEqual(first[1], second[1])
        self.assertFalse(process_creation_delivery(*first))
        self.assertTrue(process_creation_delivery(*second))
        self.assertEqual(TbUsuarioConquista.objects.filter(user=self.user).count(), 2)

    def test_review_can_be_resumed_without_changing_delivery_identity(self):
        reservation = reserve_creation_delivery(user_id=self.user.pk)
        with patch('home.event_deliveries.avaliar_primeira_ficha_evento',
                   side_effect=RuntimeError('simulated failure')):
            self.assertFalse(process_creation_delivery(*reservation, max_attempts=1))
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'revisao')
        self.assertEqual(self.delivery.ultimo_erro, 'RuntimeError')
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.user).exists())
        preview = StringIO()
        call_command('processar_entregas_criacao', resume_review_id=self.delivery.pk,
                     stdout=preview)
        self.assertIn('estado=revisao tentativas=1', preview.getvalue())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'revisao')

        with self.assertRaisesMessage(CommandError, 'outra conta'):
            call_command('processar_entregas_criacao', apply=True,
                         resume_review_id=self.delivery.pk, user_id=self.user.pk + 1,
                         stdout=StringIO())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'revisao')

        call_command('processar_entregas_criacao', apply=True,
                     resume_review_id=self.delivery.pk,
                     stdout=StringIO())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'concluida')
        self.assertEqual(self.delivery.tentativas, 2)
        self.assertEqual(self.delivery.ultimo_erro, 'RuntimeError')
        self.assertEqual(TbUsuarioConquista.objects.filter(user=self.user).count(), 2)


class CreationDeliveryConcurrencyTests(TransactionTestCase):
    def test_two_workers_cannot_reserve_the_same_delivery(self):
        user = get_user_model().objects.create_user('delivery-concurrent-owner')
        event = TbEventoConquista.objects.create(
            origem='site', chave_origem='personagem:919191:criado',
            tipo='character_created', conta=user, agregado_id=919191,
            ocorrido_em=timezone.now(), payload_json={'first_character': True})
        enqueue_creation_event(event)

        def reserve():
            close_old_connections()
            try:
                return reserve_creation_delivery()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: reserve(), range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)
        delivery = TbEntregaEventoConquista.objects.get(evento=event)
        self.assertEqual(delivery.estado, 'processando')
        self.assertEqual(delivery.tentativas, 1)
