"""Entrega administrativa de prêmios adicionados após uma conquista já concedida."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.conquistas import conceder_conquista, revogar_conquista_manual
from home.models import (TbConquista, TbConquistaNotificacao, TbCosmetico,
                         TbUsuarioConquista, TbUsuarioCosmetico)


class AchievementRewardReplayTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_superuser(
            'reward-replay-staff', 'replay@example.invalid', 'x')
        self.owner = get_user_model().objects.create_user('reward-replay-owner')
        self.revoked_owner = get_user_model().objects.create_user('reward-replay-revoked')
        self.legacy = TbCosmetico.objects.create(
            slug='replay-legacy', nome='Prêmio original', tipo='badge', origem='conquista')
        self.extra = TbCosmetico.objects.create(
            slug='replay-extra', nome='Prêmio posterior', tipo='badge', origem='conquista')

    def _run_action(self, *rules):
        self.client.force_login(self.staff)
        return self.client.post(reverse('admin:home_tbconquista_changelist'), {
            'action': 'sincronizar_recompensas_concedidas', 'select_across': '0',
            '_selected_action': [rule.pk for rule in rules],
        })

    def test_staff_delivers_new_reward_only_to_active_grants_without_new_notice(self):
        rule = TbConquista.objects.create(
            slug='replay-active', nome='Conquista ativa', recompensa=self.legacy)
        inactive = TbConquista.objects.create(
            slug='replay-inactive', nome='Conquista inativa')
        conceder_conquista(self.owner, rule, por=self.staff)
        conceder_conquista(self.revoked_owner, rule, por=self.staff)
        revoked = TbUsuarioConquista.objects.get(user=self.revoked_owner, conquista=rule)
        self.assertTrue(revogar_conquista_manual(revoked))
        conceder_conquista(self.owner, inactive, por=self.staff)
        inactive.ativo = False
        inactive.save(update_fields=['ativo'])
        rule.recompensas_extras.add(self.extra)
        inactive.recompensas_extras.add(self.extra)
        notices_before = TbConquistaNotificacao.objects.count()
        self.assertFalse(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.extra).exists())

        response = self._run_action(rule, inactive)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.extra, suspenso_em__isnull=True).exists())
        self.assertFalse(TbUsuarioCosmetico.objects.filter(
            user=self.revoked_owner, cosmetico=self.extra).exists())
        revoked.refresh_from_db()
        self.assertIsNotNone(revoked.revogada_em)
        self.assertEqual(TbConquistaNotificacao.objects.count(), notices_before)
        self.assertEqual(self._run_action(rule).status_code, 302)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.extra).count(), 1)
        self.assertEqual(TbConquistaNotificacao.objects.count(), notices_before)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('profile')), self.extra.nome)

    def test_invalid_reward_rolls_back_entire_admin_action(self):
        valid = TbConquista.objects.create(slug='replay-valid', nome='Conquista válida')
        invalid = TbConquista.objects.create(slug='replay-invalid', nome='Conquista inválida')
        frame = TbCosmetico.objects.create(
            slug='replay-frame', nome='Moldura animada', tipo='moldura',
            origem='colaborador', animado=True)
        conceder_conquista(self.owner, valid, por=self.staff)
        TbUsuarioConquista.objects.create(
            user=self.owner, conquista=invalid, concedida_por=self.staff)
        valid.recompensas_extras.add(self.extra)
        invalid.recompensas_extras.add(frame)
        response = self._run_action(valid, invalid)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.extra).exists())
        self.assertFalse(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=frame).exists())
