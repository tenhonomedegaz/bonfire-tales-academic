# -*- coding: utf-8 -*-
"""Regressão da FICHA v2 — onda A (quick wins), briefing docs/agentes/briefing_ficha_v2.md.

  1. Dinheiro exibido em MOEDA COMPOSTA PO/PP/PC (interno segue exato em PC): carteira,
     custo de item do inventário, extrato de transações e mercado. Decisão do PO que
     substituiu o "sempre em PO decimal" da onda A: não existe meio PO.
  2. O botão/form de descanso saiu do editar_ficha — o canônico é o da ficha.
  3. O resumo de magias saiu do rodapé da aba Ficha (a aba Magias cobre); fica o chip.
  4. Recursos consumíveis viram CONTADORES pequenos posicionados ACIMA de
     "Características & Habilidades".
  5. Bloco "Itens Sintonizados" entre Pontos de Vida e Ataques (só leitura).
  6. Personalidade/Ideais/Vínculos/Defeitos com UI + edição pelo dono (fetch).

Roda contra o conteúdo real (fixture conteudo.json), reusando o `LevelUpLoteBase`.
"""
from django.urls import reverse

from home.moeda import decompor, moeda_display, preco_display, preco_em_pc
from home.models import (TbItemMagico, TbPersonagemItem, TbPersonagemPersonalidade,
                         TbTransacao)
from home.test_levelup import LevelUpLoteBase


class MoedaCompostaTests(LevelUpLoteBase):
    def test_moeda_display_decompoe_em_po_pp_pc(self):
        # os três casos canônicos pedidos pelo PO
        self.assertEqual(moeda_display(134), '1 PO 3 PP 4 PC')
        self.assertEqual(moeda_display(20), '2 PP')
        self.assertEqual(moeda_display(0), '0 PO')
        # componentes zero somem no meio e no fim
        self.assertEqual(moeda_display(160), '1 PO 6 PP')
        self.assertEqual(moeda_display(104), '1 PO 4 PC')
        self.assertEqual(moeda_display(100), '1 PO')
        self.assertEqual(moeda_display(7), '7 PC')
        self.assertEqual(moeda_display(150000), '1500 PO')
        # negativo leva UM sinal na frente, nunca um por componente
        self.assertEqual(moeda_display(-500), '-5 PO')
        self.assertEqual(moeda_display(-134), '-1 PO 3 PP 4 PC')
        # nada de exibição decimal: 1250 PC não é mais "12,5 PO"
        self.assertEqual(moeda_display(1250), '12 PO 5 PP')
        self.assertNotIn(',', moeda_display(1250))
        # decompor devolve os números das três caixinhas da ficha
        self.assertEqual(decompor(134), (False, 1, 3, 4))
        self.assertEqual(decompor(-134), (True, 1, 3, 4))
        self.assertEqual(decompor(0), (False, 0, 0, 0))
        # preço do catálogo entra em uma moeda e sai composto
        self.assertEqual(preco_display('2 PP'), '2 PP')
        self.assertEqual(preco_display('5 PO'), '5 PO')
        self.assertEqual(preco_display('15 PC'), '1 PP 5 PC')
        self.assertIsNone(preco_display(''))

    def test_ficha_mostra_carteira_em_tres_caixinhas(self):
        p = self._guerreiro_no_nivel(1)
        p.carteira_pc = 134  # 1 PO 3 PP 4 PC
        p.save(update_fields=['carteira_pc'])
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('data-carteira', html)
        # as TRÊS caixinhas existem e trazem cada componente
        for attr, valor in (('data-carteira-po', '1'), ('data-carteira-pp', '3'),
                            ('data-carteira-pc', '4')):
            self.assertIn('<span class="coin-val" %s>%s</span>' % (attr, valor), html)
        self.assertIn('1 PO 3 PP 4 PC', html)   # string composta no title da caixa
        self.assertNotIn('1,3 PO', html)        # sem decimal em lugar nenhum

    def test_extrato_de_transacoes_composto(self):
        p = self._guerreiro_no_nivel(1)
        TbTransacao.objects.create(id_personagem=p, tipo='compra',
                                   descricao='Corda de cânhamo', valor_pc=-250, saldo_pc=1250)
        self.client.force_login(p.dono)
        html = self.client.get(
            reverse('ficha_detail', args=[p.pk]) + '?aba=historico').content.decode('utf-8')
        self.assertIn('-2 PO 5 PP', html)   # valor
        self.assertIn('12 PO 5 PP', html)   # saldo
        self.assertIn('Valores em PO / PP / PC', html)
        self.assertNotIn('-2,5 PO', html)

    def test_custo_do_item_no_inventario_composto(self):
        # item com custo em PP no catálogo continua exibido em PP (não vira "0,2 PO")
        p = self._guerreiro_no_nivel(1)
        TbPersonagemItem.objects.create(id_personagem=p, nome='Vela de teste', qtd=1,
                                        custo='2 PP')
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('Vela de teste', html)
        self.assertIn('2 PP', html)
        self.assertNotIn('0,2 PO', html)

    def test_mercado_lista_precos_compostos(self):
        # A loja migrou para o Mercado na onda C — a regra da moeda é a mesma: preço e
        # carteira decompostos, zero decimal.
        p = self._guerreiro_no_nivel(1)
        p.carteira_pc = 100_000
        p.save(update_fields=['carteira_pc'])
        self.client.force_login(p.dono)
        html = self.client.get(reverse('mercado_itens_mundanos')).content.decode('utf-8')
        self.assertIn('1000 PO', html)   # carteira do personagem ativo
        # item barato de verdade do catálogo aparece em PP/PC, não arredondado para PO
        self.assertRegex(html, r'mkt-row-price">\d+ P[PC]')


