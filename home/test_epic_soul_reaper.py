"""Corpo do Ceifador as tag-driven passives in the real sheet."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.template.loader import render_to_string
from django.urls import reverse

from home.character_engine import derive
from home.epic_death_seal import death_seal_state, restoration_allowed
from home.epic_reaping import reaping_state
from home.epic_talent_catalog import ATTRIBUTE_TAGS, VERIFIED_EFFECTS, epic_candidates
from home.models import TbOperacaoRecurso, TbPersonagem, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


SLUG = "dadiva-do-ceifador-de-almas"


class SoulReaperBodyTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="epic-soul-reaper")
        self.character = TbPersonagem.objects.create(dono=owner, nome="Ceifador")
        self.talent = TbTalento.objects.create(
            nome="Dádiva do Ceifador de Almas", slug=SLUG, tipo="geral",
            etiquetas_adicionais="epico", descricao="Efeitos do Ceifador em teste.",
            tags_json=ATTRIBUTE_TAGS + VERIFIED_EFFECTS[SLUG],
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
        self.assertIsNone(death_seal_state(self.character))
        self.assertIsNone(reaping_state(self.character))

        owned.detalhes = "talent_attr:CON"
        owned.save(update_fields=["detalhes"])
        self.assertTrue(death_seal_state(self.character)["active"])
        self.assertTrue(reaping_state(self.character)["available"])
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
        self.assertIsNone(death_seal_state(self.character))
        self.assertIsNone(reaping_state(self.character))
        removed = derive(self.character)
        self.assertEqual(removed["imunidades"].count("veneno"), 1)
        self.assertNotIn("envenenado", {row["slug"] for row in removed["imunidades_condicao"]})
        self.assertFalse(any("salvaguardas contra a morte" in value
                             for value in removed["vantagens"]))
        other.delete()
        self.assertNotIn("veneno", derive(self.character)["imunidades"])

    def test_complete_tags_validate_and_catalog_includes_talent(self):
        diagnostics = validate_tags_json(VERIFIED_EFFECTS[SLUG], Library())
        self.assertEqual([row for row in diagnostics if row.level == ERROR], [])
        self.assertIn(SLUG, {row["slug"] for row in epic_candidates()})


class SoulReaperIntegratedTests(TestCase):
    def test_catalog_candidate_drives_sheet_damage_and_death_lifecycle(self):
        candidate = next(row for row in epic_candidates() if row["slug"] == SLUG)
        self.assertIn("**Aumento de Atributo:**", candidate["descricao"])
        self.assertEqual(candidate["tipo"], "geral")
        self.assertEqual(candidate["tags_json"], ATTRIBUTE_TAGS + VERIFIED_EFFECTS[SLUG])
        owner = get_user_model().objects.create_user(username="epic-reaper-integrated")
        person = TbPersonagem.objects.create(dono=owner, nome="Ceifador integrado")
        talent = TbTalento.objects.create(**candidate)
        owned = TbPersonagemTalento.objects.create(
            id_personagem=person, id_talento=talent, categoria="epico",
            nome=talent.nome, detalhes="talent_attr:CON",
        )
        self.client.force_login(owner)
        sheet = self.client.get(reverse("ficha_detail", args=[person.pk]))
        self.assertContains(sheet, "Aplicar Ceifa")
        self.assertContains(sheet, "Registrar morte selada")
        self.assertIn("veneno", derive(person)["imunidades"])

        target = "encounter-9:creature-2"
        damage = {
            "operation_id": str(uuid.uuid4()), "creature_ref": target,
            "source_kind": "spell", "chosen_type": "necrótico",
            "damage_type": ["cortante", "necrótico"],
            "dice_expression": ["3d8", "2d6"],
            "rolled_values": ["1,4,8", "2,5"],
            "fixed_damage": ["2", "0"],
        }
        damage_url = reverse("personagem_ceifar_dano", args=[person.pk])
        self.assertEqual(self.client.post(damage_url, damage).status_code, 302)
        self.assertEqual(self.client.post(damage_url, damage).status_code, 302)
        self.assertFalse(reaping_state(person)["available"])
        self.assertEqual(self.client.post(damage_url, dict(damage, operation_id=str(uuid.uuid4()))).status_code, 400)

        seal = {
            "target": target, "operation_id": str(uuid.uuid4()),
            "caused_by_own_damage": "on", "death_confirmed": "on",
        }
        seal_url = reverse("personagem_registrar_morte_selada", args=[person.pk])
        self.assertEqual(self.client.post(seal_url, seal).status_code, 302)
        self.assertEqual(self.client.post(seal_url, seal).status_code, 302)
        self.assertFalse(restoration_allowed(person, target, method="resurrection"))
        self.assertFalse(restoration_allowed(person, target, method="undead_transformation"))
        self.assertTrue(restoration_allowed(person, target, method="desejo"))

        release = {"operation_id": str(uuid.uuid4()), "creature_ref": target,
                   "current_hp": "0", "dead": "on"}
        release_url = reverse("personagem_liberar_ceifa", args=[person.pk])
        self.assertEqual(self.client.post(release_url, release).status_code, 302)
        self.assertTrue(reaping_state(person)["available"])
        self.assertEqual(TbOperacaoRecurso.objects.filter(id_personagem=person).count(), 3)

        owned.delete()
        self.assertIsNone(reaping_state(person))
        self.assertFalse(restoration_allowed(person, target, method="resurrection"))
        self.assertEqual(self.client.post(damage_url, dict(damage, operation_id=str(uuid.uuid4()))).status_code, 400)
