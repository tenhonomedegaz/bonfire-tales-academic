# -*- coding: utf-8 -*-
import json
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.core import serializers
from django.core.management import call_command
from django.test import TestCase

from home import deploy_sync
from home.models import (
    CosmeticCheckoutOffer,
    TbBestiario,
    TbCosmetico,
    TbItemMagico,
    TbPersonagem,
    TbPersonagemItem,
    TbPersonagemMagia,
    TbRegiao,
    TbMagia,
    TbRegra,
    TbClasse,
    TbSubclasse,
)


class DeploySyncContractTests(TestCase):
    def test_bestiary_only_fixture_preserves_other_replace_tables_and_pk(self):
        rule = TbRegra.objects.create(
            slug='regra-seletiva-sync', nome='Regra preservada', categoria='core')
        creature = TbBestiario.objects.create(
            slug='demonio-menor-seletivo', nome='Demônio Menor',
            statblock_json={'name': 'Demônio Menor'})
        fixture = json.loads(serializers.serialize('json', [creature]))
        fixture[0]['fields']['statblock_json']['selection_note'] = 'Escolha a espécie concreta.'

        report = deploy_sync.sincronizar_conteudo(json.dumps(fixture))

        creature.refresh_from_db()
        rule.refresh_from_db()
        self.assertEqual(creature.pk, fixture[0]['pk'])
        self.assertEqual(creature.statblock_json['selection_note'], 'Escolha a espécie concreta.')
        self.assertEqual(rule.nome, 'Regra preservada')
        self.assertTrue(TbRegra.objects.filter(pk=rule.pk).exists())
        self.assertIn(('TbRegra', 'modelo ausente no fixture; tabela preservada'),
                      report['pass2_skipped'])

    def test_fixture_pk_collision_preserves_dev_only_subclass_and_cosmetic(self):
        hunter = TbClasse.objects.create(nome='Caçador', slug='cacador-sync-only')
        extra_subclass = TbSubclasse.objects.create(
            id_classe=hunter, nome='Ordem local', slug='ordem-local-sync')
        extra_cosmetic = TbCosmetico.objects.create(
            nome='Cosmético local', slug='cosmetico-local-sync', tipo='badge')
        fixture_subclass = TbSubclasse(
            id_subclasse=extra_subclass.pk, id_classe=hunter,
            nome='Ordem do fixture', slug='ordem-fixture-sync')
        fixture_cosmetic = TbCosmetico(
            pk=extra_cosmetic.pk, nome='Cosmético do fixture',
            slug='cosmetico-fixture-sync', tipo='badge')
        fixture = serializers.serialize('json', [fixture_subclass, fixture_cosmetic])

        with patch.object(deploy_sync, '_load_content_deletions', return_value={}):
            report = deploy_sync.sincronizar_conteudo(fixture)

        self.assertEqual(TbSubclasse.objects.get(pk=extra_subclass.pk).slug,
                         'ordem-local-sync')
        self.assertEqual(TbCosmetico.objects.get(pk=extra_cosmetic.pk).slug,
                         'cosmetico-local-sync')
        self.assertNotEqual(TbSubclasse.objects.get(slug='ordem-fixture-sync').pk,
                            extra_subclass.pk)
        self.assertNotEqual(TbCosmetico.objects.get(slug='cosmetico-fixture-sync').pk,
                            extra_cosmetic.pk)
        self.assertTrue(report['mem_ok'])

    def test_dry_run_reports_live_tombstone_references_without_deleting(self):
        slug = 'sacrificio-de-sangue'
        with patch.object(deploy_sync, '_load_content_deletions', return_value={'TbMagia': [slug]}):
            self.assertEqual(deploy_sync.inspect_content_deletions()[0][2], 'absent')
            spell = TbMagia.objects.create(nome='Sacrifício de Sangue', slug=slug)
            self.assertEqual(deploy_sync.inspect_content_deletions()[0][2], 'would_delete')
            with self.assertRaisesRegex(ValueError, 'autorização operacional'):
                deploy_sync.sincronizar_conteudo('[]')
            self.assertTrue(TbMagia.objects.filter(pk=spell.pk).exists())
            owner = User.objects.create_user(username='tombstone-preflight')
            person = TbPersonagem.objects.create(dono=owner, nome='Preservar magia')
            acquired = TbPersonagemMagia.objects.create(
                id_personagem=person, id_magia=spell, nome=spell.nome,
                origem='Caçador', preparada=True)
            output = StringIO()
            call_command('sync_conteudo', dry_run=True, stdout=output)
            self.assertIn('TbMagia.sacrificio-de-sangue: blocked', output.getvalue())
            self.assertIn('TbPersonagemMagia.id_magia=1', output.getvalue())
            self.assertTrue(TbMagia.objects.filter(pk=spell.pk).exists())
            self.assertTrue(TbPersonagemMagia.objects.filter(pk=acquired.pk).exists())

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
        self.assertIn("SocialCreditRedemption", deploy_sync.MEMORY_MODELS)
        for name in (
            "TbMapLayer", "TbRegiao", "TbTerritorio", "TbOrganizacao",
            "TbMapMarker", "TbMapDesenho",
        ):
            self.assertIn(name, deploy_sync.PRODUCTION_PRESERVED_MODELS)
            self.assertNotIn(name, deploy_sync.CONTENT_MODELS)

    def test_sync_ignores_local_checkout_offer_api_key_and_audit_fixture(self):
        cosmetic = TbCosmetico.objects.create(
            slug='sync-local-offer', nome='Oferta local', tipo='badge', origem='conquista')
        offer = CosmeticCheckoutOffer.objects.create(
            cosmetico=cosmetic, amount=Decimal('12.00'), active=False)
        Key = apps.get_model('home', 'ManagedApiKey')
        Audit = apps.get_model('home', 'DbAccessAudit')
        key = Key.objects.create(
            name='Local key', prefix='local-sync-test', secret_hash='a' * 64,
            scopes=['read'])
        audit = Audit.objects.create(api_key=key, action='read', status_code=200)
        fixture = json.loads(serializers.serialize('json', [offer, key, audit]))
        for row in fixture:
            if row['model'] == 'home.cosmeticcheckoutoffer':
                row['fields']['amount'] = '999.00'
                row['fields']['active'] = True
            elif row['model'] == 'home.managedapikey':
                row['fields']['scopes'] = ['write']
                row['fields']['secret_hash'] = 'b' * 64
            elif row['model'] == 'home.dbaccessaudit':
                row['fields']['status_code'] = 500
        report = deploy_sync.sincronizar_conteudo(json.dumps(fixture))
        offer.refresh_from_db()
        key.refresh_from_db()
        audit.refresh_from_db()
        self.assertEqual(offer.amount, Decimal('12.00'))
        self.assertFalse(offer.active)
        self.assertEqual(key.scopes, ['read'])
        self.assertEqual(key.secret_hash, 'a' * 64)
        self.assertEqual(audit.status_code, 200)
        self.assertTrue(report['mem_ok'])
        self.assertTrue(report['prod_preservada_ok'])
        self.assertIn('TbClassPublication', deploy_sync.PRODUCTION_PRESERVED_MODELS)
        self.assertIn('SocialCreditHistoricalCampaign', deploy_sync.MEMORY_MODELS)

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

    def test_slug_rename_updates_catalog_and_preserves_inventory_fk(self):
        user = User.objects.create_user(username="inventario-rename-sync")
        personagem = TbPersonagem.objects.create(dono=user, nome="Heroi do Rename")
        production_item = TbItemMagico.objects.create(
            nome="Tiara do Intelecto",
            nome_ingles="Headband of Intellect",
            slug="Tiara-do-Intelecto",
            tags_json=["attr:str_score:=max(int_score,19)"],
        )
        production_pk = production_item.pk
        inventory = TbPersonagemItem.objects.create(
            id_personagem=personagem,
            id_item_magico=production_item,
            nome=production_item.nome,
        )
        source = TbItemMagico.objects.create(
            nome="Tiara do Intelecto",
            nome_ingles="Headband of Intellect",
            slug="tiara-do-intelecto",
            tags_json=["attr:int_score:=max(int_score,19)"],
        )
        fixture_text = serializers.serialize("json", [source])
        source.delete()

        report = deploy_sync.sincronizar_conteudo(fixture_text)

        canonical = TbItemMagico.objects.get(slug="tiara-do-intelecto")
        inventory.refresh_from_db()
        self.assertEqual(canonical.pk, production_pk)
        self.assertEqual(inventory.id_item_magico_id, production_pk)
        self.assertEqual(
            canonical.tags_json,
            ["attr:int_score:=max(int_score,19)"],
        )
        self.assertFalse(
            TbItemMagico.objects.filter(slug="Tiara-do-Intelecto").exists()
        )
        self.assertIn(
            (
                "TbItemMagico", "Tiara-do-Intelecto",
                "tiara-do-intelecto", production_pk,
            ),
            report["renames"],
        )
