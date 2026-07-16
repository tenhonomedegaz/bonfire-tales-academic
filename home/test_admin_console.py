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

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from home.models import TbRegra


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
        session["admin_console_authenticated"] = True
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


class BaseSiteTemplateSmokeTests(TestCase):
    def test_login_page_does_not_render_broken_comment_as_text(self):
        """GET /admin/login/ não exige auth e estende base_site.html — o comentário
        {# ... #} quebrado (multi-linha) vazava como texto literal no topo da página."""
        response = self.client.get(reverse("admin:login"))

        self.assertNotContains(response, "Recarrega o tema")
