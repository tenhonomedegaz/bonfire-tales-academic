"""Chronicle publication awards are disabled until an explicit policy is activated."""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from home.models import SocialCreditEntry, SocialCreditPolicy, SocialCreditWallet, TbCronica
from home.social_credits import award_first_chronicle_publication
from home.views import _cronica_author_snapshot, _cronica_pending_snapshot


class FirstPublicationAwardTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.author = users.objects.create_user('award-author', password='test')
        self.reviewer = users.objects.create_user('award-reviewer', password='test', is_staff=True)
        self.reviewer.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbcronica',
        ))
        self.story = TbCronica.objects.create(
            titulo='Primeira história', slug='primeira-historia',
            conteudo_markdown='Texto aprovado', autor=self.author, status='pendente',
        )
        self.client.force_login(self.reviewer)

    def approve(self):
        return self.client.post(
            reverse('cronica_review_action', args=[self.story.pk]),
            json.dumps({'action': 'aprovar',
                        'expected_snapshot': _cronica_pending_snapshot(self.story)}),
            content_type='application/json',
        )

    def test_no_rule_means_no_credit_on_publication(self):
        self.assertEqual(self.approve().status_code, 200)
        self.assertFalse(SocialCreditWallet.objects.filter(user=self.author).exists())
        self.assertFalse(SocialCreditEntry.objects.exists())

    def test_explicit_active_rule_awards_once_and_records_version(self):
        policy = SocialCreditPolicy.objects.create(
            version='test-v1', first_publication_amount=7, active=True,
        )
        self.assertEqual(self.approve().status_code, 200)
        self.story.refresh_from_db()
        entry = SocialCreditEntry.objects.get(operation_ref=f'chronicle:{self.story.pk}:first_publication')
        self.assertEqual(entry.wallet.user_id, self.author.pk)
        self.assertEqual(entry.policy_id, policy.pk)
        self.assertEqual(entry.delta, 7)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 7)
        self.assertEqual(self.approve().status_code, 409)
        self.assertEqual(award_first_chronicle_publication(self.story).pk, entry.pk)
        self.assertEqual(SocialCreditEntry.objects.count(), 1)

    def test_inactive_rule_does_not_activate_accidentally(self):
        SocialCreditPolicy.objects.create(version='unapproved', first_publication_amount=7)
        self.assertEqual(self.approve().status_code, 200)
        self.assertFalse(SocialCreditEntry.objects.exists())

    def test_approved_revision_does_not_renew_first_publication_credit(self):
        SocialCreditPolicy.objects.create(version='test-v1', first_publication_amount=7, active=True)
        self.assertEqual(self.approve().status_code, 200)
        self.story.refresh_from_db()
        self.client.force_login(self.author)
        edited = self.client.post(reverse('cronica_edit', args=[self.story.slug]), json.dumps({
            'titulo': 'Primeira história revisada', 'conteudo_markdown': 'Texto revisado',
            'resumo': 'Resumo revisado', 'territorio': [], 'regiao': [],
            'expected_edit': _cronica_author_snapshot(self.story),
        }), content_type='application/json')
        self.assertEqual(edited.status_code, 200)
        self.story.refresh_from_db()
        self.client.force_login(self.reviewer)
        reviewed = self.client.post(reverse('cronica_review_action', args=[self.story.pk]),
                                    json.dumps({'action': 'aprovar', 'expected_revision':
                                                self.story.revisao_edicao['submetida_em']}),
                                    content_type='application/json')
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(SocialCreditEntry.objects.count(), 1)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.author).balance, 7)

    def test_failed_ledger_posting_rolls_back_publication(self):
        SocialCreditPolicy.objects.create(version='test-v1', first_publication_amount=7, active=True)
        with patch('home.social_credits.post_social_credit', side_effect=RuntimeError('ledger unavailable')):
            with self.assertRaisesMessage(RuntimeError, 'ledger unavailable'):
                self.approve()
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'pendente')
        self.assertIsNone(self.story.data_publicacao)
        self.assertFalse(SocialCreditEntry.objects.exists())
