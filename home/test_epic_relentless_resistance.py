"""PostgreSQL-isolated checks for the Relentless Resistance tag runtime."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from home.epic_relentless_resistance import (
    ALTER_RUIN_TAG, CHOICE_STATE_KEY, DAMAGE_TYPES, RESISTANCE_TAG,
    alter_ruin, choose_resistances, reset_alter_ruin_on_round, resistance_state,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS, epic_candidates
from home.models import TbPersonagem, TbPersonagemEstado, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import validate_tags_json


class RelentlessResistanceTests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        owner = get_user_model().objects.create_user(username=f"relentless-resistance-{uuid.uuid4()}")
        self.person = TbPersonagem.objects.create(dono=owner, nome="Inabalável", nivel=17,
                                                   constituicao=18)
        self.talent = TbTalento.objects.create(
            nome="Fonte sintética", slug=f"relentless-resistance-{uuid.uuid4()}", tipo="geral",
            tags_json=ATTRIBUTE_TAGS + [RESISTANCE_TAG, ALTER_RUIN_TAG])
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent, nome=self.talent.nome,
            detalhes="talent_attr:CON")

    def choose(self, operation_id=None, **changes):
        payload = {"operation_id": operation_id or uuid.uuid4(),
                   "damage_types": ["fogo", "veneno"]}
        payload.update(changes)
        return choose_resistances(self.person, **payload)

    def use(self, operation_id=None, **changes):
        payload = {"operation_id": operation_id or uuid.uuid4(), "round_ref": "encounter:round:1",
                   "damage_type": "fogo", "damage_received": True, "target_distance_ft": 60,
                   "target_visible": True, "target_has_total_cover": False,
                   "target_save_modifier": 0, "declared_modifier": "constitution"}
        payload.update(changes)
        with patch("home.epic_relentless_resistance.secrets.randbelow", side_effect=[9, 0, 1, 2]):
            return alter_ruin(self.person, **payload)

    def test_two_distinct_choices_upgrade_existing_other_resistance(self):
        other = TbTalento.objects.create(nome="Outra fonte", slug=f"other-resist-{uuid.uuid4()}",
                                         tipo="geral", tags_json=["resist:fogo"])
        TbPersonagemTalento.objects.create(id_personagem=self.person, id_talento=other,
                                           nome=other.nome)
        result = self.choose()
        self.assertEqual(result["types"], ["fogo", "veneno"])
        self.assertEqual(result["defenses"], [
            {"damage_type": "fogo", "defense": "immune", "upgraded": True,
             "other_defense": "resist"},
            {"damage_type": "veneno", "defense": "resist", "upgraded": False,
             "other_defense": "none"},
        ])
        with self.assertRaises(ValueError):
            self.choose(damage_types=["fogo", "fogo"])
        self.assertEqual(set(resistance_state(self.person)["available_types"]), set(DAMAGE_TYPES))
        from home.character_engine import derive
        sheet = derive(self.person)
        self.assertIn("veneno", sheet["resistencias"])
        self.assertIn("fogo", sheet["imunidades"])

    def test_swap_requires_long_rest_and_commands_are_idempotent(self):
        operation = uuid.uuid4()
        first = self.choose(operation)
        replay = self.choose(operation)
        self.assertEqual(replay, dict(first, replayed=True))
        with self.assertRaises(ValueError):
            self.choose(damage_types=["frio", "raio"])
        changed = self.choose(damage_types=["frio", "raio"], long_rest_ref="rest:7",
                              long_rest_confirmed=True)
        self.assertTrue(changed["changed"])
        self.assertEqual(changed["types"], ["frio", "raio"])
        self.assertEqual(TbPersonagemEstado.objects.get(chave=CHOICE_STATE_KEY).payload_json["types"],
                         ["frio", "raio"])

    def test_alter_ruin_uses_declared_modifier_cd_and_free_reaction_once_per_round(self):
        self.choose()
        result = self.use()
        self.assertEqual(result["declared_modifier"], "constitution")
        self.assertEqual(result["modifier"], 5)
        self.assertEqual(result["save_dc"], 19)
        self.assertEqual(result["dice"], [1, 2, 3])
        self.assertEqual(result["damage"], 11)
        self.assertFalse(result["reaction_spent"])
        with self.assertRaises(ValueError):
            self.use()
        reset_alter_ruin_on_round(self.person, operation_id=uuid.uuid4(),
                                  round_ref="encounter:round:2", confirmed=True)
        self.use(round_ref="encounter:round:2")

    def test_reaction_checks_range_sight_cover_duplicate_and_source_removal(self):
        self.choose()
        for changes in ({"target_distance_ft": 61}, {"target_visible": False},
                        {"target_has_total_cover": True}, {"damage_type": "frio"}):
            with self.assertRaises(ValueError):
                self.use(**changes)
        operation = uuid.uuid4()
        first = self.use(operation)
        self.assertEqual(self.use(operation), dict(first, replayed=True))
        self.owned.delete()
        self.assertIsNone(resistance_state(self.person))
        with self.assertRaises(ValueError):
            self.use(round_ref="encounter:round:2")

    def test_real_candidate_has_valid_tags(self):
        candidate = next(row for row in epic_candidates()
                         if row["slug"] == "dadiva-da-resistencia-implacavel")
        self.assertIn("Alterar Ruína", candidate["descricao"])
        self.assertEqual(validate_tags_json(candidate["tags_json"], Library()), [])
