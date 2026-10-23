"""Runtime contracts for the generic tags used by Dádiva da Tempestade."""

from django.test import SimpleTestCase

from home.epic_talent_catalog import PARTIAL_EFFECTS, epic_candidates
from home.tag_engine.combat_encounter import CombatEncounter
from home.tag_engine.evaluator import evaluate_tags


TEMPEST_DEFENSES = tuple(PARTIAL_EFFECTS["dadiva-da-tempestade"])


def encounter(*, hp, defensive_tags=TEMPEST_DEFENSES):
    return CombatEncounter([
        {"id": "adversario", "team": "oponentes", "max_hp": 20},
        {"id": "portador", "team": "grupo", "max_hp": 20, "hp": hp,
         "defensive_tags": defensive_tags},
    ])


class EpicTempestDefensesTests(SimpleTestCase):
    def test_talento_permanece_fora_da_carga_ate_todos_os_efeitos(self):
        self.assertNotIn("dadiva-da-tempestade", {
            row["slug"] for row in epic_candidates()
        })

    def _take_damage(self, combat, damage_type, damage=7):
        combat.start_turn("adversario", 1)
        combat.attack("portador", (), hit=True, damage=damage,
                      damage_type=damage_type)

    def test_resists_lightning_and_thunder_while_not_bloodied(self):
        for damage_type in ("raio", "trovejante"):
            with self.subTest(damage_type=damage_type):
                combat = encounter(hp=20)
                self._take_damage(combat, damage_type)
                self.assertEqual(combat.combatants["portador"]["hp"], 17)

    def test_is_immune_to_only_those_types_while_bloodied(self):
        for damage_type in ("raio", "trovejante"):
            with self.subTest(damage_type=damage_type):
                combat = encounter(hp=10)
                self._take_damage(combat, damage_type)
                self.assertEqual(combat.combatants["portador"]["hp"], 10)

    def test_coexists_with_other_generic_defenses(self):
        combat = encounter(hp=10, defensive_tags=TEMPEST_DEFENSES + (
            "always_active{resist:frio}",
        ))
        self._take_damage(combat, "frio")
        self.assertEqual(combat.combatants["portador"]["hp"], 7)

    def test_removing_the_tags_removes_their_effect(self):
        combat = encounter(hp=10, defensive_tags=())
        self._take_damage(combat, "raio")
        self.assertEqual(combat.combatants["portador"]["hp"], 3)

    def test_duplicate_tags_are_idempotent(self):
        result = evaluate_tags(TEMPEST_DEFENSES * 2, {
            "resolve_runtime": True,
            "event": "take_damage",
            "self_hp": 20,
            "self_max_hp": 20,
        })
        self.assertEqual(result.state["resistencias"], ["raio", "trovejante"])
        self.assertNotIn("imunidades", result.state)

    def test_uses_generic_tags_without_a_talent_name(self):
        result = evaluate_tags(TEMPEST_DEFENSES, {
            "resolve_runtime": True,
            "event": "take_damage",
            "self_hp": 10,
            "self_max_hp": 20,
        })
        self.assertEqual(result.state["resistencias"], ["raio", "trovejante"])
        self.assertEqual(result.state["imunidades"], ["raio", "trovejante"])
