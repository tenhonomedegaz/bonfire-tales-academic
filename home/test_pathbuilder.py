import json

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

    def test_start_pages_require_login_and_render_catalog(self):
        self.client.logout()
        response = self.client.get(reverse("pathbuilder"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(reverse("pathbuilder_laboratorio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pathbuilder")
        self.assertContains(response, "pb-catalogs")

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
        build = {
            "modo": "sandbox",
            "classes": [{"slug": "mago", "nivel": 2, "subclasse": ""}],
            "atributos_bonus": {},
            "escolhas": {},
            "talentos": [],
            "itens": [],
            "magias": [],
        }
        before = TbPersonagemEscolha.objects.count()
        first = self._post_preview(payload, build)
        self.assertEqual(first.status_code, 200, first.content)
        group = next(
            row for row in first.json()["build"]["escolhas_grupos"]
            if row["label"] == "Teste Pathbuilder"
        )
        self.assertEqual(group["pendentes"], 1)
        self.assertEqual(group["opcoes"][0]["valor"], option.slug)

        build["escolhas"] = {group["key"]: [option.slug]}
        second = self._post_preview(payload, build)
        self.assertEqual(second.status_code, 200, second.content)
        resolved = next(
            row for row in second.json()["build"]["escolhas_grupos"]
            if row["key"] == group["key"]
        )
        self.assertEqual(resolved["pendentes"], 0)
        self.assertEqual(resolved["selecionadas"], [option.slug])
        self.assertEqual(TbPersonagemEscolha.objects.count(), before)

    def test_modo_regras_e_conjuracao_usam_estado_derivado(self):
        payload = self._payload("mago")
        build = {
            "modo": "regras",
            "classes": [{"slug": "mago", "nivel": 1, "subclasse": ""}],
            "atributos_bonus": {},
            "escolhas": {},
            "talentos": [],
            "itens": [],
            "magias": [],
        }
        response = self._post_preview(payload, build)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["build"]
        self.assertEqual(result["validacao"]["modo"], "regras")
        self.assertFalse(result["validacao"]["valida"])
        self.assertTrue(result["validacao"]["problemas"])
        self.assertTrue(result["conjuracao"]["spellcasters"])
