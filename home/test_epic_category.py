from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, SimpleTestCase

from home.admin import TbItemMundanoAdmin
from home.epic_talents import is_epic_talent, talent_category
from home.models import TbItemMundano, TbTalento
from home.views import _talent_payload, talentos_view
from home import picks


class EpicCategoryTests(SimpleTestCase):
    def test_explicit_category_and_exact_legacy_labels(self):
        for tipo, labels, expected in [
            ("epico", None, True), ("geral", "social, EPICO , suporte", True),
            ("geral", "epico-extra", False), ("geral", "nao-epico", False),
            ("geral", "epic", False), ("geral", None, False), ("origem", "epico", False),
        ]:
            with self.subTest(tipo=tipo, labels=labels):
                talent = SimpleNamespace(tipo=tipo, etiquetas_adicionais=labels,
                                         nome="Dadiva Epica", tags_json=[])
                self.assertEqual(is_epic_talent(talent), expected)
                self.assertEqual(talent_category(tipo, labels) == "epico", expected)
        self.assertTrue(is_epic_talent(SimpleNamespace(etiquetas_adicionais="epico")))
        self.assertEqual(talent_category("origem", "epico"), "origem")

    def test_model_form_and_payload_accept_epic_without_mechanical_tags(self):
        field = TbTalento._meta.get_field("tipo")
        field.validate("epico", TbTalento())
        self.assertEqual([key for key, _ in field.choices], ["origem", "geral", "epico"])
        for tipo, labels in [("epico", None), ("geral", " EPICO ")]:
            talent = TbTalento(tipo=tipo, etiquetas_adicionais=labels, nome="Qualquer")
            payload = _talent_payload(talent)
            self.assertEqual(payload["tipo_key"], "epico")
            self.assertEqual(payload["tipo"], dict(field.choices)["epico"])
            self.assertEqual(payload["tags_json"], [])
            self.assertEqual(talent.tipo, tipo)

    def test_public_documents_expose_category_and_choices(self):
        request = RequestFactory().get("/jogador/talentos/")
        request.user = SimpleNamespace(is_staff=False)
        documents = [{"Tipo": "geral", "EtiquetasAdicionais": "epico"},
                     {"Tipo": "epico"}, {"Tipo": "origem"}]
        with patch("home.views._site_docs", return_value=documents), patch(
            "home.views.render", side_effect=lambda request, template, context: context
        ):
            context = talentos_view.__wrapped__(request)
        self.assertEqual([t["tipo_key"] for t in context["json_talentos"]],
                         ["epico", "epico", "origem"])
        self.assertIn("epico", dict(context["talent_tipo_choices"]))


class MundaneAdminSearchTests(SimpleTestCase):
    def test_search_compiles_without_nonexistent_field_or_sql_execution(self):
        model_admin = TbItemMundanoAdmin(TbItemMundano, AdminSite())
        self.assertEqual(model_admin.search_fields, ("nome", "slug", "descricao_markdown"))
        for text in ("100", "espada", "espada longa"):
            query, _ = model_admin.get_search_results(
                RequestFactory().get("/admin/"), TbItemMundano.objects.all(), text
            )
            sql, params = query.query.sql_with_params()
            self.assertTrue(sql)
            self.assertTrue(params)
            self.assertNotIn("NomeIngles", sql)


