"""Conditional light, resistance and invisibility for the night spirit gift."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from home.character_engine import derive
from home.epic_talent_catalog import ATTRIBUTE_TAGS, VERIFIED_EFFECTS, epic_candidates
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento
from home.tag_engine.combat_encounter import CombatEncounter
from home.tag_engine.library import Library
from home.tag_engine.validator import validate_tags_json


SLUG = "dadiva-do-espirito-noturno"


class NightSpiritTests(TestCase):
    def setUp(self):
        self.candidate = next(row for row in epic_candidates() if row["slug"] == SLUG)
        owner = get_user_model().objects.create_user(username="night-spirit-owner")
        self.person = TbPersonagem.objects.create(dono=owner, nome="Noturno")
        self.talent = TbTalento.objects.create(**self.candidate)
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, categoria="epico", detalhes="talent_attr:DES",
        )

    def encounter(self, tags=None, *, other_resistance=False):
        tags = tuple(self.talent.tags_json if tags is None else tags)
        if other_resistance:
            tags += ("resist:concussao",)
        return CombatEncounter([
            {"id": "night", "team": "allies", "max_hp": 50,
             "defensive_tags": tags, "offensive_tags": tags},
            {"id": "enemy", "team": "enemies", "max_hp": 50},
        ])

    def test_real_candidate_and_tags_are_complete(self):
        self.assertEqual(self.candidate["tags_json"],
                         ATTRIBUTE_TAGS + VERIFIED_EFFECTS[SLUG])
        self.assertIn("Um com as Sombras", self.candidate["descricao"])
        self.assertIn("Forma Sombria", self.candidate["descricao"])
        self.assertEqual(validate_tags_json(VERIFIED_EFFECTS[SLUG], Library()), [])
        self.assertNotIn("cortante", derive(self.person)["resistencias"])

    def test_light_controls_resistance_and_preserves_other_source(self):
        game = self.encounter(other_resistance=True)
        game.start_turn("enemy", "enemy-1")
        game.attack("night", (), hit=True, damage=10, damage_type="cortante")
        self.assertEqual(game.combatants["night"]["hp"], 40)
        game.end_turn()
        game.set_lighting("night", in_dim_light=True)
        game.start_turn("enemy", "enemy-2")
        game.attack("night", (), hit=True, damage=10, damage_type="cortante")
        self.assertEqual(game.combatants["night"]["hp"], 35)
        game.end_turn()
        game.set_lighting("night", in_dim_light=False)
        game.start_turn("enemy", "enemy-3")
        game.attack("night", (), hit=True, damage=10, damage_type="concussao")
        self.assertEqual(game.combatants["night"]["hp"], 30)
        game.end_turn()
        self.owned.delete()
        without_source = self.encounter(())
        without_source.set_lighting("night", in_dim_light=True)
        without_source.start_turn("enemy", "enemy-1")
        without_source.attack("night", (), hit=True, damage=10, damage_type="cortante")
        self.assertEqual(without_source.combatants["night"]["hp"], 40)

    def test_bonus_invisibility_affects_attacks_and_ends_on_action(self):
        game = self.encounter()
        game.start_turn("night", "night-1")
        with self.assertRaises(ValueError):
            game.bonus_action_invisibility()
        self.assertFalse(game.bonus_action_used)
        game.set_lighting("night", in_dim_light=True)
        self.assertTrue(game.bonus_action_invisibility())
        self.assertTrue(game.invisibility_state("night"))
        self.assertFalse(game.action_used)
        game.set_lighting("night", in_dim_light=False)
        with self.assertRaises(ValueError):
            game.attack("enemy", (), hit=True, damage=1)
        self.assertTrue(game.invisibility_state("night"))
        game.attack("enemy", (), hit=True, damage=1,
                    invisible_advantage_applied=True)
        self.assertFalse(game.invisibility_state("night"))
        game.end_turn()
        game.set_lighting("night", in_dim_light=True)
        game.start_turn("night", "night-2")
        game.bonus_action_invisibility()
        game.end_turn()
        game.start_turn("enemy", "enemy-1")
        with self.assertRaises(ValueError):
            game.attack("night", (), hit=True, damage=1)
        game.attack("night", (), hit=True, damage=1,
                    invisible_disadvantage_applied=True)
        self.assertTrue(game.invisibility_state("night"))
        game.register_action("night", "reaction")
        self.assertFalse(game.invisibility_state("night"))

    def test_external_action_and_source_removal_block_reactivation(self):
        game = self.encounter()
        game.set_lighting("night", in_dim_light=True)
        game.start_turn("night", "night-1")
        game.bonus_action_invisibility()
        game.register_action("night", "action")
        self.assertFalse(game.invisibility_state("night"))
        with self.assertRaises(ValueError):
            game.bonus_action_invisibility()
        game.end_turn()
        without_source = self.encounter(())
        without_source.set_lighting("night", in_dim_light=True)
        without_source.start_turn("night", "night-1")
        with self.assertRaises(ValueError):
            without_source.bonus_action_invisibility()

    def test_healing_temporary_hp_and_other_bonus_action_end_invisibility(self):
        tags = tuple(self.talent.tags_json) + tuple(
            VERIFIED_EFFECTS["dadiva-das-sombras-vivas"])
        game = self.encounter(tags)
        game.set_lighting("night", in_dim_light=True)
        game.start_turn("night", "night-1")
        game.bonus_action_invisibility()
        game.end_turn()
        game.start_turn("night", "night-2")
        game.bonus_action_dodge()
        self.assertFalse(game.invisibility_state("night"))
        game.end_turn()
        game.start_turn("night", "night-3")
        game.bonus_action_invisibility()
        game.heal("night", 1)
        self.assertFalse(game.invisibility_state("night"))
        game.end_turn()
        game.start_turn("night", "night-4")
        game.bonus_action_invisibility()
        game.grant_temporary_hp("night", 3)
        self.assertFalse(game.invisibility_state("night"))
