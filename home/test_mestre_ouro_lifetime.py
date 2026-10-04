"""Mestre Ouro lifetime rights follow proven MM purchases, never monthly billing."""

import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.badges import badges_derivadas
from home.mestre_ouro import buy_mestre_ouro_lifetime, reconcile_mestre_ouro
from home.models import (MestreOuroDireito, MestreOuroRevisao, TbRecompensaMestre,
                         TbTransacaoMestre, UserProfile)
from home.permissions import is_mestre_ouro, limite_detalhe


class MestreOuroLifetimeTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user('old-gold', password='test')
        self.admin = users.objects.create_superuser('gold-admin', 'admin@example.test', 'test')
        self.profile = UserProfile.objects.get_or_create(user=self.user)[0]
        self.offer = TbRecompensaMestre.objects.create(
            slug='mestre-ouro-lifetime-test', nome='Mestre Ouro', tipo='assinatura',
            preco_mm=700, mensalidade_mm=99, ativo=True,
            descricao='Pagar 500 Moedas por Mês ou perder o espaço.',
        )

    def purchase(self, *, amount=500):
        return TbTransacaoMestre.objects.create(
            mestre=self.user, tipo='assinatura', valor_mm=-amount,
            saldo_mm=0, descricao='Mestre Ouro (assinatura)',
        )

    def test_historical_first_purchase_restores_inactive_benefit_once(self):
        first = self.purchase()
        self.profile.mestre_ouro_ativo = False
        self.profile.mestre_ouro_proximo_pgto = timezone.now().date() - timedelta(days=30)
        self.profile.save(update_fields=['mestre_ouro_ativo', 'mestre_ouro_proximo_pgto'])
        preview = StringIO()
        call_command('reconcile_mestre_ouro_lifetime', stdout=preview)
        self.assertEqual(json.loads(preview.getvalue())['rows'][0]['status'], 'eligible')
        self.assertFalse(MestreOuroDireito.objects.exists())
        with self.assertRaises(CommandError):
            call_command('reconcile_mestre_ouro_lifetime', apply=True,
                         actor=self.admin.username, stdout=StringIO())
        output = StringIO()
        call_command('reconcile_mestre_ouro_lifetime', apply=True,
                     confirm='MESTRE_OURO_VITALICIO', actor=self.admin.username,
                     stdout=output)
        grant = MestreOuroDireito.objects.get(user=self.user)
        self.assertEqual(grant.primeira_compra, first)
        self.assertEqual(grant.adquirido_em, first.criado_em)
        self.assertEqual(json.loads(output.getvalue())['rows'][0]['status'], 'granted')
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.mestre_ouro_ativo)
        self.assertIsNone(self.profile.mestre_ouro_proximo_pgto)
        self.assertTrue(is_mestre_ouro(self.user))
        self.assertEqual(reconcile_mestre_ouro(self.user.pk)[1], 'already_granted')
        self.assertEqual(MestreOuroDireito.objects.count(), 1)
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)

    def test_ambiguous_history_is_recorded_without_a_grant(self):
        self.purchase()
        self.purchase(amount=600)
        grant, result = reconcile_mestre_ouro(self.user.pk)
        self.assertIsNone(grant)
        self.assertEqual(result, 'review_required')
        self.assertEqual(MestreOuroRevisao.objects.get(user=self.user).motivo,
                         'multiple_first_purchases')
        self.assertFalse(is_mestre_ouro(self.user))

    def test_unproven_legacy_flag_is_not_a_lifetime_entitlement(self):
        self.profile.mestre_ouro_ativo = True
        self.profile.save(update_fields=['mestre_ouro_ativo'])
        self.assertFalse(is_mestre_ouro(self.user))
        preview = StringIO()
        call_command('reconcile_mestre_ouro_lifetime', stdout=preview)
        self.assertEqual(json.loads(preview.getvalue())['rows'][0]['status'],
                         'review_required')
        self.assertEqual(reconcile_mestre_ouro(self.user.pk)[1], 'review_required')
        self.assertEqual(MestreOuroRevisao.objects.get(user=self.user).motivo,
                         'legacy_status_without_purchase')

    def test_approved_single_purchase_and_replay_have_one_debit(self):
        slots_before = limite_detalhe(self.user)['total']
        self.profile.moedas_mestragem = 900
        self.profile.save(update_fields=['moedas_mestragem'])
        with self.assertRaisesMessage(ValueError, 'not approved'):
            buy_mestre_ouro_lifetime(self.user.pk, self.offer.pk)
        self.assertFalse(TbTransacaoMestre.objects.exists())
        self.offer.preco_vitalicio_aprovado_mm = 700
        self.offer.save(update_fields=['preco_vitalicio_aprovado_mm'])
        grant, created = buy_mestre_ouro_lifetime(self.user.pk, self.offer.pk)
        self.assertTrue(created)
        self.assertEqual(grant.primeira_compra.valor_mm, -700)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.moedas_mestragem, 200)
        self.assertIsNone(self.profile.mestre_ouro_proximo_pgto)
        self.assertEqual(limite_detalhe(self.user)['total'], slots_before + 1)
        self.assertIn('mestre_ouro', [badge['slug'] for badge in
                                     badges_derivadas(self.user, is_colaborador=False)])
        same, created = buy_mestre_ouro_lifetime(self.user.pk, self.offer.pk)
        self.assertFalse(created)
        self.assertEqual(same.pk, grant.pk)
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 200)

    def test_price_change_invalidates_prior_approval(self):
        self.profile.moedas_mestragem = 900
        self.profile.save(update_fields=['moedas_mestragem'])
        self.offer.preco_vitalicio_aprovado_mm = 700
        self.offer.preco_mm = 800
        self.offer.save(update_fields=['preco_vitalicio_aprovado_mm', 'preco_mm'])
        with self.assertRaisesMessage(ValueError, 'not approved'):
            buy_mestre_ouro_lifetime(self.user.pk, self.offer.pk)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_legacy_billing_command_cannot_charge_or_revoke_and_page_has_no_monthly_offer(self):
        first = self.purchase()
        self.profile.moedas_mestragem = 800
        self.profile.mestre_ouro_ativo = True
        self.profile.mestre_ouro_proximo_pgto = timezone.now().date() - timedelta(days=1)
        self.profile.save(update_fields=['moedas_mestragem', 'mestre_ouro_ativo',
                                         'mestre_ouro_proximo_pgto'])
        reconcile_mestre_ouro(self.user.pk)
        out = StringIO()
        call_command('cobrar_mestre_ouro', stdout=out)
        self.assertIn('0 débitos', out.getvalue())
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)
        self.assertEqual(TbTransacaoMestre.objects.get().pk, first.pk)
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 800)
        self.client.force_login(self.user)
        with patch('home.permissions.is_mestre', return_value=True):
            response = self.client.get(reverse('mestre_mercado'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vitalício')
        self.assertNotContains(response, 'Próxima mensalidade')
        self.assertNotContains(response, 'Pagar mensalidade')
        self.assertNotContains(response, '500 Moedas por Mês')

    def test_post_offer_without_approved_price_does_not_debit(self):
        self.profile.moedas_mestragem = 900
        self.profile.save(update_fields=['moedas_mestragem'])
        self.client.force_login(self.user)
        with patch('home.permissions.is_mestre', return_value=True):
            response = self.client.post(reverse('mestre_resgatar'),
                                        {'recompensa': self.offer.pk})
        self.assertEqual(response.status_code, 302)
        self.assertIn('ouro_indisponivel', response['Location'])
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_post_approved_offer_delivers_once_and_shows_lifetime_status(self):
        self.profile.moedas_mestragem = 900
        self.profile.save(update_fields=['moedas_mestragem'])
        self.offer.preco_vitalicio_aprovado_mm = 700
        self.offer.save(update_fields=['preco_vitalicio_aprovado_mm'])
        self.client.force_login(self.user)
        with patch('home.permissions.is_mestre', return_value=True):
            first = self.client.post(reverse('mestre_resgatar'),
                                     {'recompensa': self.offer.pk})
            replay = self.client.post(reverse('mestre_resgatar'),
                                      {'recompensa': self.offer.pk})
            page = self.client.get(reverse('mestre_mercado'))
        self.assertIn('?m=ouro', first['Location'])
        self.assertIn('?m=ouro_existente', replay['Location'])
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 200)
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)
        self.assertContains(page, 'Adquirido permanentemente')
        self.assertNotContains(page, 'Pagar mensalidade')
