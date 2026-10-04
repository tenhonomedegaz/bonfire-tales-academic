from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.models import SocialCreditEntry, SocialCreditPolicy, SocialCreditWallet, TbPersonagem
from home.social_credits import redemption_quotes


class RedemptionQuoteTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user('quote-owner', password='test')
        self.other = users.objects.create_user('quote-other', password='test')
        self.character = TbPersonagem.objects.create(dono=self.owner, nome='Aventureira')
        TbPersonagem.objects.create(dono=self.owner, nome='Arquivada', arquivado=True)
        TbPersonagem.objects.create(dono=self.other, nome='Outro')
        self.policy = SocialCreditPolicy.objects.create(
            version='quote-test', first_publication_amount=2, active=True,
            redemption_enabled=True,
        )

    def configure_offer(self):
        self.policy.redemption_cost = 5
        self.policy.redemption_gold_pc = 120
        self.policy.redemption_counts_for_progression = False
        self.policy.redemption_period_days = 30
        self.policy.redemption_period_limit = 1
        self.policy.redemption_character_limit = 2
        self.policy.save()

    def test_incomplete_policy_does_not_offer_or_write(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['social_redemption_quotes'], [])
        self.assertNotContains(response, 'Prévia do resgate')
        self.assertFalse(SocialCreditWallet.objects.exists())
        self.assertFalse(SocialCreditEntry.objects.exists())

    def test_private_quote_exposes_exact_terms_without_debit_or_delivery(self):
        self.configure_offer()
        SocialCreditWallet.objects.create(user=self.owner, balance=6)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        quote, = response.context['social_redemption_quotes']
        self.assertEqual(quote['character'], self.character)
        self.assertEqual((quote['cost'], quote['gold_pc'], quote['progression']),
                         (5, 120, False))
        self.assertTrue(quote['affordable'])
        self.assertContains(response, 'Aventureira')
        self.assertContains(response, '120 PC por 5 créditos')
        self.assertEqual([row['character'].pk for row in response.context['social_redemption_quotes']],
                         [self.character.pk])
        self.assertNotContains(self.client.get(reverse('public_profile', args=[self.owner.username])),
                               'Prévia do resgate')
        self.character.refresh_from_db()
        self.assertEqual((self.character.aventuras, self.character.carteira_pc), (0, 0))
        self.assertEqual(SocialCreditWallet.objects.get(user=self.owner).balance, 6)
        self.assertFalse(SocialCreditEntry.objects.exists())
        self.assertFalse(self.character.aventuras_ledger.exists())

    def test_inactive_or_invalid_policy_is_not_offered(self):
        self.configure_offer()
        self.policy.redemption_period_limit = 0
        self.policy.save(update_fields=['redemption_period_limit'])
        self.assertEqual(redemption_quotes(self.owner), [])
        self.policy.redemption_period_limit = 1
        self.policy.redemption_gold_pc = 0
        self.policy.save(update_fields=['redemption_period_limit', 'redemption_gold_pc'])
        self.assertEqual(redemption_quotes(self.owner), [])
        self.policy.redemption_gold_pc = 120
        self.policy.active = False
        self.policy.save(update_fields=['redemption_gold_pc', 'active'])
        self.assertEqual(redemption_quotes(self.owner), [])
