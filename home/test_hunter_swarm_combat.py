from django.test import SimpleTestCase, RequestFactory
from types import SimpleNamespace
from unittest.mock import patch
from django.http import HttpResponse
from django.template.loader import render_to_string

from .hunter_rework import prepare
from .hunter_combat import evaluate as base
from .hunter_swarm_combat import evaluate
from .hunter_views import laboratory


class SwarmCombatTests(SimpleTestCase):
    def calc(self, level=10, order='ordem-do-enxame', **kwargs):
        prepared = prepare(level=level, ability='wis', order=order)
        return evaluate(prepared, base(prepared, wisdom=18), **kwargs)

    def test_commands_and_mark_threshold(self):
        for level in range(3, 21):
            for marked in (False, True):
                data = self.calc(level, marked=marked, hit=True, own_turn=True,
                                 commands=['push'])
                self.assertEqual(data['command_limit'], 2 if level >= 10 and marked else 1)
                self.assertIn('Resistência de Força CD', data['effects'][0]['text'])
        data = self.calc(marked=True, hit=True, own_turn=True, commands=['weakening', 'step'])
        self.assertEqual(data['extra_damage'], '1d8')
        self.assertEqual(len(data['effects']), 2)
        self.assertIn('horizontalmente', data['effects'][1]['text'])
        self.assertIn('metade', self.calc(hit=True, own_turn=True, commands=['subjugate'])['effects'][0]['text'])

    def test_invalid_commands_and_turn_gates(self):
        for kwargs in ({'commands':['unknown']}, {'commands':['push', 'push']},
                       {'commands':['push']}, {'commands':['push'], 'hit':True},
                       {'commands':['push'], 'hit':True, 'own_turn':True, 'command_used':True},
                       {'commands':['push','step'], 'hit':True, 'own_turn':True}):
            with self.assertRaises(ValueError): self.calc(**kwargs)
        with self.assertRaises(ValueError):
            self.calc(order='ordem-dos-exterminadores', commands=['step'], hit=True, own_turn=True)

    def test_barrier_all_or_nothing_and_ability_independent(self):
        self.assertEqual(self.calc(5, damage=1)['damage_taken'], 1)
        for damage, expected in ((9,0), (10,0), (11,11)):
            result = self.calc(6, damage=damage, intelligence=18, wisdom=8)
            self.assertEqual(result['damage_taken'], expected)
        self.assertEqual(self.calc(6, damage=8, intelligence=8)['damage_taken'], 8)
        self.assertEqual(self.calc(6, damage=7, intelligence=8)['damage_taken'], 0)
        self.assertEqual(self.calc(6, damage=9, intelligence=18, barrier_used=True)['damage_taken'], 9)
        self.assertEqual(self.calc(6, damage=10, wisdom=18, barrier_ability='wis')['damage_taken'], 0)
        self.assertEqual(self.calc(order='ordem-dos-exterminadores', damage=1)['damage_taken'], 1)
        with self.assertRaises(ValueError): self.calc(damage=-1)

    @patch('home.hunter_views.render', side_effect=lambda request, template, context, status:
           HttpResponse(render_to_string(template, context), status=status))
    def test_laboratory_get_renders_results_and_rejects_invalid_turn(self, rendered):
        params = dict(level=10, ability='wis', order='ordem-do-enxame', wisdom=18,
                      swarm_hit='1', swarm_own_turn='1', marked='1',
                      swarm_command=['push', 'step'], swarm_damage=11)
        request = RequestFactory().get('/', params)
        request.user = SimpleNamespace(is_authenticated=True)
        with patch('home.views._criador_hunter_catalog_args', return_value={}):
            response = laboratory(request)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Dano adicional do Enxame: 1d8', html)
        self.assertIn('Resistência de Força CD 16', html)
        self.assertIn('Dano após a Barreira: 0', html)
        params['swarm_command_used'] = '1'
        request = RequestFactory().get('/', params)
        request.user = SimpleNamespace(is_authenticated=True)
        with patch('home.views._criador_hunter_catalog_args', return_value={}):
            self.assertEqual(laboratory(request).status_code, 400)
