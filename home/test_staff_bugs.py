# -*- coding: utf-8 -*-
"""Regressão dos 3 bugs do teste da staff (prints):

A. Cavaleiro Arcano não deixava ESCOLHER TRUQUE no wizard de subir de nível — a
   conjuração do third-caster vem da SUBCLASSE, escolhida NO MESMO passo, e a
   pendência de magias (calculada antes da subclasse ser atribuída) vinha vazia,
   então a seção de truques nunca era renderizada.
B. O card de detalhe de 'Golpe Certeiro' do Brigão de Taverna puxava a descrição
   da MAGIA homônima (colisão de nome) — a descrição linkava a sub-habilidade à
   `(tbMagia, golpe-certeiro)`.
C. Brigão de Taverna não somava o +1 de dano do Golpe Desarmado Aprimorado quando
   o desarmado já causa >= 1d6 (Bárbaro/Monge) — o `+1` vivia num while_active
   (bloco ativo) e nunca era avaliado no derive, apesar de ser estático.

Roda contra o conteúdo real (fixture `conteudo.json`).
"""
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from home import views
from home.models import (
    TbClasse, TbSubclasse, TbTalento, TbClassehabilidade, TbItemMagico,
    TbPersonagem, TbPersonagemClasse, TbPersonagemMagia,
)
from home.test_criador import _CriadorBase
from home.test_levelup import LevelUpLoteBase


