# -*- coding: utf-8 -*-
"""Regressão dos 3 bugs do PAINEL DE TRAÇOS do criador (staff/Ookami, prints do Discord).

1. TRAÇO RESIDUAL AO TROCAR RAÇA — Anão + Essência Vampirismo (clã Corvinus) e depois
   troca para Elfo/Lunareth: o painel mostrava os traços do elfo E continuava exibindo
   "Educação Corvinus" embaixo. Causa: `onRaca()` reconstrói o <select> de essência por
   `innerHTML`, o que ZERA a seleção SEM disparar 'change' — e o listener que redesenha
   o painel da essência estava pendurado SÓ no select de essência. O painel (uma caixa
   irmã, logo abaixo da de raça) ficava congelado com os traços da essência anterior.

2. TODAS AS "EDUCAÇÕES" APARECEM — os traços de herança do Vampirismo (Educação Corvinus /
   Rubedo / Sybaris / Tenebrus / Vesánia + Sangue Ruim) são MUTUAMENTE EXCLUSIVOS (um clã
   por personagem), mas o catálogo entregava `essencias[].tracos` sem o clã de origem e o
   painel listava os seis. O filtro de clã já existia para talentos, perícias concedidas e
   picks — faltava para o painel de traços.

3. LEGIBILIDADE — os cards de traço vinham no formato corrido "Nome — descrição". Agora o
   NOME é título em linha própria (peso forte) e a descrição vem embaixo.

Roda contra o conteúdo real (fixture `conteudo.json`). Os itens 1 e 3 vivem no front
(criador.js / criador.css), então são provados por asserção na FONTE do asset — mesmo
padrão de `test_staff_lote4.DescansoBotaoCSSTests`.
"""
import os
import re

from django.test import SimpleTestCase

from home import views
from home.character_engine import clas_de_essencia
from home.models import TbEssencia
from home.test_criador import _CriadorBase

_BASE = os.path.dirname(os.path.abspath(__file__))
_JS_CRIADOR = os.path.join(_BASE, 'static', 'js', 'criador.js')
_CSS_CRIADOR = os.path.join(_BASE, 'static', 'css', 'pages', 'criador.css')


