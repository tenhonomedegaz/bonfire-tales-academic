# -*- coding: utf-8 -*-
"""Regressão da FICHA v2 — onda A (quick wins), briefing docs/agentes/briefing_ficha_v2.md.

  1. Dinheiro SEMPRE exibido em PO (interno segue em PC): carteira, custo de item do
     inventário, extrato de transações e loja. PP/PC sumiram da UI.
  2. O botão/form de descanso saiu do editar_ficha — o canônico é o da ficha.
  3. O resumo de magias saiu do rodapé da aba Ficha (a aba Magias cobre); fica o chip.
  4. Recursos consumíveis viram CONTADORES pequenos posicionados ACIMA de
     "Características & Habilidades".
  5. Bloco "Itens Sintonizados" entre Pontos de Vida e Ataques (só leitura).
  6. Personalidade/Ideais/Vínculos/Defeitos com UI + edição pelo dono (fetch).

Roda contra o conteúdo real (fixture conteudo.json), reusando o `LevelUpLoteBase`.
"""
from django.urls import reverse

from home.moeda import po_display, preco_display, preco_em_pc
from home.models import (TbItemMagico, TbPersonagemItem, TbPersonagemPersonalidade,
                         TbTransacao)
from home.test_levelup import LevelUpLoteBase


class MoedaEmPoTests(LevelUpLoteBase):
    def test_po_display_formata_sempre_em_po(self):
        # inteiro sem casa decimal; fração com UMA casa e vírgula pt-BR; negativo com sinal
        self.assertEqual(po_display(0), '0 PO')
        self.assertEqual(po_display(100), '1 PO')
        self.assertEqual(po_display(1250), '12,5 PO')
        self.assertEqual(po_display(150000), '1500 PO')
        self.assertEqual(po_display(-500), '-5 PO')
        # PP/PC do catálogo entram e saem em PO
        self.assertEqual(preco_display('2 PP'), '0,2 PO')
        self.assertEqual(preco_display('5 PO'), '5 PO')
        self.assertIsNone(preco_display(''))

    def test_ficha_mostra_carteira_em_po_sem_pp_nem_pc(self):
        p = self._guerreiro_no_nivel(1)
        p.carteira_pc = 1250  # 12,5 PO
        p.save(update_fields=['carteira_pc'])
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('data-carteira', html)
        self.assertIn('12,5 PO', html)
        # as caixinhas PP/PC da mochila morreram
        self.assertNotIn('tracking-wider text-[var(--muted)]">PP<', html)
        self.assertNotIn('tracking-wider text-[var(--muted)]">PC<', html)

    def test_extrato_de_transacoes_em_po(self):
        p = self._guerreiro_no_nivel(1)
        TbTransacao.objects.create(id_personagem=p, tipo='compra',
                                   descricao='Corda de cânhamo', valor_pc=-250, saldo_pc=1250)
        self.client.force_login(p.dono)
        html = self.client.get(
            reverse('ficha_detail', args=[p.pk]) + '?aba=historico').content.decode('utf-8')
        self.assertIn('-2,5 PO', html)      # valor
        self.assertIn('12,5 PO', html)      # saldo
        self.assertIn('Valores em peças de ouro (PO).', html)
        self.assertNotIn('<span class="cur">PC</span>', html)

    def test_custo_do_item_no_inventario_em_po(self):
        # item comprado com custo em PP no catálogo aparece convertido em PO na mochila
        p = self._guerreiro_no_nivel(1)
        TbPersonagemItem.objects.create(id_personagem=p, nome='Vela de teste', qtd=1,
                                        custo='2 PP')
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('Vela de teste', html)
        self.assertIn('0,2 PO', html)
        self.assertNotIn('>2 PP<', html)

    def test_loja_lista_precos_em_po(self):
        # A loja migrou para o Mercado na onda C — a regra da moeda é a mesma: preço e
        # carteira SEMPRE em PO, nunca em PP/PC.
        p = self._guerreiro_no_nivel(1)
        p.carteira_pc = 100_000
        p.save(update_fields=['carteira_pc'])
        self.client.force_login(p.dono)
        html = self.client.get(reverse('mercado_itens_mundanos')).content.decode('utf-8')
        self.assertIn('1000 PO', html)  # carteira do personagem ativo, em PO
        for moeda in (' PP<', ' PC<'):
            self.assertNotIn('goods-price">%s' % moeda, html)


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
        p.publico = True  # pode_ver_ficha: dono, staff OU ficha pública
        p.save(update_fields=['publico'])
        TbPersonagemPersonalidade.objects.create(id_personagem=p, tipo='ideal', texto='Liberdade.')
        outro = self._novo_usuario('pers-visitante', staff=False)
        self.client.force_login(outro)
        resp = self.client.get(reverse('ficha_detail', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('Liberdade.', html)
        self.assertIn('pers-box is-read', html)
        # nada de formulário: sem textarea e sem o endpoint de gravação na página
        # (o seletor `[data-pers-form]` aparece só no <script>, por isso não serve de prova)
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