# ======================================================================================
# BUG A — truques do Cavaleiro Arcano aparecem no wizard de subir de nível
# ======================================================================================
class BugACavaleiroArcanoTruquesTests(LevelUpLoteBase):
    def _sub(self, classe, needle):
        return TbSubclasse.objects.filter(id_classe=classe, nome__icontains=needle).first()

    def test_pendencia_prospectiva_para_subclasse_conjuradora(self):
        # Guerreiro N3 SEM subclasse: a pendência normal é None (classe base não conjura),
        # mas a variante do level-up enxerga a subclasse conjuradora que será escolhida.
        cl = TbClasse.objects.get(slug='guerreiro')
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('bugA-prosp'), nome='GP', nivel=3,
            forca=15, destreza=13, constituicao=14, inteligencia=13, sabedoria=10, carisma=8)
        TbPersonagemClasse.objects.create(id_personagem=p, id_classe=cl, nivel=3, principal=True)
        self.assertIsNone(views._pendencias_magias(p), 'classe base não conjura → None')
        pend = views._pendencias_nivel(p)
        pm = views._pendencias_magias_levelup(p, pend)
        self.assertIsNotNone(pm, 'a pendência prospectiva deve existir')
        self.assertTrue(pm['prospectiva'])
        self.assertEqual(pm['cantrips_pend'], 2)          # truques {3:2} do Cavaleiro Arcano
        self.assertIn('cavaleiro-arcano', pm['subclasses_prospectivas'])
        self.assertTrue(pm['lista_truques'], 'pool de truques (lista do Mago) não pode ser vazio')
        # e o pool é a lista do Mago (o truque de ataque homônimo deve estar lá)
        slugs = {m['slug'] for m in pm['lista_truques']}
        self.assertTrue(slugs, 'lista de truques materializada')

    def test_pagina_renderiza_secao_de_truques_prospectiva(self):
        # A página dedicada (Guerreiro N3 elegível → alvo N4) já traz a seção de magias
        # marcada como prospectiva, com o pool — mesmo com a subclasse ainda pendente.
        p = self._guerreiro_no_nivel(3, apelido='bugA-page')
        self.client.force_login(p.dono)
        html = self.client.get(reverse('personagem_subir_nivel', args=[p.pk])).content.decode('utf-8')
        self.assertIn('data-step="magias"', html)
        self.assertIn('data-prospectiva="1"', html)
        self.assertIn('data-subclasses="cavaleiro-arcano"', html)
        self.assertIn('data-lvl-group="truques"', html)

    def test_preview_com_ek_no_lote_destrava_os_truques(self):
        # Prévia ao vivo COM a subclasse Cavaleiro Arcano no lote: a pendência de truques
        # passa a ser > 0 (é o sinal que o cliente usa p/ revelar a etapa).
        p = self._guerreiro_no_nivel(3, apelido='bugA-prev')
        pc = p.classes.first()
        ek = self._sub(pc.id_classe, 'Cavaleiro Arcano')
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_levelup_preview', args=[p.pk]),
            data=json.dumps({'acoes': [
                {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
                {'tipo': 'subclasse', 'payload': {'subclasse': ek.id_subclasse}}]}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertGreaterEqual(resp.json()['pendencias']['cantrips_pend'], 2)

    def test_preview_com_subclasse_nao_conjuradora_nao_destrava(self):
        # Campeão (não-conjurador) no lote: nenhuma pendência de truque — a etapa fica travada.
        p = self._guerreiro_no_nivel(3, apelido='bugA-champ')
        pc = p.classes.first()
        champ = self._sub(pc.id_classe, 'Campeão')
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_levelup_preview', args=[p.pk]),
            data=json.dumps({'acoes': [
                {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
                {'tipo': 'subclasse', 'payload': {'subclasse': champ.id_subclasse}}]}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['pendencias']['cantrips_pend'], 0)

    def test_lote_ek_mais_truques_persiste_os_truques(self):
        # Fluxo completo num POST: subir + subclasse (Cavaleiro Arcano) + aprender_magias
        # com todas as escolhas do NÍVEL-ALVO → as magias ficam materializadas na ficha.
        from django.db import transaction

        p = self._guerreiro_no_nivel(3, apelido='bugA-lote')
        pc = p.classes.first()
        ek = self._sub(pc.id_classe, 'Cavaleiro Arcano')
        # O lote sobe para N4 antes de escolher a subclasse pendente. Calcula o contrato
        # exatamente nesse estado, em transação revertida, como a página de level-up faz.
        with transaction.atomic():
            views._lvl_aplicar_subir_nivel(p, {'classe': pc.id_classe_id})
            views._lvl_aplicar_subclasse(
                p, {'classe': pc.id_classe_id, 'subclasse': ek.id_subclasse})
            pm = views._pendencias_magias(p, classe_id=pc.id_classe_id)
            transaction.set_rollback(True)
        p.refresh_from_db()
        truques = [m['slug'] for m in pm['lista_truques']][:pm['cantrips_pend']]
        magias = [m['slug'] for m in pm['lista_magias']][:pm['known_pend']]
        self.assertEqual(len(truques), 2)
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_levelup_aplicar', args=[p.pk]),
            data=json.dumps({'acoes': [
                {'tipo': 'subir_nivel', 'payload': {'classe': pc.id_classe_id}},
                {'tipo': 'subclasse', 'payload': {'subclasse': ek.id_subclasse}},
                {'tipo': 'aprender_magias', 'payload': {
                    'truques': truques, 'magias': magias}}]}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['ok'], resp.content)
        p.refresh_from_db()
        self.assertEqual(p.magias.filter(nivel=0).count(), 2, 'os 2 truques deviam persistir')
        self.assertEqual(
            p.magias.filter(nivel__gt=0, origem__icontains='guerreiro').count(),
            len(magias))

    def test_barbaro_sem_subclasse_conjuradora_nao_tem_passo_de_magias(self):
        # Bárbaro (nenhuma subclasse conjuradora): nada de seção de magias no wizard.
        cl = TbClasse.objects.get(slug='barbaro')
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('bugA-barb'), nome='B', nivel=3,
            forca=15, destreza=13, constituicao=14, inteligencia=10, sabedoria=12, carisma=8)
        TbPersonagemClasse.objects.create(id_personagem=p, id_classe=cl, nivel=3, principal=True)
        pend = views._pendencias_nivel(p)
        self.assertIsNone(views._pendencias_magias_levelup(p, pend))


# ======================================================================================
# BUG B — 'Golpe Certeiro' do Brigão não puxa mais a magia homônima
# ======================================================================================
class BugBGolpeCerteiroCardTests(_CriadorBase):
    REF = '(tbMagia, golpe-certeiro)'

    def test_brigao_descricao_sem_ref_de_magia(self):
        t = TbTalento.objects.get(slug='brigao-de-taverna')
        self.assertNotIn(self.REF, t.descricao, 'a referência espúria à MAGIA deve ter sido removida')
        # a sub-habilidade continua como texto (negrito comum), sem virar card de magia
        self.assertIn('**Golpe Certeiro:**', t.descricao)

    def test_dominio_da_cacada_sem_ref_de_magia(self):
        h = TbClassehabilidade.objects.get(pk=1077)
        self.assertNotIn(self.REF, h.descricao)
        self.assertIn('Terceiro Golpe Certeiro', h.descricao)

    def test_nenhuma_ref_golpe_certeiro_sobrou(self):
        for M in (TbTalento, TbClassehabilidade):
            sobra = [o.pk for o in M.objects.filter(descricao__contains='golpe-certeiro')]
            self.assertEqual(sobra, [], '%s ainda referencia golpe-certeiro: %s' % (M.__name__, sobra))

    def test_refs_legitimas_de_magia_preservadas(self):
        # Regressão: cards LEGÍTIMOS de magia (talento que de fato concede o truque) intactos —
        # o fix é cirúrgico ao slug golpe-certeiro, não mexe em nenhuma outra referência.
        t = TbTalento.objects.filter(descricao__contains='(tbMagia, chama-sagrada)').first()
        self.assertIsNotNone(t, 'talento com ref legítima de magia deveria existir na fixture')
        self.assertIn('(tbMagia, chama-sagrada)', t.descricao)

    def test_api_card_da_magia_ainda_funciona(self):
        # O endpoint de card de magia (infra) continua resolvendo a magia por referência —
        # o bug era de DADO (link espúrio), não da infra de cards.
        u = self._novo_usuario('cardviewer')
        self.client.force_login(u)
        resp = self.client.get(reverse('api_card_preview'),
                               {'table': 'tbMagia', 'args': 'chama-sagrada'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('success'))
        self.assertEqual(resp.json()['title'], 'Chama Sagrada')


class AbilityCardScopeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='card-scope', password='x')
        self.client.force_login(self.user)
        self.base = TbClasse.objects.create(nome='Classe Card', slug='classe-card')
        self.other = TbClasse.objects.create(nome='Outra Card', slug='outra-card')
        self.sub = TbSubclasse.objects.create(
            id_classe=self.base, nome='Subclasse Card', slug='subclasse-card')
        self.base_ability = TbClassehabilidade.objects.create(
            id_classe=self.base, nome='Nome Igual', descricao='base correta', niveladquirido=1)
        TbClassehabilidade.objects.create(
            id_classe=self.other, nome='Nome Igual', descricao='outra errada', niveladquirido=1)
        TbClassehabilidade.objects.create(
            id_classe=self.base, id_subclasse=self.sub, nome='Nome Igual',
            descricao='sub correta', niveladquirido=3)

    def _card(self, owner, ability='nome-igual'):
        return self.client.get(reverse('api_card_preview'), {
            'table': 'tbClasseHabilidade', 'args': '%s,%s' % (owner, ability)})

    def test_classe_nao_captura_habilidade_homonima_da_subclasse(self):
        response = self._card('classe-card')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['description'], 'base correta')

    def test_subclasse_resolve_apenas_o_proprio_escopo(self):
        response = self._card('subclasse-card')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['description'], 'sub correta')

    def test_table_only_nao_pode_ser_referenciada_como_card(self):
        TbClassehabilidade.objects.create(
            id_classe=self.base, nome='Linha de Tabela', descricao='não renderizar',
            niveladquirido=2, table_only=True)
        response = self._card('classe-card', 'linha-de-tabela')
        self.assertEqual(response.status_code, 404)

    def test_sem_origem_exata_nao_faz_fallback_global(self):
        response = self._card('classe-inexistente')
        self.assertEqual(response.status_code, 404)


