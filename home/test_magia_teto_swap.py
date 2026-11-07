# -*- coding: utf-8 -*-
"""Regressão do laudo de magia: TETO de nível de magia pela TABELA DE SLOTS da própria classe,
SWAP declarado no contrato `spellcasting`, e ADEPTO DAS VESTES (spell_selection `any`/classe com
`qtd` implícito e `escola:{A | B}` em conjunto).

Cobre as três correções do laudo:

  1. `_pendencias_magias`/`_magias_preparadas_info`: o nível máximo conhecível/preparável vem
     do TOPO da tabela de slots DA PRÓPRIA classe (single-class de propósito), não de uma
     fórmula fechada nem dos slots *pooled* de multiclasse.
       Paladino (half):          nv7 → 2,  nv9 → 3.
       Cavaleiro Arcano (third): nv3 → 1,  nv7 → 2,  nv13 → 3  (tabela guardada na SUBCLASSE).
     O APPLY (validação do lote) lê o MESMO `_pendencias_magias` — logo o mesmo teto.

  2. Troca de magia ao subir de nível: EXPLÍCITA em `swap{event:level_up,max:1|all}`.
     Cavaleiro Arcano/Místico trocam uma; Bardo/Feiticeiro podem trocar todo o repertório;
     conjuradores preparados não recebem troca de repertório no level-up.

  3. Adepto da Veste Negra: `spell_selection:any{nivel:2, escola:{encantamento | necromancia}}`
     + `cast{spell:spell_selection}` oferece a escolha de 1 magia de 2º ciclo de encantamento
     OU necromancia e persiste como `magia-concedida`. Adepto Místico (escopo de classe,
     `qtd` implícito) idem, com pool de 1º ciclo do Místico.

Reaproveita o `_CriadorBase` de test_criador.py (fixture real `conteudo.json`, formato que o
character_engine lê — tags com underscore)."""
from django.urls import reverse

from home import views
from home.character_engine import magias_concedidas, _norm_escola
from home.models import (
    TbClasse, TbSubclasse, TbTalento, TbMagia, TbPersonagem, TbPersonagemClasse,
    TbPersonagemTalento, TbPersonagemEscolha, TbPersonagemMagia,
)
from home.test_criador import _CriadorBase


class _MagiaBase(_CriadorBase):
    def _personagem(self, nome, staff=False):
        u = self._novo_usuario('dono-%s' % nome.lower(), staff=staff)
        return TbPersonagem.objects.create(dono=u, nome=nome)

    def _com_classe(self, classe_slug, nivel, sub_nome=None, nome='caster'):
        """Personagem single-class REAL (só o que `_pendencias_magias` lê: classe principal +
        nível + subclasse já desbloqueada, quando pedida)."""
        p = self._personagem(nome)
        classe = TbClasse.objects.get(slug=classe_slug)
        sub = TbSubclasse.objects.get(id_classe=classe, nome__icontains=sub_nome) if sub_nome else None
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=classe, id_subclasse=sub, nivel=nivel, principal=True)
        p.nivel = nivel
        p.save(update_fields=['nivel'])
        return p

    def _com_talento(self, talento_slug, nome):
        p = self._personagem(nome)
        tal = TbTalento.objects.get(slug=talento_slug)
        TbPersonagemTalento.objects.create(
            id_personagem=p, id_talento=tal, categoria='talento', nome=tal.nome)
        return p, tal


