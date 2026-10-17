"""The G01-D pre-change artifact captures affected values without changing them."""

import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from .models import (CosmeticCheckoutOffer, TbCosmetico, TbRecompensaMestre,
                     TbUsuarioCosmetico, UserProfile)


class RedesignDInventoryTests(TransactionTestCase):
    def test_snapshot_preserves_reward_theme_offer_entitlement_and_mm_balance(self):
        user = get_user_model().objects.create_user('inventory_master', password='test-pass')
        profile = UserProfile.objects.get(user=user)
        profile.moedas_mestragem = 75
        profile.mestre_ouro_ativo = True
        profile.save(update_fields=['moedas_mestragem', 'mestre_ouro_ativo'])
        reward = TbRecompensaMestre.objects.create(slug='legacy-master-gold', nome='Mestre Ouro',
                                                   tipo='assinatura', ativo=True, preco_mm=5000)
        theme = TbCosmetico.objects.create(slug='theme-inventory-test', tipo='tema', nome='Tema teste',
                                           origem='colaborador', ativo=True)
        offer = CosmeticCheckoutOffer.objects.create(cosmetico=theme, amount='19.00', active=True)
        entitlement = TbUsuarioCosmetico.objects.create(user=user, cosmetico=theme, origem='staff')

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prechange.json'
            output = StringIO()
            call_command('preview_redesign_d', output=str(path),
                         expected_home_head='0154_redesign_master_portfolio', stdout=output)
            report = json.loads(output.getvalue())
            raw = path.read_bytes()
            saved = json.loads(raw)
            self.assertEqual(report['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(saved['kind'], 'G01-D-prechange')
            self.assertEqual(saved['rows']['subscription_rewards'][0]['id_recompensa'], reward.pk)
            self.assertTrue(saved['rows']['subscription_rewards'][0]['ativo'])
            self.assertIn(theme.slug, {row['slug'] for row in saved['rows']['themes']})
            self.assertIn(offer.pk, {row['id'] for row in saved['rows']['theme_checkout_offers']})
            self.assertIn(entitlement.pk, {row['id'] for row in saved['rows']['theme_inventory']})
            self.assertEqual(next(row['moedas_mestragem'] for row in saved['rows']['mm_profiles']
                                  if row['user_id'] == user.pk), 75)
            with self.assertRaises(CommandError):
                call_command('preview_redesign_d', output=str(path),
                             expected_home_head='0154_redesign_master_portfolio', stdout=StringIO())
            with self.assertRaises(CommandError):
                call_command('preview_redesign_d', output=str(Path(directory) / 'late.json'),
                             expected_home_head='0158_theme_studio_pilot', stdout=StringIO())

        reward.refresh_from_db()
        offer.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(reward.ativo)
        self.assertTrue(offer.active)
        self.assertEqual(profile.moedas_mestragem, 75)