def _asset(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _bloco(js, nome):
    """CÓDIGO da função `nome` em criador.js (até a próxima declaração de função no mesmo
    nível de indentação), sem as linhas de comentário — o bastante para perguntar 'esta
    função aplica o filtro?' sem depender de um parser de JS. Os comentários saem para que
    a asserção fale do que o painel EMITE, não do que a explicação cita."""
    m = re.search(r'\n(\s*)function %s\(' % re.escape(nome), js)
    assert m, 'função %s não existe em criador.js' % nome
    resto = js[m.end():]
    fim = re.search(r'\n%sfunction ' % m.group(1), resto)
    corpo = resto[:fim.start()] if fim else resto
    return re.sub(r'^\s*//.*$', '', corpo, flags=re.M)


# ======================================================================================
# BUG 1 — trocar raça/linhagem/essência re-renderiza OS DOIS painéis de info
# ======================================================================================
class TracoResidualAoTrocarRacaTests(SimpleTestCase):
    def test_todo_seletor_de_origem_redesenha_os_dois_paineis(self):
        js = _asset(_JS_CRIADOR)
        self.assertRegex(
            js, r'function renderRaceInfoPanels\(\)\s*\{[^}]*renderRacaInfo\(\);'
                r'\s*renderEssenciaInfo\(\);[^}]*\}')
        # raça, linhagem, essência E sub-escolha (vertente/clã): qualquer uma delas
        # invalida os DOIS painéis, então todas passam pelo mesmo refresher.
        for sel in ('racaSel', 'linSel', 'essSel', 'verSel'):
            self.assertIn("%s.addEventListener('change', renderRaceInfoPanels)" % sel, js,
                          '%s não redesenha os painéis de info' % sel)

    def test_painel_da_essencia_nao_fica_amarrado_so_ao_select_de_essencia(self):
        js = _asset(_JS_CRIADOR)
        # O bug era exatamente este par: o select de raça só redesenhava o painel da RAÇA.
        self.assertNotIn("racaSel.addEventListener('change', renderRacaInfo)", js)
        self.assertNotIn("linSel.addEventListener('change', renderRacaInfo)", js)

    def test_painel_da_essencia_e_apagado_quando_nao_ha_essencia(self):
        js = _asset(_JS_CRIADOR)
        bloco = _bloco(js, 'renderEssenciaInfo')
        # fillInfo(box, null) esconde e LIMPA a caixa — é o que mata o traço residual.
        self.assertRegex(bloco, r'essWrap\.hidden \|\| !e\).*null')


class CatalogoNaoMisturaFontesTests(_CriadorBase):
    def test_tracos_da_raca_nao_trazem_traco_de_essencia(self):
        cat = views._criador_catalogos()
        nomes_ess = {t['nome'] for e in cat['essencias'] for t in e['tracos']}
        self.assertIn('Educação Corvinus', nomes_ess)
        for r in cat['racas']:
            vazamento = {t['nome'] for t in r['tracos']} & nomes_ess
            self.assertFalse(vazamento, 'raça %s traz traço de essência: %s'
                             % (r['slug'], sorted(vazamento)))


# ======================================================================================
# BUG 2 — painel de traços da essência filtrado pelo clã/herança selecionado
# ======================================================================================
class EducacaoFiltradaPorClaTests(_CriadorBase):
    def _vampirismo(self):
        cat = views._criador_catalogos()
        return next(e for e in cat['essencias'] if e['slug'] == 'vampirismo')

    def test_catalogo_marca_o_cla_de_cada_traco(self):
        tracos = {t['nome']: t.get('vertente') for t in self._vampirismo()['tracos']}
        self.assertEqual(tracos['Educação Corvinus'], 'corvinus')
        self.assertEqual(tracos['Educação Rubedo'], 'rubedo')
        self.assertEqual(tracos['Educação Sybaris'], 'sybaris')
        self.assertEqual(tracos['Educação Tenebrus'], 'tenebrus')
        self.assertEqual(tracos['Educação Vesánia'], 'vesania')
        self.assertEqual(tracos['Sangue Ruim'], 'mesticos')

    def test_traco_compartilhado_nao_tem_cla(self):
        tracos = {t['nome']: t.get('vertente') for t in self._vampirismo()['tracos']}
        for nome in ('Mordida Vampírica', 'Presença da Noite', 'Pressão Solar'):
            self.assertEqual(tracos[nome], '', '%s não é traço de clã' % nome)

    def test_um_cla_ve_uma_unica_educacao(self):
        """Com Corvinus escolhido, o painel (mesmo filtro do front) mostra 1 Educação."""
        tracos = self._vampirismo()['tracos']
        for cla in ('corvinus', 'rubedo', 'sybaris', 'tenebrus', 'vesania', 'mesticos'):
            visiveis = [t['nome'] for t in tracos
                        if not t.get('vertente') or t['vertente'] == cla]
            educacoes = [n for n in visiveis if n.startswith('Educação') or n == 'Sangue Ruim']
            self.assertEqual(len(educacoes), 1,
                             'clã %s vê %s' % (cla, educacoes))

    def test_essencia_sem_cla_mostra_todos_os_tracos(self):
        """Elemental/Dracônica/Nephilim não têm herança: nada é escondido (a menção a
        'ifrit' na DESCRIÇÃO de um traço elemental não pode virar filtro)."""
        cat = views._criador_catalogos()
        for e in cat['essencias']:
            if clas_de_essencia(TbEssencia.objects.get(slug=e['slug'])):
                continue
            self.assertTrue(e['tracos'], 'essência %s sem traços' % e['slug'])
            for t in e['tracos']:
                self.assertEqual(t.get('vertente'), '',
                                 'traço %s/%s ganhou filtro indevido' % (e['slug'], t['nome']))

    def test_js_filtra_os_tracos_da_essencia_pelo_cla_escolhido(self):
        bloco = _bloco(_asset(_JS_CRIADOR), 'renderEssenciaInfo')
        self.assertIn('currentVertente()', bloco)
        self.assertRegex(bloco, r't\.vertente === vert')


# ======================================================================================
# BUG 3 — card de traço: NOME como título em cima, descrição embaixo
# ======================================================================================
class TracoTituloEmLinhaPropriaTests(SimpleTestCase):
    def test_js_emite_nome_e_descricao_em_elementos_separados(self):
        bloco = _bloco(_asset(_JS_CRIADOR), 'infoTraitsHtml')
        self.assertIn('cf-info-trait-nome', bloco)
        self.assertIn('cf-info-trait-desc', bloco)
        # o formato corrido "Nome — descrição" morreu
        self.assertNotIn('— ', bloco)

    def test_css_poe_o_nome_em_bloco_e_a_descricao_embaixo(self):
        css = _asset(_CSS_CRIADOR)
        self.assertRegex(css, r'\.cf-info-trait-nome\s*\{[^}]*display:\s*block')
        self.assertRegex(css, r'\.cf-info-trait-nome\s*\{[^}]*font-weight:\s*7')
        self.assertRegex(css, r'\.cf-info-trait-desc\s*\{[^}]*display:\s*block')
