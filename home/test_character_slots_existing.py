from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import (MestreOuroDireito, TbCosmetico, TbPersonagem,
                     TbTransacaoMestre, TbUsuarioCosmetico, UserProfile)


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

    def test_slot_page_manages_preserved_sheets_with_existing_actions(self):
        self.client.force_login(self.owner)
        slots = reverse('character_slots')
        archive = reverse('personagem_arquivar', args=[self.active.pk])
        restore = reverse('personagem_restaurar', args=[self.archived.pk])
        before = self.client.get(slots)
        self.assertContains(before, f'action="{archive}"')
        self.assertContains(before, 'Arquive uma ficha ativa para liberar espaço.')
        self.assertNotContains(before, f'action="{restore}"')
        self.assertEqual(self.client.post(archive).status_code, 302)
        after_archive = self.client.get(slots)
        self.assertContains(after_archive, f'action="{restore}"')
        self.assertContains(after_archive, '0 ativas')
        self.assertEqual(self.client.post(restore).status_code, 302)
        self.assertContains(self.client.get(slots), '2 fichas preservadas')
        self.active.refresh_from_db()
        self.archived.refresh_from_db()
        self.assertTrue(self.active.arquivado)
        self.assertFalse(self.archived.arquivado)
        self.assertEqual(TbPersonagem.objects.filter(dono=self.owner).count(), 2)

    def test_character_cards_archive_and_restore_without_losing_sheets(self):
        self.client.force_login(self.owner)
        TbPersonagem.objects.filter(pk=self.active.pk).update(publico=True)
        archive = reverse('personagem_arquivar', args=[self.active.pk])
        restore = reverse('personagem_restaurar', args=[self.archived.pk])
        page = self.client.get(reverse('personagens'))
        self.assertContains(page, f'action="{archive}"')
        self.assertContains(page, 'Arquivar e retirar publicação')
        self.assertContains(page, 'Prévia privada')
        self.assertContains(page, 'Limite de fichas ativas atingido')
        self.assertNotContains(page, f'action="{restore}"')

        self.assertEqual(self.client.post(archive).status_code, 302)
        self.active.refresh_from_db()
        self.assertTrue(self.active.arquivado)
        self.assertFalse(self.active.publico)
        self.assertContains(self.client.get(reverse('personagens')), f'action="{restore}"')
        self.assertEqual(self.client.post(restore).status_code, 302)
        self.archived.refresh_from_db()
        self.assertFalse(self.archived.arquivado)
        self.assertEqual(self.client.post(reverse('personagem_restaurar',
                                                args=[self.active.pk])).status_code, 400)
        self.active.refresh_from_db()
        self.assertTrue(self.active.arquivado)
        self.assertEqual(TbPersonagem.objects.filter(dono=self.owner).count(), 2)


class CharacterSlotRedemptionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('slot-master', password='test')
        self.profile = UserProfile.objects.get_or_create(user=self.user)[0]
        self.profile.moedas_mestragem = 6000
        self.profile.save(update_fields=['moedas_mestragem'])
        for slug, kind in (('titulo-mestre-ouro', 'titulo'),
                           ('moldura-mestre-ouro', 'moldura')):
            TbCosmetico.objects.get_or_create(slug=slug, defaults={
                'tipo': kind, 'nome': slug, 'raridade': 'lendario',
                'origem': 'mestre_ouro', 'escopo': 'perfil', 'ativo': True,
            })
        self.client.force_login(self.user)
        self.url = reverse('buy_character_slot')

    @patch('home.permissions.is_mestre', return_value=True)
    def test_purchase_once_uses_existing_right_and_mm_ledger(self, _is_mestre):
        page = self.client.get(reverse('character_slots'))
        self.assertContains(page, 'Confirmar resgate por 5.000 MM')
        first = self.client.post(self.url)
        self.assertRedirects(first, reverse('character_slots'))
        again = self.client.post(self.url)
        self.assertRedirects(again, reverse('character_slots'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.moedas_mestragem, 1000)
        self.assertFalse(self.profile.mestre_ouro_ativo)
        self.assertEqual(MestreOuroDireito.objects.filter(user=self.user).count(), 1)
        ledger = TbTransacaoMestre.objects.get(mestre=self.user)
        self.assertEqual((ledger.tipo, ledger.valor_mm, ledger.saldo_mm),
                         ('resgate', -5000, 1000))
        self.assertEqual(MestreOuroDireito.objects.get(user=self.user).primeira_compra, ledger)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(user=self.user).count(), 2)
        self.assertContains(self.client.get(reverse('character_slots')), '+1 permanente')

    @patch('home.permissions.is_mestre', return_value=True)
    def test_legacy_or_insufficient_balance_never_debits(self, _is_mestre):
        self.profile.moedas_mestragem = 4999
        self.profile.save(update_fields=['moedas_mestragem'])
        page = self.client.get(reverse('character_slots'))
        self.assertContains(page, reverse('mestre_mercado'))
        self.assertContains(page, 'Seu saldo ainda não cobre este resgate.')
        self.client.post(self.url)
        self.assertFalse(MestreOuroDireito.objects.exists())
        self.assertFalse(TbTransacaoMestre.objects.exists())
        self.profile.moedas_mestragem = 6000
        self.profile.save(update_fields=['moedas_mestragem'])
        TbTransacaoMestre.objects.create(
            mestre=self.user, tipo='assinatura', valor_mm=-500,
            saldo_mm=5500, descricao='Compra legada')
        self.client.post(self.url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.moedas_mestragem, 6000)
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)
        self.assertFalse(MestreOuroDireito.objects.exists())
        self.assertContains(self.client.get(reverse('character_slots')),
                            'histórico legado de Mestre Ouro')

    @patch('home.permissions.is_mestre', return_value=False)
    def test_eligibility_and_csrf_are_enforced_server_side(self, _is_mestre):
        self.client.post(self.url)
        self.assertEqual(self.profile.moedas_mestragem, 6000)
        self.assertFalse(MestreOuroDireito.objects.exists())
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.user)
        self.assertEqual(guarded.post(self.url).status_code, 403)
        self.assertEqual(guarded.get(self.url).status_code, 405)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    @patch('home.permissions.is_mestre', return_value=True)
    def test_orphan_slot_redemption_blocks_second_debit(self, _is_mestre):
        old = TbTransacaoMestre.objects.create(
            mestre=self.user, tipo='resgate', valor_mm=-5000,
            saldo_mm=6000, descricao='Slot permanente de personagem (Mestre Ouro)',
        )
        page = self.client.get(reverse('character_slots'))
        self.assertContains(page, 'histórico legado de Mestre Ouro')
        self.assertNotContains(page, 'Confirmar resgate por 5.000 MM')
        market = self.client.get(reverse('mestre_mercado'))
        self.assertContains(market, 'Histórico em revisão')
        self.assertNotContains(market, 'Não adquirido')
        self.client.post(self.url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.moedas_mestragem, 6000)
        self.assertEqual(list(TbTransacaoMestre.objects.values_list('pk', flat=True)), [old.pk])
        self.assertFalse(MestreOuroDireito.objects.exists())

    @patch('home.permissions.is_mestre', return_value=True)
    def test_legacy_subscription_without_right_has_matching_market_status(self, _is_mestre):
        TbTransacaoMestre.objects.create(
            mestre=self.user, tipo='assinatura', valor_mm=-500,
            saldo_mm=6000, descricao='Mestre Ouro antigo',
        )
        self.assertContains(self.client.get(reverse('character_slots')),
                            'histórico legado de Mestre Ouro')
        market = self.client.get(reverse('mestre_mercado'))
        self.assertContains(market, 'Histórico em revisão')
        self.assertNotContains(market, 'Não adquirido')