class EpicPickCategoryTests(SimpleTestCase):
    def test_explicit_epic_pick_and_default_pools_preserve_categories(self):
        rows = [SimpleNamespace(id_talento=i, nome=f"Fonte {i}", slug=f"fonte-{i}",
                                tipo=tipo, etiquetas_adicionais=labels,
                                descricao="", pre_requisito="")
                for i, (tipo, labels) in enumerate([
                    ("origem", None), ("geral", None), ("epico", None), ("geral", "epico")])]
        with patch.object(TbTalento.objects, "all", return_value=rows):
            for text, expected in [("pick:talento:1(tipo:epico)", [2, 3]),
                                   ("pick:talento:1(tipo:geral)", [1]),
                                   ("pick:talento:1(tipo:origem)", [0]),
                                   ("pick:talento:1", [0, 1]),
                                   ("pick:talento:1(tipo:unknown)", []),
                                   ("pick:talento:1(tipo:epico, tipo:origem)", [])]:
                with self.subTest(text=text):
                    result = picks._talento_universe({"tag_text": text})
                    self.assertEqual([item["id"] for item in result], expected)
                    if expected == [2, 3]:
                        self.assertEqual([item["tipo"] for item in result], ["epico", "epico"])

    def test_explicit_epic_pick_keeps_category_when_persisted(self):
        from home.models import TbPersonagemEscolha, TbPersonagemTalento
        talent = TbTalento(pk=12, tipo="epico", nome="Qualquer", slug="qualquer")
        with patch.object(TbTalento.objects, "filter") as catalog, patch.object(
            TbPersonagemEscolha.objects, "update_or_create"
        ), patch.object(TbPersonagemTalento.objects, "get_or_create") as grant:
            catalog.return_value.first.return_value = talent
            group = {"universo": [{"id": 12, "slug": "qualquer", "nome": "Qualquer",
                                    "tipo": "epico"}]}
            picks._talento_persist(SimpleNamespace(nivel=20), group, ["qualquer"])
        self.assertEqual(grant.call_args.kwargs["defaults"]["categoria"], "epico")


class EpicCategoryMigrationTests(SimpleTestCase):
    def setUp(self):
        self.migration = import_module("home.migrations.0161_tbtalento_epic_category")

    def run_migration(self, function, rows):
        manager = Mock()

        def filtered(**criteria):
            selected = [row for row in rows if all(row[key] == value
                        for key, value in criteria.items())]
            query = Mock()
            query.values_list.return_value.iterator.side_effect = lambda: iter(
                [(row["pk"], row["etiquetas_adicionais"]) for row in selected]
            )
            query.update.side_effect = lambda **values: [row.update(values) for row in selected]
            return query

        manager.filter.side_effect = filtered
        objects = Mock()
        objects.using.return_value = manager
        apps = Mock()
        apps.get_model.return_value.objects = objects
        function(apps, SimpleNamespace(connection=SimpleNamespace(alias="isolated")))
        apps.get_model.assert_called_once_with("home", "TbTalento")
        objects.using.assert_called_once_with("isolated")

    def test_forward_is_exact_idempotent_and_preserves_rows_and_relations(self):
        rows = [dict(pk=i, tipo=tipo, etiquetas_adicionais=labels, relations=[i + 100],
                     tags_json=["unchanged"], nome="Qualquer")
                for i, (tipo, labels) in enumerate([
                    ("geral", "social, EPICO ,suporte"), ("geral", "epico-extra"),
                    ("geral", None), ("origem", "epico"), ("epico", None),
                    ("geral", "nao-epico"), ("geral", "epico"),
                ])]
        before = [row.copy() for row in rows]
        identities = [id(row) for row in rows]
        self.run_migration(self.migration.forwards, rows)
        self.run_migration(self.migration.forwards, rows)
        self.assertEqual([row["tipo"] for row in rows],
                         ["epico", "geral", "geral", "origem", "epico", "geral", "epico"])
        self.assertEqual([id(row) for row in rows], identities)
        for old, new in zip(before, rows):
            self.assertEqual({k: v for k, v in old.items() if k != "tipo"},
                             {k: v for k, v in new.items() if k != "tipo"})

    def test_reverse_preserves_legacy_and_new_epics_and_can_reapply(self):
        rows = [dict(pk=i, tipo="epico", etiquetas_adicionais=labels)
                for i, labels in enumerate(["social, EPICO ", None, "suporte", "epico-extra"])]
        self.run_migration(self.migration.backwards, rows)
        self.run_migration(self.migration.backwards, rows)
        self.assertEqual([row["etiquetas_adicionais"] for row in rows],
                         ["social, EPICO ", "epico", "suporte,epico", "epico-extra,epico"])
        self.assertTrue(all(row["tipo"] == "geral" for row in rows))
        self.run_migration(self.migration.forwards, rows)
        self.assertTrue(all(row["tipo"] == "epico" for row in rows))

    def test_dependency_and_field_match_model(self):
        migration = self.migration.Migration
        self.assertEqual(migration.dependencies, [("home", "0160_tbfeitolenda")])
        field = migration.operations[0].field
        self.assertEqual(field.deconstruct()[1:], TbTalento._meta.get_field("tipo").deconstruct()[1:])
        self.assertIs(migration.operations[1].reverse_code, self.migration.backwards)
