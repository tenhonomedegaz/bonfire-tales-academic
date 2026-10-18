"""The approved catalog transition must preserve acquired rights and MM."""

import json
import hashlib
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase
from django.utils import timezone

from .models import (MestreOuroDireito, TbCosmetico, TbPersonagem,
                     TbRecompensaMestre, TbTransacaoMestre, TbUsuarioCosmetico,
                     UserProfile)
from .test_redesign_d_support import capture_pre_d_snapshot


class RedesignDRewardsTests(TransactionTestCase):
    def test_narrow_snapshot_captures_imported_reward_and_restores_it(self):
        reward = TbRecompensaMestre.objects.create(
            slug='imported-subscription', nome='Assinatura importada',
            tipo='assinatura', ativo=True, preco_mm=5000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rewards.json'
            output = StringIO()
            call_command('preview_redesign_d_rewards', output=str(path), stdout=output)
            result = json.loads(output.getvalue())
            saved = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(saved['kind'], 'G01-D-rewards-prechange')
            self.assertEqual(saved['scope'], 'imported_rewards_pre_retirement_only')
            self.assertEqual(result['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual([row['id_recompensa'] for row in saved['rows']['subscription_rewards']],
                             [reward.pk])
            call_command('reconcile_redesign_d_rewards', snapshot=str(path),
                         sha256=result['sha256'], action='retire',
                         confirm='G01-D-REWARDS', stdout=StringIO())
            reward.refresh_from_db()
            self.assertFalse(reward.ativo)
            call_command('reconcile_redesign_d_rewards', snapshot=str(path),
                         sha256=result['sha256'], action='restore',
                         confirm='G01-D-REWARDS', stdout=StringIO())
            reward.refresh_from_db()
            self.assertTrue(reward.ativo)
            self.assertEqual(reward.preco_mm, 5000)

    def test_retire_and_restore_only_originally_active_subscription_rewards(self):
        user = get_user_model().objects.create_user('d_reward_owner', password='test-pass')
        profile = UserProfile.objects.get(user=user)
        profile.moedas_mestragem = 123
        profile.save(update_fields=['moedas_mestragem'])
        # Minimized historical shape: one level-13 sheet, two owned badges,
        # and the old subscription offer. No account data is copied from backup.
        character = TbPersonagem.objects.create(
            dono=user, nome='Ficha histórica representativa', nivel=13, arquivado=True)
        badges = [TbCosmetico.objects.create(
            slug=slug, tipo='badge', nome=slug, origem='evento_manual')
            for slug in ('badge-beta-portal', 'badge-beta-centelha')]
        owned = [TbUsuarioCosmetico.objects.create(
            user=user, cosmetico=badge, origem='evento_manual') for badge in badges]
        active = TbRecompensaMestre.objects.create(
            slug='mestre-ouro', nome='Antiga assinatura', tipo='assinatura',
            ativo=True, preco_mm=5000, mensalidade_mm=500, ordem=90)
        inactive = TbRecompensaMestre.objects.create(slug='d-legacy-inactive', nome='Inativa',
                                                     tipo='assinatura', ativo=False)
        normal = TbRecompensaMestre.objects.create(slug='d-normal', nome='Normal',
                                                   tipo='normal', ativo=True)
        purchase = TbTransacaoMestre.objects.create(mestre=user, tipo='assinatura',
                                                    valor_mm=-5000, saldo_mm=123)
        right = MestreOuroDireito.objects.create(user=user, primeira_compra=purchase,
                                                 adquirido_em=timezone.now())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'before.json'
            digest = capture_pre_d_snapshot(path)

            def run(action, sha=digest, confirm=''):
                out = StringIO()
                call_command('reconcile_redesign_d_rewards', snapshot=str(path), sha256=sha,
                             action=action, confirm=confirm, stdout=out)
                return json.loads(out.getvalue())

            self.assertEqual(run('preview')['changed_reward_ids'], [active.pk])
            with self.assertRaises(CommandError):
                run('retire')
            with self.assertRaises(CommandError):
                run('retire', sha='0' * 64, confirm='G01-D-REWARDS')
            self.assertEqual(run('retire', confirm='G01-D-REWARDS')['changed_reward_ids'],
                             [active.pk])
            active.refresh_from_db()
            self.assertFalse(active.ativo)
            self.assertEqual((active.preco_mm, active.mensalidade_mm, active.ordem),
                             (5000, 500, 90))
            self.assertTrue(TbPersonagem.objects.filter(
                pk=character.pk, dono=user, nivel=13, arquivado=True).exists())
            self.assertEqual(set(TbUsuarioCosmetico.objects.filter(
                pk__in=[row.pk for row in owned], user=user,
                suspenso_em__isnull=True).values_list('cosmetico__slug', flat=True)),
                {'badge-beta-portal', 'badge-beta-centelha'})
            self.assertTrue(MestreOuroDireito.objects.filter(pk=right.pk).exists())
            profile.refresh_from_db()
            self.assertEqual(profile.moedas_mestragem, 123)
            self.assertEqual(run('retire', confirm='G01-D-REWARDS')['changed_reward_ids'], [])
            self.assertFalse(TbRecompensaMestre.objects.get(pk=active.pk).ativo)
            self.assertEqual(run('restore', confirm='G01-D-REWARDS')['changed_reward_ids'],
                             [active.pk])
            active.refresh_from_db()
            inactive.refresh_from_db()
            normal.refresh_from_db()
            profile.refresh_from_db()
            self.assertTrue(active.ativo)
            self.assertEqual((active.preco_mm, active.mensalidade_mm, active.ordem),
                             (5000, 500, 90))
            self.assertFalse(inactive.ativo)
            self.assertTrue(normal.ativo)
            self.assertEqual(profile.moedas_mestragem, 123)
            self.assertTrue(MestreOuroDireito.objects.filter(pk=right.pk).exists())
            self.assertTrue(TbPersonagem.objects.filter(
                pk=character.pk, dono=user, nivel=13, arquivado=True).exists())
            self.assertEqual(set(TbUsuarioCosmetico.objects.filter(
                pk__in=[row.pk for row in owned], user=user,
                suspenso_em__isnull=True).values_list('cosmetico__slug', flat=True)),
                {'badge-beta-portal', 'badge-beta-centelha'})

            active.nome = 'Alterada após inventário'
            active.save(update_fields=['nome'])
            with self.assertRaises(CommandError):
                run('retire', confirm='G01-D-REWARDS')
            active.refresh_from_db()
            self.assertTrue(active.ativo)

            active.nome = 'Antiga assinatura'
            active.save(update_fields=['nome'])
            inactive.ativo = True
            inactive.save(update_fields=['ativo'])
            with self.assertRaises(CommandError):
                run('retire', confirm='G01-D-REWARDS')
            active.refresh_from_db()
            self.assertTrue(active.ativo)