class TetoNivelMagiaTests(_MagiaBase):
    """O teto de nível de magia vem do TOPO da tabela de slots da própria classe/subclasse."""

    def _teto(self, p):
        pend = views._pendencias_magias(p)
        self.assertIsNotNone(pend, 'sem pendências de magia para %s' % p.nome)
        return pend['max_nivel']

    def test_paladino_half_caster_teto_pela_tabela(self):
        # half-caster: 2º ciclo só a partir do nv5, 3º ciclo a partir do nv9. A fórmula velha
        # (min(5,(nivel+5)//4)) dava 3 no nv7 — errado; a tabela dá 2.
        self.assertEqual(self._teto(self._com_classe('paladino', 7, nome='pal7')), 2)
        self.assertEqual(self._teto(self._com_classe('paladino', 9, nome='pal9')), 3)

    def test_cavaleiro_arcano_third_caster_teto_pela_tabela(self):
        # third-caster (tabela de slots guardada na SUBCLASSE): 1º@nv3, 2º@nv7, 3º@nv13.
        self.assertEqual(self._teto(self._com_classe('guerreiro', 3, 'Arcano', 'ek3')), 1)
        self.assertEqual(self._teto(self._com_classe('guerreiro', 7, 'Arcano', 'ek7')), 2)
        self.assertEqual(self._teto(self._com_classe('guerreiro', 13, 'Arcano', 'ek13')), 3)

    def test_apply_valida_com_o_mesmo_teto(self):
        # O APPLY (`_lvl_aplicar_aprender_magias`/`_lvl_aplicar_trocar_magia`) valida contra o
        # MESMO `_pendencias_magias`: `max_nivel` e a `lista_magias` não vazam acima do teto.
        pend = views._pendencias_magias(self._com_classe('paladino', 7, nome='palapply'))
        self.assertEqual(pend['max_nivel'], 2)
        self.assertTrue(pend['lista_magias'], 'lista de magias vazia (esperava opções ≤ 2º ciclo)')
        self.assertTrue(all(m['nivel'] <= 2 for m in pend['lista_magias']),
                        'apply enxergaria magia acima do teto')

    def test_fallback_half_segue_a_escada_da_tabela(self):
        # O fallback documentado (`_max_spell_level_for_slots`) foi corrigido p/ a MESMA escada
        # (1º@nv2, 2º@nv5, 3º@nv9, 4º@nv13, 5º@nv17) — rede de segurança consistente.
        f = lambda n: views._max_spell_level_for_slots(n, 'half')
        self.assertEqual([f(n) for n in (2, 5, 7, 9, 13, 17, 20)], [1, 2, 2, 3, 4, 5, 5])


class SwapDeclaradoTests(_MagiaBase):
    """Troca de magia ao subir de nível vem somente do contrato declarativo."""

    def _swap(self, p):
        pend = views._pendencias_magias(p)
        self.assertIsNotNone(pend, 'sem pendências de magia para %s' % p.nome)
        return pend['swap_level_up']

    def test_cavaleiro_arcano_e_mistico_declaram_uma_troca(self):
        ek = self._com_classe('guerreiro', 7, 'Arcano', 'ekswap')
        mistico = self._com_classe('mistico', 7, nome='misticswap')
        for personagem in (ek, mistico):
            pend = views._pendencias_magias(personagem)
            self.assertTrue(pend['swap_level_up'])
            self.assertEqual(pend['swap_limite'], 1)
            self.assertEqual(
                views._classe_spellcasting_info(
                    personagem.classes.first().id_classe,
                    nivel_habilidades=personagem.classes.first().nivel,
                    subclasse=views._caster_subclasse(personagem.classes.first()))['swap']['max'],
                1)

    def test_bardo_e_feiticeiro_declaram_troca_de_todo_repertorio(self):
        for slug in ('bardo', 'feiticeiro'):
            p = self._com_classe(slug, 7, nome='%sswap' % slug)
            info = views._classe_spellcasting_info(
                p.classes.first().id_classe, nivel_habilidades=7)
            self.assertEqual(info['swap'], {'event': 'level_up', 'max': 'all'})

    def test_mago_preparadas_nao_ve_swap(self):
        # prepara:preparadas (re-prepara livre a cada descanso) → NÃO troca ao subir.
        self.assertFalse(self._swap(self._com_classe('mago', 7, nome='magoswap')))

    def test_paladino_preparadas_nao_ve_swap(self):
        # Decisão do PO: Paladino é conjurador PREPARADO (prepara:preparadas, re-prepara a cada
        # descanso longo) → NÃO troca ao subir de nível. O swap saiu junto com a coluna de
        # "magias conhecidas"; a inferência por prepara:preparadas já garante o False.
        self.assertFalse(self._swap(self._com_classe('paladino', 9, nome='palnoswap')))


