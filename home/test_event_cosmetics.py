"""Loja de cosméticos de evento: débito único, posse e janela da oferta."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .cosmetic_entitlements import has_permanent_cosmetic
from .cosmetics import cosmetic_allowed, invalidate_cosmetic_cache
from .event_cosmetics import redeem_event_cosmetic
from .models import (EventCosmeticOffer, EventCosmeticRedemption, TbCosmetico,
                     TbEventoConquista,
                     TbPersonagem, TbUsuarioCosmetico)
from .deploy_sync import MEMORY_MODELS, PRODUCTION_PRESERVED_MODELS


def setup_offer():
    user = get_user_model().objects.create_user(f'event-owner-{uuid4().hex[:8]}')
    other = get_user_model().objects.create_user(f'event-other-{uuid4().hex[:8]}')
    character = TbPersonagem.objects.create(
        dono=user, nome='Herói do evento', braseiros=40)
    cosmetic = TbCosmetico.objects.create(
        slug=f'moldura-evento-{uuid4().hex[:8]}', tipo='moldura',
        nome='Moldura do evento', css_class='frame-gold-trim',
        origem='loja_braseiro', escopo='ficha')
    now = timezone.now()
    offer = EventCosmeticOffer.objects.create(
        event_key='evento-outono', cosmetico=cosmetic, cost_braseiros=25,
        starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=1),
        active=True)
    invalidate_cosmetic_cache()
    return user, other, character, cosmetic, offer


class EventCosmeticShopTests(TestCase):
    def setUp(self):
        self.user, self.other, self.character, self.cosmetic, self.offer = setup_offer()
        self.url = reverse('event_cosmetic_shop')

    def tearDown(self):
        invalidate_cosmetic_cache()

    def test_player_sees_offer_and_redeems_once_even_after_event_ends(self):
        self.client.force_login(self.user)
        page = self.client.get(self.url)
        self.assertContains(page, 'Moldura do evento')
        self.assertContains(page, '40 braseiros')
        request_id = str(uuid4())
        form = {'offer': self.offer.pk, 'character': self.character.pk,
                'request_id': request_id, 'quoted_cost': 25}
        response = self.client.post(self.url, form)
        self.assertEqual(response.status_code, 302)
        redemption = EventCosmeticRedemption.objects.get(request_id=request_id)
        self.character.refresh_from_db()
        self.assertEqual(self.character.braseiros, 15)
        self.assertEqual(redemption.cost_braseiros, 25)
        self.assertEqual(redemption.balance_after, 15)
        fact = TbEventoConquista.objects.get(tipo='event_cosmetic_redeemed')
        self.assertEqual((fact.origem, fact.chave_origem, fact.agregado_id),
                         ('site_event_cosmetic', f'resgate:{request_id}', redemption.pk))
        self.assertEqual((fact.conta_id, fact.personagem_id),
                         (self.user.pk, self.character.pk))
        self.assertEqual(fact.payload_json,
                         {'offer_id': self.offer.pk, 'cosmetic_id': self.cosmetic.pk,
                          'cost_braseiros': 25})
        self.assertTrue(has_permanent_cosmetic(self.user, self.cosmetic))
        self.assertTrue(cosmetic_allowed(self.user, 'frame',
                                        self.cosmetic.slug.removeprefix('moldura-'), 'ficha'))
        self.assertContains(self.client.get(response['Location']), 'desbloqueado')
        self.assertContains(self.client.get(self.url), 'Você já possui')
        self.assertEqual(self.client.post(self.url, form).status_code, 302)
        self.assertEqual(EventCosmeticRedemption.objects.count(), 1)
        self.assertEqual(TbEventoConquista.objects.filter(
            tipo='event_cosmetic_redeemed').count(), 1)
        self.character.refresh_from_db()
        self.assertEqual(self.character.braseiros, 15)
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(active=False)
        TbUsuarioCosmetico.objects.filter(user=self.user, cosmetico=self.cosmetic).update(
            suspenso_em=timezone.now())
        self.assertTrue(cosmetic_allowed(self.user, 'frame',
                                        self.cosmetic.slug.removeprefix('moldura-'), 'ficha'))

    def test_free_manual_offer_can_be_claimed_without_character_and_stopped(self):
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(
            cost_braseiros=0, starts_at=None, ends_at=None)
        self.client.force_login(self.other)
        page = self.client.get(self.url)
        self.assertContains(page, 'Grátis')
        self.assertNotContains(page, 'name="character"')
        request_id = str(uuid4())
        form = {'offer': self.offer.pk, 'request_id': request_id, 'quoted_cost': 0}
        response = self.client.post(self.url, form)
        self.assertEqual(response.status_code, 302)
        redemption = EventCosmeticRedemption.objects.get(request_id=request_id)
        fact = TbEventoConquista.objects.get(tipo='event_cosmetic_redeemed')
        self.assertEqual((fact.conta_id, fact.personagem_id, fact.agregado_id),
                         (self.other.pk, None, redemption.pk))
        self.assertEqual(fact.payload_json['cost_braseiros'], 0)
        self.assertIsNone(redemption.character_id)
        self.assertIsNone(redemption.balance_after)
        self.assertEqual(redemption.cost_braseiros, 0)
        self.character.refresh_from_db()
        self.assertEqual(self.character.braseiros, 40)
        self.assertContains(self.client.get(response['Location']), 'desbloqueado gratuitamente')
        self.assertTrue(has_permanent_cosmetic(self.other, self.cosmetic))
        self.assertEqual(self.client.post(self.url, form).status_code, 302)
        self.assertEqual(EventCosmeticRedemption.objects.count(), 1)
        self.assertEqual(TbEventoConquista.objects.filter(
            tipo='event_cosmetic_redeemed').count(), 1)
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(active=False)
        self.assertNotContains(self.client.get(self.url), self.cosmetic.nome)
        self.assertTrue(has_permanent_cosmetic(self.other, self.cosmetic))
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(
            active=True, cost_braseiros=25)
        self.assertContains(self.client.get(self.url), 'Você já possui este cosmético.')
        self.assertTrue(has_permanent_cosmetic(self.other, self.cosmetic))

    def test_fact_write_failure_rolls_back_debit_redemption_and_entitlement(self):
        with patch('home.event_cosmetics.TbEventoConquista.objects.create',
                   side_effect=RuntimeError('event store unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'event store unavailable'):
                redeem_event_cosmetic(self.user, self.offer.pk, self.character.pk,
                                      uuid4(), 25)
        self.character.refresh_from_db()
        self.assertEqual(self.character.braseiros, 40)
        self.assertFalse(EventCosmeticRedemption.objects.exists())
        self.assertFalse(TbUsuarioCosmetico.objects.filter(
            user=self.user, cosmetico=self.cosmetic).exists())
        self.assertFalse(TbEventoConquista.objects.filter(
            tipo='event_cosmetic_redeemed').exists())

    def test_reused_request_key_cannot_claim_different_offer_price_or_character(self):
        self.client.force_login(self.user)
        request_id = str(uuid4())
        original = {'offer': self.offer.pk, 'character': self.character.pk,
                    'request_id': request_id, 'quoted_cost': 25}
        self.assertEqual(self.client.post(self.url, original).status_code, 302)
        other_character = TbPersonagem.objects.create(
            dono=self.user, nome='Segundo herói', braseiros=40)
        other_cosmetic = TbCosmetico.objects.create(
            slug=f'moldura-evento-{uuid4().hex[:8]}', tipo='moldura',
            nome='Outra moldura', origem='loja_braseiro', escopo='ficha')
        other_offer = EventCosmeticOffer.objects.create(
            event_key='evento-outono', cosmetico=other_cosmetic,
            cost_braseiros=25, active=True)
        for changed in ({'offer': other_offer.pk},
                        {'quoted_cost': 0},
                        {'character': other_character.pk}):
            form = dict(original, **changed)
            self.assertContains(self.client.post(self.url, form),
                                'Pedido inválido', status_code=409)
        self.assertEqual(EventCosmeticRedemption.objects.count(), 1)
        self.character.refresh_from_db()
        other_character.refresh_from_db()
        self.assertEqual((self.character.braseiros, other_character.braseiros),
                         (15, 40))
        self.client.force_login(self.other)
        self.assertContains(self.client.post(self.url, original),
                            'Pedido inválido', status_code=409)
        self.client.force_login(self.user)
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(
            active=False, cost_braseiros=0)
        self.assertEqual(self.client.post(self.url, original).status_code, 302)
        self.assertEqual(EventCosmeticRedemption.objects.count(), 1)

    def test_badge_offer_previews_image_or_glyph_without_broken_image(self):
        self.cosmetic.tipo = 'badge'
        self.cosmetic.asset_url = '/static/cosmetics/beta-spark.svg'
        self.cosmetic.save(update_fields=['tipo', 'asset_url'])
        self.client.force_login(self.other)
        page = self.client.get(self.url)
        self.assertContains(page, 'src="/static/cosmetics/beta-spark.svg"')
        self.cosmetic.asset_url = '*'
        self.cosmetic.save(update_fields=['asset_url'])
        page = self.client.get(self.url)
        self.assertContains(page, '>*</span>')
        self.assertNotContains(page, 'src="*"')

    def test_badge_offer_hides_unsafe_image_urls_without_losing_valid_images(self):
        self.cosmetic.tipo = 'badge'
        self.client.force_login(self.other)
        for asset in ('//external.example/badge.svg',
                      'https://user:secret@external.example/badge.svg',
                      'javascript:alert(1)'):
            with self.subTest(asset=asset):
                self.cosmetic.asset_url = asset
                self.cosmetic.save(update_fields=['tipo', 'asset_url'])
                page = self.client.get(self.url)
                self.assertNotIn(asset, page.content.decode())
        self.cosmetic.asset_url = 'https://external.example/badge.svg'
        self.cosmetic.save(update_fields=['asset_url'])
        self.assertContains(self.client.get(self.url),
                            'src="https://external.example/badge.svg"')

    def test_optional_start_and_end_dates_bound_only_when_set(self):
        now = timezone.now()
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(
            cost_braseiros=0, starts_at=now + timedelta(days=1), ends_at=None)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.url), self.cosmetic.nome)
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(
            starts_at=None, ends_at=now + timedelta(days=1))
        self.assertContains(self.client.get(self.url), self.cosmetic.nome)
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(
            ends_at=now - timedelta(seconds=1))
        self.assertNotContains(self.client.get(self.url), self.cosmetic.nome)

    def test_staff_can_configure_free_manual_offer_and_later_set_price(self):
        self.cosmetic.origem = 'evento_manual'
        self.cosmetic.save(update_fields=['origem'])
        staff = get_user_model().objects.create_superuser(
            f'event-staff-{uuid4().hex[:8]}', 'staff@example.com', 'password')
        self.client.force_login(staff)
        add_url = reverse('admin:home_eventcosmeticoffer_add')
        response = self.client.post(add_url, {
            'event_key': 'beta', 'cosmetico': self.cosmetic.pk,
            'cost_braseiros': 0, 'starts_at_0': '', 'starts_at_1': '',
            'ends_at_0': '', 'ends_at_1': '', 'active': 'on', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302, response.content.decode()[:1000])
        offer = EventCosmeticOffer.objects.get(event_key='beta', cosmetico=self.cosmetic)
        self.assertEqual((offer.cost_braseiros, offer.starts_at, offer.ends_at,
                          offer.active), (0, None, None, True))
        self.assertContains(self.client.get(self.url), 'Grátis')
        change_url = reverse('admin:home_eventcosmeticoffer_change', args=[offer.pk])
        response = self.client.post(change_url, {
            'event_key': 'beta', 'cosmetico': self.cosmetic.pk,
            'cost_braseiros': 25, 'starts_at_0': '', 'starts_at_1': '',
            'ends_at_0': '', 'ends_at_1': '', 'active': 'on', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302, response.content.decode()[:1000])
        offer.refresh_from_db()
        self.assertEqual(offer.cost_braseiros, 25)
        self.assertContains(self.client.get(self.url), '25 braseiros')

    def test_rejects_wrong_owner_low_balance_changed_price_and_closed_offer(self):
        self.client.force_login(self.other)
        form = {'offer': self.offer.pk, 'character': self.character.pk,
                'request_id': str(uuid4()), 'quoted_cost': 25}
        self.assertEqual(self.client.post(self.url, form).status_code, 409)
        self.client.force_login(self.user)
        form['quoted_cost'] = 20
        self.assertContains(self.client.post(self.url, form), 'O custo mudou', status_code=409)
        form['quoted_cost'] = 25
        TbPersonagem.objects.filter(pk=self.character.pk).update(braseiros=20)
        self.assertContains(self.client.post(self.url, form),
                            'braseiros suficientes', status_code=409)
        TbPersonagem.objects.filter(pk=self.character.pk).update(braseiros=40)
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(
            ends_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post(self.url, form).status_code, 409)
        self.assertFalse(EventCosmeticRedemption.objects.exists())
        self.character.refresh_from_db()
        self.assertEqual(self.character.braseiros, 40)

    def test_paid_offer_lists_only_characters_with_enough_braseiros(self):
        poor = TbPersonagem.objects.create(
            dono=self.user, nome='Herói sem saldo', braseiros=24)
        self.client.force_login(self.user)
        page = self.client.get(self.url)
        self.assertContains(page, f'<option value="{self.character.pk}">', html=False)
        self.assertNotIn(f'<option value="{poor.pk}">', page.content.decode())
        self.assertContains(page, 'Resgatar cosmético')

    def test_unaffordable_offer_explains_balance_without_blocking_free_claim(self):
        TbPersonagem.objects.filter(pk=self.character.pk).update(braseiros=24)
        self.client.force_login(self.user)
        page = self.client.get(self.url)
        self.assertContains(page, 'Nenhum personagem tem 25 braseiros')
        self.assertNotIn('name="character"', page.content.decode())
        self.assertNotIn('Resgatar cosmético', page.content.decode())
        EventCosmeticOffer.objects.filter(pk=self.offer.pk).update(cost_braseiros=0)
        free_page = self.client.get(self.url)
        self.assertContains(free_page, 'Resgatar cosmético')
        self.assertNotIn('name="character"', free_page.content.decode())

    def test_already_owned_right_is_not_charged_and_receipt_is_private(self):
        TbUsuarioCosmetico.objects.create(
            user=self.user, cosmetico=self.cosmetic, origem='conquista:outra')
        form = {'offer': self.offer.pk, 'character': self.character.pk,
                'request_id': str(uuid4()), 'quoted_cost': 25}
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url, form).status_code, 409)
        TbUsuarioCosmetico.objects.filter(user=self.user, cosmetico=self.cosmetic).delete()
        self.assertEqual(self.client.post(self.url, form).status_code, 302)
        receipt = EventCosmeticRedemption.objects.get()
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.url + f'?resgate={receipt.pk}'),
                               'desbloqueado')

    def test_inventory_failure_rolls_back_debit_and_offer_remains_local_content(self):
        self.assertIn('EventCosmeticOffer', PRODUCTION_PRESERVED_MODELS)
        self.assertIn('EventCosmeticRedemption', MEMORY_MODELS)
        with patch.object(TbUsuarioCosmetico.objects, 'create',
                          side_effect=RuntimeError('inventory unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'inventory unavailable'):
                redeem_event_cosmetic(
                    self.user, self.offer.pk, self.character.pk, uuid4(), 25)
        self.character.refresh_from_db()
        self.assertEqual(self.character.braseiros, 40)
        self.assertFalse(EventCosmeticRedemption.objects.exists())

    def test_superuser_can_open_offer_form_but_redemption_cannot_be_created(self):
        staff = get_user_model().objects.create_superuser(
            f'event-staff-{uuid4().hex[:8]}', 'staff@example.com', 'password')
        self.client.force_login(staff)
        offer_form = self.client.get(reverse('admin:home_eventcosmeticoffer_add'))
        self.assertEqual(offer_form.status_code, 200)
        self.assertContains(offer_form, 'cost_braseiros')
        self.assertEqual(self.client.get(
            reverse('admin:home_eventcosmeticredemption_add')).status_code, 403)


class EventCosmeticConcurrencyTests(TransactionTestCase):
    def test_parallel_free_claims_grant_once_without_character(self):
        self.assertEqual(connection.vendor, 'postgresql')
        user, _, _, cosmetic, offer = setup_offer()
        EventCosmeticOffer.objects.filter(pk=offer.pk).update(
            cost_braseiros=0, starts_at=None, ends_at=None)

        def claim():
            close_old_connections()
            try:
                try:
                    redeem_event_cosmetic(user, offer.pk, None, uuid4(), 0)
                    return 'created'
                except ValueError as exc:
                    return str(exc)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sorted(outcomes), ['created', 'ja_possui'])
        self.assertEqual(EventCosmeticRedemption.objects.filter(offer=offer).count(), 1)
        self.assertTrue(has_permanent_cosmetic(user, cosmetic))
        invalidate_cosmetic_cache()

    def test_parallel_retries_charge_only_once(self):
        self.assertEqual(connection.vendor, 'postgresql')
        user, _, character, _, offer = setup_offer()
        request_id = uuid4()

        def redeem():
            close_old_connections()
            try:
                return redeem_event_cosmetic(
                    user, offer.pk, character.pk, request_id, 25)[1]
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: redeem(), range(2)))
        self.assertEqual(sorted(outcomes), [False, True])
        character.refresh_from_db()
        self.assertEqual(character.braseiros, 15)
        self.assertEqual(EventCosmeticRedemption.objects.count(), 1)
        invalidate_cosmetic_cache()

    def test_parallel_distinct_requests_cannot_buy_same_item_twice(self):
        self.assertEqual(connection.vendor, 'postgresql')
        user, _, character, _, offer = setup_offer()

        def redeem():
            close_old_connections()
            try:
                try:
                    redeem_event_cosmetic(user, offer.pk, character.pk, uuid4(), 25)
                    return 'created'
                except ValueError as exc:
                    return str(exc)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: redeem(), range(2)))
        self.assertEqual(sorted(outcomes), ['created', 'ja_possui'])
        character.refresh_from_db()
        self.assertEqual(character.braseiros, 15)
        self.assertEqual(EventCosmeticRedemption.objects.count(), 1)
        invalidate_cosmetic_cache()


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright.')
class EventCosmeticBrowserTests(StaticLiveServerTestCase):
    def test_insufficient_balance_explained_in_mobile_and_desktop_shop(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        user, _, character, cosmetic, offer = setup_offer()
        TbPersonagem.objects.filter(pk=character.pk).update(braseiros=24)
        self.client.force_login(user)
        env = dict(os.environ, EVENT_SHOP_ORIGIN=self.live_server_url,
                   EVENT_SHOP_PATH=reverse('event_cosmetic_shop'),
                   EVENT_SHOP_SESSION=self.client.cookies['sessionid'].value,
                   EVENT_SHOP_INSUFFICIENT='1')
        result = subprocess.run(
            ['node', str(Path(__file__).parent / 'js_tests/event_cosmetics.e2e.cjs')],
            env=env, capture_output=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(EventCosmeticRedemption.objects.filter(offer=offer).exists())
        self.assertFalse(has_permanent_cosmetic(user, cosmetic))
        character.refresh_from_db()
        self.assertEqual(character.braseiros, 24)
        invalidate_cosmetic_cache()

    def test_mobile_shop_redeems_and_shows_owned_state(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        user, _, character, cosmetic, offer = setup_offer()
        self.client.force_login(user)
        env = dict(os.environ, EVENT_SHOP_ORIGIN=self.live_server_url,
                   EVENT_SHOP_PATH=reverse('event_cosmetic_shop'),
                   EVENT_SHOP_SESSION=self.client.cookies['sessionid'].value)
        result = subprocess.run(
            ['node', str(Path(__file__).parent / 'js_tests/event_cosmetics.e2e.cjs')],
            env=env, capture_output=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        character.refresh_from_db()
        self.assertEqual(character.braseiros, 15)
        self.assertTrue(has_permanent_cosmetic(user, cosmetic))
        self.assertEqual(EventCosmeticRedemption.objects.filter(offer=offer).count(), 1)
        invalidate_cosmetic_cache()

    def test_free_mobile_shop_without_character(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        _, user, _, cosmetic, offer = setup_offer()
        cosmetic.origem = 'evento_manual'
        cosmetic.save(update_fields=['origem'])
        EventCosmeticOffer.objects.filter(pk=offer.pk).update(
            cost_braseiros=0, starts_at=None, ends_at=None)
        self.client.force_login(user)
        env = dict(os.environ, EVENT_SHOP_ORIGIN=self.live_server_url,
                   EVENT_SHOP_PATH=reverse('event_cosmetic_shop'),
                   EVENT_SHOP_SESSION=self.client.cookies['sessionid'].value,
                   EVENT_SHOP_FREE='1')
        result = subprocess.run(
            ['node', str(Path(__file__).parent / 'js_tests/event_cosmetics.e2e.cjs')],
            env=env, capture_output=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        redemption = EventCosmeticRedemption.objects.get(offer=offer)
        self.assertEqual(redemption.user_id, user.pk)
        self.assertIsNone(redemption.character_id)
        self.assertTrue(has_permanent_cosmetic(user, cosmetic))
        invalidate_cosmetic_cache()
