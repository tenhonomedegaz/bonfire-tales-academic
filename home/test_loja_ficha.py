# -*- coding: utf-8 -*-
"""Regressão da LOJA da ficha (Mercado) no formato CATÁLOGO + preço no catálogo mágico.

Cobre a onda "LOJA / INVENTARIO / ITENS" (achado 1):
  1. A seção Mercado de editar_ficha.html deixa de usar <select><optgroup> e passa a
     navegação de catálogo (busca + chips + cards nome/preço), reusando os partials/CSS
     do catálogo do site.
  2. Compra via fetch (XHR) nos endpoints existentes devolve JSON {ok, carteira_display,
     inventario_html} e debita a carteira SEM reload; POST clássico continua redirect.
  3. O catálogo PÚBLICO de itens mágicos passa a exibir preço (.mi-list-item-price no card
     + linha "Preço" no detalhe); mission-only (sem preço) mostra "Recompensa de missão".

Roda contra o conteúdo real (fixture conteudo.json): 954 itens mágicos (691 com preço,
263 recompensa de missão) e 302 mundanos.
"""
from django.urls import reverse

from home.views import _preco_em_pc
from home.models import TbItemMundano, TbItemMagico, TbPersonagemItem
from home.test_levelup import LevelUpLoteBase


class LojaFichaCatalogoTests(LevelUpLoteBase):
    def test_get_ficha_200_com_loja_formato_catalogo(self):
        # A seção Mercado é o shell de catálogo (busca + chips + cards), não mais selects.
        p = self._guerreiro_no_nivel(1)
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        for needle in ('data-loja-root', 'id="loja-shell"', 'id="loja-busca"',
                       'data-loja-chipset="mundano"', 'data-loja-chipset="magico"',
                       'data-loja-list="mundano"', 'data-loja-list="magico"',
                       'data-loja-form="mundano"', 'data-loja-form="magico"',
                       'mu-list-item-price', 'mi-list-item-price',
                       'id="lvl-inventario"',
                       'js/loja_ficha.js', 'css/pages/itens_magicos.css',
                       'css/pages/itens_mundanos.css'):
            self.assertIn(needle, html, needle)
        # os <select><optgroup> da loja antiga sumiram
        self.assertNotIn('<optgroup', html)
        # os cards apontam para os endpoints de compra existentes (fallback POST + fetch)
        self.assertIn(reverse('personagem_comprar_item', args=[p.pk]), html)
        self.assertIn(reverse('personagem_comprar_magico', args=[p.pk]), html)


class LojaFichaCompraFetchTests(LevelUpLoteBase):
    def test_compra_mundana_via_fetch_retorna_json_e_debita(self):
        p = self._guerreiro_no_nivel(1)
        p.carteira_pc = 1_000_000  # 10.000 PO, folga para qualquer item
        p.save(update_fields=['carteira_pc'])
        item = next(i for i in TbItemMundano.objects.all() if _preco_em_pc(i.preco) is not None)
        custo = _preco_em_pc(item.preco)
        antes = p.carteira_pc
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_comprar_item', args=[p.pk]),
            data={'item': item.slug, 'qtd': 2},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp['Content-Type'], 'application/json')
        body = resp.json()
        self.assertTrue(body['ok'], body)
        self.assertIn('carteira_display', body)
        self.assertIn('inventario_html', body)
        self.assertIn(item.nome, body['inventario_html'])
        # debitou a carteira de verdade (2 unidades) e materializou o item
        p.refresh_from_db()
        self.assertEqual(p.carteira_pc, antes - custo * 2)
        self.assertTrue(TbPersonagemItem.objects.filter(id_personagem=p, nome=item.nome).exists())

    def test_compra_mundana_post_classico_continua_redirect(self):
        # Sem XHR: fallback progressivo continua PRG (redirect para editar_ficha).
        p = self._guerreiro_no_nivel(1)
        p.carteira_pc = 1_000_000
        p.save(update_fields=['carteira_pc'])
        item = next(i for i in TbItemMundano.objects.all() if _preco_em_pc(i.preco) is not None)
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_comprar_item', args=[p.pk]),
                                data={'item': item.slug, 'qtd': 1})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('compra=ok', resp['Location'])

    def test_compra_magica_via_fetch_retorna_json(self):
        p = self._guerreiro_no_nivel(1)
        p.carteira_pc = 100_000_000
        p.save(update_fields=['carteira_pc'])
        item = TbItemMagico.objects.filter(preco__gt=0).order_by('preco').first()
        self.assertIsNotNone(item)
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_comprar_magico', args=[p.pk]),
            data={'item': item.slug},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        self.assertIn(item.nome, body['inventario_html'])

    def test_compra_magica_mission_only_bloqueada_via_fetch(self):
        # Item mission-only (preço 0 = recompensa de missão) é recusado mesmo por fetch.
        p = self._guerreiro_no_nivel(1)
        p.carteira_pc = 100_000_000
        p.save(update_fields=['carteira_pc'])
        item = TbItemMagico.objects.filter(preco=0).first()
        self.assertIsNotNone(item)
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_comprar_magico', args=[p.pk]),
            data={'item': item.slug},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body['ok'], body)
        self.assertEqual(body['msg'], 'invalido')


class CatalogoMagicoPrecoTests(LevelUpLoteBase):
    def test_catalogo_publico_magico_exibe_preco_e_recompensa(self):
        resp = self.client.get(reverse('mercado_itens_magicos'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        # pill de preço no card (espelha .mu-list-item-price) e linha no detalhe
        self.assertIn('mi-list-item-price', html)
        self.assertIn('mi-detail-price', html)
        self.assertIn('Preço', html)
        # itens com preço mostram número em PO; mission-only mostram o rótulo
        self.assertIn(' PO', html)
        self.assertIn('Recompensa de missão', html)
