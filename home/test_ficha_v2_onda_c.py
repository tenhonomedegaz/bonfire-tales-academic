# -*- coding: utf-8 -*-
"""Regressão da FICHA v2 — onda C (MERCADO marketplace), briefing docs/agentes/briefing_ficha_v2.md.

  1. As páginas do Mercado viram LOJA: vitrine em prateleiras (categoria no mundano, campo
     `loja` do catálogo no mágico), com BALCÃO — seletor de personagem ativo (só os do
     usuário, persistido em sessão) e carteira em PO.
  2. Compra por fetch nos endpoints de sempre debita a carteira, materializa o item e
     devolve carteira + painel de venda re-renderizados (sem reload).
  3. Venda a 80% migrou da Mochila para o painel VENDER do Mercado, com a mesma regra.
  4. Item sem preço fica exposto como "Recompensa de missão", sem botão — e o POST direto
     continua recusado no backend.
  5. `editar_ficha` virou ferramenta SÓ-DA-STAFF: dono não-staff é redirecionado para a
     ficha; para a staff sobra o staffbox (aventuras + conceder/reverter item), sem loja.
  6. Fix cosmético da onda B: os atalhos [data-tab-jump] usam delegação no document.

Roda contra o conteúdo real (fixture `conteudo.json`), reusando o `LevelUpLoteBase`.
"""
import io
import os

from django.conf import settings
from django.urls import reverse

from home.models import TbItemMagico, TbItemMundano, TbPersonagem, TbPersonagemItem
from home.views import _preco_em_pc, _preco_venda_mundano_pc
from home.test_levelup import LevelUpLoteBase


class _MercadoBase(LevelUpLoteBase):
    AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
    MUNDANOS = reverse('mercado_itens_mundanos')
    MAGICOS = reverse('mercado_itens_magicos')

    def _char(self, apelido='mercado', ouro_pc=1_000_000):
        p = self._guerreiro_no_nivel(1, apelido=apelido)
        p.carteira_pc = ouro_pc
        p.save(update_fields=['carteira_pc'])
        return p

    def _dono_comum(self, p, username):
        """Troca o dono por um usuário NÃO-staff (o `_guerreiro_no_nivel` cria staff)."""
        user = self._novo_usuario(username, staff=False)
        p.dono = user
        p.save(update_fields=['dono'])
        return user

    def _item_mundano_com_preco(self):
        return next(i for i in TbItemMundano.objects.order_by('nome')
                    if _preco_em_pc(i.preco) is not None)

    def _vitrine(self, url, user=None, **params):
        if user is not None:
            self.client.force_login(user)
        resp = self.client.get(url, params)
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        return resp.content.decode('utf-8')


