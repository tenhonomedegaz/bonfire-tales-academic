"""Corpo do Ceifador as tag-driven passives in the real sheet."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.template.loader import render_to_string

from home.character_engine import derive
from home.epic_talent_catalog import ATTRIBUTE_TAGS, PARTIAL_EFFECTS, epic_candidates
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


SLUG = "dadiva-do-ceifador-de-almas"


class SoulReaperBodyTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="epic-soul-reaper")
        self.character = TbPersonagem.objects.create(dono=owner, nome="Ceifador")
        self.talent = TbTalento.objects.create(
            nome="Dádiva do Ceifador de Almas", slug=SLUG, tipo="geral",
            etiquetas_adicionais="epico", descricao="Efeitos parciais de teste.",
            tags_json=ATTRIBUTE_TAGS + PARTIAL_EFFECTS[SLUG],
        )

    def test_body_passives_follow_source_and_attribute_choice(self):
        original = derive(self.character)
        self.assertNotIn("veneno", original["imunidades"])
        self.assertNotIn("envenenado", {row["slug"] for row in original["imunidades_condicao"]})
        self.assertFalse(any("salvaguardas contra a morte" in value
                             for value in original["vantagens"]))

        owned = TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=self.talent,
            categoria="epico", nome=self.talent.nome,
        )
        self.assertNotIn("veneno", derive(self.character)["imunidades"])

        owned.detalhes = "talent_attr:CON"
        owned.save(update_fields=["detalhes"])
        for _ in range(2):
            sheet = derive(self.character)
            self.assertEqual(sheet["imunidades"].count("veneno"), 1)
            self.assertEqual(sum(row["slug"] == "envenenado"
                                 for row in sheet["imunidades_condicao"]), 1)
            self.assertEqual(sum("salvaguardas contra a morte" in value
                                 for value in sheet["vantagens"]), 1)
        html = render_to_string("home/partials/_ficha_folha_defesas.html",
                                {"ficha": sheet, "folha_readonly": True})
        self.assertIn("veneno", html)
        self.assertIn("Envenenado", html)
        self.assertIn("salvaguardas contra a morte", html)

        other_talent = TbTalento.objects.create(
            nome="Outra imunidade", slug="outra-imunidade-veneno", tipo="geral",
            tags_json=["immune:veneno"],
        )
        other = TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=other_talent,
            nome=other_talent.nome,
        )

        owned.delete()
        removed = derive(self.character)
        self.assertEqual(removed["imunidades"].count("veneno"), 1)
        self.assertNotIn("envenenado", {row["slug"] for row in removed["imunidades_condicao"]})
        self.assertFalse(any("salvaguardas contra a morte" in value
                             for value in removed["vantagens"]))
        other.delete()
        self.assertNotIn("veneno", derive(self.character)["imunidades"])

    def test_partial_tags_validate_without_publishing_talent(self):
        diagnostics = validate_tags_json(PARTIAL_EFFECTS[SLUG], Library())
        self.assertEqual([row for row in diagnostics if row.level == ERROR], [])
        self.assertNotIn(SLUG, {row["slug"] for row in epic_candidates()})
