# -*- coding: utf-8 -*-
"""Regressão da FICHA v2 — onda D (aba MAGIAS & OPÇÕES), briefing docs/agentes/briefing_ficha_v2.md.

  1. A aba de magias vira "Magias & Opções" (o identificador `magias` e `?aba=magias`
     continuam valendo) e ganha a seção OPÇÕES DE CLASSE.
  2. A seção lista TODOS os grupos que `picks.resolve_personagem` resolve para o
     personagem — rótulo, universo e origem saem do REGISTRY, nunca de lista fixa: duas
     classes diferentes produzem conjuntos diferentes de grupos sem uma linha de código
     por tipo.
  3. Cada opção escolhida traz nome legível + descrição completa expansível.
  4. TROCA só nas trocáveis: a trocabilidade vem da TAG (`swap:`/`reset:` no token ou
     marcador irmão). Trocável ganha botão e a troca persiste no MESMO slot; sem marcador
     não há botão e o endpoint recusa; `swap:level_up` fica marcado e INATIVO (é passo do
     wizard de subir de nível).
  5. Escolha de DOIS NÍVEIS (universo cuja entrada declara sub-opções — hoje a arma e as
     maestrias dela) troca no MESMO endpoint, com valor composto `'<pai>|<filho>'`: nada de
     rota/painel por kind. A detecção é ESTRUTURAL, não por nome de kind.
  6. Pendências aparecem com destaque e link para o fluxo certo (subir-nível).

Roda contra o conteúdo real (fixture `conteudo.json`), reusando o `LevelUpLoteBase`.
"""
from django.urls import reverse
from django.utils.html import conditional_escape

from home import picks, views
from home.models import TbOpcaojogo, TbPersonagem, TbPersonagemEscolha
from home.test_levelup import LevelUpLoteBase


class _OpcoesBase(LevelUpLoteBase):
    AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    def _personagem(self, classe_slug, nivel=1, apelido=''):
        """Personagem REAL da classe (o criador resolve as escolhas de N1) promovido ao
        nível pedido SEM resolver o que o nível novo abriu — é assim que nascem as
        pendências que a seção precisa mostrar."""
        user = self._novo_usuario('ondad-%s-%s%d' % (classe_slug, apelido, nivel))
        resp = self._post_criar(user, self._payload(classe_slug))
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        if nivel > 1:
            self._promover(p, nivel)
        return p

    def _html(self, p, **params):
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('ficha_detail', args=[p.pk]), params)
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        return resp.content.decode('utf-8')

    def _cartao(self, html, chave):
        """Recorte do <section> inteiro do cartão daquele grupo."""
        marca = 'data-opcao-grupo="%s"' % conditional_escape(chave)
        pos = html.find(marca)
        self.assertNotEqual(pos, -1, 'cartão do grupo %r não renderizado' % chave)
        ini = html.rfind('<section', 0, pos)
        fim = html.find('</section>', pos)
        self.assertNotEqual(fim, -1, 'cartão do grupo %r sem fechamento' % chave)
        return html[ini:fim + len('</section>')]

    def _grupo(self, p, **filtros):
        """Primeiro grupo do contexto da seção que casa com os filtros dados."""
        for g in views._opcoes_ficha(p):
            if all(g.get(k) == v for k, v in filtros.items()):
                return g
        return None

    def _trocar(self, p, grupo, escolha_id, val, esperado=200):
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_trocar_opcao', args=[p.pk]),
            {'grupo': grupo, 'escolha': escolha_id, 'val': val}, **self.AJAX)
        self.assertEqual(resp.status_code, esperado, resp.content[:400])
        return resp.json()


