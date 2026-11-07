"""Horror's catalog tags and table-resolved battle consumers."""

from django.test import SimpleTestCase

from home.epic_talent_catalog import ATTRIBUTE_TAGS, epic_candidates
from home.tag_engine.combat_encounter import CombatEncounter
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


TALENT = next(row for row in epic_candidates() if row['slug'] == 'dadiva-do-horror')
HORROR_TAGS = TALENT['tags_json']


def encounter(tags=None):
    return CombatEncounter([
        {'id': 'horror', 'team': 'allies', 'max_hp': 40,
         'offensive_tags': HORROR_TAGS if tags is None else tags,
         'tag_context': {'pb': 6, 'spell_mod': 5, 'cha_mod': 3}},
        {'id': 'enemy', 'team': 'enemies', 'max_hp': 50},
        {'id': 'friend', 'team': 'allies', 'max_hp': 50},
    ])


class EpicHorrorTests(SimpleTestCase):
    def test_real_definition_has_source_text_and_valid_tags(self):
        self.assertIn('Verdadeiro Horror', TALENT['descricao'])
        self.assertEqual(HORROR_TAGS[:2], ATTRIBUTE_TAGS)
        self.assertEqual(len(HORROR_TAGS), 5)
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
            game.record_ability_check('enemy', disadvantage_applied=False)
        game.record_ability_check('enemy', disadvantage_applied=True)
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
        game.record_ability_check('enemy', disadvantage_applied=False)

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

    def test_magic_damage_applies_hp_and_horror_once_per_turn(self):
        game = encounter()
        game.start_turn('horror', 'h1')
        with self.assertRaises(ValueError):
            game.record_action_damage('horror', 'enemy', damage=4)
        game.register_action('horror', 'action', action_kind='magic')
        self.assertEqual(game.record_action_damage(
            'horror', 'enemy', damage=7, damage_type='fire'), 7)
        self.assertEqual(game.combatants['enemy']['hp'], 43)
        self.assertEqual(game.inflict_horror(
            'enemy', wisdom_save_total=16, ability='cha'),
            {'dc': 17, 'failed': True})
        with self.assertRaises(ValueError):
            game.record_action_damage('horror', 'enemy', damage=7)
        game.end_turn()
        game.start_turn('enemy', 'e1')
        game.register_action('horror', 'reaction')
        with self.assertRaises(ValueError):
            game.record_action_damage('horror', 'enemy', damage=-1)
        self.assertEqual(game.record_action_damage(
            'horror', 'enemy', damage=3), 3)
        self.assertEqual(game.inflict_horror(
            'enemy', wisdom_save_total=16, ability='cha')['failed'], True)
        self.assertEqual(game.combatants['enemy']['hp'], 40)

    def test_non_attack_damage_respects_immunity_and_target_provenance(self):
        game = encounter()
        game.start_turn('horror', 'h1')
        game.register_action('horror', 'action', action_kind='magic')
        with self.assertRaises(ValueError):
            game.record_action_damage('friend', 'enemy', damage=5)
        self.assertEqual(game.record_action_damage(
            'horror', 'enemy', damage=5), 5)
        with self.assertRaises(ValueError):
            game.inflict_horror('friend', wisdom_save_total=1, ability='cha')
        self.assertEqual(game.inflict_horror(
            'enemy', wisdom_save_total=17, ability='cha')['failed'], False)

    def test_immune_target_takes_no_damage_or_horror(self):
        game = CombatEncounter([
            {'id': 'horror', 'team': 'allies', 'max_hp': 30,
             'offensive_tags': HORROR_TAGS,
             'tag_context': {'pb': 6, 'cha_mod': 3}},
            {'id': 'enemy', 'team': 'enemies', 'max_hp': 30,
             'defensive_tags': ('always_active', 'immune:fogo')},
        ])
        game.start_turn('horror', 'h1')
        game.register_action('horror', 'action', action_kind='magic')
        self.assertEqual(game.record_action_damage(
            'horror', 'enemy', damage=10, damage_type='fogo'), 0)
        self.assertEqual(game.combatants['enemy']['hp'], 30)
        with self.assertRaises(ValueError):
            game.inflict_horror('enemy', wisdom_save_total=1, ability='cha')

    def test_declared_damage_preserves_concentration_contract(self):
        game = CombatEncounter([
            {'id': 'horror', 'team': 'allies', 'max_hp': 30,
             'offensive_tags': HORROR_TAGS,
             'tag_context': {'pb': 6, 'cha_mod': 3}},
            {'id': 'enemy', 'team': 'enemies', 'max_hp': 30,
             'concentration': 'spell:old', 'temp_hp': 5},
        ])
        game.start_turn('horror', 'h1')
        game.register_action('horror', 'action', action_kind='magic')
        with self.assertRaises(ValueError):
            game.record_action_damage('horror', 'enemy', damage=3,
                                      concentration_save_success='yes')
        self.assertEqual(game.record_action_damage(
            'horror', 'enemy', damage=3,
            concentration_save_success=False), 3)
        self.assertEqual(game.combatants['enemy']['hp'], 30)
        self.assertEqual(game.combatants['enemy']['temp_hp'], 2)
        self.assertIsNone(game.concentration_state('enemy')['source'])
        self.assertEqual(game.inflict_horror(
            'enemy', wisdom_save_total=1, ability='cha')['failed'], True)
