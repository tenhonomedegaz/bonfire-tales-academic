"""Historical credits require a separate, read-only campaign simulation."""

import json
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from home.models import (SocialCreditEntry, SocialCreditPolicy,
                         SocialCreditReaderRecognition, SocialCreditWallet,
                         TbCronica, TbCronicaCurtida)
from home.social_credit_history import preview_historical_credit_campaign
from home.social_credits import post_social_credit


class HistoricalCampaignPreviewTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.author = users.objects.create_user('historical-author')
        self.readers = [users.objects.create_user(f'historical-reader-{i}') for i in range(3)]
        self.policy = SocialCreditPolicy.objects.create(
            version='historical-hypothetical', first_publication_amount=7,
            reader_recognition_enabled=True, reader_milestone_size=2,
            reader_milestone_amount=5, reader_consolidation_hours=24,
            reader_story_credit_cap=10, reader_author_period_credit_cap=5,
            reader_period_days=30, active=False,
        )
        now = timezone.now()
        self.start = (now - timedelta(days=5)).date()
        self.end = (now - timedelta(days=2)).date()
        self.stories = [TbCronica.objects.create(
            titulo=f'Relato antigo {i}', slug=f'relato-antigo-{i}',
            conteudo_markdown='Texto', autor=self.author,
            status='aprovada', data_publicacao=now - timedelta(days=4 - i),
        ) for i in range(2)]

    def old_like(self, story, reader, *, current=True, like_after_cutoff=False):
        recognition = SocialCreditReaderRecognition.objects.create(
            cronica=story, reader=reader, policy=None,
        )
        SocialCreditReaderRecognition.objects.filter(pk=recognition.pk).update(
            first_seen_at=timezone.now() - timedelta(days=3))
        if current:
            like = TbCronicaCurtida.objects.create(cronica=story, leitor=reader)
            days = 1 if like_after_cutoff else 3
            TbCronicaCurtida.objects.filter(pk=like.pk).update(
                criado_em=timezone.now() - timedelta(days=days))

    def preview(self):
        return preview_historical_credit_campaign(
            self.policy, published_from=self.start, published_through=self.end,
            reactions_through=self.end,
        )

    def test_inactive_policy_simulates_bounded_history_without_posting(self):
        for story in self.stories:
            for reader in self.readers[:2]:
                self.old_like(story, reader)
        self.old_like(self.stories[0], self.author)
        self.old_like(self.stories[0], self.readers[2], like_after_cutoff=True)
        rows = self.preview()
        self.assertEqual([row['historical_readers'] for row in rows], [2, 2])
        self.assertEqual([row['first_publication_credits'] for row in rows], [7, 7])
        self.assertEqual([row['reader_credits'] for row in rows], [5, 0])
        self.assertEqual(sum(row['total_credits'] for row in rows), 19)
        out = StringIO()
        call_command('preview_social_historical_campaign',
                     policy=self.policy.version,
                     published_from=self.start.isoformat(),
                     published_through=self.end.isoformat(),
                     reactions_through=self.end.isoformat(), stdout=out)
        self.assertEqual(json.loads(out.getvalue())['mode'], 'preview_only')
        self.assertEqual(json.loads(out.getvalue())['total_credits'], 19)
        self.assertFalse(SocialCreditEntry.objects.exists())
        self.assertFalse(SocialCreditWallet.objects.exists())
        self.assertEqual(SocialCreditReaderRecognition.objects.filter(policy__isnull=True).count(), 6)

    def test_reactions_can_extend_beyond_publication_window(self):
        for reader in self.readers[:2]:
            self.old_like(self.stories[0], reader, like_after_cutoff=True)
        rows = preview_historical_credit_campaign(
            self.policy, published_from=self.start, published_through=self.end,
            reactions_through=timezone.now().date(),
        )
        self.assertEqual(rows[0]['historical_readers'], 2)
        self.assertEqual(rows[0]['reader_credits'], 5)

    def test_existing_awards_and_removed_likes_do_not_reappear(self):
        first, second = self.stories
        for reader in self.readers[:2]:
            self.old_like(first, reader)
            self.old_like(second, reader)
        TbCronicaCurtida.objects.filter(cronica=first, leitor=self.readers[1]).delete()
        post_social_credit(self.author.pk,
                           operation_ref=f'chronicle:{second.pk}:first_publication',
                           kind='first_publication', delta=7, policy=self.policy)
        post_social_credit(self.author.pk,
                           operation_ref=f'chronicle:{second.pk}:reader_milestone:previous',
                           kind='reader_milestone', delta=5, policy=self.policy)
        rows = self.preview()
        self.assertEqual([row['historical_readers'] for row in rows], [1, 2])
        self.assertEqual(rows[0]['reader_credits'], 0)
        self.assertEqual(rows[1]['first_publication_credits'], 0)
        self.assertTrue(rows[1]['reader_award_already_exists'])
        self.assertEqual(rows[1]['reader_credits'], 0)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 12)
        self.assertEqual(SocialCreditEntry.objects.count(), 2)

    def test_invalid_dates_and_incomplete_policy_fail_closed(self):
        with self.assertRaisesMessage(ValueError, 'invalid historical'):
            preview_historical_credit_campaign(
                self.policy, published_from=self.end, published_through=self.start,
                reactions_through=self.end)
        with self.assertRaises(CommandError):
            call_command('preview_social_historical_campaign',
                         policy=self.policy.version, published_from='bad',
                         published_through=self.end.isoformat(),
                         reactions_through=self.end.isoformat(), stdout=StringIO())
        self.policy.reader_milestone_size = None
        self.policy.save(update_fields=['reader_milestone_size'])
        with self.assertRaisesMessage(ValueError, 'incomplete'):
            self.preview()
        self.assertFalse(SocialCreditEntry.objects.exists())