class VitrineDeLojaTests(_MercadoBase):
    def test_mundano_expoe_prateleiras_e_preco_em_po(self):
        p = self._char('vitrine-mu')
        html = self._vitrine(self.MUNDANOS, p.dono)
        # é loja, não lista-wiki: shell da vitrine + prateleiras + balcão
        for needle in ('data-shop-root', 'data-shop-kind="mundano"', 'shop-shelf',
                       'shelf-name', 'goods-price', 'data-shop-counter', 'shop-wallet',
                       'css/pages/mercado_loja.css', 'js/mercado_loja.js'):
            self.assertIn(needle, html, needle)
        # uma prateleira por categoria REAL do catálogo (dado, não lista fixa)
        for categoria in TbItemMundano.objects.values_list('categoria', flat=True).distinct():
            rotulo = dict(TbItemMundano.CATEGORIA_CHOICES).get(categoria, categoria)
            self.assertIn('>%s</h2>' % rotulo, html, rotulo)
        # preço em PO (a exibição em PP/PC morreu na onda A)
        self.assertIn(' PO<', html)

    def test_magico_agrupa_pelo_campo_loja_do_catalogo(self):
        p = self._char('vitrine-mi')
        html = self._vitrine(self.MAGICOS, p.dono)
        self.assertIn('data-shop-kind="magico"', html)
        lojas = {(l or '').strip() for l in
                 TbItemMagico.objects.values_list('loja', flat=True).distinct()}
        # as lojas do catálogo (Alquimia, Forja, Joalheria…) viram cabeçalho de prateleira
        for loja in ('Alquimia', 'Forja', 'Joalheria'):
            self.assertIn(loja, lojas, 'catálogo real deveria ter a loja %s' % loja)
            self.assertIn('>%s</h2>' % loja, html, loja)
        # filtros mantidos: busca + chips de raridade
        self.assertIn('data-shop-search', html)
        self.assertIn('data-rarity-filter="todas"', html)
        # preço no card E no detalhe do balcão (o catálogo público sempre exibiu preço)
        self.assertIn('goods-price', html)
        self.assertIn('shop-stat is-price', html)
        self.assertIn('Preço', html)
        self.assertIn(' PO<', html)
        self.assertIn('Recompensa de missão', html)

    def test_balcao_lista_so_personagens_do_usuario_e_mostra_carteira(self):
        p = self._char('balcao')
        p.carteira_pc = 123_450          # 1234,5 PO
        p.save(update_fields=['carteira_pc'])
        alheio = self._char('balcao-alheio')
        alheio.nome = 'Personagem Alheio'
        alheio.save(update_fields=['nome'])
        html = self._vitrine(self.MUNDANOS, p.dono)
        self.assertIn('data-shop-personagem', html)
        self.assertIn(p.nome, html)
        self.assertNotIn('Personagem Alheio', html)   # é de outro dono
        self.assertIn('1234,5 PO', html)              # carteira do ativo, em PO

    def test_personagem_ativo_vem_do_parametro_e_persiste_na_sessao(self):
        p1 = self._char('ativo-1')
        p2 = TbPersonagem.objects.create(dono=p1.dono, nome='Segundo Herói', carteira_pc=777_00)
        # ?personagem= fixa o ativo...
        html = self._vitrine(self.MUNDANOS, p1.dono, personagem=p2.pk)
        self.assertIn('value="%d" selected' % p2.pk, html)
        self.assertIn('777 PO', html)
        self.assertEqual(self.client.session['mercado_personagem'], p2.pk)
        # ...e a escolha atravessa para a outra vitrine sem repetir o parâmetro
        html = self._vitrine(self.MAGICOS)
        self.assertIn('value="%d" selected' % p2.pk, html)

    def test_anonimo_ve_a_vitrine_sem_botao_de_compra(self):
        html = self._vitrine(self.MUNDANOS)
        self.assertIn('shop-shelf', html)
        self.assertIn('Entre na sua conta', html)
        self.assertNotIn('data-shop-buy', html)


class CompraNoMercadoTests(_MercadoBase):
    def test_compra_mundana_por_fetch_debita_e_atualiza_sem_reload(self):
        p = self._char('compra-mu')
        item = self._item_mundano_com_preco()
        custo = _preco_em_pc(item.preco)
        antes = p.carteira_pc
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_comprar_item', args=[p.pk]),
                                data={'item': item.slug, 'qtd': 2}, **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        p.refresh_from_db()
        self.assertEqual(p.carteira_pc, antes - custo * 2)
        # o payload traz o que a vitrine precisa trocar sem recarregar
        from home.moeda import po_display
        self.assertEqual(body['carteira_display'], po_display(p.carteira_pc))
        self.assertIn('venda_html', body)
        self.assertIn(item.nome, body['inventario_html'])
        self.assertTrue(TbPersonagemItem.objects.filter(id_personagem=p, nome=item.nome).exists())

    def test_compra_magica_por_fetch(self):
        p = self._char('compra-mi', ouro_pc=100_000_000)
        item = TbItemMagico.objects.filter(preco__gt=0).order_by('preco').first()
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_comprar_magico', args=[p.pk]),
                                data={'item': item.slug}, **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        self.assertIn(item.nome, body['inventario_html'])

    def test_saldo_insuficiente_nao_debita(self):
        p = self._char('sem-ouro', ouro_pc=0)
        item = self._item_mundano_com_preco()
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_comprar_item', args=[p.pk]),
                                data={'item': item.slug}, **self.AJAX)
        self.assertFalse(resp.json()['ok'])
        self.assertEqual(resp.json()['msg'], 'saldo')
        p.refresh_from_db()
        self.assertEqual(p.carteira_pc, 0)

    def test_sem_preco_e_recompensa_de_missao_sem_botao(self):
        p = self._char('missao', ouro_pc=100_000_000)
        sem_preco = TbItemMagico.objects.filter(preco=0).first()
        self.assertIsNotNone(sem_preco, 'catálogo real deveria ter item de missão')
        html = self._vitrine(self.MAGICOS, p.dono)
        # o card existe (fica exposto para consulta) mas com rótulo e sem form de compra
        self.assertIn(sem_preco.nome, html)
        self.assertIn('Recompensa de missão', html)
        card = html.split('data-goods-open="mi-%d"' % sem_preco.pk)[1].split('</article>')[0]
        self.assertIn('goods-price is-mission', card)
        self.assertNotIn('data-shop-buy', card)
        # e o POST direto continua recusado pelo backend
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_comprar_magico', args=[p.pk]),
                                data={'item': sem_preco.slug}, **self.AJAX)
        self.assertFalse(resp.json()['ok'])
        self.assertEqual(resp.json()['msg'], 'invalido')

    def test_post_classico_sem_js_volta_para_a_vitrine(self):
        p = self._char('prg')
        item = self._item_mundano_com_preco()
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_comprar_item', args=[p.pk]),
                                data={'item': item.slug, 'next': self.MUNDANOS})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp['Location'].startswith(self.MUNDANOS), resp['Location'])
        self.assertIn('compra=ok', resp['Location'])
        # sem `next` confiável, cai na vitrine mundana (nunca mais no editar_ficha)
        resp = self.client.post(reverse('personagem_comprar_item', args=[p.pk]),
                                data={'item': item.slug, 'next': 'https://evil.example/x'})
        self.assertTrue(resp['Location'].startswith(self.MUNDANOS), resp['Location'])