class AbaMagiasEOpcoesTests(_OpcoesBase):
    def test_aba_renomeada_mantem_rota_e_ancoras(self):
        p = self._personagem('guerreiro')
        html = self._html(p)
        # rótulo novo na navegação…
        self.assertIn('data-tab="magias" aria-selected="false">Magias &amp; Opções</button>', html)
        # …e o identificador/rota de sempre continuam de pé
        self.assertIn('data-tabpanel="magias"', html)
        self.assertIn('id="ficha-opcoes"', html)
        html_aba = self._html(p, aba='magias')
        self.assertIn('data-tabpanel="magias"', html_aba)

    def test_maestria_da_aba_ficha_aponta_para_a_secao_sem_duplicar_fluxo(self):
        """A UI de troca da aba Ficha MIGROU: o painel de maestria manda para a aba nova,
        e lá o cartão traz o MESMO form de troca dos outros grupos (fluxo único)."""
        p = self._personagem('guerreiro')
        html = self._html(p)
        self.assertIn('data-tab-jump="magias"', html)
        grupo = self._grupo(p, kind='arma')
        self.assertIsNotNone(grupo, 'Guerreiro deveria ter grupo de Maestria de Arma')
        cartao = self._cartao(html, grupo['chave'])
        self.assertIn('data-opcao-form', cartao)
        self.assertIn(reverse('personagem_trocar_opcao', args=[p.pk]), cartao)
        # a página dedicada não é mais referenciada em lugar nenhum da ficha
        self.assertNotIn(reverse('personagem_trocar_maestria', args=[p.pk]), html)

    def test_rota_do_painel_dedicado_virou_redirect_permanente(self):
        p = self._personagem('guerreiro')
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('personagem_trocar_maestria', args=[p.pk]))
        self.assertEqual(resp.status_code, 301)
        self.assertIn(reverse('ficha_detail', args=[p.pk]), resp['Location'])
        self.assertIn('aba=magias', resp['Location'])


class SecaoDeOpcoesTests(_OpcoesBase):
    def test_secao_lista_os_grupos_do_registry_em_duas_classes(self):
        """Os grupos da seção SÃO os que o resolvedor devolve — nada a mais, nada a menos.
        Provado em duas classes: os conjuntos são diferentes sem uma linha por tipo."""
        conjuntos = {}
        for slug, nivel in (('guerreiro', 4), ('bardo', 4)):
            p = self._personagem(slug, nivel)
            html = self._html(p)
            esperado = [(g['kind'], g['persist_tipo'], g['label'])
                        for g in picks.resolve_personagem(p)]
            self.assertTrue(esperado, '%s N%d deveria ter grupos de escolha' % (slug, nivel))
            rendered = views._opcoes_ficha(p)
            self.assertEqual(len(rendered), len(esperado))
            for grupo in rendered:
                self.assertIn('data-opcao-grupo="%s"' % conditional_escape(grupo['chave']), html)
                self.assertIn(conditional_escape(grupo['label']), html)
            conjuntos[slug] = {(k, t) for k, t, _lbl in esperado}
        self.assertNotEqual(conjuntos['guerreiro'], conjuntos['bardo'],
                            'os grupos têm de vir do personagem, não de uma lista fixa')

    def test_descricao_completa_expansivel_da_opcao_escolhida(self):
        """O Estilo de Luta escolhido no criador aparece com nome legível e a descrição
        INTEIRA do catálogo no corpo expansível (padrão da descrição de magia)."""
        p = self._personagem('guerreiro')
        grupo = self._grupo(p, kind='opcao', tipo='estilo_de_luta')
        self.assertIsNotNone(grupo)
        self.assertTrue(grupo['escolhidas'], 'o criador deveria ter gravado o estilo de luta')
        escolhida = grupo['escolhidas'][0]
        opcao = TbOpcaojogo.objects.get(slug=escolhida['valor'])
        self.assertEqual(escolhida['nome'], opcao.nome)
        self.assertEqual(escolhida['descricao'], (opcao.descricao or '').strip())
        self.assertTrue(escolhida['descricao'], 'a opção do catálogo tem descrição')
        html = self._html(p)
        cartao = self._cartao(html, grupo['chave'])
        chave_desc = '%s-%s' % (grupo['kind'], escolhida['id'])
        self.assertIn('data-opcao-toggle="%s"' % chave_desc, cartao)
        self.assertIn('data-opcao-body="%s"' % chave_desc, cartao)
        self.assertIn(conditional_escape(escolhida['descricao'][:60]), cartao)

    def test_descricao_vem_da_sub_opcao_quando_o_valor_e_composto(self):
        """Maestria de Arma persiste `'<arma>|<maestria>'`: a descrição exibida é a da
        MAESTRIA (sub-opção declarada pela arma), sem ramo por kind no template."""
        p = self._personagem('guerreiro')
        grupo = self._grupo(p, kind='arma')
        escolhida = next(e for e in grupo['escolhidas'] if '|' in (e['valor'] or ''))
        maestria_slug = escolhida['valor'].split('|', 1)[1]
        efeito = (TbOpcaojogo.objects.get(slug=picks.normalize_slug(maestria_slug))
                  .descricao or '').strip()
        self.assertTrue(efeito, 'a maestria do catálogo tem efeito descrito')
        self.assertEqual(escolhida['descricao'], efeito)


