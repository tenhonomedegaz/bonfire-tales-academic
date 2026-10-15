# -*- coding: utf-8 -*-
"""Regressão do console do admin (server_logs_view).

Cobre o guard que recusa restaurar, pelo painel "Restaurar backup" (upsert cru
por PK), um fixture que só tem modelos de CONTEÚDO (catálogo, com PKs do dev) —
ver `home/deploy_sync.py` (`CONTENT_MODELS`) e
`docs/agentes/relatorio_restore_20260715_013659.md`. Esse foi exatamente o erro
observado em produção em 16/07/2026: subiram um fixture só-de-catálogo no painel
errado ("Restaurar backup" em vez de "Merge de conteúdo") e a operação falhou com
IntegrityError de slug único, porque os PKs do dev e da produção desalinham.

Também cobre a regressão do comentário `{# ... #}` multi-linha quebrado em
home/templates/admin/base_site.html, que renderizava como texto literal no topo
de toda página do admin.
"""
import json
import time
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from home.admin import CONSOLE_UNLOCK_TTL_SECONDS
from home.db_access import ApiProblem
from home.db_access_models import DbAccessAudit
from home.models import TbRegiao, TbRegra, TbTerritorio


class RestoreBackupGuardTests(TestCase):
    """POST em /admin/server-logs/ com action=restore_backup."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin-console-teste",
            email="admin-console@example.com",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)
        # O console tem uma segunda trava de sessão (SERVER_LOGS_PASSWORD_HASH),
        # independente do login do admin — liberamos direto na sessão do client.
        session = self.client.session
        session["admin_console_authenticated_at"] = time.time()
        session.save()
        self.url = reverse("admin:server_logs")

    def _post_restore(self, payload):
        arquivo = SimpleUploadedFile(
            "fixture.json",
            json.dumps(payload).encode("utf-8"),
            content_type="application/json",
        )
        return self.client.post(
            self.url,
            {
                "action": "restore_backup",
                "confirmar": "RESTAURAR",
                "arquivo": arquivo,
            },
        )

    def _post_map_restore(self, payload, confirmation="RESTAURAR MAPA"):
        arquivo = SimpleUploadedFile(
            "mapa.json",
            json.dumps(payload).encode("utf-8"),
            content_type="application/json",
        )
        return self.client.post(
            self.url,
            {
                "action": "restore_map_geometry",
                "confirmar": confirmation,
                "arquivo": arquivo,
            },
        )

    def test_conteudo_only_fixture_is_refused_and_nothing_is_applied(self):
        """Fixture 100% catálogo (home.tbregra) → guard recusa, nada é aplicado."""
        payload = [
            {
                "model": "home.tbregra",
                "pk": 999001,
                "fields": {
                    "slug": "guard-teste-regra",
                    "nome": "Guard Teste",
                    "nome_en": None,
                    "categoria": None,
                    "definicao": None,
                },
            }
        ]

        response = self._post_restore(payload)

        self.assertContains(response, "Merge de conteudo (dev -&gt; producao)")
        self.assertEqual(TbRegra.objects.filter(pk=999001).count(), 0)

    def test_hunter_package_uses_protected_restore_branch(self):
        package = {'kind': 'bonfire.hunter_restore.v1'}
        with patch('home.hunter_restore_package.restore_hunter_package',
                   return_value={'added': 107, 'unchanged': 0,
                                 'ruleset_checksum': 'revision-test'}) as restore:
            response = self._post_restore(package)
        self.assertContains(response, 'Inseridos: 107; ja identicos: 0')
        restore.assert_called_once_with(package)

    def test_fixture_with_non_catalog_model_is_not_blocked_by_guard(self):
        """Fixture com um model FORA do catálogo (auth.user) → guard não dispara."""
        payload = [
            {
                "model": "auth.user",
                "pk": 999002,
                "fields": {
                    "username": "guard-teste-nao-catalogo",
                    "password": "!",
                },
            }
        ]

        response = self._post_restore(payload)

        self.assertNotContains(response, "Merge de conteudo (dev -&gt; producao)")

    def test_world_only_fixture_is_also_refused(self):
        payload = [
            {
                "model": "home.tbregiao",
                "pk": 999003,
                "fields": {
                    "nome": "Região por PK",
                    "slug": "regiao-por-pk",
                },
            }
        ]

        response = self._post_restore(payload)

        self.assertContains(response, "Merge de conteudo (dev -&gt; producao)")
        self.assertFalse(TbRegiao.objects.filter(pk=999003).exists())

    def test_map_geometry_restore_updates_only_polygon_coordinates(self):
        territorio = TbTerritorio.objects.create(
            nome="Territorio de Teste",
            slug="territorio-de-teste",
            lore_markdown="Lore preservada",
            coordenadas_poligono=[[[0, 0], [0, 1], [1, 1]]],
        )
        nova_geometria = [[[10, 10], [10, 20], [20, 20]]]
        payload = [
            {
                "model": "home.tbterritorio",
                "pk": territorio.pk,
                "fields": {
                    "nome": territorio.nome,
                    "slug": "slug-do-patch-ignorado",
                    "lore_markdown": "Lore que nao pode sobrescrever",
                    "coordenadas_poligono": nova_geometria,
                },
            }
        ]

        response = self._post_map_restore(payload)

        territorio.refresh_from_db()
        self.assertContains(response, "Somente CoordenadasPoligono")
        self.assertEqual(territorio.coordenadas_poligono, nova_geometria)
        self.assertEqual(territorio.slug, "territorio-de-teste")
        self.assertEqual(territorio.lore_markdown, "Lore preservada")

    def test_map_geometry_restore_rejects_other_models(self):
        payload = [
            {
                "model": "home.tbregiao",
                "pk": 999004,
                "fields": {"nome": "Regiao indevida", "slug": "regiao-indevida"},
            }
        ]

        response = self._post_map_restore(payload)

        self.assertContains(response, "exclusivamente registros home.tbterritorio")
        self.assertFalse(TbRegiao.objects.filter(pk=999004).exists())


class ConsoleUnlockTTLTests(TestCase):
    """A segunda trava do console (SERVER_LOGS_PASSWORD_HASH) expira apos
    CONSOLE_UNLOCK_TTL_SECONDS e eh renovada a cada request autenticado —
    ver server_logs_view em home/admin.py."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin-console-ttl",
            email="admin-console-ttl@example.com",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)
        self.url = reverse("admin:server_logs")

    def test_legacy_boolean_flag_alone_does_not_unlock(self):
        session = self.client.session
        session["admin_console_authenticated"] = True
        session.save()

        response = self.client.post(
            self.url, {"action": "run_command", "command": "git status"}
        )

        self.assertContains(response, "Autentique o console")
        self.assertNotIn("admin_console_authenticated", self.client.session)

    def test_expired_timestamp_does_not_unlock(self):
        session = self.client.session
        session["admin_console_authenticated_at"] = (
            time.time() - CONSOLE_UNLOCK_TTL_SECONDS - 60
        )
        session.save()

        response = self.client.post(
            self.url, {"action": "run_command", "command": "git status"}
        )

        self.assertContains(response, "Autentique o console")
        self.assertContains(response, "expirou")

    def test_fresh_timestamp_unlocks(self):
        session = self.client.session
        session["admin_console_authenticated_at"] = time.time()
        session.save()

        response = self.client.post(
            self.url, {"action": "run_command", "command": ""}
        )

        self.assertContains(response, "Informe um comando")

    def test_sliding_renewal_extends_timestamp_on_any_request(self):
        seeded_at = time.time() - 300
        session = self.client.session
        session["admin_console_authenticated_at"] = seeded_at
        session.save()

        self.client.get(self.url)

        self.assertGreater(
            self.client.session["admin_console_authenticated_at"], seeded_at
        )

    def test_correct_password_unlocks(self):
        with override_settings(
            SERVER_LOGS_PASSWORD_HASH=make_password("senha-console-teste")
        ):
            response = self.client.post(
                self.url,
                {"action": "authenticate", "server_password": "senha-console-teste"},
            )

        self.assertContains(response, "Acesso ao console liberado")
        self.assertIn("admin_console_authenticated_at", self.client.session)

    def test_wrong_password_does_not_unlock(self):
        with override_settings(
            SERVER_LOGS_PASSWORD_HASH=make_password("senha-console-teste")
        ):
            response = self.client.post(
                self.url,
                {"action": "authenticate", "server_password": "senha-errada"},
            )

        self.assertContains(response, "Senha incorreta.")
        self.assertNotIn("admin_console_authenticated_at", self.client.session)


