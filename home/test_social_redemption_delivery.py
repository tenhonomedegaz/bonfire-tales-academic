from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.models import (SocialCreditEntry, SocialCreditPolicy, SocialCreditRedemption,
                         SocialCreditWallet, TbPersonagem, TbPersonagemAventura,
                         TbTransacao)
from home.social_credits import post_social_credit, redeem_social_credit
from home.conquistas import registrar_fato_aventura


class SocialRedemptionDeliveryTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user('redemption-owner', password='test')
        self.other = users.objects.create_user('redemption-other', password='test')
        self.character = TbPersonagem.objects.create(dono=self.user, nome='Heroína')
        self.second = TbPersonagem.objects.create(dono=self.user, nome='Segunda')
        self.foreign = TbPersonagem.objects.create(dono=self.other, nome='Alheio')
        self.policy = SocialCreditPolicy.objects.create(
            version='redeem-test-v1', first_publication_amount=1,
            active=True, redemption_enabled=True, redemption_cost=5,
            redemption_gold_pc=200, redemption_gold_source='Tabela aprovada de teste',
            redemption_counts_for_progression=False, redemption_period_days=30,
            redemption_period_limit=2, redemption_character_limit=1,
        )
        post_social_credit(self.user.pk, operation_ref='test:grant',
                           kind='test_grant', delta=15)

    def test_profile_redeems_once_and_shows_private_history(self):
        request_id = uuid4()
        self.client.force_login(self.user)
        payload = {'action': 'redeem_social_credit', 'character_id': self.character.pk,
                   'request_id': str(request_id)}
        response = self.client.post(reverse('profile'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resgate concluído')
        redemption = SocialCreditRedemption.objects.get(request_id=request_id)
        self.assertEqual((redemption.cost, redemption.gold_pc, redemption.gold_source),
                         (5, 200, 'Tabela aprovada de teste'))
        self.assertEqual(redemption.credit_entry.delta, -5)
        self.assertEqual(redemption.adventure_entry.origem, 'recompensa_comunidade')
        self.assertEqual(redemption.adventure_entry.qtd_aventuras, 0)
        self.assertIsNone(redemption.adventure_entry.id_mestre_id)
        self.assertIsNone(redemption.adventure_entry.data_missao)
        self.assertEqual(redemption.adventure_entry.detalhes_json['beneficio_aventuras'], 1)
        self.character.refresh_from_db()
        self.assertEqual((self.character.aventuras, self.character.carteira_pc), (0, 200))
        self.assertEqual(SocialCreditWallet.objects.get(user=self.user).balance, 10)
        movement = TbTransacao.objects.get(tipo='recompensa-social')
        self.assertEqual(movement.valor_pc, 200)
        self.assertEqual(movement.detalhes_json['adventure_ledger_id'],
                         redemption.adventure_entry_id)
        self.assertContains(response, 'Resgates anteriores')
        self.assertNotContains(self.client.get(reverse('public_profile', args=[self.user.username])),
                               'Resgates anteriores')

        replay = self.client.post(reverse('profile'), payload)
        self.assertContains(replay, 'já foi concluído')
        self.assertEqual(SocialCreditRedemption.objects.count(), 1)
        self.assertEqual(TbTransacao.objects.filter(tipo='recompensa-social').count(), 1)
        self.assertEqual(SocialCreditEntry.objects.filter(kind='redemption').count(), 1)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.user).balance, 10)

    def test_progression_is_explicit_and_not_a_mission(self):
        self.policy.redemption_counts_for_progression = True
        self.policy.save(update_fields=['redemption_counts_for_progression'])
        redemption, created = redeem_social_credit(self.user.pk, self.character.pk, uuid4())
        self.assertTrue(created)
        self.character.refresh_from_db()
        self.assertEqual(self.character.aventuras, 1)
        self.assertEqual(redemption.adventure_entry.qtd_aventuras, 1)
        self.assertEqual(redemption.adventure_entry.origem, 'recompensa_comunidade')
        with self.assertRaisesMessage(ValueError, 'não é mesa jogada'):
            registrar_fato_aventura(redemption.adventure_entry)

    def test_insufficient_balance_and_failed_delivery_rollback_all_records(self):
        self.policy.redemption_cost = 20
        self.policy.save(update_fields=['redemption_cost'])
        with self.assertRaisesMessage(ValueError, 'insufficient'):
            redeem_social_credit(self.user.pk, self.character.pk, uuid4())
        self.assertFalse(SocialCreditRedemption.objects.exists())
        self.assertFalse(TbPersonagemAventura.objects.exists())
        self.assertFalse(SocialCreditEntry.objects.filter(kind='redemption').exists())
        self.policy.redemption_cost = 5
        self.policy.save(update_fields=['redemption_cost'])
        with patch('home.market_services.register_transaction',
                   side_effect=RuntimeError('transaction unavailable')):
            with self.assertRaisesMessage(RuntimeError, 'transaction unavailable'):
                redeem_social_credit(self.user.pk, self.character.pk, uuid4())
        self.character.refresh_from_db()
        self.assertEqual(self.character.carteira_pc, 0)
        self.assertEqual(SocialCreditWallet.objects.get(user=self.user).balance, 15)
        self.assertFalse(SocialCreditRedemption.objects.exists())
        self.assertFalse(TbPersonagemAventura.objects.exists())
        self.assertFalse(SocialCreditEntry.objects.filter(kind='redemption').exists())

    def test_ownership_archive_and_replay_identity_are_enforced(self):
        with self.assertRaisesMessage(ValueError, 'not eligible'):
            redeem_social_credit(self.user.pk, self.foreign.pk, uuid4())
        self.character.arquivado = True
        self.character.save(update_fields=['arquivado'])
        with self.assertRaisesMessage(ValueError, 'not eligible'):
            redeem_social_credit(self.user.pk, self.character.pk, uuid4())
        self.character.arquivado = False
        self.character.save(update_fields=['arquivado'])
        request_id = uuid4()
        redeem_social_credit(self.user.pk, self.character.pk, request_id)
        with self.assertRaisesMessage(ValueError, 'another redemption'):
            redeem_social_credit(self.user.pk, self.second.pk, request_id)
        with self.assertRaisesMessage(ValueError, 'another redemption'):
            redeem_social_credit(self.other.pk, self.foreign.pk, request_id)

    def test_period_character_and_policy_limits(self):
        redeem_social_credit(self.user.pk, self.character.pk, uuid4())
        with self.assertRaisesMessage(ValueError, 'character redemption limit'):
            redeem_social_credit(self.user.pk, self.character.pk, uuid4())
        redeem_social_credit(self.user.pk, self.second.pk, uuid4())
        third = TbPersonagem.objects.create(dono=self.user, nome='Terceira')
        with self.assertRaisesMessage(ValueError, 'period limit'):
            redeem_social_credit(self.user.pk, third.pk, uuid4())
        self.policy.active = False
        self.policy.save(update_fields=['active'])
        with self.assertRaisesMessage(ValueError, 'unavailable'):
            redeem_social_credit(self.user.pk, third.pk, uuid4())

    def test_staff_mission_endpoints_cannot_change_community_reward(self):
        redemption, _ = redeem_social_credit(self.user.pk, self.character.pk, uuid4())
        staff = get_user_model().objects.create_superuser(
            'redemption-staff', 'staff@example.test', 'test')
        self.client.force_login(staff)
        for route in ('personagem_reverter_aventura', 'personagem_editar_aventura',
                      'personagem_aventura_consumo'):
            with self.subTest(route=route):
                response = self.client.post(reverse(route, args=[
                    self.character.pk, redemption.adventure_entry_id]),
                    {'tipo': 'ouro'} if route == 'personagem_aventura_consumo' else {})
                self.assertEqual(response.status_code, 404)
        redemption.adventure_entry.refresh_from_db()
        self.assertFalse(redemption.adventure_entry.revertido)
        self.assertEqual(redemption.adventure_entry.origem, 'recompensa_comunidade')
