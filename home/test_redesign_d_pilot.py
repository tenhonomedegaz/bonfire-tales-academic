"""Pilot themes are visible but never become payable without a separate gate."""

import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from .models import (AsaasCheckoutOrder, CosmeticCheckoutOffer, TbCosmetico,
                     TbUsuarioCosmetico)


class RedesignDPilotTests(TransactionTestCase):
    def test_pilot_studio_checkout_guard_and_reversible_archive(self):
        user = get_user_model().objects.create_user('pilot_user', email='pilot@example.test')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'before.json'
            call_command('preview_redesign_d', output=str(path),
                         expected_home_head='0155_redesign_theme_pilot', stdout=StringIO())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()

            def run(action, confirm=''):
                out = StringIO()
                call_command('reconcile_redesign_d_pilot', snapshot=str(path), sha256=digest,
                             action=action, confirm=confirm, stdout=out)
                return json.loads(out.getvalue())

            self.assertEqual(len(run('preview')['changed_slugs']), 3)
            with self.assertRaises(CommandError):
                run('seed')
            self.assertEqual(len(run('seed', 'G01-D-PILOT')['changed_slugs']), 3)
            self.assertEqual(run('seed', 'G01-D-PILOT')['changed_slugs'], [])
            anonymous = self.client.get(reverse('theme_studio'), {'tema': 'aurora-glacial'})
            self.assertEqual(anonymous.status_code, 200)
            self.assertContains(anonymous, 'Aurora Glacial')
            self.assertContains(anonymous, 'Preço ilustrativo')
            self.assertEqual(anonymous.context['selected']['key'], 'aurora-glacial')
            self.client.force_login(user)
            page = self.client.get(reverse('theme_studio'))
            self.assertEqual(page.status_code, 200)
            self.assertEqual(len(page.context['cards']), 3)
            offer = CosmeticCheckoutOffer.objects.get(cosmetico__slug='tema-forja-de-brasas')
            self.assertTrue(offer.demonstration)
            with override_settings(BONFIRE_COMMERCE_ENABLED=True):
                self.assertEqual(self.client.post(reverse('cosmetic_checkout'),
                                                  {'slug': 'tema-forja-de-brasas'}).status_code, 400)
            self.assertFalse(AsaasCheckoutOrder.objects.exists())
            self.assertFalse(TbUsuarioCosmetico.objects.filter(user=user).exists())
            self.assertEqual(len(run('archive', 'G01-D-PILOT')['changed_slugs']), 3)
            self.assertFalse(TbCosmetico.objects.filter(slug='tema-forja-de-brasas').first().ativo)
            self.assertEqual(run('archive', 'G01-D-PILOT')['changed_slugs'], [])

    def test_archive_refuses_to_hide_an_acquired_theme(self):
        user = get_user_model().objects.create_user('pilot_owner')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'before.json'
            call_command('preview_redesign_d', output=str(path),
                         expected_home_head='0155_redesign_theme_pilot', stdout=StringIO())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            call_command('reconcile_redesign_d_pilot', snapshot=str(path), sha256=digest,
                         action='seed', confirm='G01-D-PILOT', stdout=StringIO())
            owned = TbCosmetico.objects.get(slug='tema-aurora-glacial')
            TbUsuarioCosmetico.objects.create(user=user, cosmetico=owned, origem='staff')
            with self.assertRaises(CommandError):
                call_command('reconcile_redesign_d_pilot', snapshot=str(path), sha256=digest,
                             action='archive', confirm='G01-D-PILOT', stdout=StringIO())
            self.assertEqual(TbCosmetico.objects.filter(slug__in=(
                'tema-forja-de-brasas', 'tema-aurora-glacial', 'tema-circulo-arcano'),
                ativo=True).count(), 3)
