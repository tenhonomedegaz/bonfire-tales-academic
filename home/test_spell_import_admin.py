from io import BytesIO
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.auth import get_user_model
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from .models import TbClasse, TbMagia


class SpellImportAdminTests(TestCase):
    def setUp(self):
        self.url = reverse("admin:home_tbmagia_importar_excel")
        self.admin = get_user_model().objects.create_superuser(
            "import-admin", "import@example.invalid", "test-pass"
        )
        self.client.force_login(self.admin)

    @staticmethod
    def workbook(*rows):
        book = Workbook()
        sheet = book.active
        sheet.title = "Versão Final pra Import"
        sheet.append(["Nome", "Nivel", "Casting Time", "Ritual", "Duracao",
                      "Escola", "Alcance", "Componentes", "Descricao", "Classes"])
        for row in rows:
            name, level = row[:2]
            ritual = row[2] if len(row) > 2 else "Nao"
            classes = row[3] if len(row) > 3 else ""
            sheet.append([name, level, "Acao", ritual, "1 minuto", "Evocacao",
                          "Toque", "V", "Texto de teste", classes])
        output = BytesIO()
        book.save(output)
        return SimpleUploadedFile(
            "magias.xlsx", output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def preview(self, *rows, update=True):
        return self.client.post(self.url, {
            "arquivo": self.workbook(*rows),
            "atualizar_existentes": "on" if update else "",
        })

    def test_preview_confirm_result_and_replay_protection(self):
        preview = self.preview(("Luz de Teste", 1))
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Criar")
        self.assertContains(preview, 'id="spell-import-preview" tabindex="-1"')
        self.assertEqual(TbMagia.objects.filter(slug="luz-de-teste").count(), 0)
        payload = preview.context["payload"]
        result = self.client.post(self.url, {"confirmar": "1", "payload": payload})
        self.assertContains(result, "1 criadas, 0 atualizadas e 0 ignoradas")
        self.assertContains(result, 'id="spell-import-result" tabindex="-1"')
        self.assertEqual(TbMagia.objects.filter(slug="luz-de-teste").count(), 1)
        replay = self.client.post(self.url, {"confirmar": "1", "payload": payload})
        self.assertContains(replay, "O catalogo mudou desde a previa")
        self.assertEqual(TbMagia.objects.filter(slug="luz-de-teste").count(), 1)

    def test_import_history_identifies_editor_and_only_real_changes(self):
        TbClasse.objects.create(nome="Mago", slug="mago")
        preview = self.preview(("Magia Auditada", 1, "Nao", "Mago"))
        self.assertEqual(self.client.post(self.url, {
            "confirmar": "1", "payload": preview.context["payload"],
        }).status_code, 200)
        spell = TbMagia.objects.get(slug="magia-auditada")
        history = LogEntry.objects.filter(object_id=str(spell.pk), user=self.admin)
        self.assertEqual(history.filter(action_flag=ADDITION).count(), 1)
        self.assertContains(self.client.get(reverse(
            "admin:home_tbmagia_history", args=[spell.pk],
        )), "Importada por Excel")

        identical = self.preview(("Magia Auditada", 1, "Nao", "mago"))
        self.assertEqual(identical.context["preview"][0]["import_action"], "Ignorar")
        self.assertEqual(identical.context["preview"][0]["tags_json"], ["1", "Evocacao", "Mago"])
        with CaptureQueriesContext(connection) as queries:
            identical_result = self.client.post(self.url, {
                "confirmar": "1", "payload": identical.context["payload"],
            })
        self.assertContains(identical_result, "0 criadas, 0 atualizadas e 1 ignoradas")
        self.assertEqual(history.filter(action_flag=CHANGE).count(), 0)
        self.assertFalse(any(
            'UPDATE "spells"' in query['sql'] for query in queries.captured_queries
        ))

        changed = self.preview(("Magia Auditada", 2, "Nao", "Mago"))
        self.assertEqual(changed.context["preview"][0]["import_action"], "Atualizar")
        self.assertEqual(self.client.post(self.url, {
            "confirmar": "1", "payload": changed.context["payload"],
        }).status_code, 200)
        spell.refresh_from_db()
        self.assertEqual(spell.nivel, 2)
        self.assertEqual(history.filter(action_flag=CHANGE).count(), 1)
        self.assertContains(self.client.get(reverse(
            "admin:home_tbmagia_history", args=[spell.pk],
        )), "Importada por Excel")

    def test_existing_spell_full_preview_precedes_replacement(self):
        TbClasse.objects.create(nome="Mago", slug="mago")
        spell = TbMagia.objects.create(
            nome="Luz de Teste", slug="luz-de-teste", nivel=1,
            descricao="Texto publicado antes da importacao",
        )
        upload = self.workbook(("Luz de Teste", 2, "Nao", "Mago"))
        book = load_workbook(BytesIO(upload.read()))
        sheet = book.active
        long_description = (
            "Inicio da descricao. " + "Trecho detalhado. " * 10
            + "Final indispensavel. <script>alert(1)</script>"
        )
        sheet["E2"] = "Concentracao, ate 10 minutos"
        sheet["I2"] = long_description
        sheet["K1"] = "Em Niveis Superiores"
        sheet["K2"] = "Ao conjurar em nivel maior, ganhe outro efeito."
        output = BytesIO()
        book.save(output)
        preview = self.client.post(self.url, {
            "arquivo": SimpleUploadedFile("magias.xlsx", output.getvalue()),
            "atualizar_existentes": "on",
        })

        self.assertContains(preview, "Atualizar")
        self.assertContains(preview, "Final indispensavel.")
        self.assertContains(preview, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(preview, "<script>alert(1)</script>")
        self.assertContains(preview, "Ao conjurar em nivel maior, ganhe outro efeito.")
        self.assertContains(preview, "10 minutos")
        self.assertContains(preview, "Mago")
        self.assertContains(preview, "Tags geradas")
        spell.refresh_from_db()
        self.assertEqual(spell.descricao, "Texto publicado antes da importacao")

        result = self.client.post(self.url, {
            "confirmar": "1", "payload": preview.context["payload"],
        })
        self.assertContains(result, "0 criadas, 1 atualizadas e 0 ignoradas")
        spell.refresh_from_db()
        self.assertEqual(spell.descricao, long_description)
        self.assertEqual(spell.em_niveis_superiores, "Ao conjurar em nivel maior, ganhe outro efeito.")
        self.assertEqual(spell.nivel, 2)
        self.assertTrue(spell.concentracao)
        self.assertEqual(spell.classes_slugs, ["mago"])

    def test_invalid_row_aborts_whole_batch(self):
        preview = self.preview(("Magia Valida", 1), ("Magia Invalida", 12))
        self.assertContains(preview, "Nivel fora do intervalo")
        self.assertContains(preview, 'id="spell-import-errors" tabindex="-1"')
        self.assertNotContains(preview, "Confirmar importacao")
        self.assertFalse(TbMagia.objects.filter(slug="magia-valida").exists())

    def test_missing_name_or_ambiguous_ritual_aborts_whole_batch(self):
        preview = self.preview(("Magia Valida", 1), ("", 2),
                               ("Magia Duvidosa", 1, "talvez"))
        self.assertContains(preview, "nome obrigatorio")
        self.assertContains(preview, "Ritual invalido")
        self.assertNotContains(preview, "Confirmar importacao")
        self.assertFalse(TbMagia.objects.filter(slug="magia-valida").exists())

    def test_unknown_class_is_reported_before_confirmation(self):
        preview = self.preview(("Magia de Teste", 1, "Nao", "Classe Inexistente"))
        self.assertContains(preview, "classes nao cadastradas")
        self.assertNotContains(preview, "Confirmar importacao")
        self.assertFalse(TbMagia.objects.filter(slug="magia-de-teste").exists())

    def test_changed_existing_spell_requires_fresh_preview(self):
        spell = TbMagia.objects.create(nome="Original", slug="original", nivel=1)
        preview = self.preview(("Original", 2))
        self.assertContains(preview, "Atualizar")
        spell.descricao = "Edicao concorrente"
        spell.save(update_fields=["descricao"])
        result = self.client.post(self.url, {
            "confirmar": "1", "payload": preview.context["payload"]
        })
        self.assertContains(result, "O catalogo mudou desde a previa")
        spell.refresh_from_db()
        self.assertEqual(spell.nivel, 1)
        self.assertEqual(spell.descricao, "Edicao concorrente")

    def test_skip_existing_reports_result_without_creating_duplicate(self):
        spell = TbMagia.objects.create(nome="Original", slug="original", nivel=1)
        preview = self.preview(("Original", 2), update=False)
        self.assertContains(preview, "Ignorar")
        result = self.client.post(self.url, {
            "confirmar": "1", "payload": preview.context["payload"]
        })
        self.assertContains(result, "0 criadas, 0 atualizadas e 1 ignoradas")
        spell.refresh_from_db()
        self.assertEqual(spell.nivel, 1)
        self.assertEqual(TbMagia.objects.filter(slug="original").count(), 1)

    def test_stale_second_row_rolls_back_first_row(self):
        spell = TbMagia.objects.create(nome="Original", slug="original", nivel=1)
        preview = self.preview(("Nova Magia", 1), ("Original", 2))
        spell.descricao = "Edicao concorrente"
        spell.save(update_fields=["descricao"])
        result = self.client.post(self.url, {
            "confirmar": "1", "payload": preview.context["payload"]
        })
        self.assertContains(result, "O catalogo mudou desde a previa")
        self.assertFalse(TbMagia.objects.filter(slug="nova-magia").exists())
        self.assertFalse(LogEntry.objects.filter(
            user=self.admin, content_type__app_label="home", content_type__model="tbmagia",
        ).exists())

    def test_removed_class_after_preview_rolls_back_whole_batch(self):
        classe = TbClasse.objects.create(nome="Mago", slug="mago")
        preview = self.preview(("Nova Magia", 1), ("Magia de Classe", 2, "Nao", "Mago"))
        self.assertContains(preview, "Confirmar importacao")
        classe.delete()

        result = self.client.post(self.url, {
            "confirmar": "1", "payload": preview.context["payload"],
        })
        self.assertContains(result, "classes nao cadastradas")
        self.assertFalse(TbMagia.objects.filter(slug__in=["nova-magia", "magia-de-classe"]).exists())

    def test_duplicate_slug_and_tampered_payload_are_rejected(self):
        preview = self.preview(("Luz", 1), ("Luz", 2))
        self.assertContains(preview, "mesmo slug")
        self.assertNotContains(preview, "Confirmar importacao")
        result = self.client.post(self.url, {
            "confirmar": "1", "payload": "alterado"
        })
        self.assertContains(result, "Previa invalida ou expirada")
        self.assertFalse(TbMagia.objects.filter(slug="luz").exists())

    def test_staff_cannot_access_import(self):
        staff = get_user_model().objects.create_user(
            "ordinary-staff", "staff@example.invalid", "test-pass", is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (302, 403))


class SpellImportAdminMobileTests(StaticLiveServerTestCase):
    def test_full_preview_stays_usable_at_360_pixels(self):
        if connection.vendor != "postgresql" or not connection.settings_dict["NAME"].startswith("test_"):
            self.skipTest("Requer PostgreSQL de teste isolado.")
        try:
            import websocket
        except ImportError:
            self.skipTest("websocket-client indisponivel.")
        chrome = shutil.which("chrome") or next((str(path) for path in (
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest("Chrome ou Edge indisponivel.")

        admin_user = get_user_model().objects.create_superuser(
            "mobile-import-admin", "mobile-import@example.invalid", "test-pass"
        )
        self.client.force_login(admin_user)
        upload = SpellImportAdminTests.workbook(("Magia de Tela Compacta", 1))
        with tempfile.TemporaryDirectory(prefix="bonfire-spell-import-", ignore_cleanup_errors=True) as scratch:
            path = Path(scratch) / "magias.xlsx"
            path.write_bytes(upload.read())
            profile = Path(scratch) / "chrome"
            process = subprocess.Popen([
                chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
                "--remote-debugging-port=0", "--remote-allow-origins=*",
                f"--user-data-dir={profile}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / "DevToolsActivePort"
                for _ in range(80):
                    if port_file.exists():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.exists())
                port = port_file.read_text(encoding="utf-8").splitlines()[0]
                with urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
                    target = next(item for item in json.load(response) if item["type"] == "page")
                ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=10)
                sequence = 0

                def call(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({"id": sequence, "method": method, "params": params or {}}))
                    while True:
                        response = json.loads(ws.recv())
                        if response.get("id") == sequence:
                            self.assertNotIn("error", response, method)
                            return response["result"]

                def js(expression):
                    result = call("Runtime.evaluate", {
                        "expression": expression, "returnByValue": True,
                    })
                    self.assertNotIn("exceptionDetails", result, expression)
                    return result["result"].get("value")

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f"Tempo esgotado: {expression}")

                call("Network.enable")
                call("Network.setCookie", {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": self.live_server_url,
                })
                call("Emulation.setDeviceMetricsOverride", {
                    "width": 360, "height": 800, "deviceScaleFactor": 1, "mobile": True,
                })
                call("Page.navigate", {
                    "url": self.live_server_url + reverse("admin:home_tbmagia_importar_excel"),
                })
                wait_for('document.querySelector("input[type=file]") !== null')
                file_input = call("Runtime.evaluate", {
                    "expression": 'document.querySelector("input[type=file]")',
                })["result"]["objectId"]
                call("DOM.setFileInputFiles", {"files": [str(path)], "objectId": file_input})
                js('document.querySelector("form.spell-import-grid").requestSubmit()')
                wait_for('document.querySelector(".spell-import-details") !== null')
                wait_for('document.activeElement.id === "spell-import-preview"')
                self.assertEqual(js("window.innerWidth"), 360)
                self.assertLessEqual(js("document.documentElement.scrollWidth"), 360)
                js('document.querySelector(".spell-import-details summary").click()')
                self.assertTrue(js('document.querySelector(".spell-import-details").open'))
                self.assertTrue(js('document.querySelector(".spell-import-details").innerText.includes("Descricao completa")'))
                self.assertTrue(js('Array.from(document.querySelectorAll("input[type=submit]")).some(el => el.value === "Confirmar importacao")'))
                call("Emulation.setDeviceMetricsOverride", {
                    "width": 320, "height": 640, "deviceScaleFactor": 1, "mobile": True,
                })
                self.assertEqual(js("window.innerWidth"), 320)
                self.assertLessEqual(js("document.documentElement.scrollWidth"), 320)
                self.assertTrue(js('document.querySelector(".spell-import-details").open'))
                js('Array.from(document.querySelectorAll("input[type=submit]")).find(el => el.value === "Confirmar importacao").click()')
                wait_for('document.activeElement.id === "spell-import-result"')
                self.assertTrue(js('document.querySelector(".spell-import-result").innerText.includes("1 criadas")'))
                self.assertLessEqual(js("document.documentElement.scrollWidth"), 320)
                call("Page.navigate", {
                    "url": self.live_server_url + reverse("magias_listas") + "?magia=magia-de-tela-compacta",
                })
                wait_for('document.querySelector("#mgDetail h2")?.textContent === "Magia de Tela Compacta" && document.querySelector("#mgDetail [data-spell-editor]") !== null')
                self.assertEqual(js('document.querySelector("#mgDetail [data-spell-editor] input[name=nome]").value'), 'Magia de Tela Compacta')
                self.assertEqual(js('document.querySelectorAll("#mgDetail input[type=file], #mgDetail a[href*=importar-excel]").length'), 0)
                self.assertFalse(js('document.querySelector("#mgDetail").textContent.includes("Importar magias")'))
                self.assertLessEqual(js("document.documentElement.scrollWidth"), 320)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