# ======================================================================================
# CATÁLOGO — correções reportadas pela staff precisam sobreviver ao dump/restore
# ======================================================================================
class CatalogoItemReportadoTests(_CriadorBase):
    PISOS = {
        'cinto-da-forca-do-gigante-da-colina': 21,
        'cinto-da-forca-do-gigante-de-gelo': 23,
        'cinto-da-forca-do-gigante-de-pedra': 23,
        'cinto-de-fogo-forca-gigante': 25,
        'cinto-da-forca-gigante-da-tempestade': 29,
        'cinturao-da-tempestade-dormente': 21,
        'cinto-da-tempestade-desperto': 23,
        'cinto-da-tempestade-exaltado': 25,
    }

    def test_itens_de_forca_usam_o_piso_generico_de_atributo(self):
        for slug, valor in self.PISOS.items():
            with self.subTest(slug=slug):
                item = TbItemMagico.objects.get(slug=slug)
                self.assertIn(
                    'attr:str_score:=max(str_score,%d)' % valor,
                    item.tags_json)

    def test_pisos_de_constituicao_e_inteligencia_apontam_o_atributo_correto(self):
        self.assertIn(
            'attr:con_score:=max(con_score,19)',
            TbItemMagico.objects.get(slug='amuleto-da-saude').tags_json)
        self.assertIn(
            'attr:int_score:=max(int_score,19)',
            TbItemMagico.objects.get(
                slug='tiara-do-intelecto').tags_json)

    def test_mizzium_declara_armadura_base_e_pocao_tem_preco_oficial(self):
        mizzium = TbItemMagico.objects.get(slug='armadura-mizzium')
        self.assertIn(
            'base_item{catalog:mundane, category:armor, subtype:medium|heavy}',
            mizzium.tags_json)
        pocao = TbItemMagico.objects.get(slug='pocao-de-invulnerabilidade')
        self.assertEqual(float(pocao.preco), 2500.0)


