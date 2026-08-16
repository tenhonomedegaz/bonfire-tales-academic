# -*- coding: utf-8 -*-
"""Regressão do talento racial humano 'Multitalentoso'.

BUG (print do PO): o traço humano ``Multitalentoso``
(``pick:talento:1(from:any_raca, requires:prereq, without{asi})``) concede um talento GERAL
"de qualquer raça". Ao escolher um talento geral elegível (ex.: 'Precisão') o painel
acusava *"Escolha de opção inválida (fora do universo, duplicada ou sem slot)."*.

Causa (dupla):
  1. ``picks._talento_universe`` só honrava o marcador de ORIGEM
     (``=talento_de_origem``/``tipo:origem``). O ``from:any_raca`` caía no ``all()`` e o
     universo misturava os 43 talentos de origem em vez dos GERAIS.
  2. Um humano **Erthari** possui DOIS ``pick:talento`` — 'Determinação Comum'
     (``=talento_de_origem``, só origem) E 'Multitalentoso' (geral) —, ambos
     ``persist_tipo='talento'`` / ``classe_id=None``. O apply pegava o PRIMEIRO grupo
     (o de origem) e validava o talento geral contra o universo só-origem → "fora do
     universo". O apply passa a desambiguar pelo grupo cujo universo CONTÉM o valor.

Roda contra o conteúdo real (fixture ``conteudo.json`` — raça Humanos, linhagem Erthari,
traços 'Multitalentoso'/'Determinação Comum', talento geral 'Precisão').
"""
from home import picks, views
from home.models import (
    TbClasse, TbRaca, TbLinhagem, TbTalento,
    TbPersonagem, TbPersonagemClasse, TbPersonagemTalento,
)
from home.test_criador import _CriadorBase


class TalentoHumanoMultitalentosoTests(_CriadorBase):
    def _humano(self, nivel, erthari=True, apelido='mt'):
        """Humano REAL (raça Humanos), Guerreiro no nível pedido. Com ``erthari`` recebe a
        linhagem Erthari — que concede o pick de ORIGEM 'Determinação Comum' (o par que
        colidia com o pick geral de Multitalentoso)."""
        u = self._novo_usuario('%s-%d-%s' % (apelido, nivel, erthari))
        p = TbPersonagem.objects.create(
            dono=u, nome='Humano N%d' % nivel, nivel=nivel,
            forca=10, destreza=15, constituicao=14,
            inteligencia=13, sabedoria=12, carisma=8,
            id_raca=TbRaca.objects.get(nome='Humanos'))
        if erthari:
            p.id_linhagem = TbLinhagem.objects.get(nome__icontains='Erthari')
            p.save(update_fields=['id_linhagem'])
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='guerreiro'),
            nivel=nivel, principal=True)
        return p

    def _add_multitalentoso(self, p):
        """Materializa o traço racial 'Multitalentoso' (talento_racial, escolhido no marco
        de nível 13) — resolvido por nome pelo character_engine, expõe o pick aninhado."""
        TbPersonagemTalento.objects.create(
            id_personagem=p, categoria='racial', nivel=13, nome='Multitalentoso')

    def _grupo(self, p, origem):
        return next(g for g in picks.resolve_personagem(p)
                    if g['kind'] in ('talento', 'talento_de_origem') and g['origem'] == origem)

    # -- pool -------------------------------------------------------------------
    def test_multitalentoso_pool_e_so_geral(self):
        p = self._humano(13)
        self._add_multitalentoso(p)
        g = self._grupo(p, 'Multitalentoso')
        tipos = {TbTalento.objects.get(slug=u['slug']).tipo.lower() for u in g['universo']}
        self.assertEqual(tipos, {'geral'}, 'o pool de Multitalentoso deve ser só talentos GERAIS')
        self.assertIn('precisao', {u['slug'] for u in g['universo']},
                      "talento geral elegível 'Precisão' (Nível 4+) presente em N13")

    def test_talento_nivel4_fora_do_pool_no_n1(self):
        # Sem Erthari: o pool honra requires:prereq e não oferece talentos de N4 no N1.
        p = self._humano(1, erthari=False)
        self._add_multitalentoso(p)
        grupos = [g for g in picks.resolve_personagem(p)
                  if g['kind'] in ('talento', 'talento_de_origem')
                  and g['origem'] == 'Multitalentoso']
        self.assertEqual(
            grupos, [],
            'sem talento geral elegível no N1, não deve existir uma pendência vazia',
        )

    # -- apply / persistência ---------------------------------------------------
    def test_talento_geral_elegivel_aceito_e_persiste(self):
        p = self._humano(13)  # Erthari: coexiste com o pick de ORIGEM 'Determinação Comum'
        self._add_multitalentoso(p)
        origens = {g['origem'] for g in picks.resolve_personagem(p)
                   if g['kind'] in ('talento', 'talento_de_origem')}
        self.assertEqual(origens, {'Determinação Comum', 'Multitalentoso'},
                         'os DOIS pick:talento (origem + geral) devem coexistir')
        erros = views._lvl_aplicar_opcao(p, {'slug': 'talento', 'val': 'precisao', 'classe': ''})
        self.assertEqual(erros, [], 'talento geral elegível deve ser aceito')
        self.assertEqual(
            p.escolhas.filter(tipo='talento', origem='Multitalentoso', valor='precisao').count(), 1,
            'persiste no grupo GERAL (Multitalentoso), não no de origem')

    def test_talento_de_origem_ainda_roteia_para_determinacao_comum(self):
        # O pick de ORIGEM da Erthari continua funcionando: um talento de origem cai no
        # grupo 'Determinação Comum', não no geral (desambiguação por universo).
        p = self._humano(13)
        self._add_multitalentoso(p)
        origem_slug = self._grupo(p, 'Determinação Comum')['universo'][0]['slug']
        erros = views._lvl_aplicar_opcao(p, {'slug': 'talento', 'val': origem_slug, 'classe': ''})
        self.assertEqual(erros, [])
        self.assertEqual(
            p.escolhas.filter(tipo='talento', origem='Determinação Comum', valor=origem_slug).count(), 1)

    def test_talento_duplicado_recusado(self):
        p = self._humano(13)
        self._add_multitalentoso(p)
        self.assertEqual(
            views._lvl_aplicar_opcao(p, {'slug': 'talento', 'val': 'precisao', 'classe': ''}), [])
        erros = views._lvl_aplicar_opcao(p, {'slug': 'talento', 'val': 'precisao', 'classe': ''})
        self.assertEqual(erros, [views._ERR_OPCAO_INVALIDA], 'talento já possuído recusado')
        self.assertEqual(p.escolhas.filter(tipo='talento', valor='precisao').count(), 1)
