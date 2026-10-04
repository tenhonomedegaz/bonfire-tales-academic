import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .cosmetic_entitlements import has_permanent_cosmetic
from .cosmetics import catalog_options, cosmetic_allowed
from .badges import badges_concedidas, perfil_badges_batch, titulos_disponiveis
from .models import (AsaasCheckoutOrder, CosmeticCheckoutOffer,
                     CosmeticCheckoutPurchase, TbCosmetico, TbUsuarioCosmetico,
                     UserProfile)
from .views import (AsaasAPIError, _validated_badges_destaque,
                    _validated_titulo_equipado)


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

    @patch('home.views._asaas_api_request', return_value={'id': 'checkout_1'})
    def test_order_freezes_offer_and_reuses_checkout(self, api):
        url = reverse('cosmetic_checkout')
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
