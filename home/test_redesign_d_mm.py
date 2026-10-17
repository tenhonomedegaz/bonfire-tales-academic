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
from .cosmetics import catalog_options
from .models import (AsaasCheckoutOrder, CosmeticCheckoutOffer, CosmeticMMRedemption, TbCosmetico,
                     TbPersonagem, TbTransacaoMestre, TbUsuarioCosmetico, UserProfile)
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

    def test_success_opens_existing_profile_and_active_character_editors(self):
        active = TbPersonagem.objects.create(dono=self.user, nome='Aventureira')
        archived = TbPersonagem.objects.create(dono=self.user, nome='No cofre', arquivado=True)
        self.client.force_login(self.user)
        result = self.client.post(reverse('buy_theme_with_mm'), {
            'slug': self.theme.slug, 'request_key': str(uuid.uuid4()),
        })
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, reverse('profile') + '#perfil-aparencia')
        self.assertContains(result, reverse('ficha_detail', args=[active.pk]) +
                            '?aba=info#ficha-theme-group')
        self.assertNotContains(result, reverse('ficha_detail', args=[archived.pk]) +
                               '?aba=info#ficha-theme-group')
        self.assertIn('forja-de-brasas', [item['key'] for item in catalog_options(
            self.user, 'tema', 'ficha') if item['estado'] == 'possui'])
        profile = self.client.get(reverse('profile'))
        self.assertEqual(profile.status_code, 200)
        self.assertFalse(next(item['locked'] for item in profile.context['appearance_theme_options']
                              if item['key'] == 'forja-de-brasas'))
        editor = self.client.get(reverse('ficha_detail', args=[active.pk]), {'aba': 'info'})
        self.assertEqual(editor.status_code, 200)
        self.assertIn('forja-de-brasas', [item['key'] for item in
                      editor.context['appearance_themes'] if not item['locked']])

    def test_redeemed_pilot_composition_renders_after_equipping_profile_and_sheet(self):
        self.theme.css_class = 'theme-data'
        self.theme.escopo = 'ambos'
        self.theme.definicao_json = {
            'accent': '#ff833b', 'accent2': '#b31515',
            'surface': '#1b120f', 'deep': '#0d0908', 'gradiente': True,
        }
        self.theme.save(update_fields=['css_class', 'escopo', 'definicao_json'])
        character = TbPersonagem.objects.create(
            dono=self.user, nome='Aventureira', publico=True)
        self.client.force_login(self.user)
        redeemed = self.client.post(reverse('buy_theme_with_mm'), {
            'slug': self.theme.slug, 'request_key': str(uuid.uuid4()),
        })
        self.assertEqual(redeemed.status_code, 200)

        saved_profile = self.client.post(reverse('profile'), {
            'action': 'update_profile', 'username': self.user.username,
            'profile_theme': 'forja-de-brasas', 'avatar_frame': 'none',
            'profile_effect': 'none',
        })
        saved_sheet = self.client.post(reverse('personagem_info_salvar', args=[character.pk]), {
            'ficha_theme': 'forja-de-brasas', 'foto_frame': 'none',
            'ficha_effect': 'none',
        })
        self.assertEqual((saved_profile.status_code, saved_sheet.status_code), (200, 302))
        self.profile.refresh_from_db()
        character.refresh_from_db()
        self.assertEqual(self.profile.profile_theme, 'forja-de-brasas')
        self.assertEqual(character.ficha_theme, 'forja-de-brasas')

        for url in (reverse('profile'),
                    reverse('public_profile', args=[self.user.username]),
                    reverse('ficha_detail', args=[character.pk]),
                    reverse('ficha_publica', args=[character.pk])):
            page = self.client.get(url)
            self.assertEqual(page.status_code, 200, url)
            self.assertEqual(page.context['appearance']['theme_class'],
                             'theme-data collection-forja-de-brasas', url)
            self.assertContains(page, '#ff833b')

        self.client.force_login(get_user_model().objects.create_user('theme_viewer'))
        self.assertContains(self.client.get(reverse('public_profile', args=[self.user.username])),
                            'collection-forja-de-brasas')
        self.assertContains(self.client.get(reverse('ficha_publica', args=[character.pk])),
                            'collection-forja-de-brasas')

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
        self.assertNotContains(live, 'action="' + reverse('cosmetic_checkout') + '"')
        self.assertNotContains(live, 'Conferir compra por R$')
        self.offer.demonstration = True
        self.offer.save(update_fields=['demonstration'])
        demo = self.client.get(reverse('theme_studio'))
        self.assertNotContains(demo, reverse('buy_theme_with_mm'))

    def test_live_mm_theme_cannot_create_cash_checkout(self):
        self.client.force_login(self.user)
        listing = self.client.get(reverse('cosmetic_checkout'))
        self.assertNotContains(listing, self.theme.slug)
        response = self.client.post(reverse('cosmetic_checkout'), {'slug': self.theme.slug})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AsaasCheckoutOrder.objects.exists())
        self.assertFalse(CosmeticMMRedemption.objects.exists())

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
