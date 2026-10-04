from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from home.models import SocialCreditEntry, SocialCreditWallet
from home.social_credits import post_social_credit, reverse_social_credit


class SocialCreditLedgerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('credit-author', password='test')

    def test_posting_is_idempotent_and_balance_is_integer(self):
        entry, created = post_social_credit(self.user.pk, operation_ref='story:42:first',
                                            kind='first_publication', delta=7)
        self.assertTrue(created)
        again, created = post_social_credit(self.user.pk, operation_ref='story:42:first',
                                            kind='first_publication', delta=7)
        self.assertFalse(created)
        self.assertEqual(again.pk, entry.pk)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.user).balance, 7)
        self.assertEqual(SocialCreditEntry.objects.count(), 1)
        with self.assertRaisesMessage(ValueError, 'different posting'):
            post_social_credit(self.user.pk, operation_ref='story:42:first',
                               kind='first_publication', delta=8)

    def test_debit_and_failed_debit_do_not_overdraw_or_write_partial_history(self):
        post_social_credit(self.user.pk, operation_ref='grant:1', kind='manual_test', delta=5)
        with self.assertRaisesMessage(ValueError, 'insufficient'):
            post_social_credit(self.user.pk, operation_ref='spend:too-much',
                               kind='redemption', delta=-6)
        self.assertFalse(SocialCreditEntry.objects.filter(operation_ref='spend:too-much').exists())
        entry, _ = post_social_credit(self.user.pk, operation_ref='spend:valid',
                                      kind='redemption', delta=-3)
        self.assertEqual(entry.balance_after, 2)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.user).balance, 2)

    def test_compensation_is_a_single_visible_entry(self):
        original, _ = post_social_credit(self.user.pk, operation_ref='grant:1',
                                         kind='manual_test', delta=5)
        reversal, created = reverse_social_credit(original.pk, operation_ref='reverse:grant:1')
        self.assertTrue(created)
        again, created = reverse_social_credit(original.pk, operation_ref='reverse:grant:1')
        self.assertFalse(created)
        self.assertEqual(again.pk, reversal.pk)
        self.assertEqual(reversal.delta, -5)
        self.assertEqual(reversal.reversal_of_id, original.pk)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.user).balance, 0)
        self.assertEqual(SocialCreditEntry.objects.count(), 2)

    def test_compensation_does_not_remove_spent_credits(self):
        original, _ = post_social_credit(self.user.pk, operation_ref='grant:1',
                                         kind='manual_test', delta=5)
        post_social_credit(self.user.pk, operation_ref='spend:1', kind='redemption', delta=-3)
        with self.assertRaisesMessage(ValueError, 'insufficient'):
            reverse_social_credit(original.pk, operation_ref='reverse:grant:1')
        self.assertFalse(SocialCreditEntry.objects.filter(operation_ref='reverse:grant:1').exists())
        self.assertEqual(SocialCreditWallet.objects.get(user=self.user).balance, 2)

    def test_invalid_amounts_rejected(self):
        for invalid in (0, True, 1.5, '2'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                post_social_credit(self.user.pk, operation_ref='invalid',
                                   kind='manual_test', delta=invalid)
        self.assertFalse(SocialCreditWallet.objects.filter(user=self.user).exists())

    def test_admin_can_audit_but_cannot_edit_ledger(self):
        entry, _ = post_social_credit(self.user.pk, operation_ref='grant:audited',
                                      kind='manual_test', delta=5)
        wallet_url = reverse('admin:home_socialcreditwallet_changelist')
        entry_url = reverse('admin:home_socialcreditentry_change', args=[entry.pk])
        self.client.force_login(self.user)
        self.assertNotEqual(self.client.get(wallet_url).status_code, 200)
        auditor = get_user_model().objects.create_superuser('credit-auditor',
                                                             'auditor@example.test', 'test')
        self.client.force_login(auditor)
        self.assertContains(self.client.get(wallet_url), 'credit-author')
        self.assertContains(self.client.get(entry_url), 'grant:audited')
        self.assertNotEqual(self.client.post(entry_url, {'delta': 900}).status_code, 200)
        self.assertEqual(SocialCreditEntry.objects.get(pk=entry.pk).delta, 5)


class SocialCreditConcurrencyTests(TransactionTestCase):
    def test_simultaneous_replay_posts_once(self):
        user = get_user_model().objects.create_user('concurrent-credit-author', password='test')
        barrier = Barrier(2)

        def post():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                entry, created = post_social_credit(
                    user.pk, operation_ref='story:concurrent:first',
                    kind='first_publication', delta=4,
                )
                return entry.pk, created
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: post(), range(2)))
        self.assertEqual(len({pk for pk, _ in results}), 1)
        self.assertEqual(sorted(created for _, created in results), [False, True])
        self.assertEqual(SocialCreditWallet.objects.get(user=user).balance, 4)
        self.assertEqual(SocialCreditEntry.objects.count(), 1)