class DescansoCanonicoNaFichaTests(LevelUpLoteBase):
    def test_editar_ficha_nao_tem_mais_descanso(self):
        p = self._guerreiro_no_nivel(5)
        self.client.force_login(p.dono)
        html = self.client.get(reverse('editar_ficha', args=[p.pk])).content.decode('utf-8')
        self.assertNotIn(reverse('personagem_descansar', args=[p.pk]), html)
        self.assertNotIn('data-rest-form', html)
        self.assertNotIn('Descanso Curto', html)
        # (na onda C a página virou painel da staff: recursos, inventário e loja saíram —
        # ver test_ficha_v2_onda_b/onda_c)
        self.assertIn('lvl-aventuras-staffbox', html)

    def test_ficha_mantem_o_descanso_canonico(self):
        p = self._guerreiro_no_nivel(5)
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn(reverse('personagem_descansar', args=[p.pk]), html)
        self.assertIn('Desc. Curto', html)
        self.assertIn('Desc. Longo', html)


class MagiasForaDoRodapeTests(LevelUpLoteBase):
    def test_aba_ficha_nao_repete_a_lista_de_magias(self):
        p, _pc, _old, _new = self._ek(nivel=7, apelido='rodape')
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        # o painel de rodapé (título de seção "Magias" + regroup por nível) sumiu
        self.assertNotIn('<div class="ficha-section-title">Magias</div>', html)
        # ...e no lugar ficou só o chip de atalho para a aba própria
        self.assertIn('data-tab-jump="magias"', html)
        # a aba Magias continua sendo o lugar canônico
        self.assertIn('data-tabpanel="magias"', html)
        self.assertIn('spellbook-head', html)


class RecursosCompactosTests(LevelUpLoteBase):
    def test_contadores_pequenos_acima_de_caracteristicas(self):
        p = self._guerreiro_no_nivel(5)
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        # cartões gigantes morreram; contadores pequenos entraram
        self.assertNotIn('resource-card', html)
        self.assertNotIn('Recursos Consumiveis', html)
        self.assertIn('res-panel', html)
        self.assertIn('res-strip', html)
        self.assertIn('res-counter', html)  # Guerreiro tem recurso consumível (Retomar o Fôlego)
        # posição: painel de Recursos ANTES de "Características & Habilidades"
        self.assertLess(html.index('res-panel'), html.index('Características &amp; Habilidades'))
        # e DEPOIS do painel de ataques (ou seja: já na coluna da direita, não na central)
        self.assertLess(html.index('Ataques'), html.index('res-panel'))
        # descanso na mesma faixa dos contadores
        self.assertLess(html.index('res-strip'), html.index('res-rest'))


class ItensSintonizadosTests(LevelUpLoteBase):
    def _item_sintonizado(self, p, nome='Anel de Prova'):
        magico = TbItemMagico.objects.filter(requer_sintonizacao=True).first()
        self.assertIsNotNone(magico, 'fixture sem item mágico de sintonização')
        return TbPersonagemItem.objects.create(
            id_personagem=p, nome=nome, qtd=1, id_item_magico=magico,
            equipado=True, sintonizado=True)

    def test_bloco_entre_pv_e_ataques(self):
        p = self._guerreiro_no_nivel(5)
        self._item_sintonizado(p)
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('Itens Sintonizados', html)
        self.assertIn('data-attuned-list', html)
        self.assertIn('Anel de Prova', html)
        self.assertIn('pill attuned', html)
        # ordem: Pontos de Vida  <  Itens Sintonizados  <  Ataques
        self.assertLess(html.index('Pontos de Vida Máximos'), html.index('Itens Sintonizados'))
        self.assertLess(html.index('Itens Sintonizados'), html.index('>Ataques'))
        # só leitura: o form de sintonizar não está NESTE bloco — ele vive na aba Mochila
        # (onda B), que só começa depois do fim da aba Ficha.
        sint = reverse('personagem_sintonizar_item', args=[p.pk])
        self.assertLess(html.index('data-tabpanel="mochila"'), html.index(sint))
        self.assertNotIn(sint, html[html.index('data-attuned-list'):html.index('>Ataques')])

    def test_sem_sintonizados_nao_renderiza_o_bloco(self):
        p = self._guerreiro_no_nivel(1)
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertNotIn('Itens Sintonizados', html)


