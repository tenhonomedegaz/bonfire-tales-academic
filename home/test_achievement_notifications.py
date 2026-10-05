from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.conquistas import conceder_conquista
from home.deploy_sync import MEMORY_MODELS
from home.models import (TbConquista, TbConquistaNotificacao, TbCosmetico,
                         TbUsuarioConquista, TbUsuarioCosmetico)


class AchievementNotificationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('achievement-inbox-owner')
        self.other = get_user_model().objects.create_user('achievement-inbox-other')
        self.badge = TbCosmetico.objects.create(
            slug='badge-achievement-inbox', nome='Badge da conquista',
            tipo='badge', origem='conquista')
        self.rule = TbConquista.objects.create(
            slug='achievement-inbox', nome='Primeira conquista',
            criterio='manual', recompensa=self.badge)

    def test_grant_is_readable_only_by_owner_and_replay_does_not_duplicate(self):
        self.assertIn('TbConquistaNotificacao', MEMORY_MODELS)
        self.assertTrue(conceder_conquista(self.owner, self.rule))
        self.assertFalse(conceder_conquista(self.owner, self.rule))
        notice = TbConquistaNotificacao.objects.get()
        self.assertEqual(notice.concessao.user_id, self.owner.pk)
        inbox_url = reverse('conquista_notificacoes')
        read_url = reverse('conquista_notificacao_ler', args=[notice.pk])

        self.assertEqual(self.client.get(inbox_url).status_code, 302)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(inbox_url), self.rule.nome)
        self.assertEqual(self.client.post(read_url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(inbox_url), self.rule.nome)
        self.assertContains(self.client.get(reverse('profile')),
                            'Notificações de conquistas (1)')
        response = self.client.post(read_url, {'abrir': '1'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('profile') + '#conquistas')
        notice.refresh_from_db()
        self.assertIsNotNone(notice.lida_em)
        self.assertEqual(TbConquistaNotificacao.objects.count(), 1)

        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=self.rule)
        grant.revogada_em = timezone.now()
        grant.save(update_fields=['revogada_em'])
        self.assertNotContains(self.client.get(inbox_url), self.rule.nome)
        self.assertEqual(self.client.post(read_url).status_code, 404)
        self.assertTrue(conceder_conquista(self.owner, self.rule))
        notice.refresh_from_db()
        self.assertIsNone(notice.lida_em)
        self.assertEqual(TbConquistaNotificacao.objects.count(), 1)
        self.assertContains(self.client.get(inbox_url), self.rule.nome)

    def test_failed_reward_rolls_back_notice_with_grant(self):
        with patch.object(TbUsuarioCosmetico.objects, 'get_or_create',
                          side_effect=RuntimeError('inventario indisponivel')):
            with self.assertRaises(RuntimeError):
                conceder_conquista(self.owner, self.rule)
        self.assertFalse(TbUsuarioConquista.objects.exists())
        self.assertFalse(TbConquistaNotificacao.objects.exists())
