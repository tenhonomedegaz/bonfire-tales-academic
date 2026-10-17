"""Read-only subscriber view uses verified identity and existing bot records."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import BotTransaction


class SubscriptionManagementTests(TransactionTestCase):
    def test_verified_owner_sees_current_tier_and_unverified_account_cannot(self):
        now = timezone.now()
        with connection.schema_editor() as editor:
            editor.create_model(BotTransaction)
        try:
            owner = get_user_model().objects.create_user(
                'subscription_owner', email='owner@example.test', password='test-pass')
            other = get_user_model().objects.create_user(
                'subscription_other', email='owner@example.test', password='test-pass')
            owner.profile.email_verified = True
            owner.profile.save(update_fields=['email_verified'])
            for number, (tier, expiry) in enumerate((
                    ('conde', now + timedelta(days=15)),
                    ('marques', now + timedelta(days=10)),
                    ('duque', now - timedelta(days=1)))):
                BotTransaction.objects.create(
                    id=f'transaction-{number}', transactionCode=f'code-{number}',
                    paymentDate=now-timedelta(days=number), expirationDate=expiry,
                    subscriptionPlan=f'colaborador-{tier}-1m', subscriptionPeriod='1m',
                    status=1, grossAmount=19.9, netAmount=18.0,
                    email='owner@example.test', createdAt=now, updatedAt=now)
            url = reverse('subscription_management')
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(other)
            private = self.client.get(url)
            self.assertEqual(private.status_code, 200)
            self.assertFalse(private.context['membership']['active'])
            self.assertEqual(private.context['membership']['history'], [])
            self.client.force_login(owner)
            page = self.client.get(url)
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page.context['membership']['tier'], 'marques')
            self.assertEqual(len(page.context['membership']['history']), 3)
            self.assertContains(page, 'Marquês / Marquesa')
            self.assertIn('no-store', page.headers['Cache-Control'])
            self.assertFalse(BotTransaction.objects.filter(claimed=True).exists())
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(BotTransaction)

        unavailable = self.client.get(reverse('subscription_management'))
        self.assertEqual(unavailable.status_code, 200)
        self.assertFalse(unavailable.context['membership']['available'])
        self.assertContains(unavailable, 'Não conseguimos consultar sua assinatura agora')
