import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from home.tag_engine import CombatEncounter


def beard_tags():
    manifest = json.loads((Path(settings.BASE_DIR) /
        "ref/bestiario/retagging_veneno_turno_fonte_20261001.json").read_text(
            encoding="utf-8"))
    devil = next(row for row in manifest["rows"] if row["slug"] == "bearded-devil")
    return next(feature["tags"] for feature in devil["features"]
                if feature["name_en"] == "Beard")


class CombatEncounterTests(SimpleTestCase):
    def make_encounter(self):
        return CombatEncounter([
            {"id": "diabo", "team": "monstros", "max_hp": 9},
            {"id": "heroi", "team": "grupo", "max_hp": 20},
            {"id": "curandeiro", "team": "grupo", "max_hp": 15},
        ])

    def test_full_encounter_expires_poison_on_attacker_turn_and_releases_healing(self):
        encounter = self.make_encounter()
        self.assertTrue(encounter.start_turn("diabo", "rodada-1"))
        result = encounter.attack("heroi", beard_tags(), hit=True, damage=4)
        self.assertTrue(any(op.active and op.op == "apply_condition"
                            for op in result.operations))
        self.assertEqual(encounter.combatants["heroi"]["hp"], 16)
        encounter.end_turn()

        encounter.start_turn("curandeiro", "rodada-1")
        self.assertFalse(encounter.heal("heroi", 5))
        self.assertEqual(encounter.combatants["heroi"]["hp"], 16)
        encounter.end_turn()

        encounter.start_turn("heroi", "rodada-1")
        self.assertEqual(encounter.conditions.facts("heroi", "diabo"),
                         {"envenenado": {"self"}})
        encounter.attack("diabo", [], hit=True, damage=3)
        encounter.end_turn()
        self.assertFalse(encounter.start_turn("diabo", "rodada-1"))
        self.assertTrue(encounter.start_turn("diabo", "rodada-2"))
        self.assertEqual(encounter.conditions.facts("heroi", "diabo"), {})
        encounter.end_turn()

        encounter.start_turn("curandeiro", "rodada-2")
        self.assertTrue(encounter.heal("heroi", 5))
        self.assertEqual(encounter.combatants["heroi"]["hp"], 20)
        encounter.end_turn()
        encounter.start_turn("heroi", "rodada-2")
        encounter.attack("diabo", [], hit=True, damage=6)
        self.assertTrue(encounter.finished)
        self.assertEqual(encounter.combatants["diabo"]["hp"], 0)
        self.assertEqual(encounter.events[-1], ("encounter_end", "grupo"))
        with self.assertRaises(ValueError):
            encounter.start_turn("curandeiro", "rodada-3")

    def test_miss_never_applies_condition_and_other_target_can_be_healed(self):
        encounter = self.make_encounter()
        encounter.start_turn("diabo", 1)
        self.assertIsNone(encounter.attack("heroi", beard_tags(), hit=False))
        encounter.end_turn()
        encounter.start_turn("curandeiro", 1)
        self.assertTrue(encounter.heal("heroi", 5))
        self.assertFalse(encounter.conditions.blocks_healing("heroi"))

    def test_invalid_or_repeated_action_does_not_change_health_or_condition(self):
        encounter = self.make_encounter()
        encounter.start_turn("diabo", 1)
        with self.assertRaises(ValueError):
            encounter.attack("heroi", beard_tags(), hit=False, damage=4)
        self.assertEqual(encounter.combatants["heroi"]["hp"], 20)
        self.assertFalse(encounter.conditions.blocks_healing("heroi"))
        encounter.attack("heroi", beard_tags(), hit=True, damage=1)
        with self.assertRaises(ValueError):
            encounter.attack("heroi", beard_tags(), hit=True, damage=1)
        self.assertEqual(encounter.combatants["heroi"]["hp"], 19)
        self.assertTrue(encounter.conditions.blocks_healing("heroi"))

    def test_two_sources_keep_healing_blocked_until_both_turns_expire(self):
        encounter = CombatEncounter([
            {"id": "diabo-a", "team": "monstros", "max_hp": 10},
            {"id": "diabo-b", "team": "monstros", "max_hp": 10},
            {"id": "heroi", "team": "grupo", "max_hp": 20, "hp": 10},
            {"id": "curandeiro", "team": "grupo", "max_hp": 15},
        ])
        for actor in ("diabo-a", "diabo-b"):
            encounter.start_turn(actor, 1)
            encounter.attack("heroi", beard_tags(), hit=True, damage=0)
            encounter.end_turn()
        encounter.start_turn("curandeiro", 1)
        self.assertFalse(encounter.heal("heroi", 5))
        encounter.end_turn()
        encounter.start_turn("diabo-a", 2)
        encounter.end_turn()
        encounter.start_turn("curandeiro", 2)
        self.assertFalse(encounter.heal("heroi", 5))
        encounter.end_turn()
        encounter.start_turn("diabo-b", 2)
        encounter.end_turn()
        encounter.start_turn("curandeiro", 3)
        self.assertTrue(encounter.heal("heroi", 5))
        self.assertEqual(encounter.combatants["heroi"]["hp"], 15)
