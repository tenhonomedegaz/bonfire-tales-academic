"""Preview of reader milestones is read-only and respects consolidation and caps."""

import json
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.models import (SocialCreditEntry, SocialCreditPolicy,
                         SocialCreditReaderRecognition, SocialCreditWallet,
                         TbCronica)
from home.social_credits import post_social_credit, preview_reader_milestones


class ReaderMilestonePreviewTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.author = users.objects.create_user('preview-author')
        self.readers = [users.objects.create_user(f'preview-reader-{i}') for i in range(4)]
        self.policy = SocialCreditPolicy.objects.create(
            version='hypothetical-v1', first_publication_amount=1,
            reader_recognition_enabled=True, active=True,
            reader_milestone_size=2, reader_milestone_amount=5,
            reader_consolidation_hours=24, reader_story_credit_cap=5,
            reader_author_period_credit_cap=5, reader_period_days=30,
        )
        self.story = TbCronica.objects.create(
            titulo='Relato para marco', slug='relato-para-marco',
            conteudo_markdown='Texto', autor=self.author, status='aprovada',
            data_publicacao=timezone.now(),
        )

    def like(self, reader, story=None):
        self.client.force_login(reader)
        response = self.client.post(reverse('cronica_curtir', args=[(story or self.story).pk]),
                                    json.dumps({'curtido': True}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def consolidate(self):
        SocialCreditReaderRecognition.objects.update(
            first_seen_at=timezone.now() - timedelta(days=2),
        )

    def test_window_threshold_and_read_only_command(self):
        self.like(self.readers[0])
        self.like(self.readers[1])
        self.assertEqual(preview_reader_milestones(self.policy), [])
        self.consolidate()
        expected = [{
            'chronicle_id': self.story.pk, 'author_id': self.author.pk,
            'consolidated_readers': 2, 'milestones_due': 1,
            'milestones_ready': 1, 'credits_ready': 5,
        }]
        self.assertEqual(preview_reader_milestones(self.policy), expected)
        output = StringIO()
        call_command('preview_social_reader_awards', policy=self.policy.version, stdout=output)
        self.assertEqual(json.loads(output.getvalue())['rows'], expected)
        self.assertEqual(json.loads(output.getvalue())['mode'], 'preview_only')
        self.assertFalse(SocialCreditEntry.objects.exists())
        self.assertFalse(SocialCreditWallet.objects.exists())

    def test_current_like_and_active_accounts_are_required(self):
        for reader in self.readers[:3]:
            self.like(reader)
        self.consolidate()
        self.client.force_login(self.readers[0])
        self.client.post(reverse('cronica_curtir', args=[self.story.pk]),
                         json.dumps({'curtido': False}), content_type='application/json')
        self.readers[1].is_active = False
        self.readers[1].save(update_fields=['is_active'])
        self.assertEqual(preview_reader_milestones(self.policy)[0]['consolidated_readers'], 1)
        self.assertEqual(preview_reader_milestones(self.policy)[0]['credits_ready'], 0)
        self.story.status = 'oculta'
        self.story.save(update_fields=['status'])
        self.assertEqual(preview_reader_milestones(self.policy), [])

    def test_story_and_author_period_caps_limit_preview(self):
        second = TbCronica.objects.create(
            titulo='Outro relato', slug='outro-relato', conteudo_markdown='Texto',
            autor=self.author, status='aprovada', data_publicacao=timezone.now(),
        )
        for reader in self.readers:
            self.like(reader)
            self.like(reader, second)
        self.consolidate()
        rows = preview_reader_milestones(self.policy)
        self.assertEqual([(row['milestones_due'], row['milestones_ready']) for row in rows],
                         [(2, 1), (2, 0)])
        self.assertFalse(SocialCreditEntry.objects.exists())

    def test_historical_award_consumes_live_reader_caps_without_counting_as_live_milestone(self):
        for reader in self.readers[:2]:
            self.like(reader)
        self.consolidate()
        post_social_credit(
            self.author.pk,
            operation_ref=f'chronicle:{self.story.pk}:historical_reader_milestone:old:1',
            kind='historical_reader_milestone', delta=5, policy=self.policy,
        )
        row = preview_reader_milestones(self.policy)[0]
        self.assertEqual(row['milestones_due'], 1)
        self.assertEqual(row['milestones_ready'], 0)

    def test_paid_milestone_and_rolling_period_are_accounted_for(self):
        for reader in self.readers[:2]:
            self.like(reader)
        self.consolidate()
        entry, _ = post_social_credit(
            self.author.pk,
            operation_ref=f'chronicle:{self.story.pk}:reader_milestone:1',
            kind='reader_milestone', delta=5, policy=self.policy,
        )
        self.assertEqual(preview_reader_milestones(self.policy)[0]['milestones_ready'], 0)
        self.assertEqual(preview_reader_milestones(self.policy)[0]['milestones_due'], 0)
        SocialCreditEntry.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=31),
        )
        self.assertEqual(preview_reader_milestones(self.policy)[0]['milestones_ready'], 0)

    def test_recent_author_award_blocks_other_story_until_period_expires(self):
        second = TbCronica.objects.create(
            titulo='Relato posterior', slug='relato-posterior', conteudo_markdown='Texto',
            autor=self.author, status='aprovada', data_publicacao=timezone.now(),
        )
        for reader in self.readers[:2]:
            self.like(reader, second)
        self.consolidate()
        entry, _ = post_social_credit(
            self.author.pk,
            operation_ref=f'chronicle:{self.story.pk}:reader_milestone:1',
            kind='reader_milestone', delta=5, policy=self.policy,
        )
        self.assertEqual(preview_reader_milestones(self.policy)[0]['credits_ready'], 0)
        SocialCreditEntry.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=31),
        )
        self.assertEqual(preview_reader_milestones(self.policy)[0]['credits_ready'], 5)

    def test_incomplete_or_disabled_policy_fails_closed(self):
        self.policy.reader_milestone_amount = None
        self.policy.save(update_fields=['reader_milestone_amount'])
        with self.assertRaisesMessage(ValueError, 'incomplete'):
            preview_reader_milestones(self.policy)
        with self.assertRaises(CommandError):
            call_command('preview_social_reader_awards', policy=self.policy.version,
                         stdout=StringIO())
        self.assertFalse(SocialCreditEntry.objects.exists())
