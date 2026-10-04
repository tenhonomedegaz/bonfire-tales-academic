"""Moderation suspends pending awards and can audit explicit compensation."""

import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.models import (SocialCreditEntry, SocialCreditPolicy,
                         SocialCreditReaderRecognition, SocialCreditWallet,
                         TbCronica, TbCronicaDenuncia)
from home.social_credits import (award_first_chronicle_publication,
                                 post_social_credit, reverse_moderated_story_credits,
                                 settle_reader_milestones)


class SocialModerationTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.author = users.objects.create_user('moderation-author', password='test')
        self.readers = [users.objects.create_user(f'moderation-reader-{i}', password='test')
                        for i in range(2)]
        self.moderator = users.objects.create_user(
            'moderation-staff', password='test', is_staff=True)
        self.moderator.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbcronicadenuncia'))
        self.admin = users.objects.create_superuser('moderation-admin', 'admin@example.test', 'test')
        self.policy = SocialCreditPolicy.objects.create(
            version='moderation-test', first_publication_amount=7, active=True,
            reader_recognition_enabled=True, reader_milestone_size=2,
            reader_milestone_amount=5, reader_consolidation_hours=24,
            reader_story_credit_cap=10, reader_author_period_credit_cap=10,
            reader_period_days=30,
        )
        self.story = TbCronica.objects.create(
            titulo='Relato moderado', slug='relato-moderado',
            conteudo_markdown='Texto publicado', autor=self.author,
            status='aprovada', data_publicacao=timezone.now(),
        )
        award_first_chronicle_publication(self.story)
        for reader in self.readers:
            self.client.force_login(reader)
            response = self.client.post(
                reverse('cronica_curtir', args=[self.story.pk]),
                json.dumps({'curtido': True}), content_type='application/json')
            self.assertEqual(response.status_code, 200)
        SocialCreditReaderRecognition.objects.filter(cronica=self.story).update(
            first_seen_at=timezone.now() - timedelta(days=2))

    def hide(self):
        self.client.force_login(self.readers[0])
        response = self.client.post(reverse('cronica_denunciar', args=[self.story.pk]),
                                    {'motivo': 'Conteúdo inadequado'})
        self.assertEqual(response.status_code, 302)
        report = TbCronicaDenuncia.objects.get(cronica=self.story, comentario__isnull=True)
        self.client.force_login(self.moderator)
        self.assertEqual(self.client.post(
            reverse('cronica_moderar_denuncia', args=[report.pk]),
            {'action': 'ocultar'}).status_code, 302)
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'oculta')
        return report

    def test_hidden_story_suspends_pending_reader_awards_until_restored(self):
        report = self.hide()
        self.assertEqual(settle_reader_milestones(self.policy.pk, self.story.pk), [])
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 7)
        self.assertEqual(self.client.post(
            reverse('cronica_moderar_denuncia', args=[report.pk]),
            {'action': 'restaurar'}).status_code, 302)
        self.assertEqual(len(settle_reader_milestones(self.policy.pk, self.story.pk)), 1)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 12)

    def test_confirmed_reversal_compensates_awards_once_and_keeps_report(self):
        self.assertEqual(len(settle_reader_milestones(self.policy.pk, self.story.pk)), 1)
        report = self.hide()
        with self.assertRaises(CommandError):
            call_command('reverse_moderated_story_credits', report_id=report.pk,
                         actor=self.admin.username, stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command('reverse_moderated_story_credits', report_id=report.pk,
                         actor=self.moderator.username, apply=True,
                         confirm_id=report.pk, stdout=StringIO())
        output = StringIO()
        call_command('reverse_moderated_story_credits', report_id=report.pk,
                     actor=self.admin.username, apply=True,
                     confirm_id=report.pk, stdout=output)
        self.assertIn('reversed; 2 reversal(s)', output.getvalue())
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 0)
        self.assertEqual(SocialCreditEntry.objects.filter(kind='compensation').count(), 2)
        self.assertEqual(SocialCreditEntry.objects.filter(delta__gt=0).count(), 2)
        report.refresh_from_db()
        audit = report.historico_decisoes[-1]
        self.assertEqual((audit['acao'], audit['credits_reversed'], audit['staff_id']),
                         ('credit_reversal', 12, self.admin.pk))
        self.assertEqual(len(audit['entry_ids']), 2)
        self.client.force_login(self.moderator)
        self.assertContains(self.client.get(reverse('cronica_denuncias')),
                            'Créditos comunitários estornados')
        self.assertEqual(reverse_moderated_story_credits(
            report.pk, actor_id=self.admin.pk), ([], 'nothing_to_reverse'))
        self.assertEqual(SocialCreditEntry.objects.filter(kind='compensation').count(), 2)

    def test_insufficient_balance_opens_one_review_without_partial_debit(self):
        settle_reader_milestones(self.policy.pk, self.story.pk)
        report = self.hide()
        post_social_credit(self.author.pk, operation_ref='test:spent',
                           kind='test_spend', delta=-8)
        for _ in range(2):
            entries, state = reverse_moderated_story_credits(
                report.pk, actor_id=self.admin.pk)
            self.assertEqual((entries, state), ([], 'review_required'))
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 4)
        self.assertFalse(SocialCreditEntry.objects.filter(kind='compensation').exists())
        report.refresh_from_db()
        self.assertEqual(sum(item['acao'] == 'credit_reversal_review'
                             for item in report.historico_decisoes), 1)
        self.client.force_login(self.moderator)
        self.assertContains(self.client.get(reverse('cronica_denuncias')),
                            'Estorno dos créditos pendente de análise administrativa')

    def test_restored_story_and_non_superuser_cannot_reverse(self):
        report = self.hide()
        with self.assertRaises(PermissionError):
            reverse_moderated_story_credits(report.pk, actor_id=self.moderator.pk)
        self.client.force_login(self.moderator)
        self.client.post(reverse('cronica_moderar_denuncia', args=[report.pk]),
                         {'action': 'restaurar'})
        with self.assertRaisesMessage(ValueError, 'hidden-story report'):
            reverse_moderated_story_credits(report.pk, actor_id=self.admin.pk)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 7)

    def test_failed_second_compensation_rolls_back_first_and_audit(self):
        settle_reader_milestones(self.policy.pk, self.story.pk)
        report = self.hide()
        from home.social_credits import reverse_social_credit
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('ledger unavailable')
            return reverse_social_credit(*args, **kwargs)

        with patch('home.social_credits.reverse_social_credit', side_effect=fail_second):
            with self.assertRaisesMessage(RuntimeError, 'ledger unavailable'):
                reverse_moderated_story_credits(report.pk, actor_id=self.admin.pk)
        report.refresh_from_db()
        self.assertFalse(any(item['acao'] == 'credit_reversal'
                             for item in report.historico_decisoes))
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 12)
        self.assertFalse(SocialCreditEntry.objects.filter(kind='compensation').exists())