class VendaNoMercadoTests(_MercadoBase):
    def _com_item_vendavel(self, apelido):
        p = self._char(apelido)
        item = self._item_mundano_com_preco()
        linha = TbPersonagemItem.objects.create(id_personagem=p, nome=item.nome, qtd=1,
                                                custo=item.preco)
        return p, linha, _preco_venda_mundano_pc(item.preco)

    def test_painel_vender_lista_o_inventario_com_valor_de_80(self):
        p, linha, venda_pc = self._com_item_vendavel('venda-painel')
        html = self._vitrine(self.MUNDANOS, p.dono)
        self.assertIn('data-shop-tab="vender"', html)
        self.assertIn('data-shop-venda', html)
        self.assertIn(linha.nome, html)
        self.assertIn('data-shop-sell', html)
        # 80% do preço de catálogo, exibido em PO
        from home.moeda import po_display
        self.assertIn(po_display(venda_pc), html)
        self.assertEqual(venda_pc, int(round(_preco_em_pc(linha.custo) * 0.8)))

    def test_venda_por_fetch_credita_a_carteira_e_some_do_inventario(self):
        p, linha, venda_pc = self._com_item_vendavel('venda-fetch')
        antes = p.carteira_pc
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_vender_item', args=[p.pk]),
                                data={'item': linha.id, 'qtd': 1}, **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        self.assertEqual(body['msg'], 'vendido')
        self.assertIn('credito_display', body)
        self.assertIn('venda_html', body)
        p.refresh_from_db()
        self.assertEqual(p.carteira_pc, antes + venda_pc)
        self.assertFalse(TbPersonagemItem.objects.filter(pk=linha.pk).exists())
        # o painel volta re-renderizado, já sem a linha vendida
        self.assertNotIn(linha.nome, body['venda_html'])
        # e a transação ficou no extrato
        self.assertTrue(p.transacoes.filter(tipo='venda').exists())

    def test_item_magico_nao_vende_pelo_balcao(self):
        p = self._char('venda-magico')
        magico = TbItemMagico.objects.filter(preco__gt=0).first()
        linha = TbPersonagemItem.objects.create(id_personagem=p, nome=magico.nome, qtd=1,
                                                custo='%g PO' % float(magico.preco),
                                                id_item_magico=magico)
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_vender_item', args=[p.pk]),
                                data={'item': linha.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['msg'], 'magico_venda')
        self.assertTrue(TbPersonagemItem.objects.filter(pk=linha.pk).exists())

    def test_item_sem_preco_nao_entra_no_painel_nem_vende(self):
        p = self._char('venda-sem-preco')
        linha = TbPersonagemItem.objects.create(id_personagem=p, nome='Lembrança da Missão',
                                                qtd=1, custo=None)
        html = self._vitrine(self.MUNDANOS, p.dono)
        self.assertNotIn('Lembrança da Missão', html)
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_vender_item', args=[p.pk]),
                                data={'item': linha.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['msg'], 'sem_preco')

    def test_venda_saiu_da_mochila_da_ficha(self):
        p, linha, _venda = self._com_item_vendavel('venda-migrou')
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn(linha.nome, html)                                   # continua na mochila
        self.assertNotIn(reverse('personagem_vender_item', args=[p.pk]), html)
        self.assertIn(self.MUNDANOS, html)                                # com atalho pro Mercado


