from django.test import SimpleTestCase

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