class AdeptoDasVestesTests(_MagiaBase):
    """spell_selection com `qtd` implícito (via cast{spell:spell_selection}), escopo `any` sem
    filtro de classe e `escola:{A | B}` como conjunto. Materializa como `magia-concedida`."""

    def _bloco(self, info, fonte):
        return next((b for b in info['pendentes'] if b['fonte'] == fonte), None)

    def test_veste_negra_encant_ou_necro_2o_ciclo_e_persiste(self):
        p, tal = self._com_talento('adepto-da-veste-negra', 'vestenegra')
        bloco = self._bloco(magias_concedidas(p), tal.nome)
        self.assertIsNotNone(bloco, 'Adepto da Veste Negra não ofereceu escolha de magia')
        self.assertEqual(bloco['qtd'], 1)                       # "1 magia à sua escolha"
        self.assertIn('Encantamento', bloco['rotulo'])
        self.assertIn('Necromancia', bloco['rotulo'])
        opc = set(bloco['opcoes'])
        self.assertTrue(opc, 'pool vazio')
        for slug in opc:                                        # só 2º ciclo de encant/necro
            mg = TbMagia.objects.get(slug=slug)
            self.assertEqual(mg.nivel, 2, slug)
            self.assertIn(_norm_escola(mg.escola), {'encantamento', 'necromancia'}, slug)

        # PERSISTE pelo endpoint das vertentes (magia-concedida) e sai de pendente → concedida.
        escolhido = sorted(opc)[0]
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_escolher_magia_essencia', args=[p.pk]),
            data={'fonte': tal.nome, 'slot': bloco['slot'], 'magia': escolhido})
        self.assertEqual(resp.status_code, 302, resp.content)
        self.assertTrue(TbPersonagemEscolha.objects.filter(
            id_personagem=p, tipo='magia-concedida', origem=tal.nome, valor=escolhido).exists())
        info2 = magias_concedidas(p)
        self.assertNotIn(tal.nome, [b['fonte'] for b in info2['pendentes']])
        self.assertIn(escolhido, [c['slug'] for c in info2['concedidas']])
        self.assertTrue(TbPersonagemMagia.objects.filter(
            id_personagem=p, id_magia__slug=escolhido, sempre_preparada=True).exists())

    def test_adepto_mistico_escopo_classe_qtd_implicito_e_persiste(self):
        p, tal = self._com_talento('adepto-mistico', 'adeptomistico')
        bloco = self._bloco(magias_concedidas(p), tal.nome)
        self.assertIsNotNone(bloco, 'Adepto Místico não ofereceu escolha (escopo de classe)')
        self.assertEqual(bloco['qtd'], 1)                       # qtd IMPLÍCITO = 1
        mistico_nome = TbClasse.objects.get(slug='mistico').nome
        self.assertIn(mistico_nome, bloco['rotulo'])
        opc = set(bloco['opcoes'])
        self.assertTrue(opc, 'pool vazio')
        for slug in opc:                                        # 1º ciclo da lista do Místico
            mg = TbMagia.objects.get(slug=slug)
            self.assertEqual(mg.nivel, 1, slug)
            self.assertIn(mistico_nome, {c.strip() for c in (mg.classes or '').split(',')}, slug)

        # persiste pela mesma via de escolha (TbPersonagemEscolha) e vira concedida.
        escolhido = sorted(opc)[0]
        TbPersonagemEscolha.objects.create(
            id_personagem=p, tipo='magia-concedida', origem=tal.nome,
            slot=bloco['slot'], valor=escolhido)
        info2 = magias_concedidas(p)
        self.assertIn(escolhido, [c['slug'] for c in info2['concedidas']])
        self.assertNotIn(tal.nome, [b['fonte'] for b in info2['pendentes']])

    def test_talento_sem_cast_selection_nao_inventa_escolha(self):
        # Guarda de não-regressão: um spell_selection com filtro MAS sem `cast{spell:spell_selection}`
        # e sem `qtd:` continua sem oferecer escolha (o `qtd` implícito exige o cast irmão).
        from home.character_engine import _grants_de_tag
        catalog = {sl: nv for sl, nv in TbMagia.objects.values_list('slug', 'nivel')}
        tag = 'spell_selection:mistico{nivel:1, spell_mod:cha_mod}'
        _fx, esc_on, _g = _grants_de_tag(tag, {}, catalog, 20, casts_selection=True)
        _fx, esc_off, _g = _grants_de_tag(tag, {}, catalog, 20, casts_selection=False)
        self.assertIsNotNone(esc_on)      # com o cast irmão → escolha
        self.assertIsNone(esc_off)        # sem o cast irmão → nada


