"""Runtime coverage for generic temporary-HP modifiers used by Saúde Abundante."""

from django.test import SimpleTestCase

from home.epic_talent_catalog import PARTIAL_EFFECTS
from home.tag_engine.combat_encounter import CombatEncounter


HEALTHY_TEMP_HP = tuple(PARTIAL_EFFECTS["dadiva-da-saude-abundante"])


def encounter(tags=(), *, temp_hp=0):
    return CombatEncounter([
        {"id": "ally", "team": "group", "max_hp": 20},
        {"id": "bearer", "team": "group", "max_hp": 20,
         "temp_hp": temp_hp, "defensive_tags": tags},
        {"id": "enemy", "team": "enemy", "max_hp": 20},
    ])


class EpicHealthTemporaryHpTests(SimpleTestCase):
    def receive(self, combat, amount):
        turn = 1 + sum(event[0] == "turn_start" for event in combat.events)
        combat.start_turn("ally", turn)
        received = combat.grant_temporary_hp("bearer", amount)
        combat.end_turn()
        return received

    def test_application_adds_five_to_temporary_hp_received(self):
        combat = encounter(HEALTHY_TEMP_HP)

        self.assertEqual(self.receive(combat, 7), 12)
        self.assertEqual(combat.combatants["bearer"]["temp_hp"], 12)

    def test_removing_tag_removes_temporary_hp_bonus(self):
        combat = encounter()

        self.assertEqual(self.receive(combat, 7), 7)
        self.assertEqual(combat.combatants["bearer"]["temp_hp"], 7)

    def test_coexists_with_other_generic_temporary_hp_modifier(self):
        combat = encounter(HEALTHY_TEMP_HP + ("always_active{temp_hp:+2}",))

        self.assertEqual(self.receive(combat, 7), 14)
        self.assertEqual(combat.combatants["bearer"]["temp_hp"], 14)

    def test_repeating_receipt_replaces_instead_of_accumulating(self):
        combat = encounter(HEALTHY_TEMP_HP)

        self.receive(combat, 7)
        combat.start_turn("enemy", 1)
        combat.end_turn()
        self.assertEqual(self.receive(combat, 7), 12)
        self.assertEqual(combat.combatants["bearer"]["temp_hp"], 12)

    def test_temporary_hp_absorbs_damage_before_current_hp(self):
        combat = encounter(HEALTHY_TEMP_HP)
        self.receive(combat, 7)
        combat.start_turn("enemy", 1)
        combat.attack("bearer", (), hit=True, damage=9)

        self.assertEqual(combat.combatants["bearer"]["temp_hp"], 3)
        self.assertEqual(combat.combatants["bearer"]["hp"], 20)
