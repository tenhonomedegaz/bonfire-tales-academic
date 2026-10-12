import json
import os
import re

from django.urls import reverse

from home.models import (
    TbClasse,
    TbClassehabilidade,
    TbItemMagico,
    TbItemMundano,
    TbEssencia,
    TbLinhagem,
    TbMagia,
    TbPersonagem,
    TbPersonagemAtributoBonus,
    TbPersonagemClasse,
    TbPersonagemEscolha,
    TbPersonagemItem,
    TbPersonagemMagia,
    TbPersonagemTalento,
    TbSubclasse,
    TbTalento,
    TbOpcaojogo,
    TbRaca,
    TbTracoracial,
)
from home.test_criador import _CriadorBase

_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
_JS = os.path.join(_STATIC, 'js', 'pathbuilder.js')
_CSS = os.path.join(_STATIC, 'css', 'pages', 'pathbuilder.css')


def _texto(caminho):
    with open(caminho, encoding='utf-8') as fh:
        return fh.read()


class PathbuilderContratoClienteTests(_CriadorBase):
    """Sem navegador no CI, o que quebra a pagina em silencio e o contrato JS x template:
    um `byId('pb-x')` sem o `id` correspondente devolve null e o laboratorio morre no
    primeiro render. Estes testes amarram os dois lados."""

    def setUp(self):
        self.user = self._novo_usuario("pathbuilder-contrato")
        self.client.force_login(self.user)

    def test_todo_id_procurado_pelo_js_existe_no_template(self):
        html = self.client.get(reverse("pathbuilder_laboratorio")).content.decode("utf-8")
        js = _texto(_JS)
        ids = sorted(set(re.findall(r"byId\('([^']+)'\)", js)))
        self.assertGreaterEqual(len(ids), 12, ids)
        faltando = [i for i in ids if ('id="%s"' % i) not in html]
        self.assertEqual(faltando, [], "ids que o JS busca e o template nao tem: %s" % faltando)

    def test_ganchos_de_dados_do_js_existem_no_template(self):
        html = self.client.get(reverse("pathbuilder_laboratorio")).content.decode("utf-8")
        for gancho in ('data-step-tab', 'data-step=', 'data-build-tab', 'data-build-mode',
                       'data-item-kind', 'data-picker=', 'data-picker-search',
                       'data-picker-list', 'data-step-prev', 'data-step-next'):
            self.assertIn(gancho, html, gancho)

    def test_classes_emitidas_pelo_js_estao_estilizadas(self):
        """Nenhum cartao do laboratorio sai sem CSS (era o cheiro de 'CSS genérico de IA':
        markup novo no JS e folha de estilo desatualizada)."""
        css = _texto(_CSS)
        for classe in ('pb-opt', 'pb-opt-pick', 'pb-opt-mark', 'pb-opt-main', 'pb-opt-name',
                       'pb-opt-meta', 'pb-opt-more', 'pb-opt-desc', 'pb-opt-group',
                       'pb-opt-lines', 'pb-opts-inline', 'pb-subclass', 'pb-row',
                       'pb-row-head', 'pb-row-name', 'pb-row-note', 'pb-line',
                       'pb-line-name', 'pb-line-tools', 'pb-stepper-num', 'pb-attr',
                       'pb-attr-sig', 'pb-attr-final', 'pb-base-cell', 'pb-check', 'pb-x',
                       'pb-counter', 'pb-diff-cell', 'pb-diff-lbl', 'pb-sheet-error',
                       'pb-choice-search', 'pb-opt-control', 'pb-racial-select',
                       'pb-muted'):
            self.assertIn('.%s' % classe, css, classe)

    def test_o_laboratorio_nao_reimplementa_a_folha_no_css_nem_no_js(self):
        """A folha é a da ficha: o CSS/JS do laboratório não redeclara o vocabulário dela."""
        css = _texto(_CSS)
        js = _texto(_JS)
        for da_ficha in ('.attr-box', '.attr-stack', '.seal-num', '.hp-track',
                         '.feat-grid', '.line-row', '.ficha-panel {'):
            self.assertNotIn(da_ficha, css, da_ficha)
        # o JS injeta a folha pronta; não monta <table>/vitals/atributos por conta própria
        for markup in ('<table', 'pb-table', 'pb-vitals', 'pb-attrs"'):
            self.assertNotIn(markup, js, markup)


