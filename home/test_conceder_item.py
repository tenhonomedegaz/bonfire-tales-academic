# -*- coding: utf-8 -*-
"""Regressão do PAINEL STAFF de CONCESSÃO de item na ficha.

Cobre a feature pedida pela staff (dossiê do beta, cluster FEATURES PEDIDAS, item 1):
a staff não conseguia dar itens de MISSÃO (sem preço) a um personagem — a loja só
lista/vende itens com preço. Agora há um painel (mesmo gate `is_staff` do registrar-
aventuras) que concede QUALQUER item do catálogo (mágico ou mundano, inclusive sem
preço) SEM debitar ouro, com trilha (quem/quando/origem) na própria linha de inventário
e reversão guardada.

Regras verificadas:
  1. Conceder item mission-only (preço 0) — impossível pela compra — funciona.
  2. Não debita ouro nem cria transação.
  3. Empilha consumível idêntico da mesma origem (qtd); equipável vira linha própria.
  4. Item concedido é linha normal (equipável/sintonizável) com a trilha marcada.
  5. Reverter remove a linha; guarda recusa item em uso (equipado/sintonizado) e linha
     que não é concessão.
  6. Permissões: DONO não-staff não concede nem reverte (404); staff sim.

Reusa a fixture real (`conteudo.json`) e o `_guerreiro_no_nivel` do test_levelup.
"""
from django.urls import reverse

from home.character_engine import (
    _item_consumivel_meta, _item_magico_equipavel, _recursos_consumiveis, derive,
)
from home.models import (
    TbItemMagico, TbItemMundano, TbPersonagem, TbPersonagemItem,
)
from home.test_levelup import LevelUpLoteBase


class ConcederItemBase(LevelUpLoteBase):
    def _char_dono_staff(self, apelido='conc'):
        """Guerreiro N1 real; o dono é STAFF (herdado de _guerreiro_no_nivel)."""
        return self._guerreiro_no_nivel(1, apelido=apelido)

    def _rebind_dono_nao_staff(self, p, username):
        dono = self._novo_usuario(username, staff=False)
        p.dono = dono
        p.save(update_fields=['dono'])
        return dono

    def _item_magico_missao(self):
        it = TbItemMagico.objects.filter(preco=0).first()
        self.assertIsNotNone(it, 'fixture deveria ter item mágico mission-only (preço 0)')
        return it

    def _item_magico_consumivel(self):
        it = next((i for i in TbItemMagico.objects.all()
                   if _item_consumivel_meta(None, i)['consumivel']), None)
        self.assertIsNotNone(it, 'fixture deveria ter item mágico consumível (poção/pergaminho)')
        return it

    def _item_magico_equipavel(self):
        it = next((i for i in TbItemMagico.objects.all()
                   if not _item_consumivel_meta(None, i)['consumivel']), None)
        self.assertIsNotNone(it)
        return it


