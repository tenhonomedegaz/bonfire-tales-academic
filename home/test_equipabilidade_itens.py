# -*- coding: utf-8 -*-
import io
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from home.models import TbItemMagico


class AuditarEquipabilidadeItensTests(TestCase):
    def test_dry_run_e_apply_preservam_hold(self):
        alteravel = TbItemMagico.objects.create(
            nome="Apito de Teste", slug="apito-de-teste",
            slot="empunhado", tipo="Wondrous Item")
        hold = TbItemMagico.objects.create(
            nome="Artefato Ambiguo", slug="artefato-ambiguo",
            slot="empunhado", tipo="Wondrous Item")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scratch = root / "scratch"
            scratch.mkdir()
            (scratch / "equipaveis_batch_a_g.json").write_text(
                json.dumps([
                    {
                        "slug": alteravel.slug,
                        "slot_alvo": "objeto",
                        "equipavel": False,
                        "confianca": "alta",
                        "motivo": "ativacao pontual",
                    },
                    {
                        "slug": hold.slug,
                        "slot_alvo": "acessorio",
                        "equipavel": True,
                        "confianca": "baixa",
                        "motivo": "uso ambiguo",
                    },
                ]),
                encoding="utf-8")

            with override_settings(BASE_DIR=root):
                output = io.StringIO()
                call_command("auditar_equipabilidade_itens", stdout=output)
                alteravel.refresh_from_db()
                self.assertEqual(alteravel.slot, "empunhado")
                self.assertIn("DRY-RUN", output.getvalue())

                call_command(
                    "auditar_equipabilidade_itens", "--apply", stdout=io.StringIO())

            alteravel.refresh_from_db()
            hold.refresh_from_db()
            self.assertEqual(alteravel.slot, "objeto")
            self.assertEqual(hold.slot, "empunhado")
            log = json.loads(
                (scratch / "equipaveis_aplicacao_log.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(len(log["alteracoes"]), 1)
            self.assertEqual(log["alteracoes"][0]["antes"], "empunhado")
            self.assertEqual(log["alteracoes"][0]["depois"], "objeto")
            self.assertEqual([row["slug"] for row in log["holds"]],
                             ["artefato-ambiguo"])
