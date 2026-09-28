from django.test import SimpleTestCase

from .hunter_combat import evaluate
from .hunter_rework import prepare, catalog


class HunterCombatTests(SimpleTestCase):
    def result(self, level, ability='int', **kwargs):
        prepared = prepare(level=level, ability=ability,
            order=kwargs.pop('order', catalog()['orders'][0]['id']) if level >= 3 else '',
            total_level=kwargs.pop('total_level', level))
        return evaluate(prepared, **kwargs)

    def test_ability_choice_multiclass_and_negative_modifiers(self):
        data = self.result(2, intelligence=8, wisdom=20, favored=True, total_level=9)
        self.assertEqual((data['spell_dc'], data['spell_attack'], data['favored_damage']), (11, 3, 1))
        data = self.result(2, 'wis', intelligence=8, wisdom=20, favored=True, total_level=9)
        self.assertEqual((data['secret_dc'], data['spell_attack'], data['favored_damage']), (17, 9, 5))
        self.assertEqual(self.result(9, intelligence=8)['physical_save_bonus'], -1)
        self.assertEqual(self.result(1, favored=True)['favored_damage'], 0)

    def test_every_level_and_target_condition(self):
        for level in range(1, 21):
            ordinary = self.result(level, intelligence=18)
            marked = self.result(level, intelligence=18, marked=True, first_attack=True)
            secret = self.result(level, intelligence=18, secret_affected=True)
            self.assertEqual(ordinary['attacks'], 2 if level >= 5 else 1)
            self.assertFalse(ordinary['attack_advantage'])
            self.assertEqual(marked['attack_advantage'], level >= 11)
            self.assertEqual(secret['attack_advantage'], level == 20)
            self.assertEqual(marked['enemy_attack_disadvantage'], level == 20)
            self.assertEqual(secret['attacks'], 3 if level == 20 else ordinary['attacks'])
            self.assertEqual(marked['mark_damage'], '1d12' if level >= 17 else
                             '1d10' if level >= 11 else '1d8' if level >= 5 else '1d6')
            self.assertEqual(ordinary['mark_damage'], '')
            self.assertEqual(ordinary['physical_save_bonus'], 4 if level >= 9 else 0)
            self.assertEqual(ordinary['walking_speed'], 40 if level >= 7 else 30)
            self.assertEqual(ordinary['climbing_speed'], 40 if level >= 7 else None)
            self.assertEqual(ordinary['bonus_hide'], level >= 13)
            self.assertEqual(ordinary['charmed_immune'], level >= 15)
            self.assertEqual(ordinary['blindsight'], 30 if level >= 17 else 0)

    def test_first_attack_and_once_per_turn_never_leak(self):
        self.assertFalse(self.result(11, marked=True)['attack_advantage'])
        self.assertFalse(self.result(19, secret_affected=True, first_attack=True)['attack_advantage'])
        data = self.result(20, marked=True, third_attack_available=False)
        self.assertEqual(data['attacks'], 2)
        self.assertTrue(data['attack_advantage'])
        self.assertFalse(data['third_attack_once_per_turn'])

    def test_invalid_inputs_rejected(self):
        for kwargs in ({'intelligence': 0}, {'wisdom': 31}, {'walking_speed': -1},
                       {'intelligence': 'invalid'}):
            with self.assertRaises(ValueError):
                self.result(1, **kwargs)

    def test_exterminator_thresholds_and_independent_defensive_ability(self):
        for level in range(3, 21):
            data = self.result(level, order='ordem-dos-exterminadores',
                intelligence=8, wisdom=18, protective_ability='wis', marked=True,
                injured=True, enemy_hit_this_turn=True, final_hunt=True)
            self.assertEqual(data['effective_favored'], level >= 10)
            self.assertEqual(data['favored_damage'], 1 if level >= 10 else 0)
            self.assertEqual(data['favored_save_bonus'], 4 if level >= 10 else 0)
            self.assertEqual(data['executor_ac_bonus'], 4 if level >= 14 else 0)
            self.assertEqual(data['final_hunt'], level >= 18)
            self.assertEqual(data['mark_damage'][0], '2' if level >= 18 else '1')
            self.assertTrue(data['punishment_damage'])
        negative = self.result(6, order='ordem-dos-exterminadores', intelligence=8,
                               favored=True, protective_ability='int')
        self.assertEqual(negative['favored_save_bonus'], -1)
        self.assertEqual(negative['damage_reduction'], 1)

    def test_exterminator_conditions_never_leak_to_other_orders_or_targets(self):
        data = self.result(20, final_hunt=True, injured=True, enemy_hit_this_turn=True, marked=True)
        self.assertFalse(data['final_hunt'])
        self.assertEqual(data['executor_ac_bonus'], 0)
        self.assertEqual(data['punishment_damage'], '')
        data = self.result(20, order='ordem-dos-exterminadores', final_hunt=True,
                           injured=True, punishment_available=False)
        self.assertFalse(data['final_hunt'])
        self.assertFalse(data['effective_favored'])
        self.assertEqual(data['punishment_damage'], '')
