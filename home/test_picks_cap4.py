# -*- coding: utf-8 -*-
"""Regressão do Cap4 (R3): registro genérico de `pick:<kind>` (menu define/inline) +
persistência e resolução das SUB-ESCOLHAS DE ESSÊNCIA.

Cobre:
  - Parser balanceado de tokens (`pick:sangue:1(=match(vertente){...})` não trunca).
  - Rota de MENU genérica: kinds define-based (Máscara de Guerra) e inline
    (energia/polo/elemento/sangue/save_prof/move) ABREM como grupo de escolha.
  - Universo DEPENDENTE (`pick:sangue` ramifica pela vertente): undine/sylph têm
    sub-escolha; ifrit/oread não (universo vazio -> sem pendência).
  - Derive materializa o VALOR ESCOLHIDO em resist:/immune: (nunca o literal
    'sangue'/'alento'/'match'); sem escolha, o literal é SUPRIMIDO (RELATORIO_R1 §9).
  - Guard do Oread (Scar): nenhuma pendência de essência nova, nenhum lixo na ficha.
  - Fix do vazamento de sub-pick de menu (Doutrina Marcial não vaza pick:arma/opcao).

Roda contra o conteúdo real (fixture `conteudo.json`).
"""
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from home import picks, character_engine as ce
from home.models import (
    TbPersonagem, TbPersonagemClasse, TbPersonagemEscolha,
    TbEssencia, TbClasse, TbRaca, TbClassehabilidade,
    TbRegra,
)


class _EssenciaBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        TbRegra.objects.filter(slug='aumento-de-atributo').delete()
        call_command('loaddata', 'home/fixtures/conteudo.json', verbosity=0)
        cls.user = User.objects.create_user('dono-cap4', password='x')
        cls.classe = TbClasse.objects.first()
        cls.raca = TbRaca.objects.first()

    def _personagem(self, essencia_pk, vertente=None, nivel=5):
        ess = TbEssencia.objects.get(pk=essencia_pk)
        p = TbPersonagem.objects.create(
            dono=self.user, nome='T-%s' % (vertente or ess.slug), nivel=nivel,
            id_raca=self.raca, id_essencia=ess,
            forca=10, destreza=12, constituicao=14,
            inteligencia=10, sabedoria=10, carisma=13)
        TbPersonagemClasse.objects.create(id_personagem=p, id_classe=self.classe,
                                           nivel=nivel, principal=True)
        if vertente:
            TbPersonagemEscolha.objects.create(
                id_personagem=p, origem='Essência %s' % ess.nome,
                tipo='vertente', valor=vertente)
        return p

    def _grupo(self, p, kind):
        return next((g for g in picks.resolve_personagem(p) if g['kind'] == kind), None)


class ParserBalanceadoTests(TestCase):
    """O parser de tokens casa ()/{} balanceado — a constraint com match() aninhado
    não é truncada no 1º ')' interno (bug que zerava o universo de pick:sangue)."""

    def test_constraint_com_match_aninhado_nao_trunca(self):
        tag = 'pick:sangue:1(=match(vertente){undine:{frio | acido}, sylph:{raio | trovejante}})'
        toks = list(picks.iter_pick_tokens(tag))
        self.assertEqual(len(toks), 1)
        tok = toks[0]
        self.assertEqual(tok.kind, 'sangue')
        self.assertEqual(tok.count_expr, '1')
        # a constraint inteira, com o bloco {...} fechado, chega ao parser
        self.assertIn('sylph:{raio | trovejante}}', tok.constraints['raw'])

    def test_inline_universe_depende_da_vertente(self):
        tag = 'pick:sangue:1(=match(vertente){undine:{frio | acido}, sylph:{raio | trovejante}})'
        tok = next(picks.iter_pick_tokens(tag))
        undine = [o['slug'] for o in picks._inline_menu_options(tok, {'vertente': 'undine'})]
        sylph = [o['slug'] for o in picks._inline_menu_options(tok, {'vertente': 'sylph'})]
        oread = [o['slug'] for o in picks._inline_menu_options(tok, {'vertente': 'oread'})]
        self.assertEqual(undine, ['frio', 'acido'])
        self.assertEqual(sylph, ['raio', 'trovejante'])
        self.assertEqual(oread, [])          # oread não ramifica -> sem sub-escolha

    def test_picks_de_runtime_nao_viram_escolha_persistente(self):
        tags = (
            'trigger=long_rest, instant{pick:mascara_guerra:1}',
            'while_active{pick:aspecto_selvagem:1}',
            'trigger=hit{pick:mordida_lacerante:1}',
        )
        for tag in tags:
            with self.subTest(tag=tag):
                self.assertEqual(list(picks.iter_pick_tokens(tag)), [])

    def test_picks_legitimos_fora_de_runtime_continuam_sendo_papel_a(self):
        tags = (
            'pick:opcao:metamagia:2',
            'pick:arma:2',
            'pick:pericia:1',
        )
        self.assertEqual(
            [next(picks.iter_pick_tokens(tag)).kind for tag in tags],
            ['opcao', 'arma', 'pericia'],
        )


