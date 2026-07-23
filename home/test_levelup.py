# -*- coding: utf-8 -*-
"""Regressão do LEVEL-UP em lote (endpoints JSON novos).

Cobre a refatoração que extraiu os 8 handlers PRG do level-up em funções puras
`_lvl_aplicar_*` e as expôs por dois endpoints JSON no padrão do criador:

  - `personagem_levelup_aplicar`  — aplica um LOTE [{tipo, payload}] numa única
     transação (ordem estável), ressincroniza uma vez e devolve {ok, ficha, pendencias}.
  - `personagem_levelup_preview`  — aplica o mesmo lote em transação REVERTIDA e devolve
     o derive previsto SEM persistir (padrão `criar_personagem_preview_view`).

Reaproveita o `_CriadorBase` de test_criador.py (mesma fixture `conteudo.json` real).
"""
import json

from django.urls import reverse

from home import views
from home.models import (
    TbClasse, TbSubclasse, TbPersonagem, TbPersonagemClasse,
    TbPersonagemAtributoBonus, TbPersonagemTalento,
    TbMagia, TbPersonagemMagia, TbPersonagemEscolha,
)
from home.test_criador import _CriadorBase


class LevelUpLoteBase(_CriadorBase):
    def _guerreiro_no_nivel(self, nivel, apelido='lvl'):
        """Cria um Guerreiro N1 REAL (todas as escolhas de N1) e o promove ao `nivel`
        pedido, com aventuras suficientes para o teto não travar o próximo nível."""
        user = self._novo_usuario('%s-guerreiro-%d' % (apelido, nivel), staff=True)
        resp = self._post_criar(user, self._payload('guerreiro'))
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        pc = p.classes.first()
        pc.nivel = nivel
        pc.save(update_fields=['nivel'])
        p.nivel = nivel
        p.aventuras = 500  # teto = 20 (min(nivel_por_aventuras, 20)); não trava a subida
        p.save(update_fields=['nivel', 'aventuras'])
        return p

    def _promover(self, p, nivel):
        """Sobe o nível da classe (e do personagem) sem resolver as escolhas intermediárias,
        com aventuras de sobra para o teto não travar a próxima subida."""
        pc = p.classes.first()
        pc.nivel = nivel
        pc.save(update_fields=['nivel'])
        p.nivel = nivel
        p.aventuras = 500
        p.save(update_fields=['nivel', 'aventuras'])
        return p

    def _ek(self, nivel=7, apelido='ek', com_conhecida=True):
        """Guerreiro REAL (criador N1) promovido a `nivel` e apontado para a subclasse
        Cavaleiro Arcano — caster CONHECIDO (swap por inferência de `prepara:conhecidas`).
        Com `com_conhecida`, materializa 1 magia na estante e devolve (p, pc, old, new):
        `old` é a conhecida (candidata a sair), `new` uma da lista da classe ainda não sabida."""
        p = self._guerreiro_no_nivel(nivel, apelido=apelido)
        pc = p.classes.first()
        sub = TbSubclasse.objects.get(id_classe=pc.id_classe, nome__icontains='Arcano')
        pc.id_subclasse = sub
        pc.save(update_fields=['id_subclasse'])
        old = new = None
        if com_conhecida:
            pend = views._pendencias_magias(p)
            self.assertTrue(pend and pend['swap_level_up'],
                            'Cavaleiro Arcano deveria permitir troca ao subir de nível')
            magias = [m['slug'] for m in pend['lista_magias']]
            self.assertGreaterEqual(len(magias), 2, 'pool de magias insuficiente para a troca')
            old, new = magias[0], magias[1]
            mg = TbMagia.objects.get(slug=old)
            TbPersonagemMagia.objects.create(
                id_personagem=p, id_magia=mg, nivel=mg.nivel, nome=mg.nome,
                preparada=True, origem=pc.id_classe.nome)
        return p, pc, old, new

    def _zerar_pendencias(self, p):
        """Resolve as pendências abertas (o talento racial de marco N1 do anão é a sticky)
        para exercitar o caminho 'sem pendências'."""
        for _ in range(6):
            tr = views._pendencias_talento_racial(p)
            if not tr:
                break
            for bloco in tr:
                views._lvl_aplicar_talento_racial(
                    p, {'nivel': bloco['nivel'], 'talento': bloco['opcoes'][0]['nome']})
        return p


