import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import patch
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from home.models import AsaasCheckoutOrder, BotMember, BotTransaction
from home.views import _asaas_map_transacao


class AsaasPaymentMappingTests(SimpleTestCase):
    def test_external_reference_has_priority(self):
        result = _asaas_map_transacao({
            'id': 'pay_1',
            'externalReference': 'colaborador-conde-3m',
            'paymentLink': '8875kbi9lmlnbpbs',
        }, 'PAYMENT_RECEIVED')

        self.assertEqual(result['subscriptionPlan'], 'colaborador-conde-3m')
        self.assertEqual(result['subscriptionPeriod'], 'QUARTERLY')
        self.assertEqual(result['_meses'], 3)

    def test_payment_link_is_used_as_fallback(self):
        result = _asaas_map_transacao({
            'id': 'pay_2',
            'paymentLink': 'hojk0lk7zssxsa8w',
        }, 'PAYMENT_CONFIRMED')

        self.assertEqual(result['subscriptionPlan'], 'colaborador-duque-12m')
        self.assertEqual(result['subscriptionPeriod'], 'YEARLY')
        self.assertEqual(result['_meses'], 12)

    def test_payment_link_object_is_supported(self):
        result = _asaas_map_transacao({
            'id': 'pay_3',
            'paymentLink': {'id': 'seyli68v427zvbds'},
        }, 'PAYMENT_RECEIVED')

        self.assertEqual(result['subscriptionPlan'], 'token-boost')

    def test_unknown_payment_stays_unmapped(self):
        result = _asaas_map_transacao({
            'id': 'pay_4',
            'paymentLink': 'link-desconhecido',
        }, 'PAYMENT_RECEIVED')

        self.assertEqual(result['subscriptionPlan'], '')

    def test_order_product_overrides_opaque_external_reference(self):
        result = _asaas_map_transacao({
            'id': 'pay_5',
            'externalReference': 'bonfire_order:00000000-0000-0000-0000-000000000001',
        }, 'PAYMENT_RECEIVED', 'token-superboost')

        self.assertEqual(result['subscriptionPlan'], 'token-superboost')


class AsaasCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='checkout-user',
            email='checkout@example.com',
            password='test-password',
        )
        self.user.profile.email_verified = True
        self.user.profile.discord_user_id = '123456789'
        self.user.profile.discord_username = 'Checkout User'
        self.user.profile.save()
        self.client.force_login(self.user)

    def test_ready_account_renders_authenticated_checkout_forms(self):
        response = self.client.get(reverse('colaborador'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('colaborador_checkout'))
        self.assertContains(response, 'name="product" value="token-boost"')
        self.assertNotContains(response, 'Use o mesmo e-mail')

    @patch('home.views._asaas_api_request')
    def test_creates_linked_checkout_with_prefilled_email(self, api_request):
        api_request.return_value = {'id': 'checkout-test-id'}

        response = self.client.post(reverse('colaborador_checkout'), {
            'product': 'token-boost',
            'mode': 'single',
        })
        repeated_response = self.client.post(reverse('colaborador_checkout'), {
            'product': 'token-boost',
            'mode': 'single',
        })

        self.assertRedirects(
            response,
            'https://asaas.com/checkoutSession/show?id=checkout-test-id',
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            repeated_response,
            'https://asaas.com/checkoutSession/show?id=checkout-test-id',
            fetch_redirect_response=False,
        )
        order = AsaasCheckoutOrder.objects.get()
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.discord_user_id, '123456789')
        self.assertEqual(order.email, self.user.email)
        self.assertEqual(order.product_code, 'token-boost')
        self.assertEqual(order.amount, Decimal('19.90'))
        payload = api_request.call_args.args[2]
        self.assertEqual(payload['externalReference'], order.external_reference)
        self.assertEqual(payload['customerData']['email'], self.user.email)
        self.assertEqual(payload['chargeTypes'], ['DETACHED'])
        api_request.assert_called_once()

    @patch('home.views._asaas_api_request')
    def test_email_only_account_can_start_checkout(self, api_request):
        api_request.return_value = {'id': 'checkout-email-id'}
        self.user.profile.discord_user_id = None
        self.user.profile.save(update_fields=['discord_user_id'])

        response = self.client.post(reverse('colaborador_checkout'), {
            'product': 'token-missao',
            'mode': 'single',
        })

        self.assertEqual(response.status_code, 302)
        order = AsaasCheckoutOrder.objects.get()
        self.assertEqual(order.email, 'checkout@example.com')
        self.assertEqual(order.discord_user_id, '')
        self.assertEqual(api_request.call_args.args[2]['customerData']['email'], order.email)

    @patch('home.views._asaas_api_request')
    def test_discord_only_account_can_start_checkout(self, api_request):
        api_request.return_value = {'id': 'checkout-discord-id'}
        self.user.email = ''
        self.user.save(update_fields=['email'])

        response = self.client.post(reverse('colaborador_checkout'), {
            'product': 'token-superboost',
            'mode': 'single',
        })

        self.assertEqual(response.status_code, 302)
        order = AsaasCheckoutOrder.objects.get()
        self.assertEqual(order.email, '')
        self.assertEqual(order.discord_user_id, '123456789')
        self.assertNotIn('email', api_request.call_args.args[2]['customerData'])

    def test_rejects_unknown_product(self):
        response = self.client.post(reverse('colaborador_checkout'), {
            'product': 'produto-inventado',
            'mode': 'single',
        })

        self.assertRedirects(
            response,
            '%s?checkout=error' % reverse('colaborador'),
            fetch_redirect_response=False,
        )
        self.assertFalse(AsaasCheckoutOrder.objects.exists())


