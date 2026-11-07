"""Pure walking tests: py -m unittest home.test_vtt_lab_movement -v."""

import builtins
import json
import subprocess
import sys
import unittest
from copy import deepcopy
from unittest.mock import patch
from uuid import UUID

from home import vtt_lab_movement as movement


A, B, C = [str(UUID(int=index)) for index in (1, 2, 3)]


def profile(walk=30):
    return {'schema': 1, 'unit': 'ft', 'speeds': {'walk': walk}, 'warnings': []}


class WalkingTests(unittest.TestCase):
    def setUp(self):
        self.board = movement.validate_board({'width': 6, 'height': 5})
        self.positions = {A: {'x': 0, 'y': 0, 'z': 0}, B: {'x': 5, 'y': 0, 'z': 0}}
        self.teams = {A: 'one', B: 'two'}

    def plan(self, x, y, budget=72, **kwargs):
        return movement.plan_walk(self.board, self.positions, self.teams, A,
                                  {'x': x, 'y': y, 'z': 0}, budget, **kwargs)

    def test_defaults_are_normalized_and_copies_are_independent(self):
        original = {'width': 24, 'height': 18, 'cell_meters': 1.5}
        result = movement.validate_board(original)
        self.assertEqual(result['movement']['step_cost'], 12)
        self.assertEqual(result['movement']['cost_scale'], 12)
        self.assertEqual(result['cell_feet'], 5)
        self.assertEqual(result['metric'], 'manhattan3d')
        self.assertEqual(result['blocked_cells'], [])
        self.assertEqual(movement.validate_board(result), result)
        result['movement']['terrain_costs']['normal'] = 4
        self.assertNotIn('movement', original)

    def test_walk_uses_networkx_and_is_read_only(self):
        import networkx as nx
        before = deepcopy((self.board, self.positions, self.teams))
        with patch.object(nx, 'single_source_dijkstra', wraps=nx.single_source_dijkstra) as dijkstra:
            result = self.plan(2, 0)
        dijkstra.assert_called_once()
        self.assertEqual(result['cost_units'], 24)
        self.assertEqual(result['remaining_units'], 48)
        self.assertEqual(result['path'], [{'x': x, 'y': 0, 'z': 0} for x in range(3)])
        self.assertEqual((self.board, self.positions, self.teams), before)

    def test_detour_around_enemy_wall_and_difficult_cell_matches_http_fixture(self):
        self.positions[B].update(x=1, y=0)
        self.board['blocked_cells'] = [{'x': 0, 'y': 2}]
        self.board['terrain_cells'] = {'0,1': 'difficult'}
        result = self.plan(0, 3)
        self.assertEqual(result['cost_units'], 72)
        self.assertEqual(result['remaining_units'], 0)
        self.assertNotIn({'x': 0, 'y': 2, 'z': 0}, result['path'])
        self.assertNotIn({'x': 1, 'y': 0, 'z': 0}, result['path'])
        self.assertEqual(len(result['path']), 6)  # Five steps; one has double cost.

    def test_costs_are_board_data_not_fixed_policy_constants(self):
        self.board['movement']['step_cost'] = 6
        self.board['movement']['terrain_costs']['difficult'] = 3
        self.board['terrain_cells'] = {'1,0': 'difficult'}
        self.assertEqual(movement.validate_board(self.board), self.board)
        result = self.plan(1, 0)
        self.assertEqual(result['cost_units'], 18)
        self.assertEqual(result['remaining_units'], 54)
        self.assertEqual(movement.movement_budget(self.board, profile()), 72)

    def test_allies_pass_through_but_cannot_end_on_any_occupant(self):
        self.board['height'] = 1
        self.positions[B]['x'] = 1
        self.teams[B] = 'one'
        self.assertEqual(self.plan(2, 0)['cost_units'], 24)
        with self.assertRaises(ValueError):
            self.plan(1, 0)
        self.teams[B] = 'two'
        with self.assertRaises(ValueError):
            self.plan(2, 0)
        del self.teams[B]
        with self.assertRaises(ValueError):
            self.plan(2, 0)

    def test_budget_floor_is_decimal_exact_and_unknown_is_not_invented(self):
        self.assertEqual(movement.movement_budget(self.board, profile(30)), 72)
        self.assertEqual(movement.movement_budget(self.board, profile(0)), 0)
        board = movement.validate_board(dict(self.board, cell_feet=0.1))
        self.assertEqual(movement.movement_budget(board, profile(0.3)), 36)
        self.assertEqual(movement.movement_budget(self.board, profile(1.1)), 2)
        self.assertIsNone(movement.movement_budget(self.board, None))
        self.assertIsNone(movement.movement_budget(self.board, dict(profile(), speeds={'fly': 60})))
        self.assertEqual(self.plan(0, 0, budget=0)['cost_units'], 0)
        with self.assertRaises(ValueError):
            self.plan(1, 0, budget=11)

    def test_optional_hover_and_fall_are_preserved_without_interpretation(self):
        value = profile()
        value['speeds']['fly'] = 60
        value['properties'] = {'fly': {'hover': True}}
        value['fall'] = {'threshold_ft': 20, 'max_per_turn_ft': 60}
        copy = movement.validate_movement(value)
        self.assertEqual(copy, value)
        self.assertEqual(movement.movement_budget(self.board, value), 72)
        copy['properties']['fly']['hover'] = False
        self.assertTrue(value['properties']['fly']['hover'])
        for bad in ({'properties': {'fly': {'hover': 1}}},
                    {'fall': {'threshold_ft': True, 'max_per_turn_ft': 30}},
                    {'fall': {'threshold_ft': 20, 'max_per_turn_ft': 0}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                movement.validate_movement({**value, **bad})

    def test_strict_bounded_coordinates_board_costs_and_speeds(self):
        for value in (True, 1.0, -1, 64, float('nan')):
            with self.subTest(coordinate=value), self.assertRaises(ValueError):
                self.plan(value, 0)
        for value in (True, 0, -1, 1.0, 1_000_001):
            for key in ('step_cost', 'cost_scale'):
                board = deepcopy(self.board)
                board['movement'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    movement.validate_board(board)
            board = deepcopy(self.board)
            board['movement']['terrain_costs']['difficult'] = value
            with self.assertRaises(ValueError):
                movement.validate_board(board)
        for value in (True, -1, float('inf'), float('nan'), 10 ** 400):
            with self.subTest(speed=repr(value)), self.assertRaises(ValueError):
                movement.validate_movement(profile(value))
        for changes in ({'width': 65}, {'height': True}, {'metric': 'hex'}, {'cell_feet': 0},
                        {'blocked_cells': [{'x': 0, 'y': 0}] * 4097},
                        {'blocked_cells': [{'x': 6, 'y': 0}]}, {'terrain_cells': {'01,0': 'difficult'}},
                        {'terrain_cells': {'0,0': 'lava'}}):
            with self.subTest(changes=repr(changes)[:100]), self.assertRaises(ValueError):
                movement.validate_board({**self.board, **changes})

    def test_occupant_bounds_and_unsupported_modes_fail_closed(self):
        for change in ({'z': 1}, {'footprint': 2}):
            self.positions[A].update(change)
            with self.assertRaises(ValueError):
                self.plan(1, 0)
            self.positions[A] = {'x': 0, 'y': 0, 'z': 0}
        oversized = {str(UUID(int=i)): {'x': 0, 'y': 0, 'z': 0} for i in range(1, 130)}
        with self.assertRaises(ValueError):
            movement.validate_positions(self.board, oversized)
        with self.assertRaises(ValueError):
            movement.plan_walk(self.board, self.positions, {B: 'two'}, A, {'x': 0, 'y': 1, 'z': 0}, 72)

    def test_maximum_board_is_bounded_and_json_roundtrip_is_deterministic(self):
        self.board = movement.validate_board({'width': 64, 'height': 64})
        before = self.plan(3, 1)
        self.board, self.positions, self.teams = json.loads(json.dumps([self.board, self.positions, self.teams]))
        self.assertEqual(self.plan(3, 1), before)

    def test_dependency_is_lazy_and_missing_dependency_rejects_only_walking(self):
        result = subprocess.run([sys.executable, '-c',
                                 'import sys; import home.vtt_lab_combat; '
                                 'assert "networkx" not in sys.modules'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        original = builtins.__import__
        def absent(name, *args, **kwargs):
            if name == 'networkx':
                raise ImportError('deliberately unavailable')
            return original(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=absent), self.assertRaisesRegex(ValueError, 'unavailable'):
            self.plan(1, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
