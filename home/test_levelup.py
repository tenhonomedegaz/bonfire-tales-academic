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
    """A página repaginada (editar_ficha.html) renderiza no design system do criador,
    com os hooks que o levelup.js consome (lote local + prévia + aplicar)."""

    def test_get_200_e_hooks_do_lote_presentes(self):
        # Guerreiro N4: N3 abre a subclasse e o N4 abre o slot de ASI -> dois cartões
        # de pendência do lote, além do cartão de progressão e da prévia lateral.
        p = self._guerreiro_no_nivel(4)
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        # layout + prévia + barra de ação do lote (design do criador)
        for needle in ('class="cf-layout"', 'id="lvl-topcard"', 'id="lvl-preview"',
                       'id="lvl-actionbar"', 'id="lvl-aplicar"', 'id="lvl-descartar"'):
            self.assertIn(needle, html, needle)
        # cartões de pendência por tipo com os data-hooks do lote
        self.assertIn('data-lvl-card="asi"', html)
        self.assertIn('data-lvl-card="subclasse"', html)
        self.assertIn('data-lvl-queue="subir_nivel"', html)   # subir de nível vira ação do lote
        self.assertIn('data-prev-attrs', html)                # prévia consome o resumo
        # wiring de JS/CSS + URLs dos endpoints em lote
        self.assertIn('js/levelup.js', html)
        self.assertIn('css/pages/levelup.css', html)
        self.assertIn('css/pages/criador.css', html)          # reuso do design system
        self.assertIn(reverse('personagem_levelup_aplicar', args=[p.pk]), html)
        self.assertIn(reverse('personagem_levelup_preview', args=[p.pk]), html)
        # o mercado continua como POST normal (não entra no lote nesta fase)
        self.assertIn(reverse('personagem_comprar_item', args=[p.pk]), html)

    def test_get_200_sem_pendencias(self):
        # N1 recém-criado (todas as escolhas de N1 já feitas): página abre 200 e ainda
        # oferece a ação de subir de nível no cartão de progressão.
        p = self._guerreiro_no_nivel(1)
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('id="lvl-preview"', html)
        self.assertIn('data-lvl-queue="subir_nivel"', html)


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
