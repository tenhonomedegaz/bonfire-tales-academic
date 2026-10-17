"""G01-D theme redemption against the existing MM wallet and inventory."""

import uuid
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from .cosmetic_entitlements import has_permanent_cosmetic
from .models import (CosmeticCheckoutOffer, CosmeticMMRedemption, TbCosmetico,
                     TbTransacaoMestre, TbUsuarioCosmetico, UserProfile)
from .theme_mm import redeem_theme_mm, reverse_theme_mm


@override_settings(BONFIRE_COMMERCE_ENABLED=True)
class ThemeMMTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('theme_mm_user', password='test-pass')
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.moedas_mestragem = 120
        self.profile.save(update_fields=['moedas_mestragem'])
        self.theme = TbCosmetico.objects.create(
            slug='tema-forja-de-brasas', tipo='tema', nome='Forja de Brasas',
            origem='loja_mm', preco=50, ativo=True,
        )
        self.offer = CosmeticCheckoutOffer.objects.create(
            cosmetico=self.theme, amount='10.00', active=True, demonstration=False,
        )

    def test_post_debits_once_and_replay_keeps_receipt_and_right(self):
        self.client.force_login(self.user)
        key = str(uuid.uuid4())
        url = reverse('buy_theme_with_mm')
        first = self.client.post(url, {'slug': self.theme.slug, 'request_key': key})
        again = self.client.post(url, {'slug': self.theme.slug, 'request_key': key})
        self.profile.refresh_from_db()
        self.assertEqual((first.status_code, again.status_code), (200, 200))
        self.assertEqual(self.profile.moedas_mestragem, 70)
        self.assertEqual(CosmeticMMRedemption.objects.count(), 1)
        self.assertEqual(TbTransacaoMestre.objects.filter(mestre=self.user, tipo='resgate').count(), 1)
        self.assertTrue(has_permanent_cosmetic(self.user, self.theme))
        self.assertContains(again, 'nenhum novo débito')

    def test_demo_or_insufficient_balance_never_debits(self):
        self.offer.demonstration = True
        self.offer.save(update_fields=['demonstration'])
        with self.assertRaises(ValueError):
            redeem_theme_mm(self.user.pk, self.theme.slug, uuid.uuid4())
        self.offer.demonstration = False
        self.offer.save(update_fields=['demonstration'])
        self.profile.moedas_mestragem = 49
        self.profile.save(update_fields=['moedas_mestragem'])
        with self.assertRaises(ValueError):
            redeem_theme_mm(self.user.pk, self.theme.slug, uuid.uuid4())
        self.assertFalse(CosmeticMMRedemption.objects.exists())
        self.assertFalse(TbTransacaoMestre.objects.filter(mestre=self.user, tipo='resgate').exists())

    def test_studio_exposes_live_mm_offer_but_not_demo_checkout(self):
        self.client.force_login(self.user)
        live = self.client.get(reverse('theme_studio'))
        self.assertContains(live, reverse('buy_theme_with_mm'))
        self.offer.demonstration = True
        self.offer.save(update_fields=['demonstration'])
        demo = self.client.get(reverse('theme_studio'))
        self.assertNotContains(demo, reverse('buy_theme_with_mm'))

    def test_checkout_disabled_on_server_even_for_live_offer(self):
        self.client.force_login(self.user)
        with override_settings(BONFIRE_COMMERCE_ENABLED=False):
            response = self.client.post(reverse('buy_theme_with_mm'), {
                'slug': self.theme.slug, 'request_key': str(uuid.uuid4()),
            })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CosmeticMMRedemption.objects.exists())

    def test_other_request_does_not_charge_owned_theme(self):
        redeem_theme_mm(self.user.pk, self.theme.slug, uuid.uuid4())
        with self.assertRaises(ValueError):
            redeem_theme_mm(self.user.pk, self.theme.slug, uuid.uuid4())
        self.assertEqual(CosmeticMMRedemption.objects.count(), 1)

    def test_failed_inventory_grant_rolls_back_wallet_and_ledger(self):
        with patch.object(TbUsuarioCosmetico.objects, 'get_or_create',
                          side_effect=RuntimeError('inventory unavailable')):
            with self.assertRaises(RuntimeError):
                redeem_theme_mm(self.user.pk, self.theme.slug, uuid.uuid4())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.moedas_mestragem, 120)
        self.assertFalse(CosmeticMMRedemption.objects.exists())
        self.assertFalse(TbTransacaoMestre.objects.filter(mestre=self.user).exists())

    def test_compensation_is_once_only_and_keeps_audit(self):
        receipt, _ = redeem_theme_mm(self.user.pk, self.theme.slug, uuid.uuid4())
        with self.assertRaises(CommandError):
            call_command('reverse_redesign_d_mm', receipt.pk)
        output = StringIO()
        call_command('reverse_redesign_d_mm', receipt.pk,
                     confirm='G01-D-MM-REVERSAL', stdout=output)
        self.assertIn('reversed=True', output.getvalue())
        _, changed = reverse_theme_mm(receipt.pk)
        self.assertFalse(changed)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.moedas_mestragem, 120)
        self.assertEqual(TbTransacaoMestre.objects.filter(mestre=self.user).count(), 2)
        self.assertFalse(has_permanent_cosmetic(self.user, self.theme))
        self.assertIsNotNone(TbUsuarioCosmetico.objects.get(
            user=self.user, cosmetico=self.theme).suspenso_em)

    def test_post_requires_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(reverse('buy_theme_with_mm'), {
            'slug': self.theme.slug, 'request_key': str(uuid.uuid4()),
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CosmeticMMRedemption.objects.exists())

    def test_compensation_restores_prior_temporary_inventory(self):
        inventory = TbUsuarioCosmetico.objects.create(
            user=self.user, cosmetico=self.theme, origem='colaborador:ouro')
        receipt, _ = redeem_theme_mm(self.user.pk, self.theme.slug, uuid.uuid4())
        inventory.refresh_from_db()
        self.assertEqual(inventory.origem, 'compra_mm')
        reverse_theme_mm(receipt.pk)
        inventory.refresh_from_db()
        self.assertEqual(inventory.origem, 'colaborador:ouro')
        self.assertIsNone(inventory.suspenso_em)