class ConcederItemTests(ConcederItemBase):
    def test_staff_concede_item_missao_sem_preco(self):
        # A COMPRA recusa item sem preço; a CONCESSÃO da staff aceita.
        p = self._char_dono_staff()
        item = self._item_magico_missao()
        carteira0 = p.carteira_pc = 10_000
        p.save(update_fields=['carteira_pc'])
        transacoes0 = p.transacoes.count()
        self.client.force_login(p.dono)  # dono é staff
        resp = self.client.post(
            reverse('personagem_conceder_item', args=[p.pk]),
            data={'tipo': 'magico', 'item': item.slug, 'qtd': 1,
                  'nota_origem': 'Recompensa da Missão X'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('concessao=ok', resp['Location'])
        linha = TbPersonagemItem.objects.get(id_personagem=p, id_item_magico=item)
        self.assertEqual(linha.qtd, 1)
        self.assertIsNotNone(linha.concedido_em)
        self.assertEqual(linha.concedido_por_id, p.dono_id)
        self.assertEqual(linha.origem_nota, 'Recompensa da Missão X')
        # NÃO debitou ouro nem registrou transação (não é compra)
        p.refresh_from_db()
        self.assertEqual(p.carteira_pc, carteira0)
        self.assertEqual(p.transacoes.count(), transacoes0)

    def test_concede_item_mundano(self):
        p = self._char_dono_staff()
        item = TbItemMundano.objects.first()
        self.assertIsNotNone(item)
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_conceder_item', args=[p.pk]),
            data={'tipo': 'mundano', 'item': item.slug, 'qtd': 3, 'nota_origem': 'Loot'})
        self.assertEqual(resp.status_code, 302)
        linha = TbPersonagemItem.objects.get(
            id_personagem=p, nome=item.nome, concedido_em__isnull=False)
        self.assertEqual(linha.qtd, 3)
        self.assertIsNone(linha.id_item_magico_id)

    def test_consumivel_identico_mesma_origem_empilha(self):
        # Duas concessões do MESMO consumível com a MESMA origem viram 1 linha (qtd somado).
        p = self._char_dono_staff()
        item = self._item_magico_consumivel()
        self.client.force_login(p.dono)
        url = reverse('personagem_conceder_item', args=[p.pk])
        self.client.post(url, data={'tipo': 'magico', 'item': item.slug, 'qtd': 2,
                                    'nota_origem': 'Missão A'})
        self.client.post(url, data={'tipo': 'magico', 'item': item.slug, 'qtd': 3,
                                    'nota_origem': 'Missão A'})
        linhas = TbPersonagemItem.objects.filter(id_personagem=p, id_item_magico=item)
        self.assertEqual(linhas.count(), 1)
        self.assertEqual(linhas.first().qtd, 5)

    def test_consumivel_origem_diferente_nao_empilha(self):
        p = self._char_dono_staff()
        item = self._item_magico_consumivel()
        self.client.force_login(p.dono)
        url = reverse('personagem_conceder_item', args=[p.pk])
        self.client.post(url, data={'tipo': 'magico', 'item': item.slug, 'qtd': 1,
                                    'nota_origem': 'Missão A'})
        self.client.post(url, data={'tipo': 'magico', 'item': item.slug, 'qtd': 1,
                                    'nota_origem': 'Missão B'})
        self.assertEqual(
            TbPersonagemItem.objects.filter(id_personagem=p, id_item_magico=item).count(), 2)

    def test_equipavel_nunca_empilha(self):
        # Item mágico equipável/sintonizável: cada concessão é uma linha (não empilha).
        p = self._char_dono_staff()
        item = self._item_magico_equipavel()
        self.client.force_login(p.dono)
        url = reverse('personagem_conceder_item', args=[p.pk])
        self.client.post(url, data={'tipo': 'magico', 'item': item.slug, 'nota_origem': 'X'})
        self.client.post(url, data={'tipo': 'magico', 'item': item.slug, 'nota_origem': 'X'})
        self.assertEqual(
            TbPersonagemItem.objects.filter(id_personagem=p, id_item_magico=item).count(), 2)

    def test_variante_magica_exige_e_preserva_item_base(self):
        p = self._char_dono_staff(apelido='conc-variante')
        base = TbItemMundano.objects.filter(
            categoria='armadura', subcategoria__in=['media', 'pesada']).first()
        self.assertIsNotNone(base)
        variante = TbItemMagico.objects.create(
            nome='Armadura Mágica Variável', slug='armadura-magica-variavel-concessao',
            tipo='variante genérica', slot='armadura', preco=0,
            tags_json=['base_item{catalog:mundane, category:armor, subtype:medium|heavy}',
                       'ca:+1'])
        self.client.force_login(p.dono)
        url = reverse('personagem_conceder_item', args=[p.pk])

        sem_base = self.client.post(
            url, data={'tipo': 'magico', 'item': variante.slug})
        self.assertIn('concessao=base_item', sem_base['Location'])
        self.assertFalse(TbPersonagemItem.objects.filter(
            id_personagem=p, id_item_magico=variante).exists())

        concedido = self.client.post(
            url, data={'tipo': 'magico', 'item': variante.slug,
                       'base_item': base.slug, 'nota_origem': 'Missão'})
        self.assertIn('concessao=ok', concedido['Location'])
        linha = TbPersonagemItem.objects.get(
            id_personagem=p, id_item_magico=variante)
        self.assertEqual(linha.id_item_mundano, base)
        self.assertEqual(linha.tags_json, base.tags_json)
        self.assertIn(base.nome, linha.nome)

    def test_painel_expoe_as_bases_de_variantes_sem_nome_hardcoded(self):
        p = self._char_dono_staff(apelido='conc-variante-ui')
        base = TbItemMundano.objects.filter(
            categoria='armadura', subcategoria='media').first()
        self.assertIsNotNone(base)
        variante = TbItemMagico.objects.create(
            nome='Variante UI', slug='variante-ui', tipo='variante', slot='armadura',
            tags_json=['base_item{catalog:mundane, category:armor, subtype:medium}'])
        self.client.force_login(p.dono)
        html = self.client.get(reverse('editar_ficha', args=[p.pk])).content.decode('utf-8')
        self.assertIn('data-conceder-base', html)
        self.assertIn('data-item-magico="%s"' % variante.slug, html)
        self.assertIn('value="%s"' % base.slug, html)


class ConsumivelInventarioTests(ConcederItemBase):
    def test_apito_da_aguia_ocupa_a_mao_enquanto_e_usado(self):
        item = TbItemMagico.objects.get(slug='apito-da-aguia')
        self.assertEqual(item.slot, 'empunhado')
        self.assertTrue(_item_magico_equipavel(item))

    def test_consumable_explicito_e_autoritativo(self):
        item = TbItemMagico.objects.create(
            nome='Amuleto consumivel', slug='amuleto-consumivel',
            slot='pescoco', tipo='item maravilhoso',
            tags_json=['slot:pescoco', 'consumable'])
        self.assertTrue(_item_consumivel_meta(None, item)['consumivel'])
        self.assertFalse(_item_magico_equipavel(item))

    def test_item_com_cargas_nao_consumido_sem_tag_consumable(self):
        item = TbItemMagico.objects.create(
            nome='Cajado com cargas', slug='cajado-com-cargas',
            slot='arma', tipo='cajado', tags_json=['charges:10(reset:dawn)'])
        self.assertFalse(_item_consumivel_meta(None, item)['consumivel'])
        self.assertTrue(_item_magico_equipavel(item))

    def test_municao_e_consumivel_por_catalogo(self):
        item = TbItemMagico.objects.create(
            nome='Flecha de teste', slug='flecha-de-teste',
            slot='municao', tipo='municao', tags_json=[])
        self.assertTrue(_item_consumivel_meta(None, item)['consumivel'])
        self.assertFalse(_item_magico_equipavel(item))

    def test_pocao_nao_pode_equipar_e_flag_antiga_e_ignorada(self):
        p = self._char_dono_staff(apelido='pocao-equip')
        item = TbItemMagico.objects.create(
            nome='Poção de Teste', slug='pocao-de-teste',
            slot='pocao', tipo='poção', tags_json=['always_active{ca:+99}'])
        linha = TbPersonagemItem.objects.create(
            id_personagem=p, id_item_magico=item, nome=item.nome,
            qtd=1, equipado=True)
        inv = next(i for i in derive(p)['inventario'] if i['id'] == linha.id)
        self.assertFalse(inv['equipado'])
        self.assertFalse(inv['pode_equipar'])
        self.client.force_login(p.dono)
        self.client.post(
            reverse('personagem_equipar_item', args=[p.pk]),
            data={'item': linha.id})
        linha.refresh_from_db()
        self.assertFalse(linha.equipado)

    def test_usar_ultima_unidade_remove_linha_sem_recurso_recuperavel(self):
        p = self._char_dono_staff(apelido='pocao-consome')
        item = self._item_magico_consumivel()
        linha = TbPersonagemItem.objects.create(
            id_personagem=p, id_item_magico=item, nome=item.nome, qtd=1)
        self.client.force_login(p.dono)
        self.client.post(
            reverse('personagem_usar_item_consumivel', args=[p.pk]),
            data={'item': linha.id, 'acao': 'usar'})
        self.assertFalse(TbPersonagemItem.objects.filter(pk=linha.pk).exists())

    def test_descanso_longo_nao_recupera_quantidade_de_consumivel(self):
        p = self._char_dono_staff(apelido='pocao-nao-recupera')
        item = self._item_magico_consumivel()
        linha = TbPersonagemItem.objects.create(
            id_personagem=p, id_item_magico=item, nome=item.nome, qtd=3)
        self.client.force_login(p.dono)

        self.client.post(
            reverse('personagem_usar_item_consumivel', args=[p.pk]),
            data={'item': linha.id, 'acao': 'usar'})
        self.client.post(
            reverse('personagem_descansar', args=[p.pk]),
            data={'tipo': 'longo'})

        linha.refresh_from_db()
        self.assertEqual(linha.qtd, 2)


class ReverterConcessaoTests(ConcederItemBase):
    def _concede(self, p, item, **extra):
        self.client.force_login(p.dono)
        data = {'tipo': 'magico', 'item': item.slug}
        data.update(extra)
        self.client.post(reverse('personagem_conceder_item', args=[p.pk]), data=data)
        return TbPersonagemItem.objects.get(id_personagem=p, id_item_magico=item)

    def test_reverter_remove_a_linha(self):
        p = self._char_dono_staff()
        linha = self._concede(p, self._item_magico_missao(), nota_origem='erro')
        resp = self.client.post(
            reverse('personagem_reverter_concessao', args=[p.pk, linha.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('concessao=revertido', resp['Location'])
        self.assertFalse(TbPersonagemItem.objects.filter(id=linha.id).exists())

    def test_reverter_guarda_item_equipado(self):
        p = self._char_dono_staff()
        linha = self._concede(p, self._item_magico_equipavel())
        linha.equipado = True
        linha.save(update_fields=['equipado'])
        resp = self.client.post(
            reverse('personagem_reverter_concessao', args=[p.pk, linha.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('concessao=rev_em_uso', resp['Location'])
        self.assertTrue(TbPersonagemItem.objects.filter(id=linha.id).exists())

    def test_reverter_recusa_linha_nao_concedida(self):
        # Linha comprada/normal (sem concedido_em) não é reversível por este endpoint.
        p = self._char_dono_staff()
        comprada = TbPersonagemItem.objects.create(id_personagem=p, qtd=1, nome='Corda')
        resp = self.client.post(
            reverse('personagem_reverter_concessao', args=[p.pk, comprada.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('concessao=rev_invalido', resp['Location'])
        self.assertTrue(TbPersonagemItem.objects.filter(id=comprada.id).exists())


class ConcederItemPermissoesTests(ConcederItemBase):
    def test_dono_nao_staff_nao_concede(self):
        p = self._char_dono_staff()
        item = self._item_magico_missao()
        dono = self._rebind_dono_nao_staff(p, 'dono-plebeu-conc')
        self.client.force_login(dono)
        resp = self.client.post(
            reverse('personagem_conceder_item', args=[p.pk]),
            data={'tipo': 'magico', 'item': item.slug})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(
            TbPersonagemItem.objects.filter(id_personagem=p, id_item_magico=item).exists())

    def test_dono_nao_staff_nao_reverte(self):
        p = self._char_dono_staff()
        # staff concede primeiro (dono ainda é staff aqui)
        self.client.force_login(p.dono)
        item = self._item_magico_missao()
        self.client.post(reverse('personagem_conceder_item', args=[p.pk]),
                         data={'tipo': 'magico', 'item': item.slug})
        linha = TbPersonagemItem.objects.get(id_personagem=p, id_item_magico=item)
        # agora o dono vira não-staff e tenta reverter
        dono = self._rebind_dono_nao_staff(p, 'dono-plebeu-rev')
        self.client.force_login(dono)
        resp = self.client.post(
            reverse('personagem_reverter_concessao', args=[p.pk, linha.id]))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(TbPersonagemItem.objects.filter(id=linha.id).exists())


class EditarFichaFetchTests(ConcederItemBase):
    AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    def test_equipar_retorna_fragmento_sem_redirect(self):
        p = self._char_dono_staff(apelido='fetch-equip')
        item = TbItemMagico.objects.create(
            nome='Anel Fetch', slug='anel-fetch', slot='aneis',
            tipo='item maravilhoso', tags_json=['always_active{ca:+1}'])
        linha = TbPersonagemItem.objects.create(
            id_personagem=p, id_item_magico=item, nome=item.nome)
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_equipar_item', args=[p.pk]),
            data={'item': linha.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['msg'], 'equipado')
        self.assertIn('inventario_html', body)
        linha.refresh_from_db()
        self.assertTrue(linha.equipado)

    def test_conceder_e_reverter_atualizam_ledger_sem_redirect(self):
        p = self._char_dono_staff(apelido='fetch-concede')
        item = self._item_magico_missao()
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_conceder_item', args=[p.pk]),
            data={'tipo': 'magico', 'item': item.slug, 'nota_origem': 'Fetch'},
            **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('ficha-concessoes-dinamico', resp.json()['concessoes_html'])
        linha = TbPersonagemItem.objects.get(id_personagem=p, id_item_magico=item)
        resp = self.client.post(
            reverse('personagem_reverter_concessao', args=[p.pk, linha.id]),
            **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['msg'], 'revertido')
        self.assertFalse(TbPersonagemItem.objects.filter(pk=linha.pk).exists())

    def test_usar_recurso_retorna_snapshot_atualizado(self):
        p = self._char_dono_staff(apelido='fetch-recurso')
        recursos = _recursos_consumiveis(
            p, list(p.classes.select_related('id_classe', 'id_subclasse')))
        self.assertTrue(recursos, 'personagem de teste deve ter recurso consumível')
        recurso = recursos[0]
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_usar_recurso', args=[p.pk]),
            data={'recurso': recurso['slug']}, **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        atualizado = next(
            r for r in resp.json()['recursos'] if r['slug'] == recurso['slug'])
        self.assertEqual(atualizado['atual'], max(0, recurso['atual'] - 1))

    def test_salvar_informacoes_retorna_json(self):
        p = self._char_dono_staff(apelido='fetch-info')
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_info_salvar', args=[p.pk]),
            data={'idade': '37', 'historia': 'Salvo sem reload.'},
            **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['ok'])
        p.refresh_from_db()
        self.assertEqual(p.idade, '37')
        self.assertEqual(p.historia, 'Salvo sem reload.')

    def test_formulario_aceita_caminhos_internos_de_imagem(self):
        p = self._char_dono_staff(apelido='relative-media')
        p.foto_url = '/media/character_uploads/teste/retrato.gif'
        p.token_url = '/media/character_uploads/teste/token.png'
        p.save(update_fields=['foto_url', 'token_url'])
        self.client.force_login(p.dono)

        html = self.client.get(
            reverse('ficha_detail', args=[p.pk]) + '?aba=info'
        ).content.decode('utf-8')
        self.assertIn('type="text" inputmode="url" name="foto_url"', html)
        self.assertIn('type="text" inputmode="url" name="token_url"', html)
        self.assertNotIn('type="url" name="foto_url"', html)

    def test_get_ficha_staff_mostra_painel_conceder(self):
        p = self._char_dono_staff()
        self.client.force_login(p.dono)  # staff
        html = self.client.get(reverse('editar_ficha', args=[p.pk])).content.decode('utf-8')
        self.assertIn('data-conceder-form', html)
        self.assertIn(reverse('personagem_conceder_item', args=[p.pk]), html)

    def test_get_ficha_dono_nao_staff_esconde_painel(self):
        # Onda C: a página inteira virou ferramenta da staff — o dono não-staff nem entra,
        # é devolvido para a própria ficha (logo, painel de concessão nenhum).
        p = self._char_dono_staff()
        self._rebind_dono_nao_staff(p, 'dono-plebeu-get')
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('ficha_detail', args=[p.pk]))
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertNotIn('data-conceder-form', html)