class TrocaDeOpcaoTests(_OpcoesBase):
    def test_trocavel_mostra_botao_e_troca_persiste(self):
        """`pick:opcao:estilo_de_luta:1(swap:long_rest)` (Guerreiro): botão presente, o
        seletor só oferece o que ele ainda não tem e a troca reescreve o MESMO slot."""
        p = self._personagem('guerreiro')
        grupo = self._grupo(p, kind='opcao', tipo='estilo_de_luta')
        self.assertEqual(grupo['swap'], 'long_rest')
        self.assertTrue(grupo['trocavel'])
        escolhida = grupo['escolhidas'][0]
        linha = TbPersonagemEscolha.objects.get(id=escolhida['id'])
        slot_antes, antigo = linha.slot, linha.valor

        html = self._html(p)
        cartao = self._cartao(html, grupo['chave'])
        self.assertIn('data-opcao-form', cartao)
        self.assertIn(reverse('personagem_trocar_opcao', args=[p.pk]), cartao)
        self.assertIn('trocável no descanso longo', cartao)
        # o seletor exclui as já possuídas
        self.assertNotIn(escolhida['nome'], [o['nome'] for o in grupo['disponiveis']])

        novo = grupo['disponiveis'][0]
        body = self._trocar(p, grupo['chave'], escolhida['id'], novo['val'])
        self.assertTrue(body['ok'], body)
        linha.refresh_from_db()
        self.assertEqual(linha.slot, slot_antes, 'a troca reescreve o slot, não anexa outro')
        self.assertNotEqual(linha.valor, antigo)
        self.assertEqual(linha.valor, TbOpcaojogo.objects.get(id_opcao=novo['val']).slug)
        self.assertEqual(TbPersonagemEscolha.objects.filter(
            id_personagem=p, tipo='estilo_de_luta').count(), 1)
        # a resposta traz a seção re-renderizada pelo servidor
        self.assertIn(conditional_escape(novo['nome']), body['opcoes_html'])

    def test_opcao_sem_marcador_de_troca_fica_so_leitura(self):
        """Pick sem `swap`/`reset` na tag (Manobras de Combate do Guerreiro): nem botão na
        seção, nem POST aceito."""
        p = self._personagem('guerreiro', 4)
        self._zerar_pendencias(p)
        grupo = next(g for g in views._opcoes_ficha(p) if not g['swap'] and g['escolhidas'])
        cartao = self._cartao(self._html(p), grupo['chave'])
        self.assertNotIn('data-opcao-form', cartao)
        self.assertNotIn('opt-action', cartao)
        alvo = grupo['escolhidas'][0]
        livre = grupo['disponiveis'][0]['val']
        body = self._trocar(p, grupo['chave'], alvo['id'], livre, esperado=400)
        self.assertFalse(body['ok'])
        self.assertEqual(body['msg'], 'nao_trocavel')
        self.assertEqual(TbPersonagemEscolha.objects.get(id=alvo['id']).valor, alvo['valor'])

    def test_swap_level_up_fica_marcado_mas_inativo(self):
        """`swap:level_up` é troca do WIZARD: a seção marca e não oferece botão; o
        endpoint recusa mesmo com payload válido."""
        p = self._personagem('bardo', 4)
        self._zerar_pendencias(p)          # Acordes de Poder escolhidos, nada pendente
        grupo = next(g for g in views._opcoes_ficha(p) if g['swap'] == 'level_up')
        self.assertTrue(grupo['so_no_levelup'])
        self.assertFalse(grupo['trocavel'])
        self.assertTrue(grupo['escolhidas'])
        cartao = self._cartao(self._html(p), grupo['chave'])
        self.assertIn('trocável ao subir de nível', cartao)
        self.assertNotIn('data-opcao-form', cartao)
        self.assertNotIn('opt-action', cartao)
        alvo = grupo['escolhidas'][0]['id']
        body = self._trocar(p, grupo['chave'], alvo, grupo['disponiveis'][0]['val'],
                            esperado=400)
        self.assertEqual(body['msg'], 'nao_trocavel')
        self.assertEqual(TbPersonagemEscolha.objects.get(id=alvo).valor,
                         grupo['escolhidas'][0]['valor'])

    def test_troca_recusa_opcao_fora_do_universo(self):
        p = self._personagem('guerreiro')
        grupo = self._grupo(p, kind='opcao', tipo='estilo_de_luta')
        body = self._trocar(p, grupo['chave'], grupo['escolhidas'][0]['id'],
                            'nao-existe-no-universo', esperado=400)
        self.assertEqual(body['msg'], 'fora_do_universo')