class PersonalidadeTests(LevelUpLoteBase):
    def test_ficha_do_dono_mostra_as_4_caixinhas_editaveis(self):
        p = self._guerreiro_no_nivel(1)
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('data-personalidade-panel', html)
        self.assertIn('data-pers-form', html)
        self.assertIn(reverse('personagem_personalidade_salvar', args=[p.pk]), html)
        for rotulo in ('Traços de Personalidade', 'Ideais', 'Vínculos', 'Defeitos'):
            self.assertIn(rotulo, html)
        for campo in ('name="traco"', 'name="ideal"', 'name="vinculo"', 'name="defeito"'):
            self.assertIn(campo, html)

    def test_endpoint_persiste_e_reexibe(self):
        p = self._guerreiro_no_nivel(1)
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_personalidade_salvar', args=[p.pk]),
            data={'traco': 'Fala pouco, observa muito.', 'ideal': 'Honra acima de tudo.',
                  'vinculo': 'Devo minha vida ao Ookami.', 'defeito': 'Não recuo de uma aposta.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        self.assertEqual([c['tipo'] for c in body['personalidade']],
                         ['traco', 'ideal', 'vinculo', 'defeito'])
        # persistiu 1 linha por tipo
        self.assertEqual(TbPersonagemPersonalidade.objects.filter(id_personagem=p).count(), 4)
        self.assertEqual(
            TbPersonagemPersonalidade.objects.get(id_personagem=p, tipo='ideal').texto,
            'Honra acima de tudo.')
        # e volta renderizado na ficha
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('Devo minha vida ao Ookami.', html)

    def test_reenvio_substitui_sem_duplicar_e_vazio_apaga(self):
        p = self._guerreiro_no_nivel(1)
        self.client.force_login(p.dono)
        url = reverse('personagem_personalidade_salvar', args=[p.pk])
        self.client.post(url, data={'traco': 'v1', 'ideal': 'i1', 'vinculo': '', 'defeito': ''})
        self.client.post(url, data={'traco': 'v2', 'ideal': '', 'vinculo': '', 'defeito': ''})
        linhas = {l.tipo: l.texto for l in TbPersonagemPersonalidade.objects.filter(id_personagem=p)}
        self.assertEqual(linhas, {'traco': 'v2'})

    def test_visitante_ve_so_leitura(self):
        p = self._guerreiro_no_nivel(1)
        p.publico = True
        p.save(update_fields=['publico'])
        TbPersonagemPersonalidade.objects.create(id_personagem=p, tipo='ideal', texto='Liberdade.')
        outro = self._novo_usuario('pers-visitante', staff=False)
        self.client.force_login(outro)
        resp = self.client.get(reverse('ficha_detail', args=[p.pk]))
        public = reverse('ficha_publica', args=[p.pk])
        self.assertRedirects(resp, public)
        html = self.client.get(public).content.decode('utf-8')
        self.assertNotIn('Liberdade.', html)
        self.assertNotIn('name="ideal"', html)
        self.assertNotIn(reverse('personagem_personalidade_salvar', args=[p.pk]), html)

    def test_endpoint_recusa_quem_nao_e_dono(self):
        p = self._guerreiro_no_nivel(1)
        outro = self._novo_usuario('pers-intruso', staff=False)
        self.client.force_login(outro)
        resp = self.client.post(reverse('personagem_personalidade_salvar', args=[p.pk]),
                                data={'traco': 'hack'})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(TbPersonagemPersonalidade.objects.filter(id_personagem=p).exists())


class PrecoEmPcSegueInternoTests(LevelUpLoteBase):
    def test_armazenamento_continua_em_pc(self):
        # a mudança é SÓ de exibição: o parser de preço e a carteira seguem em PC
        self.assertEqual(preco_em_pc('5 PO'), 500)
        self.assertEqual(preco_em_pc('2 PP'), 20)
        p = self._guerreiro_no_nivel(1)
        p.carteira_pc = 777
        p.save(update_fields=['carteira_pc'])
        p.refresh_from_db()
        self.assertEqual(p.carteira_pc, 777)
