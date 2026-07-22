# -*- coding: utf-8 -*-
"""Regressão do CLÃ/HERANÇA de Vampirismo no Criador (bugs da tester Evangeline).

O Vampirismo é uma ESSÊNCIA (TbEssencia slug='vampirismo'); suas heranças (Rubedo,
Sybaris, Tenebrus, Corvinus, Vesania, Mestiços) NÃO têm modelo próprio — são detectadas
pelo pré-requisito "Clã <Nome>" dos traços da essência e viram uma sub-escolha análoga à
vertente elemental (persistida como TbPersonagemEscolha tipo='vertente').

Cobre:
  A. Seletor de herança existe e é selecionável, com as perícias/benefícios CERTOS por clã.
  B. Exclusão mútua: só o clã escolhido aplica (Educação Rubedo XOR Sangue Ruim…).
  C. Percepção (Presença da Noite) aparece nas perícias concedidas (compartilhada).
  D. Talentos do vampiro entram no pool de talento racial, FILTRADOS pelo clã escolhido.
"""
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from home import views
from home.character_engine import (derive, _tracos_raciais, clas_de_essencia,
                                   cla_de_traco, cla_escolhido)
from home.models import (TbEssencia, TbRaca, TbClasse, TbPersonagem,
                         TbPersonagemClasse, TbPersonagemEscolha, TbTracoracial)
from home.test_criador import _CriadorBase


class _VampBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('loaddata', 'home/fixtures/conteudo.json', verbosity=0)
        cls.ess = TbEssencia.objects.get(slug='vampirismo')
        cls.raca = TbRaca.objects.filter(permite_essencia=True).first()
        cls.classe = TbClasse.objects.first()

    def _vampiro(self, cla=None, nivel=1):
        u = User.objects.create_user(username='v-%s-%s' % (cla, nivel), password='x')
        p = TbPersonagem.objects.create(dono=u, nome='Vamp', nivel=nivel,
                                        id_raca=self.raca, id_essencia=self.ess)
        TbPersonagemClasse.objects.create(id_personagem=p, id_classe=self.classe,
                                          nivel=nivel, principal=True)
        if cla:
            TbPersonagemEscolha.objects.create(id_personagem=p, origem='Essência',
                                               tipo='vertente', valor=cla)
        return p


class ClanCatalogoTests(_VampBase):
    """A/C — catálogo do criador expõe a herança selecionável e as concedidas certas."""

    def test_A_seletor_de_cla_existe(self):
        cat = views._criador_catalogos()
        ev = next(e for e in cat['essencias'] if e['slug'] == 'vampirismo')
        self.assertEqual(ev['subescolha_tipo'], 'cla')
        self.assertEqual(ev['subescolha_label'], 'Clã / Herança')
        slugs = {o['slug'] for o in ev['vertentes']}
        self.assertEqual(slugs, {'rubedo', 'sybaris', 'tenebrus', 'corvinus', 'vesania', 'mesticos'})

    def test_A_pick_rubedo_tem_lista_certa(self):
        # BUG: o `de:[arcanismo, intuicao, persuasao]` DENTRO dos parênteses era engolido pelo
        # regex e a Educação Rubedo passava a oferecer QUALQUER perícia.
        cat = views._criador_catalogos()
        picks = cat['racial_choices_essencia']['vampirismo']
        rub = next(p for p in picks if p['fonte'] == 'Educação Rubedo')
        self.assertEqual(set(rub['de']), {'arcanismo', 'intuicao', 'persuasao'})
        self.assertEqual(rub['vertente'], 'rubedo')
        sangue = next(p for p in picks if p['fonte'] == 'Sangue Ruim')
        self.assertEqual(sangue['vertente'], 'mesticos')

    def test_C_percepcao_concedida_compartilhada(self):
        cat = views._criador_catalogos()
        conc = cat['pericias_concedidas_essencia']['vampirismo']
        by = {c['slug']: c for c in conc}
        self.assertIn('percepcao', by)
        self.assertEqual(by['percepcao']['vertente'], '')          # compartilhada = sempre
        self.assertEqual(by['percepcao']['fonte'], 'Presença da Noite')
        # perícias de clã vêm marcadas com o clã (o front só as mostra no clã casado)
        self.assertEqual(by['furtividade']['vertente'], 'tenebrus')
        self.assertEqual(by['acrobacia']['vertente'], 'sybaris')


