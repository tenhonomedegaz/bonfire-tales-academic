"""Combat consumers for the two Living Shadows tags."""

from django.test import SimpleTestCase

from home.epic_talent_catalog import ATTRIBUTE_TAGS, VERIFIED_EFFECTS, epic_candidates
from home.tag_engine.combat_encounter import CombatEncounter
from home.tag_engine.library import Library
from home.tag_engine.validator import validate_tags_json


EFFECTS = tuple(VERIFIED_EFFECTS['dadiva-das-sombras-vivas'])


def encounter(tags=EFFECTS):
    return CombatEncounter([
        {'id': 'shadow', 'team': 'allies', 'max_hp': 30,
         'offensive_tags': tags, 'defensive_tags': tags},
        {'id': 'enemy', 'team': 'enemies', 'max_hp': 30},
    ])


class LivingShadowsCombatTests(SimpleTestCase):
    def test_catalog_tags_and_markdown(self):
        self.assertEqual(validate_tags_json(EFFECTS, Library()), [])
        candidate = next(row for row in epic_candidates()
                         if row['slug'] == 'dadiva-das-sombras-vivas')
        self.assertEqual(candidate['tags_json'], ATTRIBUTE_TAGS + list(EFFECTS))
        self.assertIn('Extensão Sombria', candidate['descricao'])
        self.assertIn('Silhueta Dançante', candidate['descricao'])

    def test_attack_action_grants_reach_until_turn_end_and_stacks_other_source(self):
        game = encounter(EFFECTS + ('reach:+5ft',))
        game.start_turn('shadow', 'shadow-1')
        self.assertEqual(game.attack_reach_bonus('shadow'), 0)
        game.attack('enemy', (), hit=True, damage=1, melee_weapon=True)
        self.assertEqual(game.attack_reach_bonus('shadow'), 15)
        game.end_turn()
        self.assertEqual(game.attack_reach_bonus('shadow'), 0)
        game.start_turn('shadow', 'shadow-2')
        self.assertEqual(game.attack_reach_bonus('shadow'), 0)
        without = encounter(())
        without.start_turn('shadow', 'shadow-1')
        without.attack('enemy', (), hit=True, damage=1, melee_weapon=True)
        self.assertEqual(without.attack_reach_bonus('shadow'), 0)
        ranged = encounter()
        ranged.start_turn('shadow', 'shadow-1')
        ranged.attack('enemy', (), hit=True, damage=1, melee_weapon=False)
        self.assertEqual(ranged.attack_reach_bonus('shadow'), 0)

    def test_bonus_dodge_keeps_action_requires_disadvantage_and_expires(self):
        game = encounter()
        game.start_turn('shadow', 'shadow-1')
        self.assertTrue(game.bonus_action_dodge())
        self.assertFalse(game.action_used)
        self.assertEqual(game.dodge_defense('shadow'), {
            'attacks_disadvantage': True, 'dex_saves_advantage': True})
        with self.assertRaises(ValueError):
            game.bonus_action_dodge()
        game.attack('enemy', (), hit=True, damage=1)
        game.end_turn()
        game.start_turn('enemy', 'enemy-1')
        with self.assertRaises(ValueError):
            game.attack('shadow', (), hit=True, damage=1)
        game.attack('shadow', (), hit=True, damage=1,
                    dodge_disadvantage_applied=True)
        game.end_turn()
        game.start_turn('shadow', 'shadow-2')
        self.assertFalse(game.dodge_defense('shadow')['attacks_disadvantage'])
        without = encounter(())
        without.start_turn('shadow', 'shadow-1')
        with self.assertRaises(ValueError):
            without.bonus_action_dodge()
