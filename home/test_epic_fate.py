"""Focused PostgreSQL checks for fate tag consumers."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from home.epic_fate import (
    ALTER_FATE_TAG, REVERBERANT_FATE_TAG, alter_fate, fate_state,
    recover_fate, reset_fate_on_initiative,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS, epic_candidates
from home.epic_battle_accuracy import roll_tagged_attack
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import validate_tags_json


class FateTests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.owner = get_user_model().objects.create_user(username=f"fate-{uuid.uuid4()}")
        self.person = TbPersonagem.objects.create(dono=self.owner, nome="Norna")
        talent = TbTalento.objects.create(
            nome="Fonte sintética", slug=f"synthetic-fate-{uuid.uuid4()}",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [ALTER_FATE_TAG, REVERBERANT_FATE_TAG])
        self.choice = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=talent, nome=talent.nome,
            detalhes="talent_attr:DES")

    def use(self, **changes):
        args = dict(operation_id=uuid.uuid4(), roll_ref=str(uuid.uuid4()),
                    distance_ft=60, direction="increase", d20_result_confirmed=True)
        args.update(changes)
        return alter_fate(self.person, **args)

    def test_use_recovery_direction_receipt_and_initiative(self):
        operation = uuid.uuid4()
        with patch("home.epic_fate.secrets.randbelow", side_effect=[0, 3]) as roll:
            first = self.use(operation_id=operation, roll_ref="encounter-1:roll-1")
            replay = self.use(operation_id=operation, roll_ref="encounter-1:roll-1")
        self.assertEqual(first["dice"], [1, 4])
        self.assertEqual(first["modifier"], 5)
        self.assertEqual(replay, dict(first, replayed=True))
        self.assertEqual(roll.call_count, 2)
        self.assertFalse(fate_state(self.person)["available"])
        with self.assertRaises(ValueError):
            self.use()
        with self.assertRaises(ValueError):
            self.use(roll_ref="encounter-1:roll-1")
        critical = recover_fate(
            self.person, operation_id=uuid.uuid4(), event_ref="encounter-1:critical-1",
            natural_d20=20, own_roll_confirmed=True, critical_confirmed=True)
        self.assertTrue(critical["recovered"])
        self.assertEqual(fate_state(self.person)["direction"], "decrease")
        with self.assertRaises(ValueError):
            self.use(direction="increase")
        second = self.use(direction="decrease")
        self.assertLess(second["modifier"], 0)
        reset_fate_on_initiative(self.person, operation_id=uuid.uuid4(),
                                 initiative_ref="encounter-2:initiative", confirmed=True)
        self.assertEqual(fate_state(self.person), {"available": True, "direction": None,
                         "dice": "2d4", "range_ft": 60, "recover_on_critical": True})
        self.assertGreater(self.use()["modifier"], 0)

    def test_source_removal_range_critical_and_duplicate_gates(self):
        for changes in ({"distance_ft": 61}, {"distance_ft": -1},
                        {"d20_result_confirmed": False}):
            with self.assertRaises(ValueError):
                self.use(**changes)
        with self.assertRaises(ValueError):
            recover_fate(self.person, operation_id=uuid.uuid4(), event_ref="bad",
                         natural_d20=19, own_roll_confirmed=True, critical_confirmed=True)
        with self.assertRaises(ValueError):
            recover_fate(self.person, operation_id=uuid.uuid4(), event_ref="bad",
                         natural_d20=1, own_roll_confirmed=False, critical_confirmed=True)
        self.use()
        recover_fate(self.person, operation_id=uuid.uuid4(), event_ref="critical-1",
                     natural_d20=1, own_roll_confirmed=True, critical_confirmed=True)
        self.assertEqual(fate_state(self.person)["direction"], "increase")
        with self.assertRaises(ValueError):
            recover_fate(self.person, operation_id=uuid.uuid4(), event_ref="critical-1",
                         natural_d20=1, own_roll_confirmed=True, critical_confirmed=True)
        self.choice.delete()
        self.assertIsNone(fate_state(self.person))
        with self.assertRaises(ValueError):
            self.use()

    def test_owner_only_and_sheet_form(self):
        self.client.force_login(self.owner)
        page = self.client.get(reverse("ficha_detail", args=[self.person.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Alterar Destino")
        response = self.client.post(reverse("personagem_alterar_destino", args=[self.person.pk]), {
            "operation_id": str(uuid.uuid4()), "roll_ref": "table-roll-1", "distance_ft": "10",
            "direction": "increase", "confirmed": "on"})
        self.assertEqual(response.status_code, 302)
        stranger = get_user_model().objects.create_user(username=f"other-{uuid.uuid4()}")
        self.client.force_login(stranger)
        self.assertNotEqual(self.client.post(
            reverse("personagem_iniciativa_destino", args=[self.person.pk]), {
                "operation_id": str(uuid.uuid4()), "initiative_ref": "other",
                "confirmed": "on"}).status_code, 302)

    def test_real_candidate_and_rest_lifecycle(self):
        candidate = next(row for row in epic_candidates()
                         if row["slug"] == "dadiva-do-destino")
        self.assertIn("Causalidade Reverberante", candidate["descricao"])
        self.assertEqual(candidate["tags_json"][:2], ATTRIBUTE_TAGS)
        self.assertEqual(validate_tags_json(candidate["tags_json"], Library()), [])
        source = TbTalento.objects.create(**candidate)
        self.choice.id_talento = source
        self.choice.nome = source.nome
        self.choice.save(update_fields=["id_talento", "nome"])
        self.use()
        from home.resource_engine import end_states_on
        end_states_on(self.person, "short_rest")
        self.assertEqual(fate_state(self.person), {"available": True, "direction": None,
                         "dice": "2d4", "range_ft": 60, "recover_on_critical": True})
        self.use()
        self.choice.delete()
        self.assertIsNone(fate_state(self.person))

    def test_attack_roll_automatically_recovers_only_applied_natural_critical(self):
        self.use()
        operation = uuid.uuid4()
        with patch("home.epic_battle_accuracy.secrets.randbelow", return_value=19):
            attack = roll_tagged_attack(self.person, operation_id=operation)
        self.assertEqual(attack["applied_d20"], 20)
        self.assertTrue(attack["fate_recovered"])
        self.assertEqual(fate_state(self.person)["direction"], "decrease")
        self.assertEqual(roll_tagged_attack(self.person, operation_id=operation),
                         dict(attack, replayed=True))
        self.use(direction="decrease")
        with patch("home.epic_battle_accuracy.secrets.randbelow", side_effect=[0, 9]):
            advantage = roll_tagged_attack(
                self.person, operation_id=uuid.uuid4(), advantage=True)
        self.assertEqual(advantage["applied_d20"], 10)
        self.assertNotIn("fate_recovered", advantage)
        self.assertFalse(fate_state(self.person)["available"])
        with patch("home.epic_battle_accuracy.secrets.randbelow", return_value=0):
            failure = roll_tagged_attack(self.person, operation_id=uuid.uuid4())
        self.assertTrue(failure["fate_recovered"])
        self.assertEqual(fate_state(self.person)["direction"], "increase")

    def test_fate_only_attack_card_shows_server_roll_and_recovery(self):
        self.use()
        self.client.force_login(self.owner)
        with patch("home.epic_battle_accuracy.secrets.randbelow", return_value=19):
            response = self.client.post(
                reverse("personagem_rolar_ataque_epico", args=[self.person.pk]),
                {"operation_id": str(uuid.uuid4())}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "D20 aplicado no ataque: 20")
        self.assertTrue(fate_state(self.person)["available"])
        self.assertEqual(fate_state(self.person)["direction"], "decrease")
