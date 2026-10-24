"""Existing skill sources determine an epic talent's proficiency upgrade."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from home.character_engine import derive
from home.epic_talent_catalog import ATTRIBUTE_TAGS, PARTIAL_EFFECTS, epic_candidates
from home.models import TbPersonagem, TbPersonagemPericia, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


CASES = (
    ("dadiva-da-memoria-arcana", "Arcanismo"),
    ("dadiva-da-folia", "Atuação"),
    ("dadiva-do-horror", "Intimidação"),
)


class EpicSkillUpgradeTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="epic-skill-upgrade")
        self.character = TbPersonagem.objects.create(dono=owner, nome="Skills")

    def skill(self, name):
        return next(row for row in derive(self.character)["pericias"]
                    if row["nome"] == name)

    def grant(self, slug, *, choice="talent_attr:INT"):
        talent = TbTalento.objects.create(
            nome=slug, slug=slug, tipo="geral", etiquetas_adicionais="epico",
            tags_json=ATTRIBUTE_TAGS + PARTIAL_EFFECTS[slug],
        )
        owned = TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=talent, categoria="epico",
            nome=talent.nome, detalhes=choice,
        )
        return owned

    def test_no_prior_proficiency_then_external_proficiency_and_removal(self):
        for slug, name in CASES:
            with self.subTest(slug=slug):
                owned = self.grant(slug)
                first = self.skill(name)
                self.assertTrue(first["proficiente"])
                self.assertFalse(first["expertise"])

                other = TbTalento.objects.create(
                    nome="Fonte externa " + slug, slug="external-" + slug,
                    tags_json=["prof:" + {
                        "Arcanismo": "arcanismo", "Atuação": "atuacao",
                        "Intimidação": "intimidacao",
                    }[name]],
                )
                external = TbPersonagemTalento.objects.create(
                    id_personagem=self.character, id_talento=other,
                    nome=other.nome,
                )
                for _ in range(2):
                    self.assertTrue(self.skill(name)["expertise"])
                external.delete()
                self.assertFalse(self.skill(name)["expertise"])
                owned.delete()
                self.assertFalse(self.skill(name)["proficiente"])

    def test_prior_proficiency_promotes_without_duplicating_other_skills(self):
        TbPersonagemPericia.objects.create(
            id_personagem=self.character, nome="Arcanismo", atributo="INT",
            proficiente=True,
        )
        owned = self.grant("dadiva-da-memoria-arcana")
        self.assertTrue(self.skill("Arcanismo")["expertise"])
        self.assertFalse(self.skill("Atuação")["expertise"])
        owned.detalhes = ""
        owned.save(update_fields=["detalhes"])
        self.assertFalse(self.skill("Arcanismo")["expertise"])
        owned.delete()
        self.assertTrue(self.skill("Arcanismo")["proficiente"])

    def test_horror_fear_immunity_follows_source_and_attribute_choice(self):
        owned = self.grant("dadiva-do-horror", choice="")
        self.assertFalse(self.skill("Intimidação")["proficiente"])
        self.assertNotIn("Amedrontado (condição)", derive(self.character)["imunidades"])
        owned.detalhes = "talent_attr:CAR"
        owned.save(update_fields=["detalhes"])
        self.assertIn("Amedrontado (condição)", derive(self.character)["imunidades"])
        owned.delete()
        self.assertNotIn("Amedrontado (condição)", derive(self.character)["imunidades"])

    def test_partial_tags_validate_and_are_not_importable_yet(self):
        ready = {row["slug"] for row in epic_candidates()}
        for slug, _ in CASES:
            self.assertNotIn(slug, ready)
            diagnostics = validate_tags_json(PARTIAL_EFFECTS[slug], Library())
            self.assertEqual([d for d in diagnostics if d.level == ERROR], [], slug)