class ChoiceSubsUnitTests(TestCase):
    """Unidades da resolução de referências no derive (_apply_choice_subs/_resolve_var)."""

    def test_match_pick_var_resolve(self):
        t = ce._apply_choice_subs(
            ce._resolve_match('resist:match(pick:energia){ lumen:radiante, umbra:necrotico }',
                              {'energia': 'lumen'}), {'energia': 'lumen'})
        self.assertEqual(t.strip(), 'resist:radiante')

    def test_operando_pick_ref(self):
        self.assertEqual(
            ce._apply_choice_subs('resist:pick:elemento', {'elemento': 'fogo'}),
            'resist:fogo')

    def test_declaracao_vira_verbo(self):
        self.assertEqual(
            ce._apply_choice_subs('pick:save_prof:{int|wis|cha}:1', {'save_prof': 'int'}),
            'save_prof:int')

    def test_sem_escolha_fica_inerte(self):
        # nada resolve -> token intacto (nada de lixo)
        self.assertEqual(ce._apply_choice_subs('resist:pick:elemento', {}),
                         'resist:pick:elemento')

    def test_resolve_var_suprime_literal_de_escolha(self):
        # 'sangue' sem escolha é placeholder; com escolha vira o valor
        self.assertIn('sangue', ce._PLACEHOLDERS)
        self.assertEqual(ce._resolve_var('sangue', {}, {'sangue': 'frio'}), 'frio')


class EssenciaElementalTests(_EssenciaBase):
    """Essência Elemental: pick:sangue ramifica pela vertente e materializa o escolhido."""

    def test_undine_abre_sangue_e_resolve(self):
        p = self._personagem(32, vertente='undine')
        g = self._grupo(p, 'sangue')
        self.assertIsNotNone(g, 'undine deve abrir a sub-escolha de sangue')
        self.assertEqual([o['slug'] for o in g['universo']], ['frio', 'acido'])
        self.assertEqual(g['pendentes'], 1)

        # ANTES de escolher: nenhum literal 'sangue' na ficha
        f = ce.derive(p)
        self.assertNotIn('sangue', f['resistencias'])

        # escolhe frio pela via genérica de persistência do REGISTRY
        picks.registry_entry('sangue')['persist'](p, g, ['frio'])
        f = ce.derive(p)
        self.assertIn('frio', f['resistencias'])           # valor ESCOLHIDO
        self.assertNotIn('sangue', f['resistencias'])       # nunca o literal
        # pendência zera
        self.assertEqual(self._grupo(p, 'sangue')['pendentes'], 0)

    def test_oread_nao_abre_sangue_nem_polui(self):
        """Guard do Scar (Oread): sem sub-escolha de sangue e sem literal na ficha."""
        p = self._personagem(32, vertente='oread')
        self.assertIsNone(self._grupo(p, 'sangue'),
                          'oread NÃO deve ganhar pendência de sangue')
        f = ce.derive(p)
        for lixo in ('sangue', 'match', 'vertente', 'alento'):
            self.assertNotIn(lixo, f['resistencias'])
            self.assertNotIn(lixo, f['imunidades'])

    def test_vertente_nunca_e_pendencia_generica(self):
        # vertente é fluxo dedicado do criador; nunca abre no painel genérico
        p = self._personagem(32, vertente='undine')
        self.assertIsNone(self._grupo(p, 'vertente'))


class EssenciaNephilimTests(_EssenciaBase):
    """Nephilim: polo/energia/elemento abrem inline; match(pick:energia) e pick:elemento
    materializam o valor escolhido; sem escolha, nada de literal 'match'."""

    def test_abre_polo_energia_elemento(self):
        p = self._personagem(29)
        for kind, universo in (('polo', {'celestial', 'infero'}),
                               ('energia', {'lumen', 'umbra'})):
            g = self._grupo(p, kind)
            self.assertIsNotNone(g, '%s deve abrir' % kind)
            self.assertEqual({o['slug'] for o in g['universo']}, universo)
        self.assertIsNotNone(self._grupo(p, 'elemento'))

    def test_sem_escolha_nao_vaza_match(self):
        p = self._personagem(29)
        f = ce.derive(p)
        self.assertNotIn('match', f['resistencias'])
        self.assertNotIn('energia', f['resistencias'])

    def test_energia_escolhida_materializa_resistencia(self):
        p = self._personagem(29)
        picks.registry_entry('energia')['persist'](p, self._grupo(p, 'energia'), ['lumen'])
        picks.registry_entry('elemento')['persist'](p, self._grupo(p, 'elemento'), ['fogo'])
        f = ce.derive(p)
        # resist:match(pick:energia){lumen:radiante} -> radiante ; resist:pick:elemento -> fogo
        self.assertIn('radiante', f['resistencias'])
        self.assertIn('fogo', f['resistencias'])
        self.assertNotIn('match', f['resistencias'])


class MenuDefineTests(_EssenciaBase):
    """Kinds define-based abrem via _MENU_ENTRY; sub-picks internos do menu NÃO vazam."""

    def test_doutrina_marcial_abre_sem_vazar_subpicks(self):
        o = TbClassehabilidade.objects.filter(pk=810).first()
        if o is None:
            self.skipTest('feature 810 ausente na fixture')
        grupos = picks.resolve_groups([o], classe=None, nivel=5)
        kinds = {g['kind'] for g in grupos}
        # o pick externo (doutrina_marcial) abre...
        self.assertIn('doutrina_marcial', kinds)
        dm = next(g for g in grupos if g['kind'] == 'doutrina_marcial')
        self.assertEqual({u['slug'] for u in dm['universo']},
                         {'estilo_de_luta', 'guerreiro_abencoado', 'armas_treinadas'})
        # ...e os sub-picks DENTRO do define (pick:arma:3, pick:opcao:estilo_de_luta) NÃO vazam
        self.assertNotIn('arma', kinds)
        self.assertNotIn('opcao', kinds)

    def test_registry_entry_resolve_menu_kind(self):
        # kind de menu não está no PICK_REGISTRY, mas registry_entry devolve o _MENU_ENTRY
        self.assertIs(picks.registry_entry('mascara_guerra'), picks._MENU_ENTRY)
        self.assertIs(picks.registry_entry('opcao'), picks.PICK_REGISTRY['opcao'])
