"""Reader recognition is durable and never pays under an unapproved rule."""

import importlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.deploy_sync import MEMORY_MODELS
from home.models import (SocialCreditEntry, SocialCreditPolicy,
                         SocialCreditReaderRecognition, SocialCreditWallet,
                         TbCronica, TbCronicaCurtida)


class ReaderRecognitionTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.author = users.objects.create_user('recognition-author')
        self.reader = users.objects.create_user('recognition-reader')
        self.other = users.objects.create_user('recognition-other')
        self.story = TbCronica.objects.create(
            titulo='Relato reconhecido', slug='relato-reconhecido',
            conteudo_markdown='Texto aprovado', autor=self.author, status='aprovada',
            data_publicacao=timezone.now(),
        )

    def react(self, reader, value):
        self.client.force_login(reader)
        return self.client.post(reverse('cronica_curtir', args=[self.story.pk]),
                                json.dumps({'curtido': value}),
                                content_type='application/json')

    def test_first_like_is_retained_across_replay_unlike_and_relike(self):
        self.assertEqual(self.react(self.reader, True).status_code, 200)
        first = SocialCreditReaderRecognition.objects.get(cronica=self.story, reader=self.reader)
        self.assertIsNone(first.policy_id)
        self.assertEqual(self.react(self.reader, True).status_code, 200)
        self.assertEqual(self.react(self.reader, False).status_code, 200)
        self.assertFalse(TbCronicaCurtida.objects.exists())
        SocialCreditPolicy.objects.create(
            version='test-reader-rule', first_publication_amount=1,
            reader_recognition_enabled=True, active=True,
        )
        self.assertEqual(self.react(self.reader, True).status_code, 200)
        first.refresh_from_db()
        self.assertIsNone(first.policy_id)
        self.assertEqual(SocialCreditReaderRecognition.objects.count(), 1)
        self.assertFalse(SocialCreditWallet.objects.exists())
        self.assertFalse(SocialCreditEntry.objects.exists())

    def test_new_distinct_reader_records_active_policy_without_issuing_credit(self):
        policy = SocialCreditPolicy.objects.create(
            version='test-reader-rule', first_publication_amount=1,
            reader_recognition_enabled=True, active=True,
            reader_milestone_size=2, reader_milestone_amount=1,
            reader_consolidation_hours=24, reader_story_credit_cap=5,
            reader_author_period_credit_cap=5, reader_period_days=30,
        )
        self.assertEqual(self.react(self.reader, True).status_code, 200)
        self.assertEqual(self.react(self.other, True).status_code, 200)
        self.assertEqual(set(SocialCreditReaderRecognition.objects.filter(
            cronica=self.story).values_list('reader_id', flat=True)),
            {self.reader.pk, self.other.pk})
        self.assertEqual(set(SocialCreditReaderRecognition.objects.values_list(
            'policy_id', flat=True)), {policy.pk})
        self.assertFalse(SocialCreditEntry.objects.exists())
        self.assertFalse(SocialCreditWallet.objects.exists())

    def test_incomplete_active_reader_rule_does_not_qualify_first_like(self):
        SocialCreditPolicy.objects.create(
            version='incomplete', first_publication_amount=1,
            reader_recognition_enabled=True, active=True,
        )
        self.assertEqual(self.react(self.reader, True).status_code, 200)
        self.assertIsNone(SocialCreditReaderRecognition.objects.get().policy_id)
        self.assertFalse(SocialCreditEntry.objects.exists())

    def test_disabled_reader_rule_records_evidence_without_qualifying_it(self):
        SocialCreditPolicy.objects.create(
            version='authorship-only', first_publication_amount=1, active=True,
        )
        self.assertEqual(self.react(self.reader, True).status_code, 200)
        self.assertIsNone(SocialCreditReaderRecognition.objects.get().policy_id)
        self.assertFalse(SocialCreditEntry.objects.exists())

    def test_existing_likes_are_backfilled_as_nonpayable_at_original_time(self):
        like = TbCronicaCurtida.objects.create(cronica=self.story, leitor=self.reader)
        migration = importlib.import_module('home.migrations.0134_social_credit_reader_recognition')
        migration.preserve_existing_reactions(apps, SimpleNamespace(connection=connection))
        migration.preserve_existing_reactions(apps, SimpleNamespace(connection=connection))
        recognition = SocialCreditReaderRecognition.objects.get(
            cronica=self.story, reader=self.reader)
        self.assertIsNone(recognition.policy_id)
        self.assertEqual(recognition.first_seen_at, like.criado_em)
        self.assertEqual(SocialCreditReaderRecognition.objects.count(), 1)

    def test_recognition_storage_failure_rolls_back_the_like(self):
        with patch('home.social_credits.record_reader_recognition',
                   side_effect=RuntimeError('recognition unavailable')):
            with self.assertRaisesMessage(RuntimeError, 'recognition unavailable'):
                self.react(self.reader, True)
        self.assertFalse(TbCronicaCurtida.objects.exists())
        self.assertFalse(SocialCreditReaderRecognition.objects.exists())

    def test_recognitions_and_ledger_are_protected_as_production_memory(self):
        for name in ('SocialCreditReaderRecognition', 'SocialCreditWallet',
                     'SocialCreditEntry', 'SocialCreditPolicy'):
            self.assertIn(name, MEMORY_MODELS)
