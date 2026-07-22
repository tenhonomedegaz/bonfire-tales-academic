# -*- coding: utf-8 -*-
"""Regressão do laudo de magia: TETO de nível de magia pela TABELA DE SLOTS da própria classe,
SWAP inferido de `prepara:conhecidas`, e ADEPTO DAS VESTES (spell_selection `any`/classe com
`qtd` implícito e `escola:{A | B}` em conjunto).

Cobre as três correções do laudo:

  1. `_pendencias_magias`/`_magias_preparadas_info`: o nível máximo conhecível/preparável vem
     do TOPO da tabela de slots DA PRÓPRIA classe (single-class de propósito), não de uma
     fórmula fechada nem dos slots *pooled* de multiclasse.
       Paladino (half):          nv7 → 2,  nv9 → 3.
       Cavaleiro Arcano (third): nv3 → 1,  nv7 → 2,  nv13 → 3  (tabela guardada na SUBCLASSE).
     O APPLY (validação do lote) lê o MESMO `_pendencias_magias` — logo o mesmo teto.

  2. Troca de magia ao subir de nível: INFERIDA quando o spellcasting é `prepara:conhecidas`
     (Cavaleiro Arcano — sem tag `swap:level_up` no dado) e NÃO quando é `prepara:preparadas`
     (Mago). A tag explícita (Paladino) coexiste com a inferência.

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


class SwapInferidoTests(_MagiaBase):
    """Troca de magia ao subir de nível: inferida por `prepara:conhecidas`."""

    def _swap(self, p):
        pend = views._pendencias_magias(p)
        self.assertIsNotNone(pend, 'sem pendências de magia para %s' % p.nome)
        return pend['swap_level_up']

    def test_cavaleiro_arcano_conhecidas_ve_swap_por_inferencia(self):
        # prepara:conhecidas, SEM tag swap:level_up no dado → troca INFERIDA.
        self.assertTrue(self._swap(self._com_classe('guerreiro', 7, 'Arcano', 'ekswap')))

    def test_mago_preparadas_nao_ve_swap(self):
        # prepara:preparadas (re-prepara livre a cada descanso) → NÃO troca ao subir.
        self.assertFalse(self._swap(self._com_classe('mago', 7, nome='magoswap')))

    def test_paladino_tag_e_inferencia_concordam(self):
        # Paladino tem tag swap:level_up E é prepara:conhecidas — ambos apontam True.
        self.assertTrue(self._swap(self._com_classe('paladino', 9, nome='palswap')))


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
    """Regra do PO: o caster CONHECIDO troca UMA magia por NÍVEL. Cada troca registra o nível
    total em que foi usada (TbPersonagemEscolha tipo='troca_magia'); a SEGUNDA troca no MESMO
    nível é recusada com `_ERR_TROCA_JA_USADA` — vale para o POST direto, para o endpoint
    legado (`personagem_trocar_magia`) e para o lote (`_levelup_aplicar_lote`). Subir de nível
    libera outra troca; personagens ANTIGOS (sem registro) ganham a troca do nível atual."""

    def _caster(self, nivel=9, nome='swapper'):
        """Paladino (known caster: swap:level_up + prepara:conhecidas) com 1 magia conhecida
        pronta para trocar. Devolve (p, old_slug, new_slug): `old` é a conhecida a remover,
        `new` uma magia da lista da classe ainda não conhecida (dentro do teto)."""
        p = self._com_classe('paladino', nivel, nome=nome)
        pend = views._pendencias_magias(p)
        self.assertTrue(pend['swap_level_up'], 'paladino deveria permitir troca ao subir de nível')
        opcoes = [m['slug'] for m in pend['lista_magias']]
        self.assertGreaterEqual(len(opcoes), 2, 'pool de magias insuficiente para o teste')
        old_slug, new_slug = opcoes[0], opcoes[1]
        mg = TbMagia.objects.get(slug=old_slug)
        TbPersonagemMagia.objects.create(id_personagem=p, id_magia=mg, nivel=mg.nivel,
                                         nome=mg.nome, preparada=True, origem='Paladino')
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
