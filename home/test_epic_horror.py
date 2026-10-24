"""Horror's partial tags and battle consumers remain outside publication."""

from django.test import SimpleTestCase

from home.epic_talent_catalog import PARTIAL_EFFECTS, epic_candidates
from home.tag_engine.combat_encounter import CombatEncounter
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


HORROR_TAGS = PARTIAL_EFFECTS['dadiva-do-horror']


def encounter(tags=None):
    return CombatEncounter([
        {'id': 'horror', 'team': 'allies', 'max_hp': 40,
         'offensive_tags': HORROR_TAGS if tags is None else tags,
         'tag_context': {'pb': 6, 'spell_mod': 5, 'cha_mod': 3}},
        {'id': 'enemy', 'team': 'enemies', 'max_hp': 50},
        {'id': 'friend', 'team': 'allies', 'max_hp': 50},
    ])


class EpicHorrorTests(SimpleTestCase):
    def test_partial_definition_is_valid_and_not_published(self):
        self.assertNotIn('dadiva-do-horror', {row['slug'] for row in epic_candidates()})
        self.assertEqual(len(HORROR_TAGS), 3)
        self.assertFalse(any(tag.startswith('pick:') for tag in HORROR_TAGS))
        self.assertFalse([d for d in validate_tags_json(HORROR_TAGS, Library())
                          if d.level == ERROR])

    def test_failed_save_enforces_rolls_and_full_flee_until_next_source_turn(self):
        game = encounter()
        game.start_turn('horror', 'h1')
        game.attack('enemy', (), hit=True, damage=5)
        self.assertEqual(game.inflict_horror('enemy', wisdom_save_total=18,
                                             ability='spell'), {'dc': 19, 'failed': True})
        self.assertTrue(game.horror_state('enemy')['attack_disadvantage'])
        self.assertTrue(game.horror_state('enemy')['ability_check_disadvantage'])
        with self.assertRaises(ValueError):
            game.inflict_horror('enemy', wisdom_save_total=1, ability='cha')
        game.end_turn()
        game.start_turn('enemy', 'e1')
        with self.assertRaises(ValueError):
            game.attack('horror', (), hit=True, damage=1)
        game.attack('horror', (), hit=True, damage=1,
                    horror_disadvantage_applied=True)
        with self.assertRaises(ValueError):
            game.end_turn()
        with self.assertRaises(ValueError):
            game.record_horror_flee('enemy', available_ft=30, spent_ft=20)
        self.assertEqual(game.record_horror_flee(
            'enemy', available_ft=30, spent_ft=30), 30)
        game.end_turn()
        game.start_turn('horror', 'h2')
        self.assertFalse(game.horror_state('enemy')['must_flee'])
        self.assertFalse(game.horror_state('enemy')['attack_disadvantage'])

    def test_success_and_non_source_do_not_apply(self):
        game = encounter()
        game.start_turn('horror', 'h1')
        game.attack('enemy', (), hit=True, damage=5)
        self.assertEqual(game.inflict_horror('enemy', wisdom_save_total=19,
                                             ability='spell')['failed'], False)
        self.assertEqual(game.horror_state('enemy')['sources'], ())
        game.end_turn()
        game.start_turn('horror', 'h2')
        game.attack('friend', (), hit=True, damage=1)
        with self.assertRaises(ValueError):
            game.inflict_horror('friend', wisdom_save_total=1, ability='cha')
        no_source = encounter(tags=())
        no_source.start_turn('horror', 'h1')
        no_source.attack('enemy', (), hit=True, damage=3)
        with self.assertRaises(ValueError):
            no_source.inflict_horror('enemy', wisdom_save_total=1, ability='cha')

    def test_hit_without_damage_cannot_trigger(self):
        game = encounter()
        game.start_turn('horror', 'h1')
        game.attack('enemy', (), hit=True, damage=0)
        with self.assertRaises(ValueError):
            game.inflict_horror('enemy', wisdom_save_total=1, ability='cha')
