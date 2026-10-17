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

from home.badges import badges_derivadas, titulos_disponiveis
from home.cosmetics import cosmetic_allowed
from home.mestre_ouro import buy_mestre_ouro_lifetime, reconcile_mestre_ouro
from home.models import (MestreOuroDireito, MestreOuroRevisao, TbCosmetico, TbRecompensaMestre,
                         TbTransacaoMestre, TbUsuarioCosmetico, UserProfile)
from home.permissions import is_mestre_ouro, limite_detalhe


class MestreOuroLifetimeTests(TestCase):
    def setUp(self):
        # TransactionTestCase flushes migration seed rows in a reused test DB.
        # Install the same two permanent benefits this flow requires.
        for slug, tipo, nome, css_class in (
            ('titulo-mestre-ouro', 'titulo', 'Mestre Ouro', ''),
            ('moldura-mestre-ouro', 'moldura', 'Aro do Mestre Ouro', 'frame-mestre-ouro'),
        ):
            TbCosmetico.objects.get_or_create(slug=slug, defaults={
                'tipo': tipo, 'nome': nome, 'css_class': css_class,
                'descricao': 'Benefício permanente de Mestre Ouro.',
                'raridade': 'lendario', 'origem': 'mestre_ouro',
                'escopo': 'perfil', 'ativo': True, 'ordem': 100,
            })
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
        self.assertEqual(TbUsuarioCosmetico.objects.filter(
            user=self.user, origem='mestre_ouro').count(), 2)

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
        self.assertEqual(TbUsuarioCosmetico.objects.filter(
            user=self.user, origem='mestre_ouro').count(), 2)

    def test_lifetime_title_frame_and_profile_detail_follow_proven_right(self):
        self.assertFalse(cosmetic_allowed(self.user, 'moldura', 'mestre-ouro', 'perfil'))
        self.client.force_login(self.user)
        before = self.client.get(reverse('public_profile', args=[self.user.username]))
        self.assertNotContains(before, 'Mestre Ouro vitalício desde')
        self.assertNotIn('titulo-mestre-ouro',
                         [item['slug'] for item in titulos_disponiveis(self.user)])

        self.profile.avatar_frame = 'gold-trim'
        self.profile.titulo_equipado = 'titulo-veterano-mesas'
        self.profile.moedas_mestragem = 900
        self.profile.save(update_fields=['avatar_frame', 'titulo_equipado',
                                         'moedas_mestragem'])
        self.offer.preco_vitalicio_aprovado_mm = 700
        self.offer.save(update_fields=['preco_vitalicio_aprovado_mm'])
        buy_mestre_ouro_lifetime(self.user.pk, self.offer.pk)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_frame, 'gold-trim')
        self.assertEqual(self.profile.titulo_equipado, 'titulo-veterano-mesas')
        self.assertTrue(cosmetic_allowed(self.user, 'moldura', 'mestre-ouro', 'perfil'))
        self.assertIn('titulo-mestre-ouro',
                      [item['slug'] for item in titulos_disponiveis(self.user)])
        editor = self.client.get(reverse('profile'))
        self.assertContains(editor, 'value="mestre-ouro"')
        self.assertContains(editor, 'value="titulo-mestre-ouro"')
        preview = self.client.post(reverse('perfil_preview'), {
            'avatar_frame': 'mestre-ouro',
            'titulo_equipado': 'titulo-mestre-ouro',
        })
        self.assertEqual(preview.status_code, 200)
        self.assertIn('frame-mestre-ouro', preview.json()['html'])
        self.assertIn('Mestre Ouro', preview.json()['html'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_frame, 'gold-trim')
        public = self.client.get(reverse('public_profile', args=[self.user.username]))
        self.assertContains(public, 'Mestre Ouro vitalício desde')

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
        self.assertNotContains(response, f'data-key="{self.offer.pk}"')
        self.assertContains(response, reverse('character_slots'))

    def test_legacy_offer_redirects_to_slots_without_debit(self):
        self.profile.moedas_mestragem = 900
        self.profile.save(update_fields=['moedas_mestragem'])
        self.client.force_login(self.user)
        with patch('home.permissions.is_mestre', return_value=True):
            response = self.client.post(reverse('mestre_resgatar'),
                                        {'recompensa': self.offer.pk})
        self.assertRedirects(response, reverse('character_slots'))
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_approved_legacy_offer_stays_inactive_and_normal_rewards_still_work(self):
        self.profile.moedas_mestragem = 900
        self.profile.save(update_fields=['moedas_mestragem'])
        self.offer.preco_vitalicio_aprovado_mm = 700
        self.offer.save(update_fields=['preco_vitalicio_aprovado_mm'])
        normal = TbRecompensaMestre.objects.create(
            slug='normal-reward-test', nome='Recompensa comum', tipo='normal',
            preco_mm=100, ativo=True,
        )
        self.client.force_login(self.user)
        with patch('home.permissions.is_mestre', return_value=True):
            page = self.client.get(reverse('mestre_mercado'))
            legacy = self.client.post(reverse('mestre_resgatar'),
                                      {'recompensa': self.offer.pk})
            normal_response = self.client.post(reverse('mestre_resgatar'),
                                               {'recompensa': normal.pk})
        self.assertNotContains(page, f'data-key="{self.offer.pk}"')
        self.assertContains(page, f'data-key="{normal.pk}"')
        self.assertRedirects(legacy, reverse('character_slots'))
        self.assertIn('?m=resgatado', normal_response['Location'])
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 800)
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)
        self.assertEqual(TbTransacaoMestre.objects.get().valor_mm, -100)
        self.assertFalse(MestreOuroDireito.objects.filter(user=self.user).exists())
        self.assertNotContains(page, 'Pagar mensalidade')
