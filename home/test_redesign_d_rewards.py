"""The approved catalog transition must preserve acquired rights and MM."""

import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase
from django.utils import timezone

from .models import MestreOuroDireito, TbRecompensaMestre, TbTransacaoMestre, UserProfile


class RedesignDRewardsTests(TransactionTestCase):
    def test_retire_and_restore_only_originally_active_subscription_rewards(self):
        user = get_user_model().objects.create_user('d_reward_owner', password='test-pass')
        profile = UserProfile.objects.get(user=user)
        profile.moedas_mestragem = 123
        profile.save(update_fields=['moedas_mestragem'])
        active = TbRecompensaMestre.objects.create(slug='d-legacy-active', nome='Antiga assinatura',
                                                   tipo='assinatura', ativo=True)
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
            output = StringIO()
            call_command('preview_redesign_d', output=str(path),
                         expected_home_head='0157_merge_redesign_b_d', stdout=output)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()

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
            self.assertEqual(run('restore', confirm='G01-D-REWARDS')['changed_reward_ids'],
                             [active.pk])
            active.refresh_from_db()
            inactive.refresh_from_db()
            normal.refresh_from_db()
            profile.refresh_from_db()
            self.assertTrue(active.ativo)
            self.assertFalse(inactive.ativo)
            self.assertTrue(normal.ativo)
            self.assertEqual(profile.moedas_mestragem, 123)
            self.assertTrue(MestreOuroDireito.objects.filter(pk=right.pk).exists())

            active.nome = 'Alterada após inventário'
            active.save(update_fields=['nome'])
            with self.assertRaises(CommandError):
                run('retire', confirm='G01-D-REWARDS')
            active.refresh_from_db()
            self.assertTrue(active.ativo)
