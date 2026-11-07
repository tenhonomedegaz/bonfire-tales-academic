"""Reader awards post only under an explicit active rule and remain replay-safe."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from home.models import (SocialCreditEntry, SocialCreditPolicy,
                         SocialCreditReaderRecognition, SocialCreditWallet,
                         TbCronica)
from home.social_credits import settle_reader_milestones


class ReaderSettlementTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.author = users.objects.create_user('settlement-author')
        self.readers = [users.objects.create_user(f'settlement-reader-{i}') for i in range(4)]
        self.policy = SocialCreditPolicy.objects.create(
            version='settlement-test', first_publication_amount=1,
            reader_recognition_enabled=True, active=True,
            reader_milestone_size=2, reader_milestone_amount=5,
            reader_consolidation_hours=24, reader_story_credit_cap=10,
            reader_author_period_credit_cap=5, reader_period_days=30,
        )
        self.story = TbCronica.objects.create(
            titulo='Relato remuneravel', slug='relato-remuneravel',
            conteudo_markdown='Texto aprovado', autor=self.author,
            status='aprovada', data_publicacao=timezone.now(),
        )

    def add_likes(self, story, readers):
        for reader in readers:
            self.client.force_login(reader)
            response = self.client.post(
                reverse('cronica_curtir', args=[story.pk]),
                json.dumps({'curtido': True}), content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
        SocialCreditReaderRecognition.objects.filter(cronica=story).update(
            first_seen_at=timezone.now() - timedelta(days=2),
        )

    def test_post_once_and_show_private_history(self):
        self.add_likes(self.story, self.readers[:2])
        entries = settle_reader_milestones(self.policy.pk, self.story.pk)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].delta, 5)
        self.assertEqual(entries[0].kind, 'reader_milestone')
        self.assertEqual(entries[0].policy_id, self.policy.pk)
        self.assertEqual(settle_reader_milestones(self.policy.pk, self.story.pk), [])
        self.assertEqual(SocialCreditEntry.objects.count(), 1)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 5)
        self.client.force_login(self.author)
        profile = self.client.get(reverse('profile'))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.context['social_credit_balance'], 5)
        self.assertContains(profile, entries[0].operation_ref)

    def test_inactive_policy_and_unconfirmed_command_never_post(self):
        self.add_likes(self.story, self.readers[:2])
        with self.assertRaises(CommandError):
            call_command('settle_social_reader_awards', policy=self.policy.version,
                         stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command('settle_social_reader_awards', policy=self.policy.version,
                         apply=True, confirm_version='other', stdout=StringIO())
        self.policy.active = False
        self.policy.save(update_fields=['active'])
        with self.assertRaisesMessage(ValueError, 'not active'):
            settle_reader_milestones(self.policy.pk, self.story.pk)
        with self.assertRaises(CommandError):
            call_command('settle_social_reader_awards', policy=self.policy.version,
                         apply=True, confirm_version=self.policy.version,
                         stdout=StringIO())
        self.assertFalse(SocialCreditEntry.objects.exists())

    def test_confirmed_command_respects_author_cap_and_replay(self):
        second = TbCronica.objects.create(
            titulo='Segundo relato', slug='segundo-relato',
            conteudo_markdown='Texto', autor=self.author,
            status='aprovada', data_publicacao=timezone.now(),
        )
        self.add_likes(self.story, self.readers[:2])
        self.add_likes(second, self.readers[:2])
        output = StringIO()
        call_command('settle_social_reader_awards', policy=self.policy.version,
                     apply=True, confirm_version=self.policy.version, stdout=output)
        self.assertIn('1 reader milestone(s) posted; 5 credit(s) granted', output.getvalue())
        self.assertEqual(SocialCreditEntry.objects.count(), 1)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 5)
        output = StringIO()
        call_command('settle_social_reader_awards', policy=self.policy.version,
                     apply=True, confirm_version=self.policy.version, stdout=output)
        self.assertIn('0 reader milestone(s) posted', output.getvalue())

    def test_later_period_allows_next_milestone_without_replaying_first(self):
        self.add_likes(self.story, self.readers)
        first = settle_reader_milestones(self.policy.pk, self.story.pk)
        self.assertEqual(len(first), 1)
        SocialCreditEntry.objects.filter(pk=first[0].pk).update(
            created_at=timezone.now() - timedelta(days=31),
        )
        second = settle_reader_milestones(self.policy.pk, self.story.pk)
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first[0].operation_ref, second[0].operation_ref)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 10)
        self.assertEqual(settle_reader_milestones(self.policy.pk, self.story.pk), [])

    def test_failure_rolls_back_all_due_milestones(self):
        self.add_likes(self.story, self.readers)
        self.policy.reader_author_period_credit_cap = 10
        self.policy.save(update_fields=['reader_author_period_credit_cap'])
        from home.social_credits import post_social_credit
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('ledger unavailable')
            return post_social_credit(*args, **kwargs)

        with patch('home.social_credits.post_social_credit', side_effect=fail_second):
            with self.assertRaisesMessage(RuntimeError, 'ledger unavailable'):
                settle_reader_milestones(self.policy.pk, self.story.pk)
        self.assertFalse(SocialCreditEntry.objects.exists())
        self.assertFalse(SocialCreditWallet.objects.exists())


class ReaderSettlementConcurrencyTests(TransactionTestCase):
    def test_parallel_replay_posts_once(self):
        users = get_user_model()
        author = users.objects.create_user('parallel-author')
        policy = SocialCreditPolicy.objects.create(
            version='parallel-test', first_publication_amount=1,
            reader_recognition_enabled=True, active=True,
            reader_milestone_size=2, reader_milestone_amount=5,
            reader_consolidation_hours=24, reader_story_credit_cap=5,
            reader_author_period_credit_cap=5, reader_period_days=30,
        )
        story = TbCronica.objects.create(
            titulo='Relato paralelo', slug='relato-paralelo',
            conteudo_markdown='Texto', autor=author,
            status='aprovada', data_publicacao=timezone.now(),
        )
        from home.models import TbCronicaCurtida
        for i in range(2):
            reader = users.objects.create_user(f'parallel-reader-{i}')
            TbCronicaCurtida.objects.create(cronica=story, leitor=reader)
            SocialCreditReaderRecognition.objects.create(
                cronica=story, reader=reader, policy=policy,
            )
        SocialCreditReaderRecognition.objects.update(
            first_seen_at=timezone.now() - timedelta(days=2),
        )
        barrier = Barrier(2)

        def settle():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return len(settle_reader_milestones(policy.pk, story.pk))
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: settle(), range(2)))
        self.assertEqual(sorted(results), [0, 1])
        self.assertEqual(SocialCreditEntry.objects.count(), 1)
        self.assertEqual(SocialCreditWallet.objects.get(user=author).balance, 5)