class LevelUpAplicarLoteTests(LevelUpLoteBase):
    """O batch aplica subir-nível + escolha (subclasse) + ASI num único POST JSON,
    tudo numa transação só, e o estado final bate."""

    def test_batch_subir_nivel_subclasse_e_asi_num_lote(self):
        # Guerreiro N3 -> N4: o N4 libera o slot de ASI; a subclasse (N3) ainda está aberta.
        p = self._guerreiro_no_nivel(3)
        pc = p.classes.first()
        sub = TbSubclasse.objects.filter(id_classe=pc.id_classe).order_by('id_subclasse').first()
        self.assertIsNotNone(sub)
        acoes = [
            {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
            {'tipo': 'subclasse', 'payload': {'subclasse': sub.id_subclasse}},
            {'tipo': 'asi', 'payload': {'modo': 'atributos',
                                        'asi_attr_1': 'FOR', 'asi_attr_2': 'FOR'}},
        ]
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_levelup_aplicar', args=[p.pk]),
            data=json.dumps({'acoes': acoes}), content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)

        # persistiu de verdade: nível, subclasse e o +2 de FOR do ASI
        p.refresh_from_db()
        pc.refresh_from_db()
        self.assertEqual(p.nivel, 4)
        self.assertEqual(pc.id_subclasse_id, sub.id_subclasse)
        self.assertTrue(TbPersonagemAtributoBonus.objects.filter(
            id_personagem=p, origem_tipo='asi-classe', atributo='FOR', valor=2).exists())

        # a resposta traz o derive atualizado (N4) e as pendências recalculadas
        self.assertEqual(body['ficha']['nivel'], 4)
        self.assertFalse(body['pendencias']['subclasse'])
        self.assertEqual(body['pendencias']['asi_pendentes'], 0)

    def test_batch_ordem_estavel_subir_antes_de_asi(self):
        # Mesmo que o ASI venha ANTES do subir-nível no payload, a ordem estável aplica
        # subir-nível primeiro — sem isso o slot de ASI (N4) não existiria e o ASI falharia.
        p = self._guerreiro_no_nivel(3)
        pc = p.classes.first()
        acoes = [
            {'tipo': 'asi', 'payload': {'modo': 'atributos',
                                        'asi_attr_1': 'CON', 'asi_attr_2': 'DES'}},
            {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
        ]
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_levelup_aplicar', args=[p.pk]),
            data=json.dumps({'acoes': acoes}), content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['ok'], resp.content)
        p.refresh_from_db()
        self.assertEqual(p.nivel, 4)
        self.assertTrue(TbPersonagemAtributoBonus.objects.filter(
            id_personagem=p, origem_tipo='asi-classe').exists())

    def test_resposta_oferece_continuar_quando_ainda_ha_nivel_disponivel(self):
        p = self._guerreiro_no_nivel(1, apelido='encadeado')
        self._zerar_pendencias(p)
        pc = p.classes.first()
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_levelup_aplicar', args=[p.pk]),
            data=json.dumps({'acoes': [
                {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
            ]}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['continuar'], body)
        self.assertEqual(body['proximo_nivel'], 3)

    def test_batch_invalido_reverte_tudo(self):
        # Um lote com uma ação inválida (subclasse inexistente) devolve 400 e NÃO grava
        # NADA — nem o subir-nível que veio junto (transação atômica).
        p = self._guerreiro_no_nivel(3)
        pc = p.classes.first()
        acoes = [
            {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
            {'tipo': 'subclasse', 'payload': {'subclasse': 999999}},
        ]
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_levelup_aplicar', args=[p.pk]),
            data=json.dumps({'acoes': acoes}), content_type='application/json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertFalse(resp.json().get('ok', True))
        p.refresh_from_db()
        self.assertEqual(p.nivel, 3)  # rollback: o subir-nível não sobreviveu

    def test_teto_de_aventuras_intacto_no_batch(self):
        # Gate de progressão NÃO afrouxa: com 0 aventuras (teto=1) o subir-nível é recusado.
        p = self._guerreiro_no_nivel(1)
        p.aventuras = 0
        p.save(update_fields=['aventuras'])
        pc = p.classes.first()
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_levelup_aplicar', args=[p.pk]),
            data=json.dumps({'acoes': [
                {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}}]}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertTrue(any('aventuras' in e.lower() for e in resp.json()['erros']), resp.content)
        p.refresh_from_db()
        self.assertEqual(p.nivel, 1)

    def test_permissao_de_terceiro_negada(self):
        # Mesma permissão dos endpoints legados: quem não é dono/staff leva 404.
        p = self._guerreiro_no_nivel(3)
        outro = self._novo_usuario('intruso')  # não-staff, não-dono
        self.client.force_login(outro)
        resp = self.client.post(
            reverse('personagem_levelup_aplicar', args=[p.pk]),
            data=json.dumps({'acoes': []}), content_type='application/json')
        self.assertEqual(resp.status_code, 404)


class EditarFichaRenderTests(LevelUpLoteBase):
    """editar_ficha.html AGORA é só inventário/mercado/info/manutenção: o level-up saiu para
    a página dedicada (personagem_subir_nivel GET). A página de edição só leva o botão."""

    def test_editar_sem_secao_de_levelup_com_link_pro_fluxo(self):
        p = self._guerreiro_no_nivel(4)
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        # a seção de level-up embutida (lote/prévia/pendências) foi REMOVIDA
        for gone in ('id="lvl-actionbar"', 'id="lvl-preview"', 'data-lvl-queue="subir_nivel"',
                     'data-lvl-card="asi"', 'js/levelup.js'):
            self.assertNotIn(gone, html, gone)
        # mas há um LINK/BOTÃO destacado para a experiência dedicada
        self.assertIn(reverse('personagem_subir_nivel', args=[p.pk]), html)
        # e o resto (mercado/inventário) permanece
        self.assertIn(reverse('personagem_comprar_item', args=[p.pk]), html)

    def test_editar_sem_form_legado_de_troca_de_magia(self):
        # Caster CONHECIDO com magia na estante: ANTES o form legado de troca vivia aqui;
        # agora a etapa é do wizard dedicado (o endpoint `personagem_trocar_magia` segue por compat).
        p, pc, old, new = self._ek(apelido='editveto')
        self.client.force_login(p.dono)
        html = self.client.get(reverse('editar_ficha', args=[p.pk])).content.decode('utf-8')
        self.assertNotIn(reverse('personagem_trocar_magia', args=[p.pk]), html)
        self.assertNotIn('Trocar magia conhecida', html)
        # mas a ficha de edição segue funcional e leva ao wizard dedicado
        self.assertIn(reverse('personagem_subir_nivel', args=[p.pk]), html)

    def test_editar_no_teto_mostra_proximo_nivel(self):
        # Sem folga de aventuras e sem pendências: nenhum botão de subir, só o aviso discreto.
        p = self._guerreiro_no_nivel(1)
        self._zerar_pendencias(p)
        p.aventuras = 0
        p.save(update_fields=['aventuras'])
        self.assertTrue(views._levelup_pendencias(p)['sem_pendencias'])
        self.client.force_login(p.dono)
        html = self.client.get(reverse('editar_ficha', args=[p.pk])).content.decode('utf-8')
        self.assertIn('Próximo nível em', html)


class SubirNivelPageTests(LevelUpLoteBase):
    """A EXPERIÊNCIA DEDICADA de level-up (GET /subir-nivel/): gate de permissão, stepper +
    prévia + confirmar, e os cartões de escolha derivados do NÍVEL-ALVO."""

    def test_get_200_dono_e_staff_terceiro_404(self):
        p = self._guerreiro_no_nivel(3)
        url = reverse('personagem_subir_nivel', args=[p.pk])
        # dono
        self.client.force_login(p.dono)
        self.assertEqual(self.client.get(url).status_code, 200)
        # staff (não-dono)
        staff = self._novo_usuario('staff-sn', staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 200)
        # terceiro (não-dono, não-staff) -> 404
        outro = self._novo_usuario('intruso-sn')
        self.client.force_login(outro)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_estrutura_da_pagina_e_alvo(self):
        # Guerreiro N3 -> alvo N4: o N4 abre ASI (etapa) e o cabeçalho mostra 3 ➜ 4.
        p = self._guerreiro_no_nivel(3)
        self.client.force_login(p.dono)
        html = self.client.get(reverse('personagem_subir_nivel', args=[p.pk])).content.decode('utf-8')
        # esqueleto BG3: stepper + prévia ao vivo + confirmar/cancelar
        for needle in ('id="sn-stepper"', 'id="sn-preview"', 'data-sn-confirm',
                       'data-sn-next', 'data-sn-prev', 'data-prev-attrs',
                       'data-step="ganhos"', 'data-step="revisar"'):
            self.assertIn(needle, html, needle)
        # escolha derivada do nível-ALVO (N4 = slot de ASI) aparece como etapa
        self.assertIn('data-step="asi"', html)
        self.assertIn('data-lvl-card="asi"', html)
        # cabeçalho com o salto de nível 3 -> 4
        self.assertIn('sn-leveljump', html)
        self.assertIn('>4<', html)
        # wiring dos endpoints em lote + assets
        self.assertIn(reverse('personagem_levelup_aplicar', args=[p.pk]), html)
        self.assertIn(reverse('personagem_levelup_preview', args=[p.pk]), html)
        self.assertIn('js/subir_nivel.js', html)
        self.assertIn('css/pages/subir_nivel.css', html)

    def test_opcao_exibe_descricao_completa_e_enfileira_na_selecao(self):
        u = self._novo_usuario('sn-opcao-direta')
        classe = TbClasse.objects.get(slug='feiticeiro')
        p = TbPersonagem.objects.create(
            dono=u, nome='Feiticeiro das Opções', nivel=2, aventuras=500,
            forca=8, destreza=14, constituicao=14,
            inteligencia=10, sabedoria=12, carisma=16)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=classe, nivel=2, principal=True)
        self.client.force_login(u)
        html = self.client.get(
            reverse('personagem_subir_nivel', args=[p.pk])).content.decode('utf-8')
        self.assertIn('data-lvl-auto-queue="opcao"', html)
        self.assertIn('data-desc="', html)
        self.assertNotIn('data-lvl-queue="opcao"', html)

    def test_botao_aparece_quando_elegivel(self):
        # Elegível (teto folgado): a ficha traz o botão destacado de subir de nível.
        p = self._guerreiro_no_nivel(3)
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('data-levelup-btn', html)
        self.assertIn(reverse('personagem_subir_nivel', args=[p.pk]), html)

    def test_botao_some_no_teto(self):
        # No teto e sem pendências: nada de botão; só o aviso "Próximo nível em X".
        p = self._guerreiro_no_nivel(1)
        self._zerar_pendencias(p)
        p.aventuras = 0
        p.save(update_fields=['aventuras'])
        self.client.force_login(p.dono)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertNotIn('data-levelup-btn', html)
        self.assertIn('banner-nextlvl', html)

    def test_fluxo_completo_um_nivel_com_escolhas_em_lote(self):
        # Abre a página (N3->N4), monta o lote como o front faria (subir + subclasse + ASI)
        # e confirma num ÚNICO POST; o estado final bate.
        p = self._guerreiro_no_nivel(3)
        pc = p.classes.first()
        sub = TbSubclasse.objects.filter(id_classe=pc.id_classe).order_by('id_subclasse').first()
        self.client.force_login(p.dono)
        self.assertEqual(self.client.get(reverse('personagem_subir_nivel', args=[p.pk])).status_code, 200)
        acoes = [
            {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
            {'tipo': 'subclasse', 'payload': {'subclasse': sub.id_subclasse}},
            {'tipo': 'asi', 'payload': {'modo': 'atributos', 'asi_attr_1': 'FOR', 'asi_attr_2': 'FOR'}},
        ]
        resp = self.client.post(
            reverse('personagem_levelup_aplicar', args=[p.pk]),
            data=json.dumps({'acoes': acoes}), content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['ok'], resp.content)
        p.refresh_from_db(); pc.refresh_from_db()
        self.assertEqual(p.nivel, 4)
        self.assertEqual(pc.id_subclasse_id, sub.id_subclasse)
        self.assertTrue(TbPersonagemAtributoBonus.objects.filter(
            id_personagem=p, origem_tipo='asi-classe', atributo='FOR', valor=2).exists())


class LevelUpPreviewTests(LevelUpLoteBase):
    """O preview roda o mesmo lote numa transação revertida: mostra o resultado previsto
    mas NÃO persiste nada."""

    def test_preview_nao_persiste(self):
        p = self._guerreiro_no_nivel(3)
        pc = p.classes.first()
        acoes = [
            {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
            {'tipo': 'asi', 'payload': {'modo': 'atributos',
                                        'asi_attr_1': 'FOR', 'asi_attr_2': 'FOR'}},
        ]
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_levelup_preview', args=[p.pk]),
            data=json.dumps({'acoes': acoes}), content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'] and body['ready'], body)

        # a PRÉVIA já reflete o nível previsto (N4)...
        self.assertEqual(body['preview']['nivel'], 4)
        # ...mas o banco continua intacto (nada persistido pelo preview)
        p.refresh_from_db()
        self.assertEqual(p.nivel, 3)
        self.assertFalse(TbPersonagemAtributoBonus.objects.filter(
            id_personagem=p, origem_tipo='asi-classe').exists())
        self.assertFalse(TbPersonagemTalento.objects.filter(
            id_personagem=p, categoria='asi-nivel').exists())

    def test_preview_bate_com_o_apply(self):
        # O derive do preview é IDÊNTICO ao do apply do mesmo lote (mesma lógica pura).
        acoes_de = lambda pc: [
            {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
            {'tipo': 'asi', 'payload': {'modo': 'atributos',
                                        'asi_attr_1': 'FOR', 'asi_attr_2': 'FOR'}},
        ]
        # preview
        pv = self._guerreiro_no_nivel(3, apelido='prev')
        self.client.force_login(pv.dono)
        rprev = self.client.post(
            reverse('personagem_levelup_preview', args=[pv.pk]),
            data=json.dumps({'acoes': acoes_de(pv.classes.first())}),
            content_type='application/json')
        prev = rprev.json()['preview']

        # apply num personagem equivalente
        ap = self._guerreiro_no_nivel(3, apelido='appl')
        self.client.force_login(ap.dono)
        rap = self.client.post(
            reverse('personagem_levelup_aplicar', args=[ap.pk]),
            data=json.dumps({'acoes': acoes_de(ap.classes.first())}),
            content_type='application/json')
        aplicado = rap.json()['ficha']

        self.assertEqual(prev['nivel'], aplicado['nivel'])
        self.assertEqual(prev['pv'], aplicado['pv'], 'PV diverge preview×apply')
        self.assertEqual(prev['ca'], aplicado['ca'], 'CA diverge preview×apply')
        by_sig_prev = {a['sig']: a for a in prev['atributos']}
        by_sig_ap = {a['sig']: a for a in aplicado['atributos']}
        for sig in by_sig_ap:
            self.assertEqual(by_sig_prev[sig]['valor'], by_sig_ap[sig]['valor'], 'valor %s' % sig)


class SubirNivelTrocaMagiaTests(LevelUpLoteBase):
    """A ETAPA de trocar magia no wizard dedicado (queixa do Rhogar: a opção não aparecia ao
    subir de nível). Só o caster CONHECIDO com magia na estante a vê; o PREPARADO (Mago) não;
    quando a troca do nível já foi usada, o wizard mostra o aviso no lugar do seletor; e o
    `trocar_magia` entra no LOTE junto do `subir_nivel` (o orquestrador aplica os dois)."""

    def test_ek_elegivel_ve_o_passo_de_troca(self):
        # Cavaleiro Arcano elegível: a etapa e o cartão de troca aparecem com os data-* do lote.
        p, pc, old, new = self._ek()
        self.client.force_login(p.dono)
        html = self.client.get(reverse('personagem_subir_nivel', args=[p.pk])).content.decode('utf-8')
        for needle in ('data-step="troca_magia"', 'data-lvl-card="trocar_magia"',
                       'data-lvl-queue="trocar_magia"', 'data-lvl-field="remover"',
                       'data-lvl-field="adicionar"', 'data-sn-skip'):
            self.assertIn(needle, html, needle)
        # swap disponível → é o SELETOR, não o aviso
        self.assertNotIn('data-sn-swap-usada', html)
        # a magia conhecida aparece como opção a desaprender
        self.assertIn('value="%s"' % old, html)

    def test_mago_preparado_nao_ve_o_passo(self):
        # Mago (prepara:preparadas) NÃO troca ao subir — a etapa nem existe no wizard.
        user = self._novo_usuario('mago-troca', staff=True)
        resp = self._post_criar(user, self._payload('mago'))
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        self._promover(p, 7)
        self.client.force_login(p.dono)
        html = self.client.get(reverse('personagem_subir_nivel', args=[p.pk])).content.decode('utf-8')
        self.assertNotIn('data-step="troca_magia"', html)
        self.assertNotIn('data-lvl-card="trocar_magia"', html)

    def test_swap_ja_usada_mostra_o_aviso(self):
        # Troca já registrada no NÍVEL-ALVO (7->8 → nivel_total-alvo = 8): swap_disponivel=False.
        # A seção existe (é caster conhecido), mas mostra o AVISO no lugar do seletor.
        p, pc, old, new = self._ek(apelido='usada')
        TbPersonagemEscolha.objects.create(
            id_personagem=p, origem='swap', tipo='troca_magia', slot=8, valor='8')
        self.client.force_login(p.dono)
        html = self.client.get(reverse('personagem_subir_nivel', args=[p.pk])).content.decode('utf-8')
        self.assertIn('data-step="troca_magia"', html)
        self.assertIn('data-sn-swap-usada', html)
        self.assertNotIn('data-lvl-card="trocar_magia"', html)

    def test_lote_subir_nivel_e_trocar_magia_aplica_ambos(self):
        # O front monta o lote [subir_nivel, trocar_magia]; o orquestrador sobe o nível PRIMEIRO
        # (ordem estável) e então aplica a troca no nível novo — ambos persistem num POST só.
        p, pc, old, new = self._ek(apelido='lote')
        self.client.force_login(p.dono)
        acoes = [
            {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
            {'tipo': 'trocar_magia', 'payload': {'remover': old, 'adicionar': new}},
        ]
        resp = self.client.post(
            reverse('personagem_levelup_aplicar', args=[p.pk]),
            data=json.dumps({'acoes': acoes}), content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['ok'], resp.content)
        p.refresh_from_db()
        self.assertEqual(p.nivel, 8)                                     # subiu de nível
        self.assertFalse(p.magias.filter(id_magia__slug=old).exists())   # a antiga saiu
        self.assertTrue(p.magias.filter(id_magia__slug=new).exists())    # a nova entrou
        self.assertTrue(TbPersonagemEscolha.objects.filter(              # troca registrada no nível 8
            id_personagem=p, tipo='troca_magia', valor='8').exists())
