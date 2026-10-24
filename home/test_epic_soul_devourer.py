"""Soul Devourer effects and candidate selection in the real sheet."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from home.character_engine import derive
from home.epic_talent_catalog import ATTRIBUTE_TAGS, VERIFIED_EFFECTS, epic_candidates
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


SLUG = "dadiva-do-devorador-de-almas"


class SoulDevourerSheetTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="epic-soul-devourer")
        self.character = TbPersonagem.objects.create(dono=owner, nome="Devourer")
        self.talent = TbTalento.objects.create(
            nome="Dádiva do Devorador de Almas", slug=SLUG, tipo="geral",
            etiquetas_adicionais="epico", descricao="Efeitos do talento em teste.",
            tags_json=ATTRIBUTE_TAGS + VERIFIED_EFFECTS[SLUG],
        )

    def sheet(self):
        return derive(self.character)

    def grant(self, talent, *, details=""):
        return TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=talent,
            categoria="epico" if talent == self.talent else "geral",
            nome=talent.nome, detalhes=details,
        )

    def test_resistance_and_external_immunity_are_independent_per_type(self):
        original = self.sheet()
        self.assertNotIn("frio", original["resistencias"])
        self.assertNotIn("necrotico", original["resistencias"])

        owned = self.grant(self.talent, details="talent_attr:CON")
        base = self.sheet()
        self.assertIn("frio", base["resistencias"])
        self.assertIn("necrotico", base["resistencias"])
        self.assertNotIn("frio", base["imunidades"])
        self.assertNotIn("necrotico", base["imunidades"])

        cold = TbTalento.objects.create(
            nome="Outra defesa fria", slug="outra-defesa-fria", tipo="geral",
            tags_json=["resist:frio"],
        )
        other = self.grant(cold)
        for _ in range(2):
            promoted = self.sheet()
            self.assertEqual(promoted["resistencias"].count("frio"), 1)
            self.assertEqual(promoted["imunidades"].count("frio"), 1)
            self.assertNotIn("necrotico", promoted["imunidades"])

        other.delete()
        self.assertNotIn("frio", self.sheet()["imunidades"])
        owned.delete()
        removed = self.sheet()
        self.assertNotIn("frio", removed["resistencias"])
        self.assertNotIn("necrotico", removed["resistencias"])

    def test_later_sources_and_missing_choice_do_not_self_promote(self):
        owned = self.grant(self.talent)
        self.assertNotIn("frio", self.sheet()["resistencias"])
        owned.detalhes = "talent_attr:CON"
        owned.save(update_fields=["detalhes"])
        necrotic = TbTalento.objects.create(
            nome="Outra defesa necrotica", slug="outra-defesa-necrotica",
            tipo="geral", tags_json=["resist:necrotico"],
        )
        self.grant(necrotic)
        self.assertIn("necrotico", self.sheet()["imunidades"])
        self.assertNotIn("frio", self.sheet()["imunidades"])

    def test_all_tags_validate_and_candidate_is_selectable(self):
        diagnostics = validate_tags_json(VERIFIED_EFFECTS[SLUG], Library())
        self.assertEqual([d for d in diagnostics if d.level == ERROR], [])
        candidate = next(row for row in epic_candidates() if row["slug"] == SLUG)
        self.assertEqual(candidate["tags_json"], ATTRIBUTE_TAGS + VERIFIED_EFFECTS[SLUG])
