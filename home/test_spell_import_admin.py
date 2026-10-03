from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
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
        self.assertEqual(TbMagia.objects.filter(slug="luz-de-teste").count(), 0)
        payload = preview.context["payload"]
        result = self.client.post(self.url, {"confirmar": "1", "payload": payload})
        self.assertContains(result, "1 criadas, 0 atualizadas e 0 ignoradas")
        self.assertEqual(TbMagia.objects.filter(slug="luz-de-teste").count(), 1)
        replay = self.client.post(self.url, {"confirmar": "1", "payload": payload})
        self.assertContains(replay, "O catalogo mudou desde a previa")
        self.assertEqual(TbMagia.objects.filter(slug="luz-de-teste").count(), 1)

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

    def test_invalid_row_aborts_whole_batch(self):
        preview = self.preview(("Magia Valida", 1), ("Magia Invalida", 12))
        self.assertContains(preview, "Nivel fora do intervalo")
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
