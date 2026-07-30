import json
import os
import re

from django.urls import reverse

from home.models import (
    TbClasse,
    TbClassehabilidade,
    TbItemMagico,
    TbItemMundano,
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
                       'pb-choice-search', 'pb-muted'):
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