class EditarFichaSoStaffTests(_MercadoBase):
    def test_dono_nao_staff_e_devolvido_para_a_ficha(self):
        p = self._char('so-staff')
        dono = self._dono_comum(p, 'dono-comum-mercado')
        self.client.force_login(dono)
        resp = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('ficha_detail', args=[p.pk]))
        # e a ficha dele NÃO oferece mais o atalho para o painel da staff
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertNotIn(reverse('editar_ficha', args=[p.pk]), html)
        self.assertIn(self.MUNDANOS, html)

    def test_staff_ve_o_painel_integro_e_sem_loja(self):
        p = self._char('staffbox')
        self.client.force_login(p.dono)                 # _guerreiro_no_nivel cria dono staff
        resp = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        # o que FICA: aventuras + conceder/reverter item
        self.assertIn('lvl-aventuras-staffbox', html)
        self.assertIn(reverse('personagem_conceder_item', args=[p.pk]), html)
        self.assertIn('data-conceder-form', html)
        # o que SAIU: a loja inteira (shell, chips, listas, forms e o JS dela)
        for morto in ('id="loja-shell"', 'data-loja-root', 'data-loja-list', 'data-loja-form',
                      'js/loja_ficha.js', 'loja-busca'):
            self.assertNotIn(morto, html, morto)
        self.assertNotIn(reverse('personagem_comprar_item', args=[p.pk]), html)
        self.assertNotIn(reverse('personagem_comprar_magico', args=[p.pk]), html)
        self.assertNotIn(reverse('personagem_vender_item', args=[p.pk]), html)
        # nem inventário/equipar (onda B) nem magias preparadas/recursos (são do jogador)
        self.assertNotIn('bag-list', html)
        self.assertNotIn(reverse('personagem_preparar_magias', args=[p.pk]), html)
        self.assertNotIn(reverse('personagem_usar_recurso', args=[p.pk]), html)

    def test_o_arquivo_da_loja_da_ficha_foi_removido(self):
        caminho = os.path.join(settings.BASE_DIR, 'home', 'static', 'js', 'loja_ficha.js')
        self.assertFalse(os.path.exists(caminho), 'loja_ficha.js deveria ter sido removido')

    def test_staff_ainda_alcanca_o_painel_de_ficha_alheia(self):
        p = self._char('staff-alheio')
        self._dono_comum(p, 'dono-de-outro')
        staff = self._novo_usuario('staff-do-mercado', staff=True)
        self.client.force_login(staff)
        resp = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('lvl-aventuras-staffbox', resp.content.decode('utf-8'))


class TabJumpDelegadoTests(_MercadoBase):
    def test_atalhos_de_aba_usam_delegacao_no_document(self):
        """Fix cosmético da onda B: os chips [data-tab-jump] vivem em partials que o fetch
        troca por outerHTML — um listener por elemento morreria na primeira troca."""
        caminho = os.path.join(settings.BASE_DIR, 'home', 'templates', 'home',
                               'pages', 'ficha_detail.html')
        codigo = io.open(caminho, encoding='utf-8').read()
        self.assertNotIn("querySelectorAll('[data-tab-jump]')", codigo)
        self.assertIn("closest('[data-tab-jump]')", codigo)
        # e o atalho segue funcionando na página renderizada
        p = self._char('tabjump')
        html = self._vitrine(reverse('ficha_detail', args=[p.pk]), p.dono)
        self.assertIn('data-tab-jump="mochila"', html)
