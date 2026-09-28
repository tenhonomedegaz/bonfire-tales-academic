from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from home.conquistas import registrar_fato_compra, registrar_fato_estorno_compra
from home.models import (
    TbAnuncioItemMagico, TbEventoConquista, TbItemMagico,
    TbPersonagemItem, TbTransacao,
)
from home.test_ficha_v2_onda_c import _MercadoBase


class PurchaseFactTests(_MercadoBase):
    def test_mundane_purchase_and_refund_have_distinct_idempotent_facts(self):
        character = self._char('purchase-fact')
        item = self._item_mundano_com_preco()
        self.client.force_login(character.dono)
        bought = self.client.post(reverse('personagem_comprar_item', args=[character.pk]),
                                  {'item': item.slug, 'qtd': 2}, **self.AJAX)
        self.assertTrue(bought.json()['ok'])
        transaction = TbTransacao.objects.get(tipo='compra')
        event = TbEventoConquista.objects.get(tipo='item_purchased')
        self.assertEqual(event.conta_id, character.dono_id)
        self.assertEqual(event.payload_json['transacao_id'], transaction.pk)
        self.assertEqual(event.payload_json['quantidade'], 2)
        self.assertEqual(event.payload_json['catalogo'], 'mundano')
        self.assertEqual(registrar_fato_compra(transaction).pk, event.pk)
        auditor = get_user_model().objects.create_superuser(
            'purchase-auditor', 'purchase-auditor@example.invalid', 'x')
        self.client.force_login(auditor)
        audit = self.client.get(reverse('admin:home_tbeventoconquista_change',
                                        args=[event.pk]))
        self.assertContains(audit, event.chave_origem)
        self.client.force_login(character.dono)

        refunded = self.client.post(reverse('personagem_reembolsar_compra',
                                           args=[character.pk, transaction.pk]))
        self.assertEqual(refunded.status_code, 302)
        transaction.refresh_from_db()
        self.assertTrue(transaction.revertida)
        refund_txn = TbTransacao.objects.get(tipo='ajuste',
            detalhes_json__reverte_transacao=transaction.pk)
        refund_event = TbEventoConquista.objects.get(tipo='item_purchase_refunded')
        self.assertEqual(refund_event.payload_json['compra_evento_id'], str(event.pk))
        self.assertEqual(refund_event.payload_json['reembolso_transacao_id'], refund_txn.pk)
        self.assertEqual(registrar_fato_estorno_compra(transaction, refund_txn).pk,
                         refund_event.pk)
        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[character.pk, transaction.pk]))
        self.assertEqual(TbEventoConquista.objects.filter(origem='site_market').count(), 2)

    def test_magic_purchase_records_fact_but_failed_purchase_and_gift_do_not(self):
        character = self._char('magic-fact', ouro_pc=100_000_000)
        item = TbItemMagico.objects.filter(preco__gt=0).order_by('preco').first()
        self.client.force_login(character.dono)
        bought = self.client.post(reverse('personagem_comprar_magico',
                                          args=[character.pk]), {'item': item.slug}, **self.AJAX)
        self.assertTrue(bought.json()['ok'])
        self.assertEqual(TbEventoConquista.objects.get(
            tipo='item_purchased').payload_json['catalogo'], 'magico')
        TbPersonagemItem.objects.create(id_personagem=character, nome='Presente', qtd=1,
                                       origem_tipo='presente')
        character.carteira_pc = 0
        character.save(update_fields=['carteira_pc'])
        denied = self.client.post(reverse('personagem_comprar_magico',
                                          args=[character.pk]), {'item': item.slug}, **self.AJAX)
        self.assertFalse(denied.json()['ok'])
        self.assertEqual(TbEventoConquista.objects.filter(tipo='item_purchased').count(), 1)

    def test_community_sale_keeps_listing_identity_and_seller_is_not_buyer(self):
        seller = self._char('seller-fact')
        buyer = self._char('buyer-fact')
        magic = TbItemMagico.objects.first()
        listing = TbAnuncioItemMagico.objects.create(
            vendedor=seller, id_item_magico=magic, nome=magic.nome,
            custo='10 PO', preco_pc=500, status='ativo')
        self.client.force_login(buyer.dono)
        response = self.client.post(reverse('comprar_anuncio', args=[listing.pk]),
                                    {'comprador': buyer.pk})
        self.assertEqual(response.status_code, 302)
        event = TbEventoConquista.objects.get(tipo='item_purchased')
        self.assertEqual(event.conta_id, buyer.dono_id)
        self.assertEqual(event.payload_json['catalogo'], 'comunidade')
        self.assertEqual(event.payload_json['anuncio_id'], listing.pk)
        self.client.post(reverse('comprar_anuncio', args=[listing.pk]),
                         {'comprador': buyer.pk})
        self.assertEqual(TbEventoConquista.objects.filter(origem='site_market').count(), 1)
        free_listing = TbAnuncioItemMagico.objects.create(
            vendedor=seller, id_item_magico=magic, nome='Transferência gratuita',
            preco_pc=0, status='ativo')
        self.client.post(reverse('comprar_anuncio', args=[free_listing.pk]),
                         {'comprador': buyer.pk})
        self.assertEqual(TbEventoConquista.objects.filter(origem='site_market').count(), 1)

    def test_failed_refund_fact_rolls_back_reimbursement(self):
        character = self._char('refund-atomic')
        item = self._item_mundano_com_preco()
        self.client.force_login(character.dono)
        self.client.post(reverse('personagem_comprar_item', args=[character.pk]),
                         {'item': item.slug}, **self.AJAX)
        purchase = TbTransacao.objects.get(tipo='compra')
        balance = character.transacoes.get(pk=purchase.pk).saldo_pc
        with patch('home.conquistas.registrar_fato_estorno_compra',
                   side_effect=RuntimeError('simulated refund fact failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('personagem_reembolsar_compra',
                                         args=[character.pk, purchase.pk]))
        purchase.refresh_from_db()
        character.refresh_from_db()
        self.assertFalse(purchase.revertida)
        self.assertEqual(character.carteira_pc, balance)
        self.assertFalse(TbEventoConquista.objects.filter(tipo='item_purchase_refunded').exists())
        self.assertFalse(TbTransacao.objects.filter(
            tipo='ajuste', detalhes_json__reverte_transacao=purchase.pk).exists())

    def test_refund_of_preexisting_tracked_purchase_records_both_facts(self):
        character = self._char('legacy-purchase')
        catalog_item = self._item_mundano_com_preco()
        inventory = TbPersonagemItem.objects.create(
            id_personagem=character, id_item_mundano=catalog_item,
            nome=catalog_item.nome, qtd=1, origem_tipo='compra')
        purchase = TbTransacao.objects.create(
            id_personagem=character, tipo='compra', valor_pc=-100,
            saldo_pc=character.carteira_pc,
            detalhes_json={'catalogo': 'mundano', 'catalogo_id': catalog_item.pk,
                           'inventario_id': inventory.pk, 'qtd': 1,
                           'aventuras_no_momento': character.aventuras})
        self.client.force_login(character.dono)
        response = self.client.post(reverse('personagem_reembolsar_compra',
                                            args=[character.pk, purchase.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(TbEventoConquista.objects.filter(
            origem='site_market').values_list('tipo', flat=True)),
            {'item_purchased', 'item_purchase_refunded'})

    def test_failed_fact_rolls_back_wallet_inventory_and_ledger(self):
        character = self._char('atomic-fact')
        item = self._item_mundano_com_preco()
        before = character.carteira_pc
        self.client.force_login(character.dono)
        with patch('home.conquistas.registrar_fato_compra',
                   side_effect=RuntimeError('simulated fact write failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('personagem_comprar_item', args=[character.pk]),
                                 {'item': item.slug}, **self.AJAX)
        character.refresh_from_db()
        self.assertEqual(character.carteira_pc, before)
        self.assertFalse(TbTransacao.objects.filter(tipo='compra').exists())
        self.assertFalse(TbPersonagemItem.objects.filter(
            id_personagem=character, origem_tipo='compra').exists())
