import json
import os
from pathlib import Path
import subprocess
import unittest
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .cosmetic_entitlements import has_permanent_cosmetic
from .cosmetics import catalog_options, cosmetic_allowed
from .permissions import colab_tier
from .badges import badges_concedidas, perfil_badges_batch, titulos_disponiveis
from .models import (AsaasCheckoutOrder, CosmeticCheckoutOffer,
                     CosmeticCheckoutPurchase, EventCosmeticOffer,
                     EventCosmeticRedemption, TbCosmetico, TbUsuarioCosmetico,
                     UserProfile)
from .views import (AsaasAPIError, _validated_badges_destaque,
                    _validated_titulo_equipado, _appearance_context)


@override_settings(ASAAS_WEBHOOK_TOKEN='test-webhook-token')
class CosmeticCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('buyer', email='buyer@example.test')
        self.other = get_user_model().objects.create_user('other', email='other@example.test')
        self.cosmetic = TbCosmetico.objects.create(
            slug='moldura-paga', tipo='moldura', nome='Moldura Paga',
            origem='evento_manual', animado=True,
        )
        self.offer = CosmeticCheckoutOffer.objects.create(
            cosmetico=self.cosmetic, amount=Decimal('12.34'), active=True,
        )
        self.client.force_login(self.user)

    def test_profile_catalog_shows_verified_sources_without_leaking_other_accounts(self):
        from uuid import uuid4

        event_cosmetic = TbCosmetico.objects.create(
            slug='tema-evento-teste', tipo='tema', nome='Tema Evento',
            origem='evento_manual', escopo='perfil')
        offer = EventCosmeticOffer.objects.create(
            event_key='teste-origem', cosmetico=event_cosmetic, cost_braseiros=0,
            active=False)
        EventCosmeticRedemption.objects.create(
            request_id=uuid4(), offer=offer, user=self.user,
            cosmetico=event_cosmetic, cost_braseiros=0)
        order = AsaasCheckoutOrder.objects.create(
            user=self.user, email=self.user.email,
            product_code='cosmetic:' + self.cosmetic.slug,
            mode='single', amount=Decimal('12.34'))
        CosmeticCheckoutPurchase.objects.create(
            order=order, beneficiary=self.user, cosmetico=self.cosmetic,
            slug=self.cosmetic.slug, name=self.cosmetic.nome,
            granted_at=timezone.now())
        TbUsuarioCosmetico.objects.create(
            user=self.user, cosmetico=event_cosmetic, origem='evento:123',
            suspenso_em=timezone.now())
        effect = TbCosmetico.objects.create(
            slug='efeito-conquista-teste', tipo='efeito', nome='Efeito Conquista',
            origem='conquista', escopo='perfil')
        TbUsuarioCosmetico.objects.create(
            user=self.user, cosmetico=effect,
            origem='conquista:chave-interna')
        own = self.client.get('/perfil/')
        self.assertEqual(own.status_code, 200)
        self.assertContains(own, 'Tema Evento')
        self.assertContains(own, 'Resgate de evento')
        self.assertContains(own, 'Moldura Paga (Compra confirmada)')
        self.assertContains(own, 'Efeito Conquista (Conquista)')
        self.assertNotContains(own, 'evento:123')
        self.assertNotContains(own, 'chave-interna')
        self.assertEqual(next(item['posse_origem'] for item in
                              own.context['appearance_theme_options']
                              if item['key'] == 'evento-teste'), 'Resgate de evento')
        self.client.force_login(self.other)
        other = self.client.get('/perfil/')
        self.assertEqual(other.status_code, 200)
        self.assertNotContains(other, 'Resgate de evento')
        self.assertNotContains(other, 'Compra confirmada')
        self.assertEqual(next(item['estado'] for item in
                              other.context['appearance_theme_options']
                              if item['key'] == 'evento-teste'), 'bloqueado')

    def test_profile_catalog_labels_inventory_grant_without_exposing_origin_key(self):
        TbUsuarioCosmetico.objects.create(
            user=self.user, cosmetico=self.cosmetic,
            origem='conquista:segredo-interno')
        page = self.client.get('/perfil/')
        self.assertContains(page, 'Moldura Paga (Conquista)')
        self.assertNotContains(page, 'segredo-interno')

    @patch('home.permissions.colab_tier')
    def test_colab_catalog_and_display_expire_without_erasing_preference(self, tier):
        borrowed = TbCosmetico.objects.create(
            slug='moldura-emprestada', tipo='moldura', nome='Emprestada',
            origem='colaborador', requer_plano='marques', escopo='perfil')
        tier.return_value = 'conde'
        self.assertFalse(cosmetic_allowed(self.user, 'frame', 'emprestada', 'perfil'))
        self.assertEqual(_appearance_context(frame='emprestada', user=self.user)['frame_key'], 'none')
        tier.return_value = 'marques'
        self.assertTrue(cosmetic_allowed(self.user, 'frame', 'emprestada', 'perfil'))
        self.assertEqual(_appearance_context(frame='emprestada', user=self.user)['frame_key'], 'emprestada')
        self.assertEqual(next(x['estado'] for x in catalog_options(
            self.user, 'moldura', 'perfil') if x['key'] == 'emprestada'), 'possui')
        self.assertEqual(next(x['posse_origem'] for x in catalog_options(
            self.user, 'moldura', 'perfil') if x['key'] == 'emprestada'), 'Acesso Colab')
        tier.return_value = None
        TbUsuarioCosmetico.objects.create(
            user=self.user, cosmetico=borrowed, origem='colaborador')
        self.assertEqual(_appearance_context(frame='emprestada', user=self.user)['frame_key'], 'none')
        self.assertEqual(next(x['estado'] for x in catalog_options(
            self.user, 'moldura', 'perfil') if x['key'] == 'emprestada'), 'bloqueado')
        self.assertEqual(next(x['posse_origem'] for x in catalog_options(
            self.user, 'moldura', 'perfil') if x['key'] == 'emprestada'), '')
        profile = UserProfile.objects.get_or_create(user=self.user)[0]
        profile.avatar_frame = 'emprestada'
        profile.save(update_fields=['avatar_frame'])
        public = self.client.get('/perfil/buyer/')
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.context['appearance']['frame_key'], 'none')
        profile.refresh_from_db()
        self.assertEqual(profile.avatar_frame, 'emprestada')

    @patch('home.permissions.colab_tier', return_value=None)
    def test_paid_origin_survives_colab_expiration(self, _tier):
        borrowed = TbCosmetico.objects.create(
            slug='moldura-colab-paga', tipo='moldura', nome='Colab Paga',
            origem='colaborador', requer_plano='conde', escopo='perfil')
        order = AsaasCheckoutOrder.objects.create(
            user=self.user, email=self.user.email,
            product_code='cosmetic:' + borrowed.slug,
            mode='single', amount=Decimal('12.34'))
        from django.utils import timezone
        CosmeticCheckoutPurchase.objects.create(
            order=order, beneficiary=self.user, cosmetico=borrowed,
            slug=borrowed.slug, name=borrowed.nome, granted_at=timezone.now())
        self.assertTrue(cosmetic_allowed(self.user, 'frame', 'colab-paga', 'perfil'))
        self.assertEqual(_appearance_context(frame='colab-paga', user=self.user)['frame_key'], 'colab-paga')

    @patch('home.models.BotTransaction.objects.filter')
    @patch('home.models.BotMember.objects.filter')
    def test_colab_right_requires_linked_discord_member(self, members, transactions):
        profile = UserProfile.objects.get_or_create(user=self.user)[0]
        self.assertIsNone(colab_tier(self.user))
        members.assert_not_called()
        profile.discord_user_id = '123456789'
        profile.save(update_fields=['discord_user_id'])
        self.user.refresh_from_db()
        members.return_value.values_list.return_value.first.return_value = 'member@example.test'
        transactions.return_value.values_list.return_value = ['colaborador-conde-1m', 'colaborador-duque-3m']
        self.assertEqual(colab_tier(self.user), 'duque')
        self.assertEqual(members.call_args.kwargs['discordUserId'], '123456789')
        self.assertEqual(transactions.call_args.kwargs['email__iexact'], 'member@example.test')
        members.return_value.values_list.return_value.first.return_value = None
        self.assertIsNone(colab_tier(self.user))

    @override_settings(DISCORD_OAUTH_CLIENT_ID='test-client')
    @patch('home.permissions.colab_tier')
    def test_profile_selectors_match_colab_right_and_offer_discord_link(self, tier):
        for slug, kind in (('tema-colab-theme', 'tema'),
                           ('moldura-colab-frame', 'moldura'),
                           ('efeito-colab-effect', 'efeito')):
            TbCosmetico.objects.create(
                slug=slug, tipo=kind, nome=slug,
                origem='colaborador', requer_plano='conde', escopo='perfil')
        profile = UserProfile.objects.get_or_create(user=self.user)[0]
        profile.avatar_frame = 'colab-frame'
        profile.save(update_fields=['avatar_frame'])
        tier.return_value = None
        blocked = self.client.get('/perfil/')
        self.assertEqual(blocked.status_code, 200)
        self.assertEqual(blocked.context['appearance']['frame_key'], 'none')
        self.assertTrue(next(x['locked'] for x in blocked.context['appearance_theme_options']
                             if x['key'] == 'colab-theme'))
        self.assertTrue(next(x['locked'] for x in blocked.context['appearance_effect_options']
                             if x['key'] == 'colab-effect'))
        self.assertIn('bonfire', [x['key'] for x in blocked.context['appearance_theme_options']])
        self.assertIn('none', [x['key'] for x in blocked.context['appearance_frame_options']])
        self.assertTrue(blocked.context['colab_cosmetic_locked'])
        self.assertContains(blocked, 'Cosméticos Colab exigem assinatura ativa')
        self.assertContains(blocked, 'Conectar Discord')
        tier.return_value = 'conde'
        unlocked = self.client.get('/perfil/')
        self.assertEqual(unlocked.context['appearance']['frame_key'], 'colab-frame')
        self.assertFalse(next(x['locked'] for x in unlocked.context['appearance_theme_options']
                              if x['key'] == 'colab-theme'))
        self.assertFalse(next(x['locked'] for x in unlocked.context['appearance_effect_options']
                              if x['key'] == 'colab-effect'))
        self.assertFalse(unlocked.context['colab_cosmetic_locked'])
        self.assertNotContains(unlocked, 'Cosméticos Colab exigem assinatura ativa')

    @patch('home.permissions.colab_tier')
    def test_profile_edit_preserves_expired_colab_choices_until_discarded(self, tier):
        for slug, kind in (('tema-emprestado', 'tema'),
                           ('moldura-emprestada', 'moldura'),
                           ('efeito-emprestado', 'efeito')):
            TbCosmetico.objects.create(
                slug=slug, tipo=kind, nome=slug, origem='colaborador',
                requer_plano='conde', escopo='perfil')
        profile = UserProfile.objects.get_or_create(user=self.user)[0]
        profile.profile_theme = 'emprestado'
        profile.avatar_frame = 'emprestada'
        profile.profile_effect = 'emprestado'
        profile.save(update_fields=['profile_theme', 'avatar_frame', 'profile_effect'])
        tier.return_value = None
        initial = self.client.get('/perfil/')
        self.assertTrue(initial.context['locked_theme_preference'])
        self.assertTrue(initial.context['locked_frame_preference'])
        self.assertTrue(initial.context['locked_effect_preference'])
        self.assertContains(initial, 'clear_locked_avatar_frame')
        data = {
            'action': 'update_profile', 'username': self.user.username,
            'email': self.user.email, 'bio': 'Bio atualizada',
            'profile_theme': 'bonfire', 'avatar_frame': 'none',
            'profile_effect': 'none',
        }
        response = self.client.post('/perfil/', data)
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.bio, 'Bio atualizada')
        self.assertEqual((profile.profile_theme, profile.avatar_frame, profile.profile_effect),
                         ('emprestado', 'emprestada', 'emprestado'))
        response = self.client.post('/perfil/', dict(data, clear_locked_avatar_frame='on'))
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertIsNone(profile.avatar_frame)
        self.assertEqual((profile.profile_theme, profile.profile_effect),
                         ('emprestado', 'emprestado'))
        tier.return_value = 'conde'
        public = self.client.get('/perfil/buyer/')
        self.assertEqual(public.context['appearance']['theme_key'], 'emprestado')
        self.assertEqual(public.context['appearance']['frame_key'], 'none')
        self.assertEqual(public.context['appearance']['effect_key'], 'emprestado')
        tier.return_value = None
        self.client.post('/perfil/', dict(
            data, clear_locked_profile_theme='on', clear_locked_profile_effect='on'))
        profile.refresh_from_db()
        self.assertEqual(profile.profile_theme, 'bonfire')
        self.assertIsNone(profile.profile_effect)

    @patch('home.views._asaas_api_request', return_value={'id': 'checkout_1'})
    def test_order_freezes_offer_and_reuses_checkout(self, api):
        url = reverse('cosmetic_checkout')
        storefront = self.client.get(url)
        self.assertContains(storefront, 'Comprar cosmético')
        self.assertNotContains(storefront, 'Aquisições em preparação')
        first = self.client.post(url, {'slug': self.cosmetic.slug})
        self.offer.amount = Decimal('99.99')
        self.offer.save()
        second = self.client.post(url, {'slug': self.cosmetic.slug})
        purchase = CosmeticCheckoutPurchase.objects.get()
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first['Location'], second['Location'])
        self.assertEqual(purchase.order.amount, Decimal('12.34'))
        self.assertEqual(purchase.beneficiary, self.user)
        self.assertEqual(api.call_args.args[2]['externalReference'], purchase.order.external_reference)
        api.assert_called_once()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(first['Location']).status_code, 404)

    @patch('home.views._asaas_api_request', side_effect=AsaasAPIError('timeout'))
    def test_timeout_does_not_create_second_remote_checkout(self, api):
        url = reverse('cosmetic_checkout')
        self.client.post(url, {'slug': self.cosmetic.slug})
        self.client.post(url, {'slug': self.cosmetic.slug})
        self.assertEqual(AsaasCheckoutOrder.objects.count(), 1)
        api.assert_called_once()

    @patch('home.views._asaas_api_get')
    def test_verified_webhook_grants_once_and_keeps_permanent_right(self, api_get):
        order = self._order()
        api_get.return_value = self._payment(order)
        self._webhook(order)
        self._webhook(order)
        purchase = CosmeticCheckoutPurchase.objects.get(order=order)
        self.assertIsNotNone(purchase.granted_at)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(user=self.user, cosmetico=self.cosmetic).count(), 1)
        inventory = TbUsuarioCosmetico.objects.get(user=self.user, cosmetico=self.cosmetic)
        from django.utils import timezone
        inventory.suspenso_em = timezone.now()
        inventory.save()
        self.assertTrue(has_permanent_cosmetic(self.user, self.cosmetic))
        self.assertTrue(cosmetic_allowed(self.user, 'moldura', 'paga', 'perfil'))
        self.assertFalse(cosmetic_allowed(self.other, 'moldura', 'paga', 'perfil'))
        self.assertEqual(next(item['estado'] for item in catalog_options(
            self.user, 'moldura', 'perfil') if item['key'] == 'paga'), 'possui')
        order.refresh_from_db()
        self.assertEqual(order.status, AsaasCheckoutOrder.Status.PAID)
        receipt = self.client.get(reverse('cosmetic_checkout_status', args=[order.pk]))
        self.assertContains(receipt, reverse('profile') + '#perfil-aparencia')
        self.assertContains(self.client.get(reverse('profile')), 'id="perfil-aparencia"')

    def test_paid_ficha_only_receipt_selects_character_instead_of_profile(self):
        self.cosmetic.escopo = 'ficha'
        self.cosmetic.save(update_fields=['escopo'])
        order = self._order()
        order.status = AsaasCheckoutOrder.Status.PAID
        order.save(update_fields=['status'])
        purchase = CosmeticCheckoutPurchase.objects.get(order=order)
        purchase.granted_at = timezone.now()
        purchase.save(update_fields=['granted_at'])
        receipt = self.client.get(reverse('cosmetic_checkout_status', args=[order.pk]))
        self.assertContains(receipt, 'href="' + reverse('personagens') + '">Escolher ficha</a>')
        self.assertNotContains(receipt, 'href="' + reverse('profile') + '">Personalizar meu perfil</a>')

    def test_paid_title_receipt_opens_profile_insignias(self):
        self.cosmetic.tipo = 'titulo'
        self.cosmetic.save(update_fields=['tipo'])
        order = self._order()
        order.status = AsaasCheckoutOrder.Status.PAID
        order.save(update_fields=['status'])
        purchase = CosmeticCheckoutPurchase.objects.get(order=order)
        purchase.granted_at = timezone.now()
        purchase.save(update_fields=['granted_at'])
        receipt = self.client.get(reverse('cosmetic_checkout_status', args=[order.pk]))
        self.assertContains(receipt, reverse('profile') + '#perfil-insignias')
        self.assertContains(self.client.get(reverse('profile')), 'id="perfil-insignias"')

    def test_paid_title_and_badge_remain_usable_after_inventory_suspension(self):
        from django.utils import timezone
        title = TbCosmetico.objects.create(
            slug='titulo-pago', tipo='titulo', nome='Título Pago',
            origem='evento_manual', escopo='perfil')
        badge = TbCosmetico.objects.create(
            slug='badge-paga', tipo='badge', nome='Insígnia Paga',
            origem='evento_manual', escopo='perfil')
        for item in (title, badge):
            order = AsaasCheckoutOrder.objects.create(
                user=self.user, email=self.user.email,
                product_code='cosmetic:' + item.slug,
                mode='single', amount=Decimal('12.34'))
            CosmeticCheckoutPurchase.objects.create(
                order=order, beneficiary=self.user, cosmetico=item,
                slug=item.slug, name=item.nome, granted_at=timezone.now())
            TbUsuarioCosmetico.objects.create(
                user=self.user, cosmetico=item, origem='evento_manual',
                suspenso_em=timezone.now())

        self.assertEqual(_validated_titulo_equipado(self.user, title.slug), title.slug)
        self.assertEqual(_validated_titulo_equipado(self.other, title.slug), '')
        self.assertIn(title.slug, [item['slug'] for item in titulos_disponiveis(self.user)])
        self.assertEqual(_validated_badges_destaque(self.user, [badge.slug]), [badge.slug])
        self.assertEqual(_validated_badges_destaque(self.other, [badge.slug]), [])
        self.assertIn(badge.slug, [item['slug'] for item in badges_concedidas(self.user)])
        self.assertEqual(badges_concedidas(self.other), [])
        profile = UserProfile.objects.get_or_create(user=self.user)[0]
        profile.titulo_equipado = title.slug
        profile.badges_destaque = [badge.slug]
        profile.save(update_fields=['titulo_equipado', 'badges_destaque'])
        users = list(get_user_model().objects.filter(
            pk__in=[self.user.pk, self.other.pk]).select_related('profile'))
        cards = perfil_badges_batch(users)
        self.assertEqual(cards[self.user.pk]['titulo']['slug'], title.slug)
        self.assertIn(badge.slug, [item['slug'] for item in cards[self.user.pk]['badges']])
        self.assertIsNone(cards[self.other.pk]['titulo'])

    @patch('home.views._asaas_api_get')
    def test_incomplete_and_wrong_value_never_grant(self, api_get):
        order = self._order()
        api_get.return_value = None
        self.assertEqual(self._webhook(order).status_code, 503)
        api_get.return_value = self._payment(order, value='8.00')
        self.assertEqual(self._webhook(order).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, AsaasCheckoutOrder.Status.VALUE_MISMATCH)
        self.assertFalse(has_permanent_cosmetic(self.user, self.cosmetic))
        self.assertFalse(cosmetic_allowed(self.user, 'moldura', 'paga', 'perfil'))

    @patch('home.views._asaas_api_get')
    def test_unauthorized_or_non_settled_event_never_grants(self, api_get):
        order = self._order()
        api_get.return_value = self._payment(order)
        self.assertEqual(self._webhook(order, token='wrong').status_code, 401)
        self.assertFalse(api_get.called)
        api_get.return_value = {**self._payment(order), 'status': 'PENDING'}
        self.assertEqual(self._webhook(order).status_code, 503)
        self.assertFalse(has_permanent_cosmetic(self.user, self.cosmetic))

    def test_inactive_or_missing_offer_does_not_create_order(self):
        self.offer.active = False
        self.offer.save(update_fields=['active'])
        self.assertEqual(self.client.post(reverse('cosmetic_checkout'),
                                          {'slug': self.cosmetic.slug}).status_code, 400)
        self.assertFalse(AsaasCheckoutOrder.objects.exists())

    def _order(self):
        order = AsaasCheckoutOrder.objects.create(
            user=self.user, email=self.user.email, product_code='cosmetic:moldura-paga',
            mode='single', amount=Decimal('12.34'),
        )
        CosmeticCheckoutPurchase.objects.create(
            order=order, beneficiary=self.user, cosmetico=self.cosmetic,
            slug=self.cosmetic.slug, name=self.cosmetic.nome,
        )
        return order

    def _payment(self, order, value='12.34'):
        return {'id': 'pay_cosmetic', 'externalReference': order.external_reference,
                'value': value, 'status': 'RECEIVED'}

    def _webhook(self, order, token='test-webhook-token'):
        return self.client.post(reverse('asaas_webhook'),
                                data=json.dumps({'id': 'evt_1', 'event': 'PAYMENT_RECEIVED',
                                                 'payment': {'id': 'pay_cosmetic',
                                                             'externalReference': order.external_reference}}),
                                content_type='application/json', HTTP_ASAAS_ACCESS_TOKEN=token)


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright.')
class CosmeticProfileSourceBrowserTests(StaticLiveServerTestCase):
    def test_source_labels_fit_mobile_and_desktop_selectors(self):
        from uuid import uuid4

        user = get_user_model().objects.create_user('profile-source-visual')
        theme = TbCosmetico.objects.create(
            slug='tema-evento-visual', tipo='tema', nome='Tema do evento',
            origem='evento_manual', escopo='perfil')
        offer = EventCosmeticOffer.objects.create(
            event_key='visual-event', cosmetico=theme, cost_braseiros=0,
            active=False)
        EventCosmeticRedemption.objects.create(
            request_id=uuid4(), offer=offer, user=user,
            cosmetico=theme, cost_braseiros=0)
        frame = TbCosmetico.objects.create(
            slug='moldura-paga-visual', tipo='moldura', nome='Moldura paga',
            origem='evento_manual', escopo='perfil')
        order = AsaasCheckoutOrder.objects.create(
            user=user, email='visual@example.test',
            product_code='cosmetic:' + frame.slug,
            mode='single', amount=Decimal('12.34'))
        CosmeticCheckoutPurchase.objects.create(
            order=order, beneficiary=user, cosmetico=frame,
            slug=frame.slug, name=frame.nome, granted_at=timezone.now())
        self.client.force_login(user)
        env = dict(os.environ, PROFILE_SOURCE_ORIGIN=self.live_server_url,
                   PROFILE_SOURCE_SESSION=self.client.cookies['sessionid'].value)
        result = subprocess.run(
            ['node', str(Path(__file__).parent / 'js_tests/cosmetic_profile_source.e2e.cjs')],
            env=env, capture_output=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
