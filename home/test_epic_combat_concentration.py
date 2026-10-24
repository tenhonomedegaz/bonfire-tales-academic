"""Concentration in the table-resolved encounter consumer."""

from django.test import SimpleTestCase

from home.epic_concentration import FOCUS_TAG
from home.tag_engine.combat_encounter import CombatEncounter


def encounter(tags=(), *, hp=30, temp_hp=0, concentration='spell:old'):
    return CombatEncounter([
        {'id': 'caster', 'team': 'allies', 'max_hp': 30,
         'hp': hp, 'temp_hp': temp_hp, 'defensive_tags': tags,
         'concentration': concentration},
        {'id': 'foe', 'team': 'enemies', 'max_hp': 30},
    ])


class CombatConcentrationTests(SimpleTestCase):
    def test_focus_retains_on_damage_then_hard_condition_ends(self):
        game = encounter([FOCUS_TAG])
        game.start_turn('foe', 'turn-1')
        game.attack('caster', (), hit=True, damage=8)
        self.assertEqual(game.concentration_state('caster'), {
            'source': 'spell:old', 'save_required': False})
        self.assertIn(('concentration', 'caster', 'damage', 'retained'), game.events)
        self.assertEqual(game.resolve_concentration_event('caster', 'petrified'), 'ended')
        self.assertEqual(game.concentration_state('caster')['source'], None)

    def test_nonfocused_damage_requires_declared_save_and_can_fail(self):
        game = encounter()
        game.start_turn('foe', 'turn-1')
        game.attack('caster', (), hit=True, damage=4)
        self.assertTrue(game.concentration_state('caster')['save_required'])
        self.assertEqual(game.resolve_concentration_event(
            'caster', 'damage', save_success=False), 'ended')
        self.assertIsNone(game.concentration_state('caster')['source'])

    def test_new_concentration_replaces_old_and_is_idempotent(self):
        game = encounter([FOCUS_TAG])
        self.assertTrue(game.begin_concentration('caster', 'spell:new'))
        self.assertFalse(game.begin_concentration('caster', 'spell:new'))
        self.assertEqual(game.concentration_state('caster')['source'], 'spell:new')
        self.assertEqual(game.resolve_concentration_event(
            'caster', 'unconscious'), 'ended')
        self.assertEqual(game.resolve_concentration_event(
            'caster', 'unconscious'), 'inactive')

    def test_temp_hp_damage_still_triggers_focus_and_zero_hp_ends_it(self):
        game = encounter([FOCUS_TAG], temp_hp=5)
        game.start_turn('foe', 'turn-1')
        game.attack('caster', (), hit=True, damage=3)
        self.assertEqual(game.concentration_state('caster')['source'], 'spell:old')
        game.end_turn()
        game.start_turn('foe', 'turn-2')
        game.attack('caster', (), hit=True, damage=40)
        self.assertIsNone(game.concentration_state('caster')['source'])
        self.assertIn(('concentration', 'caster', 'unconscious', 'ended'), game.events)

    def test_invalid_save_result_or_miss_does_not_consume_action(self):
        game = encounter()
        game.start_turn('foe', 'turn-1')
        with self.assertRaises(ValueError):
            game.attack('caster', (), hit=False, concentration_save_success=True)
        self.assertFalse(game.action_used)
        with self.assertRaises(ValueError):
            game.attack('caster', (), hit=True, damage=2,
                        concentration_save_success='yes')
        self.assertFalse(game.action_used)
        game.attack('caster', (), hit=True, damage=2,
                    concentration_save_success=True)
        self.assertEqual(game.concentration_state('caster'), {
            'source': 'spell:old', 'save_required': False})
