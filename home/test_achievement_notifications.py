from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.conquistas import conceder_conquista, revogar_conquista_manual
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

    def test_manual_revocation_is_idempotent_and_private_until_regrant(self):
        staff = get_user_model().objects.create_superuser('achievement-staff',
                                                          'staff@example.invalid', 'x')
        self.assertTrue(conceder_conquista(self.owner, self.rule, por=staff))
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=self.rule)
        self.client.force_login(staff)
        action_url = reverse('admin:home_tbusuarioconquista_changelist')
        payload = {'action': 'revogar_manuais', '_selected_action': [grant.pk]}
        self.assertEqual(self.client.post(action_url, payload).status_code, 302)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        possession = TbUsuarioCosmetico.objects.get(user=self.owner, cosmetico=self.badge)
        self.assertIsNotNone(possession.suspenso_em)
        self.assertEqual(self.client.post(action_url, payload).status_code, 302)
        self.assertEqual(TbConquistaNotificacao.objects.count(), 1)
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse('conquista_notificacoes')),
                               self.rule.nome)
        self.assertTrue(conceder_conquista(self.owner, self.rule, por=staff))
        possession.refresh_from_db()
        self.assertIsNone(possession.suspenso_em)
        self.assertContains(self.client.get(reverse('conquista_notificacoes')),
                            self.rule.nome)

    def test_revocation_preserves_shared_reward_and_other_origin(self):
        second = TbConquista.objects.create(slug='shared-badge', nome='Outra conquista',
                                            criterio='manual', recompensa=self.badge)
        conceder_conquista(self.owner, self.rule)
        conceder_conquista(self.owner, second)
        first_grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=self.rule)
        second_grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=second)
        self.assertTrue(revogar_conquista_manual(first_grant))
        possession = TbUsuarioCosmetico.objects.get(user=self.owner, cosmetico=self.badge)
        self.assertIsNone(possession.suspenso_em)
        possession.origem = 'staff'
        possession.save(update_fields=['origem'])
        self.assertTrue(revogar_conquista_manual(second_grant))
        possession.refresh_from_db()
        self.assertIsNone(possession.suspenso_em)

    def test_admin_revokes_staff_override_but_not_fact_award(self):
        staff = get_user_model().objects.create_superuser('override-admin',
                                                          'override@example.invalid', 'x')
        automatic = TbConquista.objects.create(
            slug='override-automatic', nome='Regra automática', criterio='automatico',
            secreta=True,
            criterio_json={'schema_version': 1, 'metric': 'characters_created',
                           'scope': 'account', 'operator': 'gte', 'target': 1},
            recompensa=self.badge)
        self.client.force_login(staff)
        rules_url = reverse('admin:home_tbconquista_changelist')
        manual_payload = {'action': 'conceder_a_usuarios', 'confirmar': '1',
                          'select_across': '0', '_selected_action': [automatic.pk],
                          'usernames': self.owner.username}
        self.assertEqual(self.client.post(rules_url, manual_payload).status_code, 302)
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=automatic)
        self.assertEqual(grant.concedida_por_id, staff.pk)
        action_url = reverse('admin:home_tbusuarioconquista_changelist')
        payload = {'action': 'revogar_manuais', '_selected_action': [grant.pk]}
        self.assertEqual(self.client.post(action_url, payload).status_code, 302)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertIsNotNone(TbUsuarioCosmetico.objects.get(
            user=self.owner, cosmetico=self.badge).suspenso_em)
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse('profile')), automatic.nome)
        self.assertNotContains(self.client.get(reverse('conquista_notificacoes')),
                               automatic.nome)
        self.client.force_login(staff)
        self.assertEqual(self.client.post(action_url, payload).status_code, 302)
        self.assertEqual(self.client.post(rules_url, manual_payload).status_code, 302)
        grant.refresh_from_db()
        self.assertIsNone(grant.revogada_em)
        self.assertIsNone(TbUsuarioCosmetico.objects.get(
            user=self.owner, cosmetico=self.badge).suspenso_em)

        other = get_user_model().objects.create_user('fact-award-owner')
        self.assertTrue(conceder_conquista(other, automatic))
        fact_grant = TbUsuarioConquista.objects.get(user=other, conquista=automatic)
        self.client.force_login(staff)
        fact_payload = {'action': 'revogar_manuais', '_selected_action': [fact_grant.pk]}
        self.assertEqual(self.client.post(action_url, fact_payload).status_code, 302)
        fact_grant.refresh_from_db()
        self.assertIsNone(fact_grant.revogada_em)