class TrocaEmDoisNiveisTests(_OpcoesBase):
    """Maestria de Arma — a escolha de DOIS NÍVEIS — troca no MESMO endpoint genérico, com
    valor composto `'<pai>|<filho>'`. Nada aqui conhece o kind: o que dispara o seletor de
    dois níveis é a ESTRUTURA do universo (a entrada declara sub-opções)."""

    def _grupo_arma(self, p):
        grupo = self._grupo(p, kind='arma')
        self.assertIsNotNone(grupo, 'Guerreiro deveria ter grupo de Maestria de Arma')
        return grupo

    def _pai_com_dois_livres(self, grupo):
        """Uma opção de 1º nível com ≥2 sub-opções livres (arma com 2 maestrias inéditas)."""
        pai = next((o for o in grupo['disponiveis'] if len(o['subs']) >= 2), None)
        self.assertIsNotNone(pai, 'catálogo precisa de uma arma com 2 maestrias livres')
        return pai

    def test_universo_de_dois_niveis_e_detectado_pela_estrutura(self):
        p = self._personagem('guerreiro')
        grupo = self._grupo_arma(p)
        self.assertTrue(grupo['dois_niveis'])
        self.assertTrue(all(o['subs'] for o in grupo['disponiveis']))
        # o grupo de UM nível do mesmo personagem não vira seletor de dois níveis
        self.assertFalse(self._grupo(p, kind='opcao', tipo='estilo_de_luta')['dois_niveis'])

    def test_cartao_renderiza_seletor_pai_e_filho_no_mesmo_form(self):
        p = self._personagem('guerreiro')
        grupo = self._grupo_arma(p)
        cartao = self._cartao(self._html(p), grupo['chave'])
        self.assertIn('data-opcao-form', cartao)
        self.assertIn('data-opcao-pai', cartao)
        self.assertIn('data-opcao-filho', cartao)
        pai = grupo['disponiveis'][0]
        self.assertIn('data-opcao-de="%s"' % conditional_escape(pai['val']), cartao)
        self.assertIn('value="%s"' % conditional_escape(pai['subs'][0]['val']), cartao)

    def test_troca_com_valor_composto_persiste_no_mesmo_slot(self):
        p = self._personagem('guerreiro')
        grupo = self._grupo_arma(p)
        self.assertEqual(grupo['swap'], 'long_rest')
        alvo = grupo['escolhidas'][0]
        slot = TbPersonagemEscolha.objects.get(id=alvo['id']).slot
        quantas = p.escolhas.filter(tipo='maestria').count()
        novo = self._pai_com_dois_livres(grupo)['subs'][0]['val']

        body = self._trocar(p, grupo['chave'], alvo['id'], novo)
        self.assertTrue(body['ok'], body)
        linha = p.escolhas.get(tipo='maestria', slot=slot)
        self.assertEqual(linha.valor, novo)                     # par novo gravado
        self.assertEqual(p.escolhas.filter(tipo='maestria').count(), quantas)

    def test_mesma_arma_com_outra_maestria_e_aceita_e_o_par_repetido_nao(self):
        """Regra de domínio: o PAR (arma, maestria) é único; a MESMA arma pode ocupar
        slots diferentes com maestrias diferentes."""
        p = self._personagem('guerreiro')
        grupo = self._grupo_arma(p)
        pai = self._pai_com_dois_livres(grupo)
        par1, par2 = pai['subs'][0]['val'], pai['subs'][1]['val']

        primeira = grupo['escolhidas'][0]
        self.assertTrue(self._trocar(p, grupo['chave'], primeira['id'], par1)['ok'])

        # 2º slot com a MESMA arma e outra maestria -> ACEITO
        grupo = self._grupo_arma(p)
        outra = next(e for e in grupo['escolhidas'] if e['valor'] != par1)
        self.assertTrue(self._trocar(p, grupo['chave'], outra['id'], par2)['ok'])
        vals = {e.valor for e in p.escolhas.filter(tipo='maestria')}
        self.assertTrue({par1, par2} <= vals)
        self.assertEqual(par1.split('|')[0], par2.split('|')[0], 'mesma arma nos dois')

        # o PAR repetido -> recusado
        grupo = self._grupo_arma(p)
        terceira = next(e for e in grupo['escolhidas'] if e['valor'] not in (par1, par2))
        body = self._trocar(p, grupo['chave'], terceira['id'], par1, esperado=400)
        self.assertEqual(body['msg'], 'duplicada')
        self.assertEqual(TbPersonagemEscolha.objects.get(id=terceira['id']).valor,
                         terceira['valor'])

    def test_arma_ja_usada_continua_no_seletor_pai_sem_o_par_tomado(self):
        """A dedução de disponíveis é pelo PAR: a arma já usada permanece no select pai,
        só o par tomado some do select filho."""
        p = self._personagem('guerreiro')
        grupo = self._grupo_arma(p)
        pai = self._pai_com_dois_livres(grupo)
        par1 = pai['subs'][0]['val']
        self.assertTrue(self._trocar(p, grupo['chave'], grupo['escolhidas'][0]['id'], par1)['ok'])

        grupo = self._grupo_arma(p)
        ainda = next((o for o in grupo['disponiveis'] if o['val'] == pai['val']), None)
        self.assertIsNotNone(ainda, 'a arma já usada tem de continuar no select pai')
        livres = [s['val'] for s in ainda['subs']]
        self.assertNotIn(par1, livres, 'o PAR já usado sai do select filho')
        self.assertIn(pai['subs'][1]['val'], livres, 'as outras maestrias dela continuam')
        cartao = self._cartao(self._html(p), grupo['chave'])
        self.assertIn('data-opcao-de="%s"' % conditional_escape(pai['val']), cartao)

    def test_par_inexistente_e_recusado_como_fora_do_universo(self):
        """Filho que não é sub-opção daquele pai não forma alternativa nenhuma."""
        p = self._personagem('guerreiro')
        grupo = self._grupo_arma(p)
        pai = grupo['disponiveis'][0]
        alvo = grupo['escolhidas'][0]
        for val in (pai['val'],                                 # só o pai não completa
                    '%s|maestria-inexistente-xyz' % pai['val']):
            body = self._trocar(p, grupo['chave'], alvo['id'], val, esperado=400)
            self.assertEqual(body['msg'], 'fora_do_universo', val)
        self.assertEqual(TbPersonagemEscolha.objects.get(id=alvo['id']).valor, alvo['valor'])

    def test_nenhum_caso_especial_por_kind_no_fluxo_de_troca(self):
        """Prova de regra: o fluxo de troca não cita kind nenhum — nem por tabela de rotas
        dedicadas (que deixou de existir), nem por `if` no código das funções envolvidas."""
        import inspect
        import re as _re
        fonte = inspect.getsource(views)
        self.assertNotIn('_OPCAO_FLUXO_DEDICADO', fonte)
        self.assertNotIn('fluxo_dedicado', fonte)
        codigo = ''
        for fn in (views._sub_opcoes, views._grupo_em_dois_niveis, views._opcao_alternativas,
                   views._opcao_alternativa, views._opcoes_ficha, views.personagem_trocar_opcao):
            src = inspect.getsource(fn)
            src = _re.sub(r'"""[\s\S]*?"""', '', src)       # sem docstring
            src = _re.sub(r'(?m)#.*$', '', src)             # sem comentário
            codigo += src
        for palavra in ('arma', 'maestria', 'estilo_de_luta'):
            self.assertNotIn(palavra, codigo,
                             'o fluxo de troca não pode ramificar por tipo de escolha')


