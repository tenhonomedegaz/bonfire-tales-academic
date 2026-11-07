"""Operacao auditada de entregas de conquistas no admin."""

from io import StringIO
from unittest.mock import patch

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from home.event_deliveries import ADVENTURE_CONSUMER
from home.models import TbEntregaEventoConquista, TbEventoConquista


class AchievementDeliveryAdminTests(TransactionTestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_superuser(
            'delivery-operator', 'operator@example.invalid', 'secret')
        self.other = get_user_model().objects.create_user(
            'delivery-staff', 'staff@example.invalid', 'secret', is_staff=True)
        self.fact = TbEventoConquista.objects.create(
            origem='site_ledger', chave_origem='admin-delivery-test',
            tipo='adventure_recorded', conta=self.operator, agregado_id=1,
            ocorrido_em=timezone.now())
        self.delivery = TbEntregaEventoConquista.objects.create(
            evento=self.fact, consumidor=ADVENTURE_CONSUMER,
            estado='revisao', tentativas=5, ultimo_erro='RuntimeError')
        self.url = reverse('admin:home_tbentregaeventoconquista_changelist')

    def test_review_can_be_found_requeued_and_processed_with_audit(self):
        self.client.force_login(self.operator)
        listing = self.client.get(self.url, {'q': 'admin-delivery-test'})
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, 'admin-delivery-test')
        self.assertContains(listing, 'RuntimeError')
        self.assertContains(listing, reverse(
            'admin:home_tbeventoconquista_change', args=[self.fact.pk]))

        response = self.client.post(self.url, {
            'action': 'retomar_revisao',
            '_selected_action': [self.delivery.pk],
            'index': 0,
        })
        self.assertEqual(response.status_code, 302)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'pendente')
        self.assertEqual(self.delivery.tentativas, 5)
        self.assertEqual(self.delivery.ultimo_erro, 'RuntimeError')
        self.assertTrue(LogEntry.objects.filter(
            user=self.operator, content_type__model='tbentregaeventoconquista',
            object_id=str(self.delivery.pk), action_flag=CHANGE).exists())

        call_command('processar_entregas_conquistas', apply=True,
                     user_id=self.operator.pk, limit=1, stdout=StringIO())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'concluida')
        self.assertEqual(self.delivery.tentativas, 6)

    def test_non_superuser_cannot_requeue_review(self):
        self.client.force_login(self.other)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url, {
            'action': 'retomar_revisao', '_selected_action': [self.delivery.pk],
        })
        self.client.post(self.url, {
            'action': 'processar_revisao', '_selected_action': [self.delivery.pk],
        })
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'revisao')
        self.assertFalse(LogEntry.objects.filter(
            content_type__model='tbentregaeventoconquista',
            object_id=str(self.delivery.pk)).exists())

    def test_immediate_recovery_processes_only_selected_review(self):
        another_fact = TbEventoConquista.objects.create(
            origem='site_ledger', chave_origem='admin-delivery-other',
            tipo='adventure_recorded', conta=self.operator, agregado_id=2,
            ocorrido_em=timezone.now())
        other_delivery = TbEntregaEventoConquista.objects.create(
            evento=another_fact, consumidor=ADVENTURE_CONSUMER,
            estado='pendente')
        self.client.force_login(self.operator)

        response = self.client.post(self.url, {
            'action': 'processar_revisao',
            '_selected_action': [self.delivery.pk],
            'index': 0,
        })

        self.assertEqual(response.status_code, 302)
        self.delivery.refresh_from_db()
        other_delivery.refresh_from_db()
        self.assertEqual((self.delivery.estado, self.delivery.tentativas),
                         ('concluida', 6))
        self.assertEqual((other_delivery.estado, other_delivery.tentativas),
                         ('pendente', 0))
        self.assertTrue(LogEntry.objects.filter(
            user=self.operator, content_type__model='tbentregaeventoconquista',
            object_id=str(self.delivery.pk), action_flag=CHANGE,
            change_message='Reprocessamento imediato solicitado').exists())

    def test_immediate_recovery_failure_returns_to_review(self):
        self.client.force_login(self.operator)

        with patch('home.event_deliveries.avaliar_quests_categorizadas',
                   side_effect=RuntimeError('failure after first evaluation')):
            response = self.client.post(self.url, {
                'action': 'processar_revisao',
                '_selected_action': [self.delivery.pk],
                'index': 0,
            })

        self.assertEqual(response.status_code, 302)
        self.delivery.refresh_from_db()
        self.assertEqual((self.delivery.estado, self.delivery.tentativas,
                          self.delivery.ultimo_erro),
                         ('revisao', 6, 'RuntimeError'))
        self.assertIsNone(self.delivery.reserva_token)
        self.assertTrue(LogEntry.objects.filter(
            user=self.operator, content_type__model='tbentregaeventoconquista',
            object_id=str(self.delivery.pk), action_flag=CHANGE).exists())

    def test_detail_form_cannot_override_delivery_state_or_delete_fact(self):
        self.client.force_login(self.operator)
        detail = reverse('admin:home_tbentregaeventoconquista_change',
                         args=[self.delivery.pk])
        self.assertEqual(self.client.get(detail).status_code, 200)
        response = self.client.post(detail, {
            'estado': 'concluida', 'tentativas': 0, 'ultimo_erro': '',
            '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.estado, 'revisao')
        self.assertEqual(self.delivery.tentativas, 5)
        self.assertEqual(self.delivery.ultimo_erro, 'RuntimeError')
        deletion = reverse('admin:home_tbentregaeventoconquista_delete',
                           args=[self.delivery.pk])
        self.assertEqual(self.client.get(deletion).status_code, 403)
