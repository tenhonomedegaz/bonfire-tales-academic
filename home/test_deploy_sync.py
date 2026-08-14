# -*- coding: utf-8 -*-
import json

from django.apps import apps
from django.contrib.auth.models import User
from django.core import serializers
from django.test import TestCase

from home import deploy_sync
from home.models import TbBestiario, TbRegiao


class DeploySyncContractTests(TestCase):
    def test_all_managed_home_models_have_an_explicit_policy(self):
        classified = set(
            deploy_sync.CONTENT_MODELS
            + deploy_sync.MEMORY_MODELS
            + deploy_sync.PRODUCTION_PRESERVED_MODELS
        )
        unclassified = sorted(
            model.__name__
            for model in apps.get_app_config("home").get_models()
            if model._meta.managed and model.__name__ not in classified
        )
        self.assertEqual(unclassified, [])

    def test_adventure_ledger_is_memory_and_world_is_production_owned(self):
        self.assertIn("TbPersonagemAventura", deploy_sync.MEMORY_MODELS)
        for name in (
            "TbMapLayer", "TbRegiao", "TbTerritorio", "TbOrganizacao",
            "TbMapMarker", "TbMapDesenho",
        ):
            self.assertIn(name, deploy_sync.PRODUCTION_PRESERVED_MODELS)
            self.assertNotIn(name, deploy_sync.CONTENT_MODELS)

    def test_official_bestiary_replace_preserves_community_rows(self):
        author = User.objects.create_user(username="autor-bestiario")
        community = TbBestiario.objects.create(
            nome="Criatura Comunitária",
            slug="criatura-comunitaria-sync",
            comunidade=True,
            autor=author,
            descricao_markdown="Não pode mudar.",
        )
        community_pk = community.pk
        TbBestiario.objects.create(
            nome="Oficial Obsoleta",
            slug="oficial-obsoleta-sync",
        )
        source = TbBestiario.objects.create(
            nome="Oficial Antes",
            slug="oficial-atual-sync",
            descricao_markdown="Versão da produção.",
        )
        source_pk = source.pk
        fixture = json.loads(serializers.serialize("json", [source]))
        fixture[0]["pk"] = 999999
        fixture[0]["fields"]["nome"] = "Oficial Atual"
        fixture[0]["fields"]["descricao_markdown"] = "Versão da dev."
        fixture_text = json.dumps(fixture)

        report = deploy_sync.sincronizar_conteudo(fixture_text)

        community.refresh_from_db()
        self.assertEqual(community.pk, community_pk)
        self.assertEqual(community.descricao_markdown, "Não pode mudar.")
        self.assertTrue(report["comunidade_ok"])
        self.assertFalse(
            TbBestiario.objects.filter(slug="oficial-obsoleta-sync").exists()
        )
        self.assertEqual(
            TbBestiario.objects.get(slug="oficial-atual-sync").descricao_markdown,
            "Versão da dev.",
        )
        self.assertEqual(
            TbBestiario.objects.get(slug="oficial-atual-sync").pk,
            source_pk,
        )

    def test_community_rows_are_rejected_from_merge_fixture(self):
        author = User.objects.create_user(username="autor-fixture-invalido")
        community = TbBestiario.objects.create(
            nome="Comunidade no Fixture",
            slug="comunidade-no-fixture",
            comunidade=True,
            autor=author,
        )
        fixture_text = serializers.serialize("json", [community])

        with self.assertRaisesRegex(ValueError, "comunitário"):
            deploy_sync.sincronizar_conteudo(fixture_text)

        self.assertTrue(
            TbBestiario.objects.filter(slug="comunidade-no-fixture").exists()
        )

    def test_world_records_in_fixture_are_ignored(self):
        production = TbRegiao.objects.create(
            nome="Região da Produção",
            slug="regiao-da-producao-sync",
            lore_markdown="Lore viva da produção.",
        )
        source = TbRegiao.objects.create(
            nome="Região da Dev",
            slug="regiao-da-dev-sync",
            lore_markdown="Não deve entrar.",
        )
        fixture_text = serializers.serialize("json", [source])
        source.delete()

        report = deploy_sync.sincronizar_conteudo(fixture_text)

        production.refresh_from_db()
        self.assertEqual(production.lore_markdown, "Lore viva da produção.")
        self.assertFalse(TbRegiao.objects.filter(slug="regiao-da-dev-sync").exists())
        self.assertTrue(report["prod_preservada_ok"])