# ======================================================================================
# BUG C — +1 de dano estático do Brigão avaliado no derive
# ======================================================================================
class BugCBrigaoDanoTests(TestCase):
    """Deriva SÓ o perfil desarmado por um caminho fiel (apply_tags -> _ataques), como o
    CondicionalEmValorEstaticoTests, mas com N features (talento + fonte de dado desarmado)."""

    BRIGAO = [
        'always_active{ unarmed_strike.dmg:=1d6+str_mod(concussao) }',
        'while_active{ trigger=hit{unarmed}, if(unarmed_strike.dmg >= 1d6): unarmed_strike.dmg:+1 }',
    ]

    def _desarmado(self, feature_tags, nivel=4, forca=16):
        from home.character_engine import apply_tags, _ataques, _build_ctx, bonus_proficiencia
        fmod = (forca - 10) // 2
        attrs = {'FOR': {'valor': forca, 'mod': fmod},
                 'DES': {'valor': 14, 'mod': 2}, 'CON': {'valor': 14, 'mod': 2},
                 'INT': {'valor': 10, 'mod': 0}, 'SAB': {'valor': 10, 'mod': 0},
                 'CAR': {'valor': 10, 'mod': 0}}
        pb = bonus_proficiencia(nivel)
        feats = []
        for i, tags in enumerate(feature_tags):
            obj = type('F', (), {'nome': 'F%d' % i,
                                 'tags_json': tags if isinstance(tags, list) else [tags],
                                 'table_only': False})()
            feats.append(('talento', 'F%d' % i, obj, None))
        state = {'_ctx': _build_ctx(nivel, pb, attrs), 'pv': {'maximo_calculado': 30},
                 'velocidade': '9 m / 30 ft', 'iniciativa': 0, 'recursos': {}, 'ca': 10}
        apply_tags(state, feats, personagem=None, escolhas={})
        res = _ataques(state['_tag'], attrs, pb)
        return next((p for p in res['perfis'] if p['escopo'] == 'unarmed-strike'), None), fmod

    def test_brigao_cru_aplica_piso_1d6_sem_bump(self):
        # Personagem sem dado próprio: Brigão sobe pra 1d6, mas NÃO soma +1 (não "já causa >= 1d6").
        d, fmod = self._desarmado([self.BRIGAO])
        self.assertIsNotNone(d)
        self.assertEqual(d['dado'], '1d6(concussao)')
        self.assertEqual(d['dano'], '1d6(concussao) %+d' % fmod)   # só FOR, sem +1

    def test_brigao_com_dado_1d6_soma_o_bump(self):
        # Já causa 1d6 por outra fonte (>= limiar): soma +1 ao dano.
        d, fmod = self._desarmado([self.BRIGAO, 'always_active{ unarmed_strike.dmg:=1d6+str_mod }'])
        self.assertIsNotNone(d)
        self.assertEqual(d['dano'], '1d6(concussao) %+d' % (fmod + 1))

    def test_brigao_com_dado_maior_soma_bump_e_nao_rebaixa(self):
        # Dado próprio 1d8 (Monge/Bárbaro): o piso 1d6 NÃO rebaixa o 1d8 e o +1 é aplicado.
        d, fmod = self._desarmado([self.BRIGAO, 'always_active{ unarmed_strike.dmg:=1d8+str_mod }'])
        self.assertIsNotNone(d)
        self.assertEqual(d['dado'], '1d8')
        self.assertEqual(d['dano'], '1d8 %+d' % (fmod + 1))

    def test_sem_brigao_dado_proprio_nao_ganha_bump(self):
        # Sem o talento não há bump: 1d8 puro (guard de que o +1 não vaza de outras features).
        d, fmod = self._desarmado(['always_active{ unarmed_strike.dmg:=1d8+str_mod }'])
        self.assertIsNotNone(d)
        self.assertEqual(d['dano'], '1d8 %+d' % fmod)
