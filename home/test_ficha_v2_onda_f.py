# -*- coding: utf-8 -*-
"""Regressão da FICHA v2 — onda F REDUZIDA (briefing docs/agentes/briefing_ficha_v2.md).

O que a onda entrega:
  1. NOTAS DO JOGADOR — o único DADO novo: `TbPersonagem.notas_jogador` (migração aditiva,
     tabela de memória) + endpoint de gravação para o dono ou a staff.
  2. REDISTRIBUIÇÃO da aba Ficha na disposição da folha clássica: atributos numa coluna
     estreita à esquerda, selos de CA/iniciativa/deslocamento + cartão de PV no topo do
     centro, ataques/recursos no centro e Características & Habilidades na coluna larga da
     direita — SEM caixa de scroll interno (reclamação explícita do PO).
  3. MOBILE em coluna única, na ordem de consulta em sessão.
  4. VERSÃO IMPRIMÍVEL (@media print): sem cromo do site, preto no branco, características
     na página seguinte.

FORA de escopo por VETO do PO: modo mesa (PV atual/temporário editável, testes contra a
morte, inspiração) — isso vive no VTT. O cartão de PV desta ficha continua sendo o display
estático do derive, e este arquivo TESTA esse veto (`test_pv_continua_display_estatico`).

Roda contra o conteúdo real (fixture conteudo.json), reusando o `LevelUpLoteBase`.
"""
import os
import re

from django.test import SimpleTestCase
from django.urls import reverse

from home.models import TbPersonagem
from home.test_levelup import LevelUpLoteBase

_CSS_FICHA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'static', 'css', 'pages', 'ficha.css')


def _css():
    with open(_CSS_FICHA, encoding='utf-8') as fh:
        return fh.read()


def _regras(css):
    """[(seletor, corpo)] das regras do arquivo — parser rasteiro, o bastante para
    perguntar 'esta seção declara scroll interno?' sem depender de biblioteca."""
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css)]


class NotasDoJogadorTests(LevelUpLoteBase):
    def test_campo_novo_nasce_vazio_e_nao_nulo(self):
        p = self._guerreiro_no_nivel(1, apelido='notas-default')
        p.refresh_from_db()
        self.assertEqual(p.notas_jogador, '')

    def test_dono_salva_e_a_nota_volta_na_ficha(self):
        p = self._guerreiro_no_nivel(1, apelido='notas-dono')
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_notas_salvar', args=[p.pk]),
            data={'notas_jogador': 'O ferreiro de Ravengard mente sobre o martelo.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        self.assertEqual(body['notas_jogador'], 'O ferreiro de Ravengard mente sobre o martelo.')
        p.refresh_from_db()
        self.assertEqual(p.notas_jogador, 'O ferreiro de Ravengard mente sobre o martelo.')
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('O ferreiro de Ravengard mente sobre o martelo.', html)

    def test_endpoint_recusa_quem_nao_e_dono(self):
        p = self._guerreiro_no_nivel(1, apelido='notas-intruso')
        outro = self._novo_usuario('notas-intruso-user', staff=False)
        self.client.force_login(outro)
        resp = self.client.post(reverse('personagem_notas_salvar', args=[p.pk]),
                                data={'notas_jogador': 'hack'})
        self.assertEqual(resp.status_code, 404)
        p.refresh_from_db()
        self.assertEqual(p.notas_jogador, '')

    def test_staff_salva_ficha_alheia(self):
        p = self._guerreiro_no_nivel(1, apelido='notas-staff')
        staff = self._novo_usuario('notas-staff-user', staff=True)
        self.assertNotEqual(staff.pk, p.dono_id)
        self.client.force_login(staff)
        resp = self.client.post(reverse('personagem_notas_salvar', args=[p.pk]),
                                data={'notas_jogador': 'Anotação da staff.'},
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200, resp.content)
        p.refresh_from_db()
        self.assertEqual(p.notas_jogador, 'Anotação da staff.')

    def test_post_sem_o_campo_nao_apaga_a_nota(self):
        # o autosave manda só o textarea; um POST de outro fluxo não pode zerar a nota
        p = self._guerreiro_no_nivel(1, apelido='notas-preserva')
        p.notas_jogador = 'não me apague'
        p.save(update_fields=['notas_jogador'])
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_notas_salvar', args=[p.pk]), data={},
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200, resp.content)
        p.refresh_from_db()
        self.assertEqual(p.notas_jogador, 'não me apague')

    def test_texto_gigante_e_truncado_no_teto(self):
        from home.views import NOTAS_JOGADOR_MAX
        p = self._guerreiro_no_nivel(1, apelido='notas-teto')
        self.client.force_login(p.dono)
        self.client.post(reverse('personagem_notas_salvar', args=[p.pk]),
                         data={'notas_jogador': 'x' * (NOTAS_JOGADOR_MAX + 500)})
        p.refresh_from_db()
        self.assertEqual(len(p.notas_jogador), NOTAS_JOGADOR_MAX)

    def test_bloco_e_privado_do_dono_e_da_staff(self):
        p = self._guerreiro_no_nivel(1, apelido='notas-privado')
        p.publico = True            # ficha pública: visitante VÊ a ficha...
        p.notas_jogador = 'segredo de mesa'
        p.save(update_fields=['publico', 'notas_jogador'])
        visitante = self._novo_usuario('notas-visitante', staff=False)
        self.client.force_login(visitante)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        # ...mas a nota do jogador é anotação pessoal, não vitrine
        self.assertNotIn('segredo de mesa', html)
        self.assertNotIn('notas-panel', html)
        self.assertNotIn(reverse('personagem_notas_salvar', args=[p.pk]), html)

    def test_dono_ve_o_textarea_com_autosave(self):
        p = self._guerreiro_no_nivel(1, apelido='notas-ui')
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('notas-panel', html)
        self.assertIn('data-notas-form', html)
        self.assertIn('data-notas-input', html)
        self.assertIn('name="notas_jogador"', html)
        self.assertIn(reverse('personagem_notas_salvar', args=[p.pk]), html)
        self.assertIn('Notas do Jogador', html)