class PendenciasNaSecaoTests(_OpcoesBase):
    def test_pendencia_generica_destacada_com_link_para_subir_nivel(self):
        p = self._personagem('bardo', 4)
        grupo = next(g for g in views._opcoes_ficha(p) if g['pendentes'])
        self.assertEqual(grupo['pendencia_url'],
                         reverse('personagem_subir_nivel', args=[p.pk]))
        cartao = self._cartao(self._html(p), grupo['chave'])
        self.assertIn('is-pendente', cartao)
        self.assertIn('em aberto', cartao)
        self.assertIn(reverse('personagem_subir_nivel', args=[p.pk]), cartao)

    def test_pendencia_de_grupo_de_dois_niveis_usa_o_mesmo_destino(self):
        """Sem fluxo próprio, a pendência de Maestria de Arma vai para o mesmo lugar das
        outras (subir de nível). O Guerreiro N4 ganha um slot novo de maestria — a
        pendência é a real, não fabricada."""
        p = self._personagem('guerreiro', 4)
        grupo = self._grupo(p, kind='arma')
        self.assertGreaterEqual(grupo['pendentes'], 1)
        self.assertEqual(grupo['pendencia_url'],
                         reverse('personagem_subir_nivel', args=[p.pk]))
        cartao = self._cartao(self._html(p), grupo['chave'])
        self.assertIn('is-pendente', cartao)
        self.assertIn(reverse('personagem_subir_nivel', args=[p.pk]), cartao)
        self.assertNotIn(reverse('personagem_trocar_maestria', args=[p.pk]), cartao)

    def test_escolha_incompleta_se_completa_no_proprio_cartao(self):
        """Linha LEGADA só-arma (sub-escolha em aberto): o cartão não manda para lugar
        nenhum — o ↻ Trocar da própria linha completa o par."""
        p = self._personagem('guerreiro')
        arma = TbPersonagemEscolha.objects.filter(id_personagem=p, tipo='maestria').first()
        arma.valor = arma.valor.split('|', 1)[0]          # vira legado (sem a maestria)
        arma.save(update_fields=['valor'])
        grupo = self._grupo(p, kind='arma')
        self.assertTrue(grupo['incompleta'])
        cartao = self._cartao(self._html(p), grupo['chave'])
        self.assertIn('Escolha incompleta', cartao)
        self.assertIn('complete no', cartao)
        self.assertNotIn(reverse('personagem_subir_nivel', args=[p.pk]), cartao)


class SwapVemDaTagTests(_OpcoesBase):
    def test_swap_scope_le_constraint_e_marcador_irmao(self):
        """A trocabilidade é leitura de tag: constraint no token OU marcador irmão. Um
        `teleport:swap{...}` (efeito) não vira trocabilidade."""
        from types import SimpleNamespace

        def escopo(tags):
            fonte = SimpleNamespace(nome='X', tags_json=tags)
            tok = next(picks.iter_pick_tokens(tags[0]))
            return picks.swap_scope(tok, fonte)

        self.assertEqual(escopo(['pick:opcao:metamagia:2(swap:long_rest)']), 'long_rest')
        self.assertEqual(escopo(['pick:opcao:metamagia:2', 'swap:level_up']), 'level_up')
        self.assertEqual(escopo(['pick:arma:2(reset:long_rest)']), 'long_rest')
        self.assertIsNone(escopo(['pick:opcao:metamagia:2']))
        self.assertIsNone(escopo(['pick:opcao:metamagia:2',
                                  'instant{ teleport:swap(target:allies) }',
                                  'uses{pb, reset:long_rest}']))
