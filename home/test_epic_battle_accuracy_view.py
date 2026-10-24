"""The sheet consumes battle accuracy tags without granting the effect by name."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_battle_accuracy import (
    AUTO_HIT_TAG, NO_DISADVANTAGE_TAG, attack_accuracy_state,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS, epic_candidates
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class BattleAccuracyViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="battle-accuracy-owner")
        self.other = get_user_model().objects.create_user(username="battle-accuracy-other")
        self.person = TbPersonagem.objects.create(dono=self.owner, nome="Combatente")
        self.talent = TbTalento.objects.create(
            nome="Fonte sintética de ataque", slug="synthetic-battle-accuracy",
            tipo="geral", tags_json=ATTRIBUTE_TAGS +
            [NO_DISADVANTAGE_TAG, AUTO_HIT_TAG],
        )
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:FOR",
        )
        self.roll_url = reverse("personagem_rolar_ataque_epico", args=[self.person.pk])
        self.hit_url = reverse("personagem_converter_ataque_epico", args=[self.person.pk])
        self.turn_url = reverse("personagem_iniciar_turno_ataque_epico", args=[self.person.pk])
        self.sheet_url = reverse("ficha_detail", args=[self.person.pk])

    def test_roll_convert_reset_and_source_removal(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.sheet_url), "Rolar ataque")
        roll_id = uuid.uuid4()
        with patch("home.epic_battle_accuracy.secrets.randbelow", return_value=6) as dice:
            rolled = self.client.post(self.roll_url, {
                "operation_id": str(roll_id), "disadvantage": "on",
            }, follow=True)
        dice.assert_called_once_with(20)
        self.assertContains(rolled, "D20 aplicado no ataque: 7")
        self.assertContains(rolled, "Escolher acertar")
        hit_id = uuid.uuid4()
        hit_data = {"operation_id": str(hit_id),
                    "attack_operation_id": str(roll_id), "miss_confirmed": "on"}
        self.assertEqual(self.client.post(self.hit_url, hit_data).status_code, 302)
        self.assertFalse(attack_accuracy_state(self.person)["auto_hit_available"])
        self.assertEqual(self.client.post(self.hit_url, dict(
            hit_data, operation_id=str(uuid.uuid4()))).status_code, 400)
        self.assertEqual(self.client.post(self.turn_url, {
            "operation_id": str(uuid.uuid4()), "turn_ref": "combate:turno-2",
            "confirmed": "on",
        }).status_code, 302)
        self.assertTrue(attack_accuracy_state(self.person)["auto_hit_available"])
        self.grant.delete()
        self.assertNotContains(self.client.get(self.sheet_url), "Rolar ataque")

    def test_other_owner_and_unrecorded_roll_cannot_convert(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.roll_url, {
            "operation_id": str(uuid.uuid4()),
        }).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.hit_url, {
            "operation_id": str(uuid.uuid4()),
            "attack_operation_id": str(uuid.uuid4()), "miss_confirmed": "on",
        }).status_code, 400)

    def test_attribute_choice_gates_attack_source(self):
        self.client.force_login(self.owner)
        self.grant.detalhes = ""
        self.grant.save(update_fields=["detalhes"])
        self.assertNotContains(self.client.get(self.sheet_url), "Rolar ataque")
        self.assertEqual(self.client.post(self.roll_url, {
            "operation_id": str(uuid.uuid4()),
        }).status_code, 400)

    def test_candidate_matches_source_and_validates_tags(self):
        candidate = next(row for row in epic_candidates()
                         if row["slug"] == "dadiva-da-aptidao-de-batalha")
        self.assertEqual(candidate["tags_json"], ATTRIBUTE_TAGS +
                         [NO_DISADVANTAGE_TAG, AUTO_HIT_TAG])
        self.assertIn("**Mão Firme:**", candidate["descricao"])
        self.assertIn("**Precisão Inigualável:**", candidate["descricao"])
        self.assertEqual([issue for issue in validate_tags_json(
            candidate["tags_json"], Library()) if issue.level == ERROR], [])