class TrocaMagiaGateTests(_MagiaBase):
    """Um contrato com ``max:1`` troca UMA magia por nível. Cada troca registra o nível
    total em que foi usada (TbPersonagemEscolha tipo='troca_magia'); a SEGUNDA troca no MESMO
    nível é recusada com `_ERR_TROCA_JA_USADA` — vale para o POST direto, para o endpoint
    legado (`personagem_trocar_magia`) e para o lote (`_levelup_aplicar_lote`). Subir de nível
    libera outra troca; personagens ANTIGOS (sem registro) ganham a troca do nível atual."""

    def _caster(self, nivel=9, nome='swapper'):
        """Místico (`swap.max:1`) com uma magia conhecida pronta para trocar."""
        p = self._com_classe('mistico', nivel, nome=nome)
        pend = views._pendencias_magias(p)
        self.assertTrue(pend['swap_level_up'], 'místico deveria permitir troca ao subir de nível')
        opcoes = [m['slug'] for m in pend['lista_magias']]
        self.assertGreaterEqual(len(opcoes), 2, 'pool de magias insuficiente para o teste')
        old_slug, new_slug = opcoes[0], opcoes[1]
        mg = TbMagia.objects.get(slug=old_slug)
        origem = p.classes.first().id_classe.nome
        TbPersonagemMagia.objects.create(id_personagem=p, id_magia=mg, nivel=mg.nivel,
                                         nome=mg.nome, preparada=True, origem=origem)
        return p, old_slug, new_slug

    def test_primeira_troca_aplica_e_registra(self):
        # 1ª troca no nível: aplica (old sai, new entra) E grava o nível da troca.
        p, old_slug, new_slug = self._caster()
        self.assertEqual(views._lvl_aplicar_trocar_magia(
            p, {'remover': old_slug, 'adicionar': new_slug}), [])
        self.assertFalse(p.magias.filter(id_magia__slug=old_slug).exists())
        self.assertTrue(p.magias.filter(id_magia__slug=new_slug).exists())
        self.assertTrue(TbPersonagemEscolha.objects.filter(
            id_personagem=p, tipo='troca_magia', valor='9').exists())

    def test_segunda_troca_no_mesmo_nivel_recusada(self):
        # 2ª troca no MESMO nível (params válidos em isolamento) → recusada pelo gate; nada muda.
        p, old_slug, new_slug = self._caster()
        self.assertEqual(views._lvl_aplicar_trocar_magia(
            p, {'remover': old_slug, 'adicionar': new_slug}), [])
        erros = views._lvl_aplicar_trocar_magia(p, {'remover': new_slug, 'adicionar': old_slug})
        self.assertEqual(erros, [views._ERR_TROCA_JA_USADA])
        self.assertTrue(p.magias.filter(id_magia__slug=new_slug).exists())
        self.assertFalse(p.magias.filter(id_magia__slug=old_slug).exists())
        self.assertEqual(TbPersonagemEscolha.objects.filter(
            id_personagem=p, tipo='troca_magia').count(), 1)

    def test_subir_de_nivel_libera_nova_troca(self):
        # Sobe 1 nível → o registro antigo (nível menor) não trava a troca do nível novo.
        p, old_slug, new_slug = self._caster()
        self.assertEqual(views._lvl_aplicar_trocar_magia(
            p, {'remover': old_slug, 'adicionar': new_slug}), [])
        pc = p.classes.first()
        pc.nivel += 1
        pc.save(update_fields=['nivel'])
        p.nivel += 1
        p.save(update_fields=['nivel'])
        self.assertEqual(views._lvl_aplicar_trocar_magia(
            p, {'remover': new_slug, 'adicionar': old_slug}), [])
        self.assertTrue(p.magias.filter(id_magia__slug=old_slug).exists())
        self.assertFalse(p.magias.filter(id_magia__slug=new_slug).exists())
        self.assertEqual(set(TbPersonagemEscolha.objects.filter(
            id_personagem=p, tipo='troca_magia').values_list('valor', flat=True)), {'9', '10'})

    def test_endpoint_legado_respeita_o_gate(self):
        # `personagem_trocar_magia` (wrapper PRG) passa pelo MESMO gate: 1ª aplica, 2ª não.
        p, old_slug, new_slug = self._caster(nome='legado')
        self.client.force_login(p.dono)
        url = reverse('personagem_trocar_magia', args=[p.pk])
        self.assertEqual(self.client.post(
            url, data={'remover': old_slug, 'adicionar': new_slug}).status_code, 302)
        self.assertTrue(p.magias.filter(id_magia__slug=new_slug).exists())
        self.assertEqual(self.client.post(
            url, data={'remover': new_slug, 'adicionar': old_slug}).status_code, 302)
        self.assertTrue(p.magias.filter(id_magia__slug=new_slug).exists())
        self.assertFalse(p.magias.filter(id_magia__slug=old_slug).exists())
        self.assertEqual(TbPersonagemEscolha.objects.filter(
            id_personagem=p, tipo='troca_magia').count(), 1)

    def test_lote_duas_trocas_so_a_primeira_aplica(self):
        # Lote com 2 trocar_magia (ordem 7, sort estável): a 1ª aplica, a 2ª bate no gate.
        p, old_slug, new_slug = self._caster(nome='lote')
        acoes = [
            {'tipo': 'trocar_magia', 'payload': {'remover': old_slug, 'adicionar': new_slug}},
            {'tipo': 'trocar_magia', 'payload': {'remover': new_slug, 'adicionar': old_slug}},
        ]
        self.assertEqual(views._levelup_aplicar_lote(p, acoes), [views._ERR_TROCA_JA_USADA])
        self.assertTrue(p.magias.filter(id_magia__slug=new_slug).exists())
        self.assertFalse(p.magias.filter(id_magia__slug=old_slug).exists())
        self.assertEqual(TbPersonagemEscolha.objects.filter(
            id_personagem=p, tipo='troca_magia').count(), 1)

    def test_swap_disponivel_reflete_o_gate(self):
        # A flag da UI (`swap_disponivel`): antigo/novo sem registro = disponível; usada = não;
        # subir de nível = disponível de novo.
        p, old_slug, new_slug = self._caster(nome='flag')
        self.assertTrue(views._pendencias_magias(p)['swap_disponivel'])
        views._lvl_aplicar_trocar_magia(p, {'remover': old_slug, 'adicionar': new_slug})
        self.assertFalse(views._pendencias_magias(p)['swap_disponivel'])
        pc = p.classes.first()
        pc.nivel += 1
        pc.save(update_fields=['nivel'])
        p.nivel += 1
        p.save(update_fields=['nivel'])
        self.assertTrue(views._pendencias_magias(p)['swap_disponivel'])


