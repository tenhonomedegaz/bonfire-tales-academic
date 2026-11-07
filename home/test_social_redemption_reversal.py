from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from home.models import (SocialCreditEntry, SocialCreditPolicy, SocialCreditRedemption,
                         SocialCreditWallet, TbPersonagem, TbPersonagemAventura,
                         TbTransacao)
from home.social_credits import (post_social_credit, redeem_social_credit,
                                 reverse_social_redemption)


class SocialRedemptionReversalTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user('reversal-owner', password='test')
        self.admin = users.objects.create_superuser('reversal-admin', 'admin@example.test', 'test')
        self.character = TbPersonagem.objects.create(dono=self.owner, nome='Heroina')
        self.policy = SocialCreditPolicy.objects.create(
            version='reversal-test-v1', first_publication_amount=1,
            active=True, redemption_enabled=True, redemption_cost=5,
            redemption_gold_pc=200, redemption_gold_source='Tabela de teste',
            redemption_counts_for_progression=True, redemption_period_days=30,
            redemption_period_limit=1, redemption_character_limit=1,
        )
        post_social_credit(self.owner.pk, operation_ref='reversal:test:grant',
                           kind='test_grant', delta=15)
        self.redemption, _ = redeem_social_credit(
            self.owner.pk, self.character.pk, uuid4())

    def test_safe_reversal_compensates_both_ledgers_once(self):
        self.policy.active = False
        self.policy.save(update_fields=['active'])
        redemption, state = reverse_social_redemption(
            self.redemption.pk, actor_id=self.admin.pk, reason='Entrega incorreta')
        self.assertEqual(state, 'reversed')
        self.character.refresh_from_db()
        self.assertEqual((self.character.aventuras, self.character.carteira_pc), (0, 0))
        self.assertEqual(SocialCreditWallet.objects.get(user=self.owner).balance, 15)
        self.assertEqual(redemption.credit_reversal_entry.delta, 5)
        self.assertEqual(redemption.credit_reversal_entry.reversal_of_id,
                         redemption.credit_entry_id)
        self.assertEqual(redemption.gold_reversal_entry.valor_pc, -200)
        self.assertEqual(redemption.gold_reversal_entry.saldo_pc, 0)
        self.assertEqual(redemption.reversal_reason, 'Entrega incorreta')
        self.assertEqual(TbTransacao.objects.filter(tipo='recompensa-social').count(), 1)
        self.assertTrue(TbPersonagemAventura.objects.get(pk=redemption.adventure_entry_id).revertido)
        self.assertEqual(reverse_social_redemption(
            redemption.pk, actor_id=self.admin.pk, reason='Repeticao')[1], 'already_reversed')
        self.assertEqual(SocialCreditEntry.objects.filter(
            reversal_of=redemption.credit_entry).count(), 1)
        self.assertEqual(TbTransacao.objects.filter(tipo='ajuste').count(), 1)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('profile')), 'estornado')

    def test_later_gold_movement_requires_review_without_touching_balances(self):
        self.character.carteira_pc = 150
        self.character.save(update_fields=['carteira_pc'])
        TbTransacao.objects.create(id_personagem=self.character, tipo='compra',
                                   descricao='Compra posterior', valor_pc=-50, saldo_pc=150)
        redemption, state = reverse_social_redemption(
            self.redemption.pk, actor_id=self.admin.pk, reason='Entrega incorreta')
        self.assertEqual(state, 'review_required')
        self.assertIn('posterior', redemption.reversal_review_reason)
        self.assertEqual(redemption.reversal_reason, 'Entrega incorreta')
        self.assertEqual(redemption.reversal_review_requested_by_id, self.admin.pk)
        self.assertIsNotNone(redemption.reversal_review_requested_at)
        self.assertIsNone(redemption.reversed_at)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.owner).balance, 10)
        self.character.refresh_from_db()
        self.assertEqual((self.character.aventuras, self.character.carteira_pc), (1, 150))
        self.assertFalse(SocialCreditEntry.objects.filter(
            reversal_of=redemption.credit_entry).exists())
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('profile')), 'em revisão administrativa')

    def test_safe_reversal_releases_redemption_limits(self):
        redemption, state = reverse_social_redemption(
            self.redemption.pk, actor_id=self.admin.pk, reason='Entrega incorreta')
        self.assertEqual(state, 'reversed')
        self.assertEqual(redemption.adventure_entry.qtd_aventuras, 1)
        replacement, created = redeem_social_credit(
            self.owner.pk, self.character.pk, uuid4())
        self.assertTrue(created)
        self.assertNotEqual(replacement.pk, redemption.pk)

    def test_changed_progression_requires_review(self):
        self.character.aventuras = 2
        self.character.save(update_fields=['aventuras'])
        redemption, state = reverse_social_redemption(
            self.redemption.pk, actor_id=self.admin.pk, reason='Revisar')
        self.assertEqual(state, 'review_required')
        self.assertIn('progressão', redemption.reversal_review_reason)

    def test_later_adventure_and_debt_transfer_require_review(self):
        original_id = self.redemption.adventure_entry.detalhes_json['gold_transaction_id']
        TbTransacao.objects.create(
            id_personagem=self.character, tipo='repasse-divida',
            descricao='Repasse', valor_pc=0, saldo_pc=200,
            detalhes_json={'origem_transacao': original_id})
        TbPersonagemAventura.objects.create(
            id_personagem=self.character, origem='recompensa_comunidade',
            nome_aventura='Posterior', qtd_aventuras=0)
        redemption, state = reverse_social_redemption(
            self.redemption.pk, actor_id=self.admin.pk, reason='Revisar')
        self.assertEqual(state, 'review_required')
        self.assertIn('posterior', redemption.reversal_review_reason)
        self.assertIsNone(redemption.credit_reversal_entry_id)

    def test_command_requires_explicit_confirmation_and_superuser(self):
        with self.assertRaises(CommandError):
            call_command('reverse_social_redemption', redemption_id=self.redemption.pk,
                         actor=self.admin.username, reason='Erro', stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command('reverse_social_redemption', redemption_id=self.redemption.pk,
                         actor=self.owner.username, reason='Erro', apply=True,
                         confirm_id=self.redemption.pk, stdout=StringIO())
        with self.assertRaises(PermissionError):
            reverse_social_redemption(self.redemption.pk, actor_id=self.owner.pk,
                                      reason='Erro')
        self.assertFalse(SocialCreditRedemption.objects.get(pk=self.redemption.pk).reversed_at)

    def test_late_failure_rolls_back_credit_and_character_changes(self):
        with patch('home.social_credits.TbTransacao.objects.create',
                   side_effect=RuntimeError('ledger unavailable')):
            with self.assertRaisesMessage(RuntimeError, 'ledger unavailable'):
                reverse_social_redemption(self.redemption.pk, actor_id=self.admin.pk,
                                          reason='Entrega incorreta')
        self.character.refresh_from_db()
        self.redemption.refresh_from_db()
        self.assertEqual((self.character.aventuras, self.character.carteira_pc), (1, 200))
        self.assertEqual(SocialCreditWallet.objects.get(user=self.owner).balance, 10)
        self.assertIsNone(self.redemption.reversed_at)
        self.assertFalse(SocialCreditEntry.objects.filter(
            reversal_of=self.redemption.credit_entry).exists())
