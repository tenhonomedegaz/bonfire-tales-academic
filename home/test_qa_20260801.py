# -*- coding: utf-8 -*-
"""RegressÃµes dos relatos de QA recebidos em 01/08/2026."""
from django.urls import reverse
from types import SimpleNamespace

from home import picks, views
from home.character_engine import derive
from home.models import (
    TbClasse, TbEssencia, TbLinhagem, TbPersonagem, TbPersonagemClasse,
    TbPersonagemEscolha, TbPersonagemPericia, TbPersonagemTalento,
    TbRaca, TbSubclasse, TbTalento, TbMagia, TbPersonagemMagia,
    TbIdioma, TbItemMundano, TbPersonagemProficiencia,
)
from home.test_criador import _CriadorBase


class QACharacterRulesTests(_CriadorBase):
    def _character(self, *, nivel=1, classe='guerreiro', subclasse=None,
                   linhagem=None, essencia=None, username='qa'):
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('%s-%s' % (username, nivel)), nome='QA', nivel=nivel,
            id_raca=TbRaca.objects.get(slug='humano'),
            id_linhagem=linhagem, id_essencia=essencia,
            forca=14, destreza=14, constituicao=14,
            inteligencia=10, sabedoria=10, carisma=10)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug=classe),
            id_subclasse=subclasse, nivel=nivel, principal=True)
        return p

    def test_sybaris_aplica_cinco_pes(self):
        p = self._character(essencia=TbEssencia.objects.get(slug='vampirismo'), username='syb')
        TbPersonagemEscolha.objects.create(
            id_personagem=p, origem='EssÃªncia', tipo='vertente', slot=0, valor='sybaris')
        ficha = derive(p)
        self.assertEqual(ficha['velocidade_bonus'], 5)
        self.assertIn('35 ft', ficha['velocidade'])

    def test_maldicao_suprime_apenas_talento_racial_de_nivel_um(self):
        p = self._character(nivel=5, essencia=TbEssencia.objects.get(slug='vampirismo'), username='vamp')
        TbPersonagemEscolha.objects.create(
            id_personagem=p, origem='EssÃªncia', tipo='vertente', slot=0, valor='sybaris')
        nomes = {o['nome'] for b in views._pendencias_talento_racial(p) for o in b['opcoes']}
        self.assertNotIn('Aprendiz Pr\u00e1tico', nomes)
        self.assertIn('Elo T\u00e1tico', nomes)
        self.assertNotIn('Adaptabilidade Ambiental', nomes)
        self.assertNotIn('Instinto de SobrevivÃªncia', nomes)

    def test_qualquer_linhagem_humana_exige_uma_das_quatro_linhagens(self):
        traco = next(t for t in views.TbTracoracial.objects.filter(nome='Aprendiz Pr\u00e1tico'))
        linhagens = list(TbLinhagem.objects.filter(id_raca__slug='humano'))
        slugs, aceita_essencia = views._talento_linhagem_info(traco, linhagens)
        self.assertEqual(set(slugs), {'erthari', 's\u00e1larin', 'durkarn', 'goruun'})
        self.assertTrue(aceita_essencia)

    def test_resiliente_abre_escolha_e_concede_save(self):
        p = self._character(nivel=4, username='res')
        talento = TbTalento.objects.get(slug='resiliente')
        TbPersonagemTalento.objects.create(
            id_personagem=p, id_talento=talento, categoria='geral', nivel=4, nome=talento.nome)
        grupo = next(g for g in picks.resolve_personagem(p) if g['kind'] == 'save_prof')
        self.assertEqual(grupo['pendentes'], 1)
        self.assertNotIn('str', {o['slug'] for o in grupo['universo']})
        self.assertNotIn('con', {o['slug'] for o in grupo['universo']})
        picks.registry_entry('save_prof')['persist'](p, grupo, ['wis'])
        self.assertTrue(derive(p)['saves']['SAB']['proficiente'])

    def test_prerequisito_generico_distingue_linhagem_de_essencia(self):
        lineage_only = SimpleNamespace(
            tags_json=['character_prereq:any{lineage:*}'])
        lineage_or_essence = SimpleNamespace(
            tags_json=['character_prereq:any{lineage:*|essence:*}'])
        curse = TbEssencia.objects.get(slug='vampirismo')
        self.assertFalse(views._character_prereq_matches(
            lineage_only, essence=curse))
        self.assertTrue(views._character_prereq_matches(
            lineage_or_essence, essence=curse))

    def test_raizes_profundas_abre_talento_de_origem(self):
        p = self._character(nivel=4, username='raiz')
        talento = TbTalento.objects.get(slug='raizes-profundas')
        TbPersonagemTalento.objects.create(
            id_personagem=p, id_talento=talento, categoria='geral', nivel=4, nome=talento.nome)
        grupos = [g for g in picks.resolve_personagem(p) if g['kind'] == 'talento']
        self.assertTrue(any(g['origem'] == 'Ra\u00edzes Profundas' and g['pendentes'] == 1 for g in grupos))

    def test_levelup_exige_e_persiste_pick_interno_do_talento(self):
        p = self._character(nivel=4, username='raiz-levelup')
        talento = TbTalento.objects.get(slug='raizes-profundas')
        attr = views._talento_attr_options(talento)[0]
        grupo = picks.resolve_groups([talento], personagem=p, nivel=4)[0]
        escolha = str(grupo['universo'][0]['id'])
        payload = {'modo': 'talento', 'talento': talento.pk, 'talento_attr': attr}
        self.assertEqual(views._lvl_aplicar_asi(p, payload), [views._ERR_ASI_TALENTO_PICK])
        self.assertFalse(p.talentos.filter(id_talento=talento).exists())
        payload['talento_picks'] = {'0': [escolha]}
        self.assertEqual(views._lvl_aplicar_asi(p, payload), [])
        self.assertTrue(p.talentos.filter(id_talento=talento).exists())
        self.assertTrue(p.escolhas.filter(origem=talento.nome, tipo='talento').exists())

    def test_presenca_intimidante_substitui_pericia_duplicada(self):
        sub = TbSubclasse.objects.get(id_classe__slug='barbaro', nome__icontains='Berserker')
        p = self._character(nivel=10, classe='barbaro', subclasse=sub, username='bers')
        grupos = picks.resolve_personagem(p, kinds={'pericia'})
        self.assertTrue(any(g['origem'] == 'Presen\u00e7a Intimidante' for g in grupos), {
            'grupos': [(g['origem'], g['universo']) for g in grupos],
            'features': list(views.TbClassehabilidade.objects.filter(
                id_subclasse=sub, niveladquirido__lte=10).values_list('nome', 'tags_json')),
        })
        grupo = next(g for g in grupos if g['origem'] == 'Presen\u00e7a Intimidante')
        self.assertEqual({o['slug'] for o in grupo['universo']}, {'intimidacao'})
        TbPersonagemPericia.objects.create(
            id_personagem=p, nome='Intimida\u00e7\u00e3o', atributo='CAR', proficiente=True)
        grupo = next(g for g in picks.resolve_personagem(p, kinds={'pericia'})
                     if g['origem'] == 'Presen\u00e7a Intimidante')
        self.assertNotIn('intimidacao', {o['slug'] for o in grupo['universo']})
        self.assertGreater(len(grupo['universo']), 1)

    def test_seletor_de_subclasse_mostra_feature_do_nivel(self):
        p = self._character(nivel=3, classe='barbaro', username='sub')
        bers = next(s for s in views._pendencias_nivel(p)['subclasses'] if 'Berserker' in s['nome'])
        self.assertTrue(any(h.nome in bers['descricao'] for h in
                            views.TbClassehabilidade.objects.filter(
                                id_subclasse__id_subclasse=bers['id'], niveladquirido=3,
                                table_only=False)))

    def test_apenas_staff_pode_trocar_talento_racial_antigo(self):
        linhagem = TbLinhagem.objects.get(slug='erthari')
        p = self._character(linhagem=linhagem, username='swap')
        atual = TbPersonagemTalento.objects.create(
            id_personagem=p, categoria='racial', nivel=1, nome='Aprendiz Pr\u00e1tico')
        card = views._talentos_raciais_ficha(p)[0]
        self.assertTrue(card['opcoes'])
        novo = card['opcoes'][0]['val']
        self.client.force_login(p.dono)
        response = self.client.post(reverse('personagem_trocar_talento_racial', args=[p.pk]), {
            'talento_atual': atual.id, 'val': novo,
        })
        self.assertEqual(response.status_code, 404)
        atual.refresh_from_db()
        self.assertEqual(atual.nome, 'Aprendiz Pr\u00e1tico')
        response = self.client.get(reverse('ficha_detail', args=[p.pk]))
        self.assertNotContains(response, reverse(
            'personagem_trocar_talento_racial', args=[p.pk]))
        staff = self._novo_usuario('staff-swap', staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertContains(response, reverse(
            'personagem_trocar_talento_racial', args=[p.pk]))
        response = self.client.post(reverse('personagem_trocar_talento_racial', args=[p.pk]), {
            'talento_atual': atual.id, 'val': novo,
        })
        self.assertEqual(response.status_code, 302)
        atual.refresh_from_db()
        self.assertEqual(atual.nome, novo)

    def test_staff_registra_idioma_e_ferramenta_por_treinamento(self):
        p = self._character(username='train')
        staff = self._novo_usuario('staff-train', staff=True)
        self.client.force_login(staff)
        initial = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertEqual(initial.status_code, 200)
        self.assertContains(initial, 'id="staff-training-search"')
        self.assertContains(initial, 'id="staff-training-group"')
        self.assertContains(initial, 'id="staff-training-choice"')
        self.assertContains(initial, '<optgroup label="Idiomas">')
        self.assertContains(initial, '<optgroup label="Ferramentas">')
        idioma = TbIdioma.objects.first()
        ferramenta = TbItemMundano.objects.filter(categoria='ferramenta').first()
        for tipo, catalog in (('idioma', idioma), ('ferramenta', ferramenta)):
            response = self.client.post(reverse('personagem_treinamento', args=[p.pk]), {
                'treinamento': '%s:%s' % (tipo, catalog.slug),
            })
            self.assertEqual(response.status_code, 302)
            self.assertTrue(TbPersonagemProficiencia.objects.filter(
                id_personagem=p, origem='Treinamento', tipo=tipo,
                nome=catalog.nome).exists())
        self.assertFalse(p.escolhas.filter(origem='Treinamento', tipo='pericia').exists())
        response = self.client.get(reverse('editar_ficha', args=[p.pk]))
        self.assertNotContains(response, 'name="pericia"')

    def test_magia_conhecida_nao_pode_ser_despreparada_por_post_direto(self):
        classe = next(c for c in TbClasse.objects.all()
                       if (views._classe_spellcasting_info(c, 1) or {}).get('prepara') == 'conhecidas')
        p = self._character(classe=classe.slug, username='known')
        magia = TbMagia.objects.filter(nivel=0).first() or TbMagia.objects.first()
        row = TbPersonagemMagia.objects.create(
            id_personagem=p, id_magia=magia, nivel=magia.nivel,
            nome=magia.nome, preparada=True, origem=classe.nome)
        self.client.force_login(p.dono)
        response = self.client.post(reverse('personagem_toggle_magia', args=[p.pk, row.pk]))
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db()
        self.assertTrue(row.preparada)
