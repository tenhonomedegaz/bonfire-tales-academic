"""Pilot themes are visible but never become payable without a separate gate."""

import json
import tempfile
from uuid import uuid4
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from .models import (AsaasCheckoutOrder, CosmeticCheckoutOffer, TbCosmetico,
                     TbTransacaoMestre, TbUsuarioCosmetico, UserProfile)
from .theme_mm import redeem_theme_mm
from .test_redesign_d_support import capture_pre_d_snapshot


class RedesignDPilotTests(TransactionTestCase):
    def test_archive_refuses_commercial_offer_without_mm_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'before.json'
            digest = capture_pre_d_snapshot(path)
            options = {'snapshot': str(path), 'sha256': digest,
                       'confirm': 'G01-D-PILOT', 'stdout': StringIO()}
            call_command('reconcile_redesign_d_pilot', action='seed', **options)
            slug = 'tema-aurora-glacial'
            CosmeticCheckoutOffer.objects.filter(cosmetico__slug=slug).update(
                demonstration=False)

            with self.assertRaisesMessage(CommandError, 'commercial offer without MM history'):
                call_command('reconcile_redesign_d_pilot', action='archive', **options)

            self.assertTrue(TbCosmetico.objects.get(slug=slug).ativo)
            self.assertTrue(CosmeticCheckoutOffer.objects.get(cosmetico__slug=slug).active)
            self.assertEqual(TbCosmetico.objects.filter(
                slug__in=('tema-forja-de-brasas', 'tema-aurora-glacial',
                          'tema-circulo-arcano'), ativo=True).count(), 3)

    def test_cash_checkout_stays_closed_if_pilot_offer_is_misconfigured(self):
        user = get_user_model().objects.create_user('pilot_cash_guard', email='cash@example.test')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'before.json'
            digest = capture_pre_d_snapshot(path)
            call_command('reconcile_redesign_d_pilot', snapshot=str(path), sha256=digest,
                         action='seed', confirm='G01-D-PILOT', stdout=StringIO())
            CosmeticCheckoutOffer.objects.filter(
                cosmetico__slug__in=('tema-aurora-glacial', 'tema-forja-de-brasas'),
            ).update(demonstration=False)

            self.client.force_login(user)
            with override_settings(BONFIRE_COMMERCE_ENABLED=True):
                studio = self.client.get(reverse('theme_studio'), {'tema': 'aurora-glacial'})
                self.assertEqual(studio.status_code, 200)
                self.assertTrue(studio.context['selected']['cash_disabled'])
                self.assertNotContains(studio, 'Conferir compra por R$')
                self.assertContains(studio, 'Preço ilustrativo')
                self.assertFalse(studio.context['cards'][0]['cash_disabled'])
                self.assertContains(studio, 'Confirmar aquisição por 1500 MM')
                checkout = self.client.get(reverse('cosmetic_checkout'))
                self.assertNotContains(checkout, 'tema-aurora-glacial')
                for slug in ('tema-aurora-glacial', 'tema-forja-de-brasas'):
                    self.assertEqual(self.client.post(reverse('cosmetic_checkout'),
                                                      {'slug': slug}).status_code, 400)
            self.assertFalse(AsaasCheckoutOrder.objects.exists())

    def test_pilot_studio_checkout_guard_and_reversible_archive(self):
        user = get_user_model().objects.create_user('pilot_user', email='pilot@example.test')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'before.json'
            digest = capture_pre_d_snapshot(path)

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

    def test_rollback_closes_offers_but_preserves_an_acquired_theme(self):
        user = get_user_model().objects.create_user('pilot_owner')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'before.json'
            digest = capture_pre_d_snapshot(path)
            call_command('reconcile_redesign_d_pilot', snapshot=str(path), sha256=digest,
                         action='seed', confirm='G01-D-PILOT', stdout=StringIO())
            owned = TbCosmetico.objects.get(slug='tema-aurora-glacial')
            TbUsuarioCosmetico.objects.create(user=user, cosmetico=owned, origem='staff')
            mm_theme = TbCosmetico.objects.get(slug='tema-forja-de-brasas')
            CosmeticCheckoutOffer.objects.filter(cosmetico=mm_theme).update(demonstration=False)
            profile = UserProfile.objects.get(user=user)
            profile.moedas_mestragem = 2000
            profile.save(update_fields=['moedas_mestragem'])
            receipt, created = redeem_theme_mm(user.pk, mm_theme.slug, uuid4())
            self.assertTrue(created)
            self.assertEqual(receipt.cost_mm, 1500)
            profile.refresh_from_db()
            self.assertEqual(profile.moedas_mestragem, 500)
            output = StringIO()
            call_command('rollback_redesign_d_pilot', snapshot=str(path), sha256=digest,
                         confirm='G01-D-ROLLBACK-PILOT', stdout=output)
            result = json.loads(output.getvalue())
            self.assertEqual(set(result['retained_owned_slugs']),
                             {'tema-forja-de-brasas', 'tema-aurora-glacial'})
            self.assertEqual(result['archived_slugs'], ['tema-circulo-arcano'])
            self.assertEqual(TbCosmetico.objects.filter(slug__in=(
                'tema-forja-de-brasas', 'tema-aurora-glacial', 'tema-circulo-arcano'),
                ativo=True).count(), 2)
            self.assertFalse(CosmeticCheckoutOffer.objects.filter(
                cosmetico__slug__startswith='tema-', active=True).exists())
            self.client.force_login(user)
            self.assertContains(self.client.get(reverse('theme_studio')), 'Aurora Glacial')
            self.assertContains(self.client.get(reverse('theme_studio')), 'Forja de Brasas')
            self.client.logout()
            self.assertNotContains(self.client.get(reverse('theme_studio')), 'Aurora Glacial')
            self.assertNotContains(self.client.get(reverse('theme_studio')), 'Forja de Brasas')
            other = get_user_model().objects.create_user('pilot_other')
            for slug in (owned.slug, mm_theme.slug):
                with self.assertRaisesMessage(ValueError, 'indisponível'):
                    redeem_theme_mm(other.pk, slug, uuid4())
            self.assertEqual(TbTransacaoMestre.objects.count(), 1)
            self.assertTrue(TbTransacaoMestre.objects.filter(pk=receipt.transaction_id,
                                                             valor_mm=-1500).exists())
            self.assertTrue(TbUsuarioCosmetico.objects.filter(user=user, cosmetico=mm_theme,
                                                             suspenso_em__isnull=True).exists())
            profile.refresh_from_db()
            self.assertEqual(profile.moedas_mestragem, 500)
            again = StringIO()
            call_command('rollback_redesign_d_pilot', snapshot=str(path), sha256=digest,
                         confirm='G01-D-ROLLBACK-PILOT', stdout=again)
            self.assertEqual(json.loads(again.getvalue())['archived_slugs'], [])
            self.assertEqual(TbTransacaoMestre.objects.count(), 1)
