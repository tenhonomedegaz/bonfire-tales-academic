"""Compensating D pilot rollback must preserve the snapshot and be atomic."""

import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from .models import CosmeticCheckoutOffer, TbCosmetico, TbRecompensaMestre
from .test_redesign_d_support import capture_pre_d_snapshot


class RedesignDPilotRollbackTests(TransactionTestCase):
    def test_rewards_only_snapshot_cannot_archive_pilot(self):
        reward = TbRecompensaMestre.objects.create(
            slug='rollback-narrow', nome='Assinatura anterior', tipo='assinatura', ativo=True)
        with tempfile.TemporaryDirectory() as directory:
            full_path = Path(directory) / 'before.json'
            full_digest = capture_pre_d_snapshot(full_path)
            narrow = json.loads(full_path.read_text(encoding='utf-8'))
            narrow['scope'] = 'imported_rewards_pre_retirement_only'
            narrow['rows'] = {'subscription_rewards': narrow['rows']['subscription_rewards']}
            narrow.pop('counts')
            narrow.pop('recent_home_migrations')
            narrow_path = Path(directory) / 'rewards-only.json'
            narrow_path.write_text(json.dumps(narrow), encoding='utf-8')
            narrow_digest = hashlib.sha256(narrow_path.read_bytes()).hexdigest()

            call_command('reconcile_redesign_d_pilot', snapshot=str(full_path),
                         sha256=full_digest, action='seed', confirm='G01-D-PILOT',
                         stdout=StringIO())
            call_command('reconcile_redesign_d_rewards', snapshot=str(full_path),
                         sha256=full_digest, action='retire', confirm='G01-D-REWARDS',
                         stdout=StringIO())
            with self.assertRaisesMessage(CommandError, 'complete verified pre-D snapshot'):
                call_command('rollback_redesign_d_pilot', snapshot=str(narrow_path),
                             sha256=narrow_digest, confirm='G01-D-ROLLBACK-PILOT',
                             stdout=StringIO())
            self.assertEqual(TbCosmetico.objects.filter(
                slug__in=['tema-forja-de-brasas', 'tema-aurora-glacial',
                          'tema-circulo-arcano'], ativo=True).count(), 3)
            reward.refresh_from_db()
            self.assertFalse(reward.ativo)

    def test_rollback_is_atomic_and_restores_only_original_reward_state(self):
        active = TbRecompensaMestre.objects.create(
            slug='rollback-active', nome='Assinatura anterior', tipo='assinatura', ativo=True)
        inactive = TbRecompensaMestre.objects.create(
            slug='rollback-inactive', nome='Assinatura inativa', tipo='assinatura', ativo=False)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'before.json'
            digest = capture_pre_d_snapshot(path)
            different = json.loads(path.read_text(encoding='utf-8'))
            different['database_identity']['HOST'] = 'different-host.example'
            wrong_path = Path(directory) / 'other-database.json'
            wrong_path.write_text(json.dumps(different), encoding='utf-8')
            wrong_digest = hashlib.sha256(wrong_path.read_bytes()).hexdigest()
            with self.assertRaises(CommandError):
                call_command('rollback_redesign_d_pilot', snapshot=str(wrong_path),
                             sha256=wrong_digest, confirm='G01-D-ROLLBACK-PILOT',
                             stdout=StringIO())

            def run(confirm='G01-D-ROLLBACK-PILOT'):
                out = StringIO()
                call_command('rollback_redesign_d_pilot', snapshot=str(path), sha256=digest,
                             confirm=confirm, stdout=out)
                return json.loads(out.getvalue())

            call_command('reconcile_redesign_d_pilot', snapshot=str(path), sha256=digest,
                         action='seed', confirm='G01-D-PILOT', stdout=StringIO())
            call_command('reconcile_redesign_d_rewards', snapshot=str(path), sha256=digest,
                         action='retire', confirm='G01-D-REWARDS', stdout=StringIO())
            active.refresh_from_db()
            self.assertFalse(active.ativo)
            with self.assertRaises(CommandError):
                run('wrong-confirmation')

            # A changed reward forces the second step to fail after the pilot
            # archive was attempted; the outer transaction restores both.
            active.nome = 'Editada depois do inventário'
            active.save(update_fields=['nome'])
            with self.assertRaises(CommandError):
                run()
            self.assertEqual(TbCosmetico.objects.filter(
                slug__in=['tema-forja-de-brasas', 'tema-aurora-glacial',
                          'tema-circulo-arcano'], ativo=True).count(), 3)
            self.assertEqual(CosmeticCheckoutOffer.objects.filter(
                cosmetico__slug__startswith='tema-', active=True,
                demonstration=True).count(), 3)
            active.nome = 'Assinatura anterior'
            active.save(update_fields=['nome'])

            result = run()
            self.assertEqual(len(result['archived_slugs']), 3)
            self.assertEqual(result['retained_owned_slugs'], [])
            self.assertEqual(result['restored_reward_ids'], [active.pk])
            active.refresh_from_db()
            inactive.refresh_from_db()
            self.assertTrue(active.ativo)
            self.assertFalse(inactive.ativo)
            self.assertEqual(run(), {'archived_slugs': [], 'retained_owned_slugs': [],
                                     'restored_reward_ids': []})