class DisposicaoDaFolhaTests(LevelUpLoteBase):
    """A ordem do HTML É a disposição: as colunas do desktop e a coluna única do celular
    saem do mesmo documento (o CSS só recoloca)."""

    def _html(self, nivel=5, apelido='layout'):
        p = self._guerreiro_no_nivel(nivel, apelido=apelido)
        self.client.force_login(p.dono)
        return p, self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')

    def test_ordem_das_colunas_no_documento(self):
        _p, html = self._html()
        ordem = [
            'ficha-col-attrs',                  # coluna estreita: atributos + saves + perícias
            'Testes de Resistência',
            'Perícias',
            'ficha-col-center',                 # centro: selos + PV, depois o corpo
            'ficha-col-vitals',
            'vital-seals',
            'Pontos de Vida Máximos',
            'ficha-col-body',
            '>Ataques',
            'res-panel',                        # recursos compactos (onda A) na faixa dos ataques
            'ficha-col-feats',                  # direita larga
            'Características &amp; Habilidades',
            'pers-panel',                       # RP em largura cheia, sem apertar
            'notas-panel',
        ]
        posicoes = []
        for marca in ordem:
            self.assertIn(marca, html, 'sumiu do HTML: %s' % marca)
            posicoes.append(html.index(marca))
        self.assertEqual(posicoes, sorted(posicoes),
                         'a ordem dos blocos da aba Ficha mudou: %s' % list(zip(ordem, posicoes)))

    def test_selos_de_combate_no_topo_central(self):
        _p, html = self._html(apelido='selos')
        for marca in ('seal seal-ca', 'seal seal-init', 'seal seal-vel',
                      '>Armadura<', '>Iniciativa<', '>Deslocamento<'):
            self.assertIn(marca, html)
        # as caixinhas antigas de combate morreram junto com o CSS delas
        self.assertNotIn('combat-grid', html)
        self.assertNotIn('combat-box', html)
        self.assertNotIn('combat-grid', _css())
        self.assertNotIn('combat-box', _css())
        # os ganchos que a Mochila atualiza por fetch continuam de pé
        self.assertIn('data-ficha-ca', html)
        self.assertIn('data-ficha-pv', html)

    def test_pv_continua_display_estatico(self):
        """VETO do PO: modo mesa (PV atual/temporário editável, testes contra a morte,
        inspiração) é do VTT — a ficha mostra só o máximo derivado."""
        p, html = self._html(apelido='veto')
        self.assertIn('Pontos de Vida Máximos', html)
        for proibido in ('name="pv_atual"', 'name="pv_temporario"', 'data-pv-atual',
                         'Testes contra a Morte', 'Inspiração'):
            self.assertNotIn(proibido, html)

    def test_atributo_traz_valor_grande_e_modificador(self):
        _p, html = self._html(apelido='attrs')
        self.assertIn('attr-stack', html)
        self.assertIn('attr-score', html)
        self.assertIn('attr-mod', html)
        # o valor vem ANTES do modificador na caixa (valor grande, mod no selo da base)
        caixa = html[html.index('attr-box'):]
        self.assertLess(caixa.index('attr-score'), caixa.index('attr-mod'))

    def test_outras_abas_intactas(self):
        _p, html = self._html(apelido='abas')
        for aba in ('mochila', 'info', 'magias', 'historico'):
            self.assertIn('data-tabpanel="%s"' % aba, html)
        self.assertIn('data-mochila-lista', html)
        self.assertIn('spellbook-head', html)
        self.assertIn('data-opcoes-slot', html)

    def test_pagina_da_ficha_usa_a_largura_de_folha(self):
        _p, html = self._html(apelido='largura')
        self.assertIn('ficha-main', html)          # teto próprio (ficha.css), no lugar do max-w-5xl
        self.assertNotIn('max-w-5xl', html)

    def test_personagem_legado_renderiza(self):
        """Linha anterior à onda F: sem nota, sem personalidade e sem item — a folha nova
        precisa abrir igual (o campo novo é aditivo, não obrigatório)."""
        p = self._guerreiro_no_nivel(1, apelido='legado')
        p.personalidade.all().delete()
        TbPersonagem.objects.filter(pk=p.pk).update(notas_jogador='')
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('ficha_detail', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('ficha-col-attrs', html)
        self.assertIn('vital-seals', html)
        self.assertIn('notas-panel', html)
        self.assertIn('<textarea name="notas_jogador" rows="5" data-notas-input '
                      'placeholder="Pistas, nomes de NPC, combinados da mesa, lembretes de '
                      'sessão…"></textarea>', html)


class CaracteristicasSemScrollInternoTests(SimpleTestCase):
    """Reclamação explícita do PO: a coluna de Características NÃO pode ser uma caixinha
    rolável. Quem rola é a página. (Prova de CSS: não precisa de banco.)"""

    def test_css_das_caracteristicas_nao_declara_scroll_nem_teto_de_altura(self):
        proibidos = re.compile(r'overflow-y\s*:|overflow-x\s*:|overflow\s*:\s*(auto|scroll)'
                               r'|max-height\s*:', re.I)
        achados = []
        for seletor, corpo in _regras(_css()):
            if 'feat' not in seletor:
                continue
            if proibidos.search(corpo):
                achados.append('%s {%s}' % (seletor, corpo.strip()))
        self.assertEqual(achados, [],
                         'seção de Características com scroll/teto interno:\n' + '\n'.join(achados))

    def test_cartoes_se_distribuem_em_colunas(self):
        # distribuição em nível alto = mais de uma coluna quando a largura permite
        self.assertRegex(_css(), r'\.feat-grid\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fill')

    def test_accordion_mantem_apenas_o_clip_da_animacao(self):
        # `overflow: hidden` no cartão/corpo é o clip do acordeão — não é área rolável
        regras = dict(_regras(_css()))
        self.assertIn('hidden', regras['.feat-body-inner'])


class MobileColunaUnicaTests(SimpleTestCase):
    """No celular a folha é UMA coluna, na ordem de consulta em sessão. A ordem visual é
    montada no CSS (o documento nasce na ordem do desktop), então a prova é o CSS."""

    def _blocos_mobile(self):
        css = _css()
        primeiro = css.index('@media (max-width: 679px)')
        ultimo = css.rindex('@media (max-width: 679px)')
        self.assertNotEqual(primeiro, ultimo, 'faltou um dos blocos mobile da onda F')
        return css[primeiro:ultimo], css[ultimo:]

    def test_ordem_pv_atributos_ataques_caracteristicas(self):
        grid, _toque = self._blocos_mobile()
        # a coluna do centro se dissolve para PV e corpo entrarem separados na fila
        self.assertRegex(grid, r'\.ficha-col-center\s*\{\s*display:\s*contents')
        for seletor, ordem in (('.ficha-col-vitals', 1), ('.ficha-col-attrs', 2),
                               ('.ficha-col-body', 3), ('.ficha-col-feats', 4)):
            self.assertRegex(grid, re.escape(seletor) + r'\s*\{[^}]*order:\s*%d' % ordem,
                             'ordem do celular mudou em %s' % seletor)

    def test_alvos_de_toque_crescem(self):
        _grid, toque = self._blocos_mobile()
        for alvo in ('.ficha-tab', '.res-counter-actions button', '.res-rest button',
                     '.ficha-jump-chip', '.banner-btn'):
            self.assertIn(alvo, toque, 'sem alvo de toque no celular: %s' % alvo)


class VersaoImprimivelTests(SimpleTestCase):
    def test_stylesheet_de_impressao_existe(self):
        css = _css()
        self.assertIn('@media print', css)
        bloco = css[css.index('@media print'):]
        # cromo do site fora do papel
        for fora in ('header', 'footer', '.support-sidebar-left', '.ficha-tabs',
                     '.ficha-noprint', '.res-rest', '.banner-actions'):
            self.assertIn(fora, bloco, 'não some na impressão: %s' % fora)
        # preto no branco pelas variáveis do tema (vence até o style inline do tema-dado)
        self.assertIn('--text: #000 !important', bloco)
        self.assertIn('--bg0: #fff !important', bloco)
        # quebra sensata: atributos+combate na página 1, características a seguir
        self.assertRegex(bloco, r'\.ficha-col-feats\s*\{[^}]*break-before:\s*page')
        self.assertRegex(bloco, r'break-inside:\s*avoid')
        self.assertIn('@page', bloco)


class GanchoDeImpressaoNoMarkupTests(LevelUpLoteBase):
    def test_anuncios_tem_gancho_de_impressao(self):
        p = self._guerreiro_no_nivel(1, apelido='print')
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('ficha-noprint', html)
