from django.test import SimpleTestCase

from .battle_familiar import FORMS, stat_block


class BattleFamiliarBlockTests(SimpleTestCase):
    def test_all_circles_and_forms_match_adopted_source(self):
        for circle in range(2, 10):
            for form in FORMS:
                with self.subTest(circle=circle, form=form):
                    block = stat_block(circle, form, 7)
                    self.assertEqual(block['ac'], 11 + circle + (2 if form == 'bruto' else 0))
                    self.assertEqual(block['hp_max'], (30 if form == 'bruto' else 20) + 5 * (circle - 2))
                    self.assertEqual(block['check_save_bonus'], circle // 2)
                    self.assertEqual(block['multiattack'], circle // 2)
                    self.assertEqual(block['rend_damage'], f'1d8+{3 + circle}')
                    self.assertEqual(block['rend_attack'], 7)
                    self.assertEqual((block['walk_m'], block['swim_m']), (12, 9))
                    self.assertEqual(block['fly_m'], 9 if form == 'voador' else 0)
                    self.assertEqual(block['stalk'], form == 'espreitador')
                    self.assertEqual([a['save'] for a in block['attributes']],
                                     [v + circle // 2 for v in (3, 3, 1, -1, 1, 0)])

    def test_invalid_circle_or_shape_is_not_guessed(self):
        for circle in (1, 10, True, 2.5, '2'):
            with self.assertRaises(ValueError):
                stat_block(circle, 'bruto')
        for form in ('', 'lobo', 'Bruto'):
            with self.assertRaises(ValueError):
                stat_block(2, form)

    def test_hunter_overrides_keep_spell_multiattack_separate_from_command(self):
        from .hunter_companion import companion_block
        block = companion_block(dict(circle=5, battle_form='espreitador', supreme=True,
            evolutions=['alcance', 'escalada'], damage=12), 18, 6, 11)
        self.assertEqual((block['hp_max'], block['hp_current'], block['ac']), (235, 223, 26))
        self.assertEqual(block['multiattack'], 4)
        self.assertEqual(block['check_save_bonus'], 10)
        self.assertEqual((block['reach_m'], block['climb_m'], block['size']), (3, 12, 'Enorme'))