class TrocaTodoRepertorioTests(_MagiaBase):
    """``max:all`` permite uma troca para cada magia conhecida no mesmo nível."""

    def test_bardo_pode_trocar_duas_magias_no_mesmo_level_up(self):
        p = self._com_classe('bardo', 9, nome='bardo-troca-todas')
        pend = views._pendencias_magias(p)
        slugs = [m['slug'] for m in pend['lista_magias']]
        self.assertGreaterEqual(len(slugs), 4)
        origem = p.classes.first().id_classe.nome
        for slug in slugs[:2]:
            magia = TbMagia.objects.get(slug=slug)
            TbPersonagemMagia.objects.create(
                id_personagem=p, id_magia=magia, nivel=magia.nivel,
                nome=magia.nome, preparada=True, origem=origem)

        self.assertEqual(views._pendencias_magias(p)['swap_limite'], 2)
        self.assertEqual(views._lvl_aplicar_trocar_magia(
            p, {'remover': slugs[0], 'adicionar': slugs[2]}), [])
        self.assertEqual(views._lvl_aplicar_trocar_magia(
            p, {'remover': slugs[1], 'adicionar': slugs[3]}), [])
        self.assertEqual(views._lvl_aplicar_trocar_magia(
            p, {'remover': slugs[2], 'adicionar': slugs[0]}),
            [views._ERR_TROCA_JA_USADA])
        self.assertEqual(TbPersonagemEscolha.objects.filter(
            id_personagem=p, tipo='troca_magia').count(), 2)