class PathbuilderTests(_CriadorBase):
    def setUp(self):
        self.user = self._novo_usuario("pathbuilder-user")
        self.client.force_login(self.user)

    def _post_preview(self, base, build):
        return self.client.post(
            reverse("pathbuilder_preview"),
            data=json.dumps({"base": base, "build": build}),
            content_type="application/json",
        )

    def _build(self, classe_slug, **overrides):
        build = {
            "modo": "sandbox",
            "classes": [{"slug": classe_slug, "nivel": 1, "subclasse": ""}],
            "atributos_bonus": {},
            "escolhas": {},
            "talentos": [],
            "talentos_raciais": [],
            "itens": [],
            "magias": [],
        }
        build.update(overrides)
        return build

    def test_start_pages_require_login_and_render_catalog(self):
        self.client.logout()
        response = self.client.get(reverse("pathbuilder"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(reverse("pathbuilder_laboratorio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pathbuilder")
        self.assertContains(response, "pb-catalogs")

    def test_q10_magia_incompativel_mantem_previa_e_impede_validacao(self):
        base = self._payload('mago')
        spell = TbMagia.objects.filter(nivel=9).first()
        before = TbPersonagem.objects.count()
        build = self._build('mago', modo='regras',
                            magias=[{'slug': spell.slug, 'preparada': True}])
        response = self._post_preview(base, build)
        self.assertEqual(response.status_code, 200)
        result = response.json()['build']
        self.assertFalse(result['validacao']['valida'])
        self.assertIn(spell.nome, ' '.join(result['validacao']['problemas']))
        self.assertIn(spell.nome, ' '.join(result['validacao']['magias']))
        self.assertTrue(any(row['nome'] == spell.nome for row in result['magias']))
        self.assertEqual(build['magias'][0]['slug'], spell.slug)
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_q10_magia_conhecida_nao_duplica_nem_bloqueia_revisao(self):
        base = self._payload('mago')
        build = self._build('mago', modo='regras',
                            magias=[{'slug': base['truques'][0], 'preparada': True}])
        result = self._post_preview(base, build).json()['build']
        for group in result['escolhas_grupos']:
            if group['pendentes']:
                build['escolhas'][group['key']] = [
                    row['valor'] for row in group['opcoes']
                    if not row.get('ja_proficiente')
                ][:group['pendentes']]
        result = self._post_preview(base, build).json()['build']
        self.assertTrue(result['validacao']['valida'], result['validacao']['problemas'])
        selected = TbMagia.objects.get(slug=base['truques'][0])
        self.assertEqual(sum(row['nome'] == selected.nome for row in result['magias']), 1)

    def test_laboratorio_usa_stepper_e_nao_tem_mais_os_selects_de_adicionar(self):
        """O fluxo velho era `busca -> <select> -> botao Adicionar` em cada secao.

        O redesenho usa o padrao do criador: stepper de etapas + cartao clicavel. Este
        teste amarra as duas pontas — o stepper existe e os selects sumiram."""
        response = self.client.get(reverse("pathbuilder_laboratorio"))
        html = response.content.decode("utf-8")
        for marker in ('id="pb-stepper"', 'data-step-tab="0"', 'data-step="0"',
                       'data-picker="talento"', 'data-picker-list', 'id="pb-folha"'):
            self.assertIn(marker, html, marker)
        for gone in ('id="pb-talent-select"', 'id="pb-item-select"', 'id="pb-spell-select"',
                     'id="pb-add-talent"', 'id="pb-add-item"', 'id="pb-add-spell"',
                     'data-detail-tab'):
            self.assertNotIn(gone, html, gone)
        # a previa e a ficha: o CSS da ficha vem inteiro, sem copia no pathbuilder.css
        self.assertIn("css/pages/ficha.css", html)

    def test_iniciar_valida_sem_criar_personagem(self):
        payload = self._payload("guerreiro")
        before = TbPersonagem.objects.count()
        response = self.client.post(
            reverse("pathbuilder_iniciar"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_fluxo_iniciar_laboratorio_preview(self):
        """O caminho que o jogador percorre: valida a base, abre o laboratorio no redirect
        que o servidor manda, e o primeiro preview ja devolve ficha."""
        payload = self._payload("guerreiro")
        iniciar = self.client.post(
            reverse("pathbuilder_iniciar"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(iniciar.status_code, 200, iniciar.content)
        destino = iniciar.json()["redirect"]
        self.assertEqual(destino, reverse("pathbuilder_laboratorio"))
        self.assertEqual(self.client.get(destino).status_code, 200)

        preview = self._post_preview(payload, self._build("guerreiro"))
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertIn("data-pb-folha", preview.json()["build"]["ficha_html"])

    def test_preview_echoes_request_id_in_success_and_validation_error(self):
        base = self._payload('guerreiro')
        request_id = 'build-A:42'
        for build, expected_status in ((self._build('guerreiro'), 200),
                                       ({'classes': []}, 400)):
            with self.subTest(expected_status=expected_status):
                response = self.client.post(
                    reverse('pathbuilder_preview'),
                    data=json.dumps({'base': base, 'build': build,
                                     'request_id': request_id}),
                    content_type='application/json')
                self.assertEqual(response.status_code, expected_status, response.content)
                self.assertEqual(response.json()['request_id'], request_id)
        invalid = self.client.post(
            reverse('pathbuilder_preview'),
            data=json.dumps({'base': base, 'build': self._build('guerreiro'),
                             'request_id': ['not-a-scalar']}),
            content_type='application/json')
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(invalid.json()['ok'])

    def test_laboratorio_rejeita_payload_malformado_sem_salvar_e_aceita_correcao(self):
        base = self._payload('guerreiro')
        valid_build = self._build('guerreiro')
        before = TbPersonagem.objects.count()
        requests = [
            (reverse('pathbuilder_iniciar'), []),
            (reverse('pathbuilder_preview'), []),
            (reverse('pathbuilder_preview'), {'base': [], 'build': valid_build}),
            (reverse('pathbuilder_preview'), {'base': base, 'build': []}),
            (reverse('pathbuilder_preview'), {'base': base, 'build': {
                **valid_build, 'classes': [valid_build['classes'][0], 7],
            }}),
        ]
        for url, payload in requests:
            with self.subTest(url=url, payload=payload):
                response = self.client.post(url, data=json.dumps(payload),
                                            content_type='application/json')
                self.assertEqual(response.status_code, 400, response.content)
                self.assertFalse(response.json()['ok'])
                self.assertTrue(response.json()['erros'])
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, valid_build)
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertIn('data-pb-folha', corrected.json()['build']['ficha_html'])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_rejeita_numeros_truncaveis_e_aceita_correcao(self):
        base = self._payload('guerreiro')
        valid_build = self._build('guerreiro')
        item = TbItemMundano.objects.first()
        self.assertIsNotNone(item)
        before = TbPersonagem.objects.count()
        invalid_builds = [
            (self._build('guerreiro', classes=[
                {'slug': 'guerreiro', 'nivel': 1.9, 'subclasse': ''},
            ]), 'Nivel de classe'),
            (self._build('guerreiro', classes=[
                {'slug': 'guerreiro', 'nivel': True, 'subclasse': ''},
            ]), 'Nivel de classe'),
            (self._build('guerreiro', atributos_bonus={'FOR': 2.5}), 'Bonus de FOR'),
            (self._build('guerreiro', itens=[
                {'tipo': 'mundano', 'slug': item.slug, 'qtd': 1.5},
            ]), 'Quantidade do item'),
        ]
        for build, label in invalid_builds:
            with self.subTest(label=label, build=build):
                response = self._post_preview(base, build)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn(label, ' '.join(response.json()['erros']))
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, valid_build)
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertIn('data-pb-folha', corrected.json()['build']['ficha_html'])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_rejeita_bonus_de_atributo_desconhecido_sem_perder_correcao(self):
        base = self._payload('guerreiro')
        before = TbPersonagem.objects.count()
        for bonus in ({'AGI': 2}, {'FOR': 1, 'AGI': 2}, None, []):
            with self.subTest(bonus=bonus):
                response = self._post_preview(base, self._build(
                    'guerreiro', atributos_bonus=bonus))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn('Bonus de atributos invalidos',
                              ' '.join(response.json()['erros']))
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, self._build(
            'guerreiro', atributos_bonus={'FOR': 1}))
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_rejeita_itens_malformados_sem_ativar_equipamento(self):
        base = self._payload('guerreiro')
        item = TbItemMundano.objects.first()
        self.assertIsNotNone(item)
        before = TbPersonagem.objects.count()
        row = {'tipo': 'mundano', 'slug': item.slug, 'qtd': 1}
        invalid = [None, [None], [{**row, 'tipo': []}],
                   [{**row, 'equipado': 'false'}],
                   [{**row, 'sintonizado': 'false'}],
                   [{**row, 'sintonizado': True}],
                   [{**row, 'slug': 123}]]
        for items in invalid:
            with self.subTest(items=items):
                response = self._post_preview(base, self._build('guerreiro', itens=items))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertFalse(response.json()['ok'])
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, self._build('guerreiro', itens=[
            {**row, 'equipado': False, 'sintonizado': False}]))
        self.assertEqual(corrected.status_code, 200, corrected.content)
        inventory = corrected.json()['build']['inventario']
        self.assertTrue(any(entry['nome'] == item.nome for entry in inventory))
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_devolve_o_markup_da_ficha_real(self):
        """A visualizacao do resultado E A FICHA: o preview devolve o HTML dos partials da
        aba Ficha (banner, atributos, selos de CA/PV, ataques, caracteristicas), nao um
        resumo em tabela generica."""
        payload = self._payload("guerreiro")
        response = self._post_preview(payload, self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 5, "subclasse": ""}],
        }))
        self.assertEqual(response.status_code, 200, response.content)
        html = response.json()["build"]["ficha_html"]

        # marcadores REAIS da folha (ficha.css / ficha_detail), nao inventados aqui
        for marker in ('data-pb-folha', 'class="ficha-header ficha-banner"', 'ficha-name',
                       'ficha-columns', 'attr-stack', 'attr-box', 'attr-score',
                       'data-ficha-ca', 'data-ficha-pv', 'seal seal-ca', 'hp-track',
                       'Testes de Resistência', 'Perícias', 'Ataques',
                       'Características &amp; Habilidades', 'feat-card', 'feat-head',
                       'Defesas &amp; Sentidos', 'ficha-feat-desc'):
            self.assertIn(marker, html, marker)

        # ... e a MESMA folha e a que a ficha salva usa: um partial so, zero drift
        self.assertIn("home/partials/_ficha_folha.html",
                      [t.name for t in response.templates])
        self.assertIn("home/partials/_ficha_banner.html",
                      [t.name for t in response.templates])

    def test_preview_da_ficha_e_somente_leitura(self):
        """Nada de acao de ficha salva dentro da previa: sem POST de recurso/descanso, sem
        atalho de aba, sem botoes do banner."""
        payload = self._payload("guerreiro")
        response = self._post_preview(payload, self._build("guerreiro"))
        html = response.json()["build"]["ficha_html"]
        for gone in ('personagem_usar_recurso', 'personagem_descansar', 'csrfmiddlewaretoken',
                     'data-tab-jump', 'banner-actions', 'data-notas-form',
                     'data-pers-form', 'Painel da staff'):
            self.assertNotIn(gone, html, gone)
        # e o selo de simulacao deixa claro que nada foi salvo
        self.assertIn("Simulação", html)
        self.assertIn("Nenhum personagem foi salvo", html)

    def test_ficha_salva_usa_os_mesmos_partials_da_previa(self):
        """Guarda de drift pelo outro lado: a aba Ficha renderiza os partials extraidos."""
        criar = self.client.post(reverse("criar_personagem"),
                                 data=json.dumps(self._payload("guerreiro")),
                                 content_type="application/json")
        self.assertEqual(criar.status_code, 200, criar.content)
        personagem = TbPersonagem.objects.filter(dono=self.user).order_by("-pk").first()
        self.assertIsNotNone(personagem)
        response = self.client.get(reverse("ficha_detail", args=[personagem.id_personagem]))
        self.assertEqual(response.status_code, 200)
        nomes = [t.name for t in response.templates]
        for partial in ("home/partials/_ficha_banner.html",
                        "home/partials/_ficha_folha.html",
                        "home/partials/_ficha_folha_defesas.html"):
            self.assertIn(partial, nomes, partial)
        # na ficha salva o que a previa esconde volta a aparecer
        html = response.content.decode("utf-8")
        self.assertIn("banner-actions", html)
        self.assertIn("data-tab-jump", html)

    def test_preview_expoe_orcamento_de_asi_para_a_ui_gastar(self):
        """O editor GASTA o orcamento em vez de reclamar depois: o servidor diz quantos
        slots de ASI existem, quantos foram para talento e quantos pontos sobram."""
        payload = self._payload("guerreiro")
        talento = TbTalento.objects.exclude(tipo__iexact="origem").first()
        build = self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
        })
        response = self._post_preview(payload, build)
        self.assertEqual(response.status_code, 200, response.content)
        orc = response.json()["build"]["orcamento"]
        self.assertGreaterEqual(orc["asi_slots"], 1)
        self.assertEqual(orc["asi_em_talento"], 0)
        self.assertEqual(orc["pontos_disponiveis"], orc["asi_slots"] * 2)
        self.assertEqual(orc["pontos_usados"], 0)
        self.assertEqual(orc["pontos_restantes"], orc["pontos_disponiveis"])

        # gastar 1 slot em talento tira 2 pontos do saldo
        build["talentos"] = [talento.slug]
        orc2 = self._post_preview(payload, build).json()["build"]["orcamento"]
        self.assertEqual(orc2["asi_em_talento"], 1)
        self.assertEqual(orc2["pontos_disponiveis"], orc["pontos_disponiveis"] - 2)

        # distribuir o que resta zera o saldo e a build fica valida pelas regras
        build["talentos"] = []
        build["modo"] = "regras"
        build["atributos_bonus"] = {"FOR": orc["pontos_disponiveis"]}
        result = self._post_preview(payload, build).json()["build"]
        self.assertEqual(result["orcamento"]["pontos_restantes"], 0)
        self.assertNotIn("distribuiu", " ".join(result["validacao"]["problemas"]))

    def test_guerreiro_asi_milestones_match_class_catalog_without_persistence(self):
        catalog = self.client.get(reverse('pathbuilder_laboratorio'))
        self.assertEqual(catalog.status_code, 200)
        fighter = next(row for row in catalog.context['catalogos']['classes']
                       if row['slug'] == 'guerreiro')
        self.assertEqual(fighter['asi_nome'], 'Aprimoramento de Atributo ou Talento')
        baseline = TbPersonagem.objects.count()
        base = self._payload('guerreiro')
        for level, expected_slots in ((1, 0), (4, 1), (6, 2), (8, 3),
                                      (12, 4), (14, 5), (16, 6), (19, 7)):
            with self.subTest(level=level):
                build = self._build('guerreiro', classes=[
                    {'slug': 'guerreiro', 'nivel': level, 'subclasse': ''},
                ])
                response = self._post_preview(base, build)
                self.assertEqual(response.status_code, 200)
                budget = response.json()['build']['orcamento']
                self.assertEqual(budget['asi_slots'], expected_slots)
                self.assertEqual(budget['pontos_disponiveis'], expected_slots * 2)
        self.assertEqual(TbPersonagem.objects.count(), baseline)

    def test_catalogo_asi_cobre_classes_e_subclasses_sem_criar_marcos(self):
        from home.pathbuilder import catalogos
        from home.views import _eh_feature_asi, _tag_levels

        rows = {row['slug']: row for row in catalogos()['classes']}
        self.assertEqual(set(rows), set(TbClasse.objects.values_list('slug', flat=True)))
        with_asi = 0
        for classe in TbClasse.objects.all():
            with self.subTest(classe=classe.slug):
                row = rows[classe.slug]
                levels = sorted(_tag_levels(classe.tags_json, 'asi-choices'))
                self.assertEqual(row['asi_niveis'], levels)
                if not levels:
                    self.assertFalse(row['asi_nome'])
                    continue
                with_asi += 1
                feature = TbClassehabilidade.objects.filter(
                    id_classe=classe, id_subclasse__isnull=True,
                    niveladquirido=levels[0], table_only=False,
                ).filter(nome__icontains='Atributo').first()
                self.assertIsNotNone(feature)
                self.assertTrue(_eh_feature_asi(feature.nome))
                self.assertEqual(row['asi_nome'], feature.nome)
                self.assertEqual(
                    {sub['slug'] for sub in row['subclasses']},
                    set(TbSubclasse.objects.filter(id_classe=classe).values_list('slug', flat=True)),
                )
        self.assertGreater(with_asi, 1)

    def test_primeiro_asi_de_cada_classe_com_subclasse_nao_duplica_orcamento(self):
        from home.pathbuilder import catalogos

        baseline = TbPersonagem.objects.count()
        for row in catalogos()['classes']:
            if 4 not in row['asi_niveis']:
                continue
            with self.subTest(classe=row['slug']):
                subclass = (row['subclasses'][0]['slug']
                            if row['subclasses'] and row['subclasse_nivel'] <= 4 else '')
                build = self._build(row['slug'], classes=[{
                    'slug': row['slug'], 'nivel': 4, 'subclasse': subclass,
                }])
                response = self._post_preview(self._payload(row['slug']), build)
                self.assertEqual(response.status_code, 200, response.content[:500])
                budget = response.json()['build']['orcamento']
                self.assertEqual(budget['asi_slots'], 1)
                self.assertEqual(budget['pontos_disponiveis'], 2)
        self.assertEqual(TbPersonagem.objects.count(), baseline)

    def test_subir_nivel_mostra_nome_asi_da_habilidade_da_classe(self):
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        criar = self._post_criar(self.user, self._payload('guerreiro'))
        self.assertEqual(criar.status_code, 200, criar.content)
        personagem = TbPersonagem.objects.get(pk=criar.json()['id'])
        TbPersonagemClasse.objects.filter(id_personagem=personagem).update(nivel=4)
        personagem.nivel = 4
        personagem.save(update_fields=['nivel'])

        habilidade = TbClassehabilidade.objects.get(
            id_classe__slug='guerreiro', id_subclasse__isnull=True,
            niveladquirido=4, table_only=False, nome__icontains='Atributo',
        )
        nome_original = habilidade.nome
        snapshot = CreatorPinnedCatalogTests.seal(self, habilidade.id_classe)
        habilidade.nome = 'Aumento de Atributo ou Talento'
        habilidade.save(update_fields=['nome'])
        response = self.client.get(reverse('personagem_subir_nivel', args=[personagem.pk]))
        self.assertEqual(response.status_code, 200, response.content[:500])
        self.assertGreater(response.context['pend']['asi_pendentes'], 0)
        self.assertEqual(response.context['asi_nome'], habilidade.nome)
        self.assertContains(response, '<h2 class="sn-step-title">Aumento de Atributo ou Talento</h2>', html=False)

        pc = personagem.classes.get(id_classe=habilidade.id_classe)
        pc.ruleset = snapshot
        pc.save(update_fields=['ruleset'])
        pinned = self.client.get(reverse('personagem_subir_nivel', args=[personagem.pk]))
        self.assertEqual(pinned.status_code, 200, pinned.content[:500])
        self.assertEqual(pinned.context['asi_nome'], nome_original)

    def test_detalhe_devolve_descricao_sob_demanda(self):
        """Cartao expansivel: a descricao nao vem no catalogo (seria 1 MB), vem aqui."""
        talento = TbTalento.objects.exclude(descricao="").first()
        magia = TbMagia.objects.exclude(descricao="").first()
        response = self.client.get(reverse("pathbuilder_detalhe"),
                                   {"tipo": "talento", "slug": talento.slug})
        self.assertEqual(response.status_code, 200, response.content)
        detalhe = response.json()["detalhe"]
        self.assertEqual(detalhe["nome"], talento.nome)
        self.assertTrue(detalhe["descricao"])

        response = self.client.get(reverse("pathbuilder_detalhe"),
                                   {"tipo": "magia", "slug": magia.slug})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["detalhe"]["linhas"])

        self.assertEqual(self.client.get(
            reverse("pathbuilder_detalhe"),
            {"tipo": "talento", "slug": "nao-existe-mesmo"}).status_code, 404)
        self.assertEqual(self.client.get(
            reverse("pathbuilder_detalhe"),
            {"tipo": "tabela_secreta", "slug": "x"}).status_code, 404)

    def test_catalogo_do_laboratorio_e_enxuto_e_tem_meta_para_o_cartao(self):
        from home.pathbuilder import catalogos

        cat = catalogos()
        self.assertTrue(cat["talentos"] and cat["magias"] and cat["itens_magicos"])
        for chave in ("talentos", "magias", "itens_mundanos", "itens_magicos"):
            linha = cat[chave][0]
            self.assertIn("grupo", linha, chave)   # cabecalho de grupo do picker
            self.assertIn("meta", linha, chave)    # subtitulo do cartao
            self.assertNotIn("descricao", linha, chave)  # texto so sob demanda
        self.assertTrue(cat["classes"][0]["subclasses"] is not None)
        self.assertTrue(all(row["grupo"].lower() == "geral" for row in cat["talentos"]))
        self.assertTrue(all(row["atributos"] for row in cat["talentos"]))

    def test_catalogo_de_magias_inclui_nome_ingles_sem_alterar_o_nome_exibido(self):
        from home.pathbuilder import catalogos

        magia = TbMagia.objects.first()
        magia.nome_ingles = "Example Spell"
        magia.save(update_fields=["nome_ingles"])
        row = next(row for row in catalogos()["magias"] if row["slug"] == magia.slug)
        self.assertEqual(row["nome"], magia.nome)
        self.assertEqual(row["nome_ingles"], "Example Spell")

    def test_talento_livre_aplica_seu_mais_um_no_atributo_escolhido(self):
        payload = self._payload("guerreiro")
        talento = TbTalento.objects.filter(tipo__iexact="geral").first()
        from home.views import _talento_attr_options
        atributo = _talento_attr_options(talento)[0]
        classes = [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}]
        base = self._post_preview(payload, self._build("guerreiro", classes=classes)).json()["build"]
        response = self._post_preview(payload, self._build("guerreiro", **{
            "classes": classes,
            "talentos": [{"slug": talento.slug, "atributo": atributo}],
        }))
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["build"]
        before = next(row["valor"] for row in base["atributos"] if row["sig"] == atributo)
        after = next(row["valor"] for row in result["atributos"] if row["sig"] == atributo)
        self.assertEqual(after, before + 1)
        self.assertNotIn("Escolha o atributo", " ".join(result["validacao"]["problemas"]))
        self.assertEqual(result["orcamento"]["asi_em_talento"], 1)
        removed = self._post_preview(payload, self._build("guerreiro", classes=classes))
        reverted = removed.json()["build"]
        self.assertEqual(next(row["valor"] for row in reverted["atributos"]
                              if row["sig"] == atributo), before)
        self.assertEqual(reverted["orcamento"]["asi_em_talento"], 0)
        invalid = self._post_preview(payload, self._build("guerreiro", **{
            "classes": classes,
            "talentos": [{"slug": talento.slug, "atributo": "INVALID"}],
        })).json()["build"]
        self.assertIn("nao pode aumentar", " ".join(invalid["validacao"]["problemas"]))
        self.assertEqual(next(row["valor"] for row in invalid["atributos"]
                              if row["sig"] == atributo), before)

    def test_talento_legado_sem_atributo_continua_editavel_mas_e_sinalizado(self):
        payload = self._payload("guerreiro")
        talento = TbTalento.objects.filter(tipo__iexact="geral").first()
        response = self._post_preview(payload, self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
            "talentos": [talento.slug],
        }))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("Escolha o atributo", " ".join(
            response.json()["build"]["validacao"]["problemas"]))

    def test_preview_sinaliza_payload_de_sessenta_pontos_para_quatro_em_ambos_os_modos(self):
        """Sandbox deriva a ficha, mas nunca considera valido burlar o orcamento de ASI."""
        payload = self._payload("guerreiro")
        base_build = self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 6, "subclasse": ""}],
            "atributos_bonus": {
                "FOR": 10, "DES": 10, "CON": 10,
                "INT": 10, "SAB": 10, "CAR": 10,
            },
        })
        before = TbPersonagem.objects.count()
        for modo in ("regras", "sandbox"):
            build = dict(base_build, modo=modo)
            response = self._post_preview(payload, build)
            self.assertEqual(response.status_code, 200, response.content)
            result = response.json()["build"]
            self.assertFalse(result["validacao"]["valida"])
            self.assertEqual(result["orcamento"]["pontos_usados"], 60)
            self.assertEqual(result["orcamento"]["pontos_disponiveis"], 4)
            self.assertIn("distribuiu 60", " ".join(result["validacao"]["problemas"]))
            self.assertEqual(TbPersonagem.objects.count(), before)

    def test_resiliente_repetido_nao_cria_duas_salvaguardas(self):
        """Duplicar o cartao no payload nao pode gastar dois slots nem abrir dois picks."""
        payload = self._payload("guerreiro")
        resiliente = TbTalento.objects.get(slug="resiliente")
        build = self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
            "talentos": [
                {"slug": resiliente.slug, "atributo": "DES"},
                {"slug": resiliente.slug, "atributo": "DES"},
            ],
        })
        first = self._post_preview(payload, build)
        self.assertEqual(first.status_code, 400, first.content)
        self.assertIn("repetido", first.json()["erros"][0])
        build["talentos"].pop()
        corrected = self._post_preview(payload, build)
        self.assertEqual(corrected.status_code, 200, corrected.content)
        first_build = corrected.json()["build"]
        self.assertEqual(first_build["orcamento"]["asi_em_talento"], 1)
        self.assertEqual(sum(row["nome"] == resiliente.nome
                             for row in first_build["features"]), 1)
        groups = [row for row in first_build["escolhas_grupos"]
                  if row["origem"] == resiliente.nome]
        self.assertEqual(len(groups), 1)

        # O unico pick concedido pelo talento aceita uma unica salvaguarda.
        group = groups[0]
        options = [row["valor"] for row in group["opcoes"]]
        self.assertGreaterEqual(len(options), 2)
        build["escolhas"] = {group["key"]: options[:2]}
        second = self._post_preview(payload, build)
        self.assertEqual(second.status_code, 400)
        self.assertIn("somente 1", second.json()["erros"][0])

    def test_talento_malformado_nao_e_descartado_da_previa(self):
        payload = self._payload("guerreiro")
        build = self._build("guerreiro", classes=[
            {"slug": "guerreiro", "nivel": 4, "subclasse": ""}])
        before = TbPersonagem.objects.count()
        for talents in (None, {}, [None], [True], [5], [""],
                        [{"slug": "resiliente", "atributo": True}]):
            with self.subTest(talents=talents):
                response = self._post_preview(payload, {**build, "talentos": talents})
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(TbPersonagem.objects.count(), before)
        legacy = self._post_preview(payload, {**build, "talentos": ["resiliente"]})
        self.assertEqual(legacy.status_code, 200, legacy.content)
        self.assertIn("Escolha o atributo", " ".join(
            legacy.json()["build"]["validacao"]["problemas"]))

    def test_subescolha_de_resiliente_fica_inerte_sem_talento(self):
        """Uma chave antiga nao concede salvaguarda sem a fonte que a declarou."""
        payload = self._payload("guerreiro")
        resiliente = TbTalento.objects.get(slug="resiliente")
        active = self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
            "talentos": [{"slug": resiliente.slug, "atributo": "DES"}],
        })
        first = self._post_preview(payload, active)
        self.assertEqual(first.status_code, 200, first.content)
        group = next(row for row in first.json()["build"]["escolhas_grupos"]
                     if row["origem"] == resiliente.nome)
        chosen = group["opcoes"][0]["valor"]
        active["escolhas"] = {group["key"]: [chosen]}

        resolved = self._post_preview(payload, active)
        self.assertEqual(resolved.status_code, 200, resolved.content)
        resolved_group = next(row for row in resolved.json()["build"]["escolhas_grupos"]
                              if row["key"] == group["key"])
        self.assertEqual([row["valor"] for row in resolved_group["resolvidas"]], [chosen])

        # A chave permanece no cliente, mas sem Resiliente nao existe grupo que a persista.
        removed = self._build("guerreiro", **{
            "classes": active["classes"],
            "escolhas": active["escolhas"],
        })
        without_talent = self._post_preview(payload, removed)
        self.assertEqual(without_talent.status_code, 200, without_talent.content)
        without_build = without_talent.json()["build"]
        self.assertFalse(any(row["origem"] == resiliente.nome
                             for row in without_build["escolhas_grupos"]))

        # O cliente limpa a chave ao retirar a fonte; recolocar exige nova escolha.
        restored = self._post_preview(payload, self._build("guerreiro", **{
            "classes": active["classes"],
            "talentos": [{"slug": resiliente.slug, "atributo": "DES"}],
        }))
        self.assertEqual(restored.status_code, 200, restored.content)
        restored_build = restored.json()["build"]
        restored_groups = [row for row in restored_build["escolhas_grupos"]
                           if row["origem"] == resiliente.nome]
        self.assertEqual(len(restored_groups), 1)
        self.assertEqual(restored_groups[0]["resolvidas"], [])
        self.assertEqual(restored_groups[0]["pendentes"], 1)

    def test_escolhas_malformadas_nao_sao_reduzidas_em_silencio(self):
        base = self._payload('guerreiro')
        build = self._build('guerreiro', classes=[
            {'slug': 'guerreiro', 'nivel': 4, 'subclasse': ''}],
            talentos=[{'slug': 'resiliente', 'atributo': 'DES'}])
        first = self._post_preview(base, build)
        self.assertEqual(first.status_code, 200, first.content)
        group = next(row for row in first.json()['build']['escolhas_grupos']
                     if row['origem'] == TbTalento.objects.get(slug='resiliente').nome)
        selected = group['opcoes'][0]['valor']
        before = TbPersonagem.objects.count()
        for choices in (None, [], {group['key']: 'invalido'},
                        {group['key']: [selected, selected]},
                        {group['key']: [selected, None]},
                        {group['key']: [True]}):
            with self.subTest(choices=choices):
                response = self._post_preview(base, {**build, 'escolhas': choices})
                self.assertEqual(response.status_code, 400, response.content)
                self.assertFalse(response.json()['ok'])
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, {**build, 'escolhas': {
            group['key']: [selected]}})
        self.assertEqual(corrected.status_code, 200, corrected.content)
        resolved = next(row for row in corrected.json()['build']['escolhas_grupos']
                        if row['key'] == group['key'])
        self.assertEqual([row['valor'] for row in resolved['resolvidas']], [selected])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_marcos_de_talento_racial_usam_o_resolvedor_do_levelup(self):
        payload = self._payload("guerreiro")
        classes = [{"slug": "guerreiro", "nivel": 17, "subclasse": ""}]
        first = self._post_preview(payload, self._build("guerreiro", classes=classes))
        self.assertEqual(first.status_code, 200, first.content)
        groups = first.json()["build"]["talentos_raciais_grupos"]
        self.assertTrue(groups, "a raca da fixture deve possuir marco racial acima do nivel 1")
        group = groups[0]
        choice = group["opcoes"][0]["nome"]
        second = self._post_preview(payload, self._build("guerreiro", **{
            "classes": classes,
            "talentos_raciais": [{"nivel": group["nivel"], "nome": choice}],
        }))
        self.assertEqual(second.status_code, 200, second.content)
        resolved = next(row for row in second.json()["build"]["talentos_raciais_grupos"]
                        if row["nivel"] == group["nivel"])
        self.assertEqual(resolved["selecionado"], choice)

    def test_talentos_raciais_ambiguos_nao_sao_descartados_silenciosamente(self):
        payload = self._payload("guerreiro")
        classes = [{"slug": "guerreiro", "nivel": 17, "subclasse": ""}]
        first = self._post_preview(payload, self._build("guerreiro", classes=classes))
        self.assertEqual(first.status_code, 200, first.content)
        group = first.json()["build"]["talentos_raciais_grupos"][0]
        choice = {"nivel": group["nivel"], "nome": group["opcoes"][0]["nome"]}
        before = TbPersonagem.objects.count()
        for rows in ([choice, dict(choice)], [None], None,
                     [{"nivel": group["nivel"], "nome": ""}]):
            with self.subTest(rows=rows):
                response = self._post_preview(payload, self._build(
                    "guerreiro", classes=classes, talentos_raciais=rows))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertFalse(response.json()["ok"])
                self.assertEqual(TbPersonagem.objects.count(), before)
        corrected = self._post_preview(payload, self._build(
            "guerreiro", classes=classes, talentos_raciais=[choice]))
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertEqual(corrected.json()["build"]["talentos_raciais_grupos"][0]["selecionado"],
                         choice["nome"])

    def test_talento_racial_obsoleto_permanece_visivel_para_correcao(self):
        payload = self._payload("guerreiro")
        classes = [{"slug": "guerreiro", "nivel": 17, "subclasse": ""}]
        first = self._post_preview(payload, self._build("guerreiro", classes=classes))
        self.assertEqual(first.status_code, 200, first.content)
        group = next(row for row in first.json()["build"]["talentos_raciais_grupos"]
                     if row["nivel"] >= 5)
        before = TbPersonagem.objects.count()
        stale = self._post_preview(payload, self._build("guerreiro", **{
            "classes": classes,
            "talentos_raciais": [{"nivel": group["nivel"], "nome": "Escolha obsoleta"}],
        }))
        self.assertEqual(stale.status_code, 200, stale.content)
        result = stale.json()["build"]
        stale_group = next(row for row in result["talentos_raciais_grupos"]
                           if row["nivel"] == group["nivel"])
        self.assertEqual(stale_group["selecionado"], "Escolha obsoleta")
        self.assertNotIn("Escolha obsoleta", [row["nome"] for row in stale_group["opcoes"]])
        self.assertFalse(result["validacao"]["valida"])
        self.assertTrue(any("Talento racial invalido" in issue
                            for issue in result["validacao"]["problemas"]))
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_marcos_raciais_5_a_17_concordam_com_criacao_laboratorio_e_ficha(self):
        from home import views

        expected_levels = [5, 9, 13, 17]
        classes = [{"slug": "guerreiro", "nivel": 17, "subclasse": ""}]
        variants = (
            ("anao-linhagem", "anao", {"linhagem_slug": "montanha"}),
            ("anao-essencia", "anao", {"essencia_slug": "draconica", "vertente": "Vermelho"}),
            ("elfo", "elfo", {}),
            ("orc", "orc", {}),
            ("humano", "humano", {}),
        )
        for label, race_slug, identity in variants:
            with self.subTest(origem=label):
                owner = self._novo_usuario("marcos-raciais-" + label)
                payload = self._payload("guerreiro", raca_slug=race_slug, **identity)
                if label == "anao-essencia":
                    payload.setdefault("escolhas_raca", {})["menus"] = [{
                        "tipo": "alento_elemental", "fonte": "Alento Elemental",
                        "valores": ["fogo"],
                    }]
                created = self._post_criar(owner, payload)
                self.assertTrue(created.json()["ok"], created.content)
                character = TbPersonagem.objects.get(pk=created.json()["id"])
                primary = character.classes.get(principal=True)
                primary.nivel = 17
                primary.save(update_fields=["nivel"])
                character.nivel = 17
                character.save(update_fields=["nivel", "atualizado_em"])
                levelup_groups = views._pendencias_talento_racial(character)
                self.assertEqual([row["nivel"] for row in levelup_groups], expected_levels)

                selections = []
                count_before_preview = TbPersonagem.objects.count()
                for level in expected_levels:
                    response = self._post_preview(payload, self._build("guerreiro", **{
                        "classes": classes, "talentos_raciais": selections,
                    }))
                    self.assertEqual(response.status_code, 200, response.content)
                    groups = response.json()["build"]["talentos_raciais_grupos"]
                    self.assertEqual([row["nivel"] for row in groups], expected_levels)
                    group = next(row for row in groups if row["nivel"] == level)
                    self.assertTrue(group["opcoes"], f"Sem escolha disponível no nível {level}")
                    selections.append({"nivel": level, "nome": group["opcoes"][0]["nome"]})

                completed = self._post_preview(payload, self._build("guerreiro", **{
                    "classes": classes, "talentos_raciais": selections,
                }))
                self.assertEqual(completed.status_code, 200, completed.content)
                result = completed.json()["build"]
                self.assertEqual(
                    [(row["nivel"], row["selecionado"])
                     for row in result["talentos_raciais_grupos"]],
                    [(row["nivel"], row["nome"]) for row in selections])
                self.assertFalse(any("Talento racial invalido" in issue
                                     for issue in result["validacao"]["problemas"]))
                self.assertEqual(TbPersonagem.objects.count(), count_before_preview)
                for selection in selections:
                    saved = self.client.post(
                        reverse("personagem_escolher_talento_racial", args=[character.pk]),
                        data={"nivel": selection["nivel"], "talento": selection["nome"]})
                    self.assertEqual(saved.status_code, 302)
                    self.assertEqual(character.talentos.filter(
                        categoria="racial", nivel=selection["nivel"],
                        nome=selection["nome"]).count(), 1)
                self.assertEqual(views._pendencias_talento_racial(character), [])

    def test_marcos_raciais_cobrem_todas_linhagens_e_essencias_do_catalogo(self):
        from home import views
        from django.db import transaction

        races = list(TbRaca.objects.order_by('slug'))
        lineages = list(TbLinhagem.objects.select_related('id_raca').order_by('id_linhagem'))
        essences = list(TbEssencia.objects.order_by('slug'))
        self.assertEqual(len(lineages), 16)
        self.assertEqual(len(essences), 4)
        variants = [
            (f'linhagem:{lineage.id_raca.slug}:{lineage.slug}', lineage.id_raca.slug,
             {'linhagem_slug': lineage.slug})
            for lineage in lineages
        ] + [
            (f'essencia:{race.slug}:{essence.slug}', race.slug,
             {'essencia_slug': essence.slug})
            for race in races if race.permite_essencia for essence in essences
        ]
        self.assertEqual(len(variants), 32)

        for index, (label, race_slug, identity) in enumerate(variants):
            with self.subTest(identity=label):
                owner = self._novo_usuario(f'matriz-racial-{index}')
                if identity.get('essencia_slug') == 'draconica':
                    identity = {**identity, 'vertente': 'Vermelho'}
                elif identity.get('essencia_slug') in ('elemental', 'vampirismo'):
                    essence = TbEssencia.objects.get(slug=identity['essencia_slug'])
                    identity = {**identity,
                                'vertente': views._essencia_subescolha(essence)['opcoes'][0]['slug']}
                payload = self._payload('guerreiro', raca_slug=race_slug, **identity)
                if identity.get('essencia_slug') == 'draconica':
                    payload.setdefault('escolhas_raca', {}).setdefault('menus', []).append({
                        'tipo': 'alento_elemental', 'fonte': 'Alento Elemental',
                        'valores': ['fogo'],
                    })
                if identity.get('essencia_slug') == 'nephilim':
                    essence = TbEssencia.objects.get(slug='nephilim')
                    sources = TbTracoracial.objects.filter(
                        id_essencia=essence, talento_racial=False, nivel_requisito__lte=1)
                    payload.setdefault('escolhas_raca', {}).setdefault('menus', []).extend({
                        'tipo': group['kind'], 'fonte': group['origem'],
                        'valores': [group['universo'][0]['slug']],
                    } for group in views._racial_menu_groups(sources))
                if (identity.get('linhagem_slug') == 'sálarin'
                        or identity.get('essencia_slug') == 'nephilim'):
                    resolved, errors = views._criador_resolver(payload)
                    self.assertFalse(errors, errors)
                    with transaction.atomic():
                        temporary = views._criador_persistir(owner, payload, resolved)
                        payload['magias_concedidas'] = [{
                            'fonte': group['fonte'], 'slot': group['slot'],
                            'magias': [group['opcoes'][0]['slug']],
                        } for group in temporary._criador_spell_groups]
                        transaction.set_rollback(True)
                created = self._post_criar(owner, payload)
                self.assertTrue(created.json().get('ok'), created.content)
                character = TbPersonagem.objects.get(pk=created.json()['id'])
                character.classes.filter(principal=True).update(nivel=17)
                character.nivel = 17
                character.save(update_fields=['nivel', 'atualizado_em'])
                groups = views._pendencias_talento_racial(character)
                self.assertEqual([group['nivel'] for group in groups], [5, 9, 13, 17])
                expected = [(group['nivel'], {option['nome'] for option in group['opcoes']})
                            for group in groups]
                self.assertTrue(all(options for _, options in expected), label)

                count_before = TbPersonagem.objects.count()
                preview = self._post_preview(payload, self._build(
                    'guerreiro', classes=[{'slug': 'guerreiro', 'nivel': 17, 'subclasse': ''}]))
                self.assertEqual(preview.status_code, 200, preview.content)
                actual = [(group['nivel'], {option['nome'] for option in group['opcoes']})
                          for group in preview.json()['build']['talentos_raciais_grupos']]
                self.assertEqual(actual, expected)
                self.assertEqual(TbPersonagem.objects.count(), count_before)

    def test_preview_deriva_niveis_subclasse_itens_talentos_e_magias_sem_persistir(self):
        payload = self._payload("guerreiro")
        classe = TbClasse.objects.get(slug="guerreiro")
        subclasse = TbSubclasse.objects.filter(id_classe=classe).first()
        talento = TbTalento.objects.exclude(tipo__iexact="origem").first()
        mundano = TbItemMundano.objects.first()
        magico = TbItemMagico.objects.first()
        magia = TbMagia.objects.first()
        self.assertIsNotNone(subclasse)
        self.assertIsNotNone(talento)
        self.assertIsNotNone(mundano)
        self.assertIsNotNone(magico)
        self.assertIsNotNone(magia)

        tracked_models = (
            TbPersonagem,
            TbPersonagemClasse,
            TbPersonagemAtributoBonus,
            TbPersonagemTalento,
            TbPersonagemItem,
            TbPersonagemMagia,
        )
        before = {model: model.objects.count() for model in tracked_models}
        build = {
            "classes": [{
                "slug": "guerreiro",
                "nivel": 5,
                "subclasse": subclasse.slug,
            }],
            "atributos_bonus": {"FOR": 2},
            "talentos": [talento.slug],
            "itens": [
                {"tipo": "mundano", "slug": mundano.slug, "qtd": 2, "equipado": True},
                {"tipo": "magico", "slug": magico.slug, "qtd": 1,
                 "equipado": True, "sintonizado": True},
            ],
            "magias": [{"slug": magia.slug, "preparada": True}],
        }

        response = self._post_preview(payload, build)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["build"]
        self.assertEqual(result["nivel"], 5)
        self.assertEqual(result["classes"][0]["subclasse"], subclasse.nome)
        self.assertEqual(
            next(row for row in result["atributos"] if row["sig"] == "FOR")["valor"],
            payload["scores"]["FOR"] + 2,
        )
        self.assertTrue(any(row["nome"] == talento.nome for row in result["features"]))
        self.assertTrue(any(row["nome"] == mundano.nome for row in result["inventario"]))
        self.assertTrue(any(row["nome"] == magia.nome for row in result["magias"]))
        # e tudo isso aparece na FOLHA, nao so no JSON
        html = result["ficha_html"]
        self.assertIn(subclasse.nome, html)
        self.assertIn(talento.nome, html)
        self.assertIn(mundano.nome, html)
        for model in tracked_models:
            self.assertEqual(model.objects.count(), before[model], model.__name__)

    def test_preview_rejeita_nivel_total_acima_de_vinte_sem_persistir(self):
        payload = self._payload("guerreiro")
        outra = TbClasse.objects.exclude(slug="guerreiro").first()
        before = TbPersonagem.objects.count()
        response = self._post_preview(payload, {
            "classes": [
                {"slug": "guerreiro", "nivel": 20, "subclasse": ""},
                {"slug": outra.slug, "nivel": 1, "subclasse": ""},
            ],
            "atributos_bonus": {},
            "talentos": [],
            "itens": [],
            "magias": [],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("20", response.json()["erros"][0])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_resolve_pick_novo_pelo_registry_sem_persistir(self):
        classe = TbClasse.objects.get(slug="mago")
        TbClassehabilidade.objects.create(
            id_classe=classe,
            nome="Escolha do Laboratorio",
            descricao="Escolha sintetica.",
            niveladquirido=2,
            tags_json=["pick:opcao:teste_pathbuilder:1"],
        )
        option = TbOpcaojogo.objects.create(
            nome="Opcao do Laboratorio",
            slug="opcao-pathbuilder",
            tipo="Teste Pathbuilder",
            descricao="Efeito sintetico.",
            tags_json=[],
        )
        payload = self._payload("mago")
        build = self._build("mago", **{
            "classes": [{"slug": "mago", "nivel": 2, "subclasse": ""}],
        })
        before = TbPersonagemEscolha.objects.count()
        first = self._post_preview(payload, build)
        self.assertEqual(first.status_code, 200, first.content)
        group = next(
            row for row in first.json()["build"]["escolhas_grupos"]
            if row["label"] == "Teste Pathbuilder"
        )
        self.assertEqual(group["pendentes"], 1)
        self.assertEqual(group["opcoes"][0]["valor"], option.slug)
        # o cartao da escolha mostra o efeito no lugar — a descricao viaja com a opcao
        self.assertEqual(group["opcoes"][0]["descricao"], "Efeito sintetico.")

        build["escolhas"] = {group["key"]: [option.slug]}
        second = self._post_preview(payload, build)
        self.assertEqual(second.status_code, 200, second.content)
        resolved = next(
            row for row in second.json()["build"]["escolhas_grupos"]
            if row["key"] == group["key"]
        )
        self.assertEqual(resolved["pendentes"], 0)
        self.assertEqual(resolved["selecionadas"], [option.slug])
        self.assertEqual([row["valor"] for row in resolved["resolvidas"]], [option.slug])
        self.assertEqual(TbPersonagemEscolha.objects.count(), before)

    def test_modo_regras_e_conjuracao_usam_estado_derivado(self):
        payload = self._payload("mago")
        build = self._build("mago", modo="regras")
        response = self._post_preview(payload, build)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["build"]
        self.assertEqual(result["validacao"]["modo"], "regras")
        self.assertFalse(result["validacao"]["valida"])
        self.assertTrue(result["validacao"]["problemas"])
        self.assertTrue(result["conjuracao"]["spellcasters"])
        # conjuracao aparece na folha (CD e ataque de magia), nao numa aba paralela
        self.assertIn("CD ", result["ficha_html"])