class ClanExclusaoDeriveTests(_VampBase):
    """B — só o clã escolhido aplica no derive; heranças são mutuamente exclusivas."""

    def _tracos_nomes(self, p):
        return {t.nome for (_o, _f, t, _c) in _tracos_raciais(p) if t.id_essencia_id}

    def test_B_rubedo_nao_herda_outros_clas(self):
        p = self._vampiro(cla='rubedo')
        nomes = self._tracos_nomes(p)
        self.assertIn('Educação Rubedo', nomes)
        self.assertIn('Presença da Noite', nomes)                  # compartilhado
        for outro in ('Educação Sybaris', 'Educação Tenebrus', 'Educação Corvinus',
                      'Educação Vesánia', 'Sangue Ruim'):
            self.assertNotIn(outro, nomes)

    def test_B_derive_pericias_do_cla_certo(self):
        # Sybaris concede Acrobacia; Rubedo NÃO. Rubedo não pode receber Furtividade/Acrobacia.
        prub = derive(self._vampiro(cla='rubedo'))
        prof_rub = {x['nome'] for x in prub['pericias'] if x['proficiente']}
        self.assertIn('Percepção', prof_rub)                       # compartilhada (Presença da Noite)
        self.assertNotIn('Acrobacia', prof_rub)                    # Sybaris — não deve vazar
        self.assertNotIn('Furtividade', prof_rub)                  # Tenebrus — não deve vazar

        psyb = derive(self._vampiro(cla='sybaris'))
        prof_syb = {x['nome'] for x in psyb['pericias'] if x['proficiente']}
        self.assertIn('Acrobacia', prof_syb)                       # Educação Sybaris aplicou
        self.assertIn('Percepção', prof_syb)

    def test_B_sem_cla_nao_aplica_traco_de_cla(self):
        p = self._vampiro(cla=None)
        nomes = self._tracos_nomes(p)
        self.assertIn('Presença da Noite', nomes)                  # compartilhado aplica
        self.assertNotIn('Educação Rubedo', nomes)                 # nenhum clã ⇒ nenhum traço de clã


class ClanTalentoPoolTests(_VampBase):
    """D — talentos do vampiro entram no pool de talento racial, filtrados pelo clã."""

    def _pool_nv5(self, p):
        out = {}
        for blk in views._pendencias_talento_racial(p):
            out[blk['nivel']] = {o['nome'] for o in blk['opcoes']}
        return out

    def test_D_pool_inclui_talentos_do_vampiro(self):
        pool = self._pool_nv5(self._vampiro(cla='rubedo', nivel=5))
        nv5 = pool.get(5, set())
        # compartilhados (qualquer clã) aparecem
        self.assertIn('Espreitador Noturno', nv5)
        self.assertIn('Brumas de Velmourn', nv5)

    def test_D_pool_filtra_segredos_por_cla(self):
        nv5_rub = self._pool_nv5(self._vampiro(cla='rubedo', nivel=5)).get(5, set())
        self.assertIn('Segredos Rubedo', nv5_rub)
        for outro in ('Segredos Sybaris', 'Segredos Tenebrus', 'Segredos Corvinus', 'Segredos Vesánia'):
            self.assertNotIn(outro, nv5_rub)

        nv5_syb = self._pool_nv5(self._vampiro(cla='sybaris', nivel=5)).get(5, set())
        self.assertIn('Segredos Sybaris', nv5_syb)
        self.assertNotIn('Segredos Rubedo', nv5_syb)


class ClanHelperTests(_VampBase):
    """Unidades dos detectores de clã (base para A–D)."""

    def test_clas_de_essencia(self):
        clas = {c['slug'] for c in clas_de_essencia(self.ess)}
        self.assertEqual(clas, {'rubedo', 'sybaris', 'tenebrus', 'corvinus', 'vesania', 'mesticos'})

    def test_cla_de_traco(self):
        clas = clas_de_essencia(self.ess)
        by = {t.nome: t for t in TbTracoracial.objects.filter(id_essencia=self.ess)}
        self.assertEqual(cla_de_traco(by['Educação Rubedo'], clas), 'rubedo')
        self.assertEqual(cla_de_traco(by['Sangue Ruim'], clas), 'mesticos')
        self.assertEqual(cla_de_traco(by['Segredos Rubedo'], clas), 'rubedo')
        self.assertEqual(cla_de_traco(by['Presença da Noite'], clas), '')   # compartilhado


class ClanEndpointTests(_CriadorBase):
    """A/B/validação — criação via endpoint persiste o clã e valida a sub-escolha.
    Reusa o _payload/_post_criar completos do test_criador (montam picks/estilo/maestria)."""

    def _vamp_payload(self, vertente='rubedo', escolhas_raca=None):
        # 'anao' permite essência (mesmo caminho do test_feiticeiro_com_essencia).
        return self._payload('guerreiro', raca_slug='anao', essencia_slug='vampirismo',
                             vertente=vertente, escolhas_raca=escolhas_raca or {})

    def test_criacao_persiste_cla(self):
        user = self._novo_usuario('dono-vamp', staff=True)
        resp = self._post_criar(user, self._vamp_payload(
            vertente='rubedo', escolhas_raca={'pericias': ['arcanismo']}))
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body.get('ok'), body)
        p = TbPersonagem.objects.get(pk=body['id'])
        self.assertEqual(cla_escolhido(p), 'rubedo')
        nomes = {t.nome for (_o, _f, t, _c) in _tracos_raciais(p) if t.id_essencia_id}
        self.assertIn('Educação Rubedo', nomes)
        self.assertNotIn('Sangue Ruim', nomes)               # herança mutuamente exclusiva

    def test_criacao_sem_cla_falha(self):
        # sub-escolha obrigatória: sem clã, criação recusada (400) com mensagem de erro.
        user = self._novo_usuario('dono-vamp2', staff=True)
        resp = self._post_criar(user, self._vamp_payload(vertente=''))
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertFalse(body.get('ok'), body)
        self.assertTrue(any(('Clã' in e or 'Herança' in e) for e in body.get('erros', [])), body)