class PaladinoPreparadoTests(_MagiaBase):
    """Decisão do PO: o Paladino é conjurador PREPARADO, não "conhecido". A tag virou
    `spellcasting{... mode:prepared, spell_limit{resource:magias_preparadas}}`; a quantidade
    vem da progressão da classe e não de atributo. Verificado aqui:
      • painel de PREPARADAS mostra o limite da tabela;
      • sem pendência de "magias conhecidas" no level-up (known_pend == 0);
      • sem troca de magia ao subir de nível (swap_level_up False — o swap saiu junto);
      • RECONCILIAÇÃO: paladino com MAIS magias que o limite (era "conhecido") não é deletado —
        o painel marca todas (deixa desmarcar) e só o SAVE trunca ao limite."""

    def _paladino(self, nivel=5, carisma=16, nome='pal'):
        u = self._novo_usuario('pal-%s' % nome, staff=False)
        p = TbPersonagem.objects.create(
            dono=u, nome=nome, nivel=nivel,
            forca=13, destreza=12, constituicao=14, inteligencia=10, sabedoria=10, carisma=carisma)
        classe = TbClasse.objects.get(slug='paladino')
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=classe, nivel=nivel, principal=True)
        return p

    def _prep_info(self, p):
        from home.character_engine import derive
        info = views._magias_preparadas_info(p, derive(p))
        self.assertIsNotNone(info, 'Paladino deveria expor o painel de magias PREPARADAS')
        return info

    def test_spellcasting_e_preparado_com_recurso_tabelado(self):
        classe = TbClasse.objects.get(slug='paladino')
        info = views._classe_spellcasting_info(classe, nivel_habilidades=5)
        self.assertEqual(info['prepara'], 'preparadas')
        self.assertIsNone(info['prep_formula'])
        self.assertEqual(
            info['spell_limit'], {'kind': 'resource', 'value': 'magias_preparadas'})

    def test_limite_vem_da_tabela(self):
        # N5: tabela do Paladino informa 6, independentemente de Carisma.
        info = self._prep_info(self._paladino(nivel=5, carisma=16))
        self.assertEqual(info['classe'], 'Paladino')
        self.assertEqual(info['limite'], 6)
        self.assertEqual(info['max_nivel'], 2)
        self.assertTrue(info['grupos'])
        self.assertTrue(all(g['nivel'] <= 2 for g in info['grupos']))

    def test_limite_nao_muda_com_carisma(self):
        # N2 informa 3 na tabela mesmo com Carisma 8.
        info = self._prep_info(self._paladino(nivel=2, carisma=8, nome='minimo'))
        self.assertEqual(info['limite'], 3)

    def test_sem_pendencia_de_conhecidas_e_sem_swap(self):
        pend = views._pendencias_magias(self._paladino(nivel=5, carisma=16, nome='pend'))
        self.assertIsNotNone(pend)
        self.assertEqual(pend['known_pend'], 0)     # a coluna "magias conhecidas" saiu
        self.assertFalse(pend['swap_level_up'])     # preparado re-prepara, não troca ao subir

    def test_preparar_ate_o_limite_pelo_endpoint(self):
        p = self._paladino(nivel=5, carisma=16, nome='save')
        info = self._prep_info(p)
        pool = [m['slug'] for g in info['grupos'] for m in g['magias']]
        self.assertGreaterEqual(len(pool), info['limite'])
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_preparar_magias', args=[p.pk]),
                                data={'magia': pool[:info['limite']]})
        self.assertEqual(resp.status_code, 302, resp.content)
        self.assertEqual(
            p.magias.filter(nivel__gte=1, preparada=True, sempre_preparada=False).count(),
            info['limite'])

    def test_endpoint_trunca_excesso_no_save(self):
        p = self._paladino(nivel=5, carisma=16, nome='trunca')
        info = self._prep_info(p)
        pool = [m['slug'] for g in info['grupos'] for m in g['magias']]
        excesso = info['limite'] + 3
        self.assertGreaterEqual(len(pool), excesso)
        self.client.force_login(p.dono)
        self.client.post(reverse('personagem_preparar_magias', args=[p.pk]),
                         data={'magia': pool[:excesso]})
        self.assertEqual(
            p.magias.filter(nivel__gte=1, preparada=True, sempre_preparada=False).count(),
            info['limite'])   # o SAVE trunca ao limite

    def test_reconciliacao_excesso_nao_deleta_e_aparece_marcado(self):
        # Simula um paladino ANTIGO (era "conhecido") com MAIS magias que o novo limite: as magias
        # atuais viram o conjunto preparado. Só LER o painel NÃO deleta nada; todas vêm marcadas.
        p = self._paladino(nivel=5, carisma=16, nome='reconc')
        info = self._prep_info(p)
        pool = [m['slug'] for g in info['grupos'] for m in g['magias']]
        excesso = info['limite'] + 2
        self.assertGreaterEqual(len(pool), excesso)
        for slug in pool[:excesso]:
            mg = TbMagia.objects.get(slug=slug)
            TbPersonagemMagia.objects.create(id_personagem=p, id_magia=mg, nivel=mg.nivel,
                                             nome=mg.nome, preparada=True, origem='Paladino')
        info2 = self._prep_info(p)
        self.assertEqual(info2['preparadas_count'], excesso)          # nada deletado ao ler
        self.assertGreater(info2['preparadas_count'], info2['limite'])
        marcadas = {m['slug'] for g in info2['grupos'] for m in g['magias'] if m['marcada']}
        self.assertEqual(marcadas, set(pool[:excesso]))               # painel marca todas