@override_settings(BONFIRE_CHECKOUT_SIGNING_SECRET='checkout-test-secret')
class AsaasDiscordCheckoutTests(TestCase):
    def _token(self, **overrides):
        payload = {
            'discord_id': '987654321',
            'discord_name': 'Discord Buyer',
            'product': 'token-boost',
            'mode': 'single',
            'exp': int(time.time()) + 300,
        }
        payload.update(overrides)
        payload_part = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(',', ':')).encode('utf-8'),
        ).decode('ascii').rstrip('=')
        signature = hmac.new(
            b'checkout-test-secret', payload_part.encode('ascii'), hashlib.sha256,
        ).digest()
        signature_part = base64.urlsafe_b64encode(signature).decode('ascii').rstrip('=')
        return '%s.%s' % (payload_part, signature_part)

    def test_signed_discord_checkout_renders_without_site_account(self):
        response = self.client.get(reverse('colaborador_discord_checkout'), {
            'token': self._token(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Discord Buyer')
        self.assertContains(response, 'Token de Boost')

    @patch('home.views._bot_member_for_identity', return_value=None)
    @patch('home.views._asaas_api_request', return_value={'id': 'discord-checkout-id'})
    def test_signed_discord_checkout_creates_order(self, api_request, resolve_member):
        response = self.client.post(reverse('colaborador_discord_checkout'), {
            'token': self._token(),
        })

        self.assertRedirects(
            response,
            'https://asaas.com/checkoutSession/show?id=discord-checkout-id',
            fetch_redirect_response=False,
        )
        order = AsaasCheckoutOrder.objects.get()
        self.assertIsNone(order.user)
        self.assertEqual(order.discord_user_id, '987654321')
        self.assertEqual(order.product_code, 'token-boost')
        self.assertEqual(order.email, '')
        resolve_member.assert_called_once_with(discord_id='987654321')
        self.assertNotIn('email', api_request.call_args.args[2]['customerData'])

    def test_expired_or_tampered_discord_checkout_is_rejected(self):
        expired = self.client.get(reverse('colaborador_discord_checkout'), {
            'token': self._token(exp=int(time.time()) - 1),
        })
        token = self._token()
        tampered = self.client.get(reverse('colaborador_discord_checkout'), {
            'token': token[:-1] + ('a' if token[-1] != 'a' else 'b'),
        })

        self.assertEqual(expired.status_code, 400)
        self.assertEqual(tampered.status_code, 400)
        self.assertFalse(AsaasCheckoutOrder.objects.exists())


@override_settings(ASAAS_WEBHOOK_TOKEN='webhook-test-secret')
class AsaasWebhookIdentityTests(TestCase):
    @patch('home.views._asaas_api_get')
    def test_duplicate_colab_payment_is_acknowledged_during_api_outage(self, api_get):
        api_get.return_value = None
        with patch.object(BotTransaction, 'objects') as transaction_objects:
            transaction_objects.filter.return_value.exists.return_value = True
            response = self.client.post(
                reverse('asaas_webhook'),
                data=json.dumps({
                    'event': 'PAYMENT_RECEIVED',
                    'payment': {'id': 'pay_already_processed'},
                }),
                content_type='application/json',
                HTTP_ASAAS_ACCESS_TOKEN='webhook-test-secret',
            )

        self.assertEqual(response.status_code, 200)
        api_get.assert_called_once_with('payments/pay_already_processed')

    @patch('home.views._bot_member_for_identity')
    @patch('home.views._asaas_api_get')
    def test_discord_order_uses_billing_email_and_delivers_immediately(self, api_get, resolve_member):
        order = AsaasCheckoutOrder.objects.create(
            discord_user_id='555666777',
            product_code='token-boost',
            mode='single',
            amount=Decimal('19.90'),
        )
        payment = {
            'id': 'pay_discord_only',
            'externalReference': order.external_reference,
            'customer': 'cus_1',
            'value': 19.90,
            'netValue': 19.20,
            'paymentDate': '2026-08-14',
        }
        api_get.side_effect = [payment, {
            'email': 'payer@example.com',
            'name': 'Payer Name',
        }]
        member = SimpleNamespace(
            pk='member_1',
            email='payer@example.com',
            discordUserTag='Discord Buyer',
        )
        resolve_member.return_value = member

        with patch.object(BotTransaction, 'objects') as transaction_objects, \
                patch.object(BotMember, 'objects') as member_objects:
            transaction_objects.filter.return_value.exists.return_value = False
            transaction_objects.select_for_update.return_value.filter.return_value.exists.return_value = False
            response = self.client.post(
                reverse('asaas_webhook'),
                data=json.dumps({
                    'event': 'PAYMENT_RECEIVED',
                    'payment': {'id': 'pay_discord_only'},
                }),
                content_type='application/json',
                HTTP_ASAAS_ACCESS_TOKEN='webhook-test-secret',
            )

        self.assertEqual(response.status_code, 200)
        resolve_member.assert_called_once_with(
            discord_id='555666777',
            email='payer@example.com',
            username='Payer Name',
            create=True,
        )
        member_objects.filter.return_value.update.assert_called_once()
        created = transaction_objects.create.call_args.kwargs
        self.assertEqual(created['email'], 'payer@example.com')
        self.assertEqual(created['subscriptionPlan'], 'token-boost')
        self.assertTrue(created['claimed'])
        order.refresh_from_db()
        self.assertEqual(order.status, AsaasCheckoutOrder.Status.PAID)
        self.assertEqual(order.email, 'payer@example.com')