class AdminSuperuserOnlyTests(TestCase):
    """Decisao do PO (2026-07-17): o /admin/ inteiro (models, console, baixar
    backup, editor markdown) e exclusivo de superuser — staff comum usa apenas
    os recursos inline do SITE. Ver _admin_superuser_only em home/admin.py."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff-sem-super",
            email="staff-sem-super@example.com",
            password="senha-forte-123",
            is_staff=True,
            is_superuser=False,
        )
        self.superuser = User.objects.create_superuser(
            username="super-admin",
            email="super-admin@example.com",
            password="senha-forte-123",
        )

    def test_staff_non_superuser_blocked_from_admin_index(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertNotEqual(response.status_code, 200)
        self.assertIn(response.status_code, (302, 403))

    def test_staff_non_superuser_blocked_from_console(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:server_logs"))
        self.assertNotEqual(response.status_code, 200)
        self.assertIn(response.status_code, (302, 403))

    def test_staff_non_superuser_blocked_from_download_backup(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:download_backup"))
        self.assertNotEqual(response.status_code, 200)
        self.assertIn(response.status_code, (302, 403))

    def test_superuser_reaches_admin_index(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)

    def test_superuser_reaches_console(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:server_logs"))
        self.assertEqual(response.status_code, 200)


class BaseSiteTemplateSmokeTests(TestCase):
    def test_login_page_does_not_render_broken_comment_as_text(self):
        """GET /admin/login/ não exige auth e estende base_site.html — o comentário
        {# ... #} quebrado (multi-linha) vazava como texto literal no topo da página."""
        response = self.client.get(reverse("admin:login"))

        self.assertNotContains(response, "Recarrega o tema")


class CatalogSyncConsoleTests(TestCase):
    def setUp(self):
        user = User.objects.create_superuser(
            username="catalog-console-test", email="catalog@example.com", password="test-password")
        self.client.force_login(user)
        session = self.client.session
        session["admin_console_authenticated_at"] = time.time()
        session.save()
        self.url = reverse("admin:server_logs")
        self.preview = {
            "package_sha256": "a" * 64, "base_version": "b" * 64,
            "backup_ready": True, "unsafe_deletions": 0,
            "models": {"TbRegra": {"current": 1, "incoming": 1,
                                   "new": 0, "changed_records": 0, "would_remove": 0}},
        }

    def test_apply_requires_preview_in_same_console_session(self):
        with patch("home.catalog_sync_api.catalog_sync_operation") as apply:
            response = self.client.post(self.url, {"action": "catalog_apply"})
        self.assertContains(response, "Gere uma previa")
        apply.assert_not_called()

    def test_preview_then_apply_consumes_session_state(self):
        with patch("home.catalog_sync_api.catalog_sync_preview_operation",
                   return_value=self.preview):
            response = self.client.post(self.url, {"action": "catalog_preview"})
        self.assertContains(response, "Aplicar pacote conferido com backup")
        self.assertEqual(self.client.session["admin_catalog_sync_preview"], {
            "package_sha256": "a" * 64, "base_version": "b" * 64})
        result = {"backup_file": "verified.dump", "updated": 0, "inserted": 0,
                  "replaced": 0, "memory_preserved": True}
        with patch("home.catalog_sync_api.catalog_sync_operation",
                   return_value=result) as apply:
            response = self.client.post(self.url, {"action": "catalog_apply"})
        self.assertContains(response, "verified.dump")
        self.assertNotIn("admin_catalog_sync_preview", self.client.session)
        self.assertEqual(apply.call_args.args[0], {
            "package_sha256": "a" * 64, "base_version": "b" * 64})
        self.assertTrue(apply.call_args.args[1].pk.startswith("admin:"))
        self.assertTrue(DbAccessAudit.objects.filter(
            action="admin_catalog_sync", status_code=200,
            object_pk=str(self.client.session.get("_auth_user_id")),
        ).exists())

    def test_unsafe_preview_hides_apply_and_failed_apply_requires_new_preview(self):
        preview = {**self.preview, "unsafe_deletions": 1}
        with patch("home.catalog_sync_api.catalog_sync_preview_operation",
                   return_value=preview):
            response = self.client.post(self.url, {"action": "catalog_preview"})
        self.assertNotContains(response, "Aplicar pacote conferido com backup")
        with patch("home.catalog_sync_api.catalog_sync_operation",
                   side_effect=ApiProblem(409, "catalog_deletions_pending", "Unsafe")):
            response = self.client.post(self.url, {"action": "catalog_apply"})
        self.assertContains(response, "catalog_deletions_pending")
        self.assertNotIn("admin_catalog_sync_preview", self.client.session)
        self.assertTrue(DbAccessAudit.objects.filter(
            action="admin_catalog_sync", status_code=409).exists())

    def _upload(self, stage, content=b'[]'):
        return self.client.post(self.url, {
            "action": "merge_conteudo", "merge_stage": stage,
            "arquivo": SimpleUploadedFile("conteudo.json", content),
        })

    def test_manual_upload_requires_preview_and_reupload(self):
        with patch("home.catalog_sync_api.catalog_upload_sync_operation") as apply:
            response = self._upload("apply")
        self.assertContains(response, "Gere uma previa do arquivo")
        apply.assert_not_called()
        with patch("home.catalog_sync_api.catalog_upload_preview_operation",
                   return_value=self.preview) as preview:
            response = self._upload("preview", b'[{"model":"home.tbregra"}]')
        self.assertContains(response, "Aplicar arquivo conferido com backup")
        preview.assert_called_once()
        self.assertEqual(preview.call_args.args[0], b'[{"model":"home.tbregra"}]')
        result = {"backup_file": "upload-verified.dump", "memory_preserved": True}
        with patch("home.catalog_sync_api.catalog_upload_sync_operation",
                   return_value=result) as apply:
            response = self._upload("apply", b'[{"model":"home.tbregra"}]')
        self.assertContains(response, "upload-verified.dump")
        self.assertEqual(apply.call_args.args[0], b'[{"model":"home.tbregra"}]')
        self.assertNotIn("admin_manual_catalog_preview", self.client.session)
        self.assertTrue(DbAccessAudit.objects.filter(
            action="admin_upload_sync", status_code=200).exists())

    def test_manual_merge_failure_rolls_back_and_audits_failure(self):
        with patch("home.catalog_sync_api.catalog_upload_preview_operation",
                   return_value=self.preview):
            self._upload("preview")

        def failed_merge(*_args):
            TbRegra.objects.create(slug="partial-upload", nome="Parcial", categoria="core")
            raise ApiProblem(409, "catalog_sync_failed", "Merge falhou")

        with patch("home.catalog_sync_api.catalog_upload_sync_operation",
                   side_effect=failed_merge):
            response = self._upload("apply")
        self.assertContains(response, "catalog_sync_failed")
        self.assertFalse(TbRegra.objects.filter(slug="partial-upload").exists())
        self.assertFalse(DbAccessAudit.objects.filter(
            action="admin_upload_sync", status_code=200).exists())
        self.assertTrue(DbAccessAudit.objects.filter(
            action="admin_upload_sync", status_code=409).exists())

    def test_manual_unsafe_preview_hides_apply(self):
        with patch("home.catalog_sync_api.catalog_upload_preview_operation",
                   return_value={**self.preview, "unsafe_deletions": 1}):
            response = self._upload("preview")
        self.assertNotContains(response, "Aplicar arquivo conferido com backup")
