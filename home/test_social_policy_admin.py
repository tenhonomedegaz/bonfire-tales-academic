"""Only a deliberate superuser action may activate a complete social policy."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.models import SocialCreditEntry, SocialCreditPolicy
from home.social_credits import post_social_credit


class SocialPolicyAdminTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_superuser('policy-admin', 'admin@example.test', 'test')
        self.staff = users.objects.create_user('policy-staff', password='test', is_staff=True)
        self.author = users.objects.create_user('policy-author', password='test')
        self.list_url = reverse('admin:home_socialcreditpolicy_changelist')
        self.add_url = reverse('admin:home_socialcreditpolicy_add')
        self.client.force_login(self.admin)

    def action(self, policy, name, confirmation=None):
        payload = {'action': name, '_selected_action': str(policy.pk),
                   'select_across': '0', 'index': '0'}
        if confirmation is not None:
            payload['confirm_version'] = confirmation
        return self.client.post(self.list_url, payload)

    def test_superuser_can_author_draft_but_cannot_activate_with_form_field(self):
        self.assertContains(self.client.get(self.add_url), 'Reconhecimento por leitores')
        self.assertContains(self.client.get(self.add_url), 'Resgate de aventura e recompensa')
        response = self.client.post(self.add_url, {
            'version': 'draft-from-admin', 'first_publication_amount': '7',
            'active': 'on', '_save': 'Salvar',
        })
        self.assertEqual(response.status_code, 302)
        policy = SocialCreditPolicy.objects.get(version='draft-from-admin')
        self.assertFalse(policy.active)
        self.assertEqual(self.client.post(reverse(
            'admin:home_socialcreditpolicy_change', args=[policy.pk]), {
                'version': policy.version, 'first_publication_amount': '8',
                'active': 'on', '_save': 'Salvar',
            }).status_code, 302)
        policy.refresh_from_db()
        self.assertEqual(policy.first_publication_amount, 8)
        self.assertFalse(policy.active)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.add_url).status_code, 302)
        self.assertEqual(self.client.post(self.add_url, {
            'version': 'staff-attempt', 'first_publication_amount': '99', '_save': 'Salvar',
        }).status_code, 302)
        self.assertFalse(SocialCreditPolicy.objects.filter(version='staff-attempt').exists())
        self.assertEqual(self.action(policy, 'activate_version', policy.version).status_code, 302)
        policy.refresh_from_db()
        self.assertFalse(policy.active)

    def test_confirmation_and_complete_policy_are_required(self):
        policy = SocialCreditPolicy.objects.create(
            version='incomplete-draft', first_publication_amount=7,
            reader_recognition_enabled=True,
        )
        self.assertEqual(self.action(policy, 'activate_version').status_code, 200)
        self.assertContains(self.action(policy, 'activate_version', 'wrong'),
                            'Digite exatamente a versão')
        self.assertEqual(self.action(policy, 'activate_version', policy.version).status_code, 302)
        policy.refresh_from_db()
        self.assertFalse(policy.active)
        self.assertEqual(SocialCreditEntry.objects.count(), 0)

    def test_incomplete_redemption_cannot_be_activated(self):
        policy = SocialCreditPolicy.objects.create(
            version='missing-redemption-values', first_publication_amount=7,
            redemption_enabled=True, redemption_cost=5,
        )
        self.assertEqual(self.action(policy, 'activate_version', policy.version).status_code, 302)
        policy.refresh_from_db()
        self.assertFalse(policy.active)

    def test_version_switch_and_used_policy_immutability(self):
        first = SocialCreditPolicy.objects.create(
            version='complete-v1', first_publication_amount=7,
            reader_recognition_enabled=True, reader_milestone_size=2,
            reader_milestone_amount=5, reader_consolidation_hours=24,
            reader_story_credit_cap=10, reader_author_period_credit_cap=10,
            reader_period_days=30, redemption_enabled=True, redemption_cost=5,
            redemption_gold_pc=200, redemption_gold_source='Tabela de teste',
            redemption_counts_for_progression=False, redemption_period_days=30,
            redemption_period_limit=2, redemption_character_limit=1,
        )
        second = SocialCreditPolicy.objects.create(
            version='complete-v2', first_publication_amount=9,
        )
        self.assertEqual(self.action(first, 'activate_version', first.version).status_code, 302)
        first.refresh_from_db()
        self.assertTrue(first.active)
        self.assertEqual(self.client.get(reverse(
            'admin:home_socialcreditpolicy_change', args=[first.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse(
            'admin:home_socialcreditpolicy_change', args=[first.pk]),
            {'version': first.version, 'first_publication_amount': '999', '_save': 'Salvar'}
        ).status_code, 403)
        self.assertEqual(self.action(second, 'activate_version', second.version).status_code, 302)
        second.refresh_from_db()
        self.assertFalse(second.active)

        post_social_credit(self.author.pk, operation_ref='test:published',
                           kind='first_publication', delta=7, policy=first)
        self.assertEqual(self.action(first, 'deactivate_version', first.version).status_code, 302)
        first.refresh_from_db()
        self.assertFalse(first.active)
        self.assertEqual(self.client.post(reverse(
            'admin:home_socialcreditpolicy_change', args=[first.pk]),
            {'version': first.version, 'first_publication_amount': '999', '_save': 'Salvar'}
        ).status_code, 403)
        self.assertEqual(self.action(second, 'activate_version', second.version).status_code, 302)
        second.refresh_from_db()
        self.assertTrue(second.active)
        self.assertEqual(SocialCreditEntry.objects.get(operation_ref='test:published').delta, 7)
