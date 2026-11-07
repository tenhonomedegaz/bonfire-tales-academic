"""Focused PostgreSQL checks for the Storm epic talent's real consumer."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.character_engine import derive
from home.epic_storm_save import STORM_SAVE_TAG, roll_storm_spell_save, storm_save_types
from home.epic_talent_catalog import epic_candidates
from home.models import TbClasse, TbPersonagem, TbPersonagemClasse, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class EpicStormSaveTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="storm-owner")
        self.other = get_user_model().objects.create_user(username="storm-other")
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome="Tempestade", pv_maximo=30, pv_atual=30)
        fighter = TbClasse.objects.create(
            nome="Classe tempestade", slug="classe-tempestade", dado_vida="d10")
        TbPersonagemClasse.objects.create(
            id_personagem=self.person, id_classe=fighter, nivel=1, principal=True)
        candidate = next(row for row in epic_candidates()
                         if row["slug"] == "dadiva-da-tempestade")
        self.talent = TbTalento.objects.create(**candidate)
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent, categoria="epico",
            nome=self.talent.nome, detalhes="talent_attr:CON")
        self.url = reverse("personagem_salvaguarda_tempestade", args=[self.person.pk])

    def roll(self, operation_id=None, **changes):
        data = {"operation_id": operation_id or uuid.uuid4(),
                "damage_type": "raio", "target_modifier": 3,
                "save_dc": 15, "target_has_advantage": False, "confirmed": True}
        data.update(changes)
        return roll_storm_spell_save(self.person, **data)

    def test_candidate_tags_and_passive_defenses_recalculate(self):
        self.assertEqual([issue for issue in validate_tags_json(
            self.talent.tags_json, Library()) if issue.level == ERROR], [])
        self.assertIn(STORM_SAVE_TAG, self.talent.tags_json)
        self.assertEqual(storm_save_types(self.person), ["raio", "trovejante"])
        self.assertIn("raio", derive(self.person)["resistencias"])
        self.person.pv_atual = 1
        self.person.save(update_fields=["pv_atual"])
        self.assertGreater(derive(self.person)["pv"]["maximo_calculado"], 2)
        self.assertIn("raio", derive(self.person)["imunidades"])
        self.grant.delete()
        self.assertEqual(storm_save_types(self.person), [])
        self.assertNotIn("raio", derive(self.person)["imunidades"])

    def test_server_rolls_disadvantage_and_replay_keeps_result(self):
        operation = uuid.uuid4()
        with patch("home.epic_storm_save.secrets.randbelow", side_effect=[16, 4]):
            first = self.roll(operation)
        self.assertEqual((first["rolls"], first["die"], first["total"],
                          first["succeeded"]), ([17, 5], 5, 8, False))
        with patch("home.epic_storm_save.secrets.randbelow",
                   side_effect=AssertionError("replay must not reroll")):
            self.assertTrue(self.roll(operation)["replayed"])
        with self.assertRaises(ValueError):
            self.roll(operation, save_dc=20)

    def test_target_advantage_cancels_disadvantage_without_extra_roll(self):
        with patch("home.epic_storm_save.secrets.randbelow", return_value=19) as roller:
            result = self.roll(damage_type="trovejante", target_has_advantage=True)
        self.assertEqual(result["rolls"], [20])
        self.assertTrue(result["succeeded"])
        self.assertEqual(roller.call_count, 1)
        with self.assertRaises(ValueError):
            self.roll(damage_type="fogo")
        self.grant.detalhes = ""
        self.grant.save(update_fields=["detalhes"])
        with self.assertRaises(ValueError):
            self.roll()

    def test_sheet_owner_can_roll_and_other_account_cannot(self):
        payload = {"operation_id": str(uuid.uuid4()), "damage_type": "raio",
                   "target_modifier": "2", "save_dc": "15", "confirmed": "on"}
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, payload).status_code, 404)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("ficha_detail", args=[self.person.pk])),
                            "Salvaguarda contra magia da Tempestade")
        with patch("home.epic_storm_save.secrets.randbelow", side_effect=[12, 3]):
            self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
