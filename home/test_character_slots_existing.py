from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import MestreOuroDireito, TbPersonagem, TbTransacaoMestre, UserProfile


class ExistingCharacterSlotsTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('slot-owner', password='test')
        self.other = get_user_model().objects.create_user('slot-other', password='test')
        UserProfile.objects.get_or_create(user=self.owner)
        UserProfile.objects.get_or_create(user=self.other)
        self.active = TbPersonagem.objects.create(dono=self.owner, nome='Fiel', nivel=13)
        self.archived = TbPersonagem.objects.create(
            dono=self.owner, nome='Guardada', nivel=20, arquivado=True)
        TbPersonagem.objects.create(dono=self.other, nome='Secreta')

    def test_private_capacity_uses_existing_right_without_awarding_milestones(self):
        url = reverse('character_slots')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.owner)
        before = self.client.get(url)
        self.assertEqual(before.status_code, 200)
        self.assertContains(before, '<strong>1</strong><span>fichas ativas permitidas</span>', html=True)
        self.assertContains(before, '2 fichas preservadas')
        self.assertContains(before, 'Fiel')
        self.assertContains(before, 'Guardada')
        self.assertNotContains(before, 'Secreta')
        self.assertNotContains(before, 'Confirmar por 5.000 MM')

        purchase = TbTransacaoMestre.objects.create(
            mestre=self.owner, tipo='assinatura', valor_mm=-5000,
            saldo_mm=0, descricao='Compra vitalícia existente')
        MestreOuroDireito.objects.create(
            user=self.owner, primeira_compra=purchase,
            adquirido_em=purchase.criado_em)
        after = self.client.get(url)
        self.assertContains(after, '<strong>2</strong><span>fichas ativas permitidas</span>', html=True)
        self.assertContains(after, '+1 permanente')
        self.assertEqual(self.client.post(url, {'action': 'buy_mm'}).status_code, 405)
        self.active.refresh_from_db()
        self.archived.refresh_from_db()
        self.assertFalse(self.active.arquivado)
        self.assertTrue(self.archived.arquivado)
        self.assertEqual(TbTransacaoMestre.objects.filter(mestre=self.owner).count(), 1)

    def test_character_list_links_to_capacity_and_uses_actual_totals(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('personagens'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('character_slots'))
        self.assertContains(response, '2 fichas preservadas')
        self.assertNotContains(response, '#slots-g01')
