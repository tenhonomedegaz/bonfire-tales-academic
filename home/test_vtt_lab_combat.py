"""Pure focused tests: py -m unittest home.test_vtt_lab_combat -v.

Only the actual vocabulary JSON is read. Django settings, models, environment
and databases are not needed for the adapter or these tests.
"""

import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from uuid import UUID

from home import vtt_lab_combat as adapter
from home.tag_engine.combat_encounter import CombatEncounter
from home.tag_engine.library import Library, library_scope


A, B, C = [str(UUID(int=index)) for index in (1, 2, 3)]
POISON = [
    'instant{trigger=hit, apply:envenenado(duration:until_source_turn_start)}',
    'while_active{requires:target{condition{envenenado, source:self}}, restricts{heal,target}}',
]


def rules(tags=None):
    return {'defensive_tags': [], 'offensive_tags': [], 'tag_context': {},
            'actions': [{'id': 'manual', 'nome': 'Manual attack', 'tags': list(tags or [])}]}


def fixture():
    return {'schema': 1, 'board': {'width': 24, 'height': 18, 'cell_meters': 1.5}, 'turn': 0, 'events': [],
            'tokens': [{'id': A, 'nome': 'One', 'x': 0, 'y': 0, 'z': 0, 'hp': 30, 'max_hp': 30,
                        'rules': rules()},
                       {'id': B, 'nome': 'Two', 'x': 1, 'y': 0, 'z': 0, 'hp': 30, 'max_hp': 30,
                        'rules': dict(rules(), defensive_tags=['always_active', 'resist:fogo'])}]}


class VttLabCombatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = Library(prefer_db=False).raw

    def setUp(self):
        self.state = fixture()
        self.enterContext(patch('home.tag_engine.library._active_database_library',
                                side_effect=AssertionError('No live library or DB reads')))

    def apply(self, kind, **fields):
        return adapter.apply_combat(self.state, {'type': kind, **fields})

    def start(self, raw=None):
        return adapter.apply_combat(self.state, {'type': 'combat_start', 'teams': {A: 'one', B: 'two'}},
                                    self.raw if raw is None else raw)

    def hp(self, actor):
        return next(token for token in self.state['tokens'] if token['id'] == actor)['hp']

    def attack(self, target=B, **fields):
        data = dict(target_id=target, action_id='manual', hit=True, damage=5, damage_type='fogo')
        data.update(fields)
        return self.apply('combat_attack', **data)

    def invalid(self, command, *, state=None, raw=None):
        target = self.state if state is None else state
        before = deepcopy(target)
        with self.assertRaises(ValueError):
            adapter.apply_combat(target, command, raw)
        self.assertEqual(target, before)

    def test_ui_flow_resistance_healing_and_manual_end(self):
        self.assertIsNone(self.start())
        self.assertEqual(self.apply('combat_start_turn', actor_id=A), A)
        self.assertEqual(self.attack(), B)
        self.assertEqual(self.hp(B), 28)
        self.assertTrue(self.state['combat']['view']['action_used'])
        self.apply('combat_end_turn')
        self.apply('combat_start_turn', actor_id=B)
        self.assertEqual(self.apply('combat_heal', target_id=B, amount=2), B)
        self.assertEqual(self.hp(B), 30)
        self.apply('combat_end')
        combat = self.state['combat']
        self.assertFalse(combat['active'])
        self.assertTrue(combat['view']['finished'])
        self.assertIsNone(combat['view']['current_actor'])
        self.assertEqual(combat['end_reason'], 'manual')
        self.assertEqual(combat['view']['conditions'], {A: [], B: []})
        self.assertEqual(combat['view']['damage_types'], self.raw['catalogs']['damage_type']['valores'])
        self.assertEqual(combat['view']['events'][-1], ['heal', B, B, 2, False])
        self.assertEqual(combat['view']['resources'], {A: {}, B: {}})
        self.assertEqual(self.state['tokens'][0]['resources'], {})

    def resource_attack(self, *, current=5, tags=None):
        self.state['tokens'][0]['resources'] = {
            'tag:charges': {'nome': 'Charges', 'max': 5, 'current': current, 'aliases': ['charges']}}
        self.state['tokens'][0]['rules']['actions'][0]['tags'] = tags or ['resource_cost:charges:2']
        self.start()
        self.apply('combat_start_turn', actor_id=A)

    def test_resource_cost_is_paid_on_miss_and_replay_preserves_spending(self):
        self.resource_attack()
        self.attack(hit=False, damage=0)
        self.assertEqual(self.hp(B), 30)
        self.assertEqual(self.state['tokens'][0]['resources']['tag:charges']['current'], 3)
        self.assertEqual(self.state['combat']['view']['resources'][A]['tag:charges']['current'], 3)
        self.assertTrue(self.state['combat']['view']['action_used'])
        self.state = json.loads(json.dumps(self.state))
        self.apply('combat_end_turn')
        self.assertEqual(self.state['tokens'][0]['resources']['tag:charges']['current'], 3)
        self.apply('combat_end')
        self.start()
        self.assertEqual(self.state['combat']['initial'][0]['resources']['tag:charges']['current'], 3)
        self.assertEqual(self.state['combat']['last_result']['view']['resources'][A]['tag:charges']['current'], 3)

    def test_insufficient_unsupported_or_engine_rejected_attack_roll_back_everything(self):
        self.resource_attack(current=1)
        self.invalid({'type': 'combat_attack', 'target_id': B, 'action_id': 'manual',
                      'hit': True, 'damage': 5, 'damage_type': 'fogo'})
        self.assertFalse(self.state['combat']['view']['action_used'])
        self.state = fixture()
        self.resource_attack(tags=['resource_cost:unknown'])
        self.invalid({'type': 'combat_attack', 'target_id': B, 'action_id': 'manual',
                      'hit': True, 'damage': 5, 'damage_type': 'fogo'})
        self.state = fixture()
        self.resource_attack()
        self.invalid({'type': 'combat_attack', 'target_id': B, 'action_id': 'manual',
                      'hit': False, 'damage': 5, 'damage_type': 'fogo'})
        self.assertEqual(self.state['tokens'][0]['resources']['tag:charges']['current'], 5)

    def test_heal_has_no_automatic_cost_without_action_id(self):
        self.state['tokens'][0]['hp'] = 25
        self.resource_attack()
        self.apply('combat_heal', target_id=A, amount=3)
        self.assertEqual(self.hp(A), 28)
        self.assertEqual(self.state['tokens'][0]['resources']['tag:charges']['current'], 5)

    def test_resource_formula_uses_action_context_and_does_not_mutate_snapshot(self):
        self.state['tokens'][0]['rules']['tag_context'] = {'pb': 1}
        self.state['tokens'][0]['rules']['actions'][0]['context'] = {'pb': 3}
        self.resource_attack(tags=['resource_cost:charges:pb'])
        self.attack()
        self.assertEqual(self.state['tokens'][0]['resources']['tag:charges']['current'], 2)
        self.assertEqual(self.state['combat']['initial'][0]['resources']['tag:charges']['current'], 5)
        self.assertEqual(self.state['tokens'][0]['rules']['tag_context'], {'pb': 1})

    def test_uuid_caller_deduplicates_resource_charge_and_engine_fingerprint_covers_resource_modules(self):
        self.resource_attack()
        command = {'type': 'combat_attack', 'target_id': B, 'action_id': 'manual',
                   'hit': False, 'damage': 0, 'damage_type': 'fogo', 'command_id': A, 'expected_revision': 1}
        receipts = set()
        for _ in range(2):
            if command['command_id'] not in receipts:
                adapter.apply_combat(self.state, command)
                receipts.add(command['command_id'])
        self.assertEqual(self.state['tokens'][0]['resources']['tag:charges']['current'], 3)
        original = adapter.Path.read_bytes
        for target in ('vtt_lab_resources.py', 'resource_engine.py'):
            def changed(path):
                value = original(path)
                return value + b'\n# changed\n' if path.name == target else value
            with patch.object(adapter.Path, 'read_bytes', changed):
                self.assertNotEqual(adapter._engine_revision(), adapter.ENGINE_REVISION)

    def test_real_condition_blocks_healing_and_expires_on_source_turn(self):
        self.state['tokens'][0]['rules']['actions'][0]['tags'] = POISON
        self.state['tokens'][1]['hp'] = 20
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        self.apply('combat_attack', target_id=B, action_id='manual', hit=True, damage=4, damage_type='fogo')
        self.assertEqual(self.hp(B), 18)
        self.assertEqual(self.state['combat']['view']['conditions'][B], ['envenenado'])
        self.apply('combat_end_turn')
        self.apply('combat_start_turn', actor_id=B)
        self.apply('combat_heal', target_id=B, amount=2)
        self.assertEqual(self.hp(B), 18)
        self.assertTrue(self.state['combat']['view']['events'][-1][-1])
        self.apply('combat_end_turn')
        self.apply('combat_start_turn', actor_id=A)
        self.assertEqual(self.state['combat']['view']['conditions'][B], [])
        self.apply('combat_end_turn')
        self.apply('combat_start_turn', actor_id=B)
        self.apply('combat_heal', target_id=B, amount=2)
        self.assertEqual(self.hp(B), 20)

    def test_zero_hp_replays_from_initial_snapshot_without_reviving(self):
        self.state['tokens'].append(dict(deepcopy(self.state['tokens'][1]), id=C))
        adapter.apply_combat(self.state, {'type': 'combat_start', 'teams': {A: 'one', B: 'two', C: 'two'}}, self.raw)
        self.apply('combat_start_turn', actor_id=A)
        self.apply('combat_attack', target_id=B, action_id='manual', hit=True, damage=100, damage_type='fogo')
        self.assertEqual(self.hp(B), 0)
        self.assertTrue(self.state['combat']['active'])
        self.apply('combat_end_turn')
        self.invalid({'type': 'combat_start_turn', 'actor_id': B})
        self.apply('combat_start_turn', actor_id=C)
        self.invalid({'type': 'combat_heal', 'target_id': B, 'amount': 10})
        self.assertEqual(self.hp(B), 0)
        self.assertEqual(self.state['combat']['initial'][1]['hp'], 30)

    def test_engine_finish_and_explicit_restart_preserve_previous_result(self):
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        self.apply('combat_attack', target_id=B, action_id='manual', hit=True, damage=100, damage_type='fogo')
        self.assertFalse(self.state['combat']['active'])
        self.assertTrue(self.state['combat']['view']['finished'])
        self.assertEqual(self.state['combat']['end_reason'], 'engine')
        self.invalid({'type': 'combat_start_turn', 'actor_id': A})
        # A separate caller command may set HP after combat, never this adapter.
        self.state['tokens'][1]['hp'] = 30
        previous = deepcopy(self.state['combat']['view'])
        self.start()
        self.assertEqual(self.state['combat']['last_result']['view'], previous)
        self.assertEqual(self.state['combat']['last_result']['end_reason'], 'engine')
        self.assertTrue(self.state['combat']['active'])

    def test_library_hash_pinning_and_no_fallback_to_live_library(self):
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        changed = deepcopy(self.raw)
        changed['primitives']['resist']['target'] = 'not-a-defense'
        with library_scope(changed):
            self.attack()
        self.assertEqual(self.hp(B), 28)
        self.invalid({'type': 'combat_end_turn'}, raw=changed)
        self.state['combat']['library_raw']['primitives']['resist']['target'] = 'tampered'
        self.invalid({'type': 'combat_end_turn'})

    def test_engine_revision_fails_closed_without_changing_old_state_and_new_combats_pin_new_revision(self):
        self.start()
        self.assertEqual(self.state['combat']['engine_revision'], adapter.ENGINE_REVISION)
        self.assertEqual(len(adapter.ENGINE_REVISION), 64)
        before = deepcopy(self.state)
        with patch.object(adapter, 'ENGINE_REVISION', 'a' * 64):
            with self.assertRaisesRegex(ValueError, 'engine revision changed'):
                self.apply('combat_start_turn', actor_id=A)
            self.assertEqual(self.state, before)
            self.state = fixture()
            self.start()
            self.assertEqual(self.state['combat']['engine_revision'], 'a' * 64)

    def test_turn_ids_are_monotonic_and_not_user_controlled(self):
        self.start()
        self.invalid({'type': 'combat_start_turn', 'actor_id': A, 'turn_id': 99})
        for actor in (A, B, A):
            self.apply('combat_start_turn', actor_id=actor)
            self.apply('combat_end_turn')
        ids = [command['turn_id'] for command in self.state['combat']['journal'] if command['type'] == 'combat_start_turn']
        self.assertEqual(ids, [1, 2, 3])
        self.state['combat']['journal'][2]['turn_id'] = 1
        self.invalid({'type': 'combat_start_turn', 'actor_id': A})

    def test_json_roundtrip_matches_engine_and_ignores_untrusted_cached_view(self):
        self.state['tokens'][1]['temp_hp'] = 3
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        self.attack()
        with library_scope(self.raw):
            direct = CombatEncounter([
                {'id': A, 'team': 'one', 'max_hp': 30},
                {'id': B, 'team': 'two', 'max_hp': 30, 'temp_hp': 3,
                 'defensive_tags': ['always_active', 'resist:fogo']}])
            direct.start_turn(A, 1)
            direct.attack(B, [], hit=True, damage=5, damage_type='fogo')
        self.assertEqual(self.state['combat']['view']['combatants'], direct.combatants)
        self.assertEqual(self.state['tokens'][1]['temp_hp'], 1)
        self.state = json.loads(json.dumps(self.state))
        self.state['combat']['view'] = {'false-cache': True}
        self.apply('combat_end_turn')
        self.assertNotIn('false-cache', self.state['combat']['view'])
        self.assertEqual(self.hp(B), 30)
        self.assertEqual(self.state['tokens'][1]['temp_hp'], 1)

    def test_only_active_actors_server_action_tags_can_be_used(self):
        self.state['tokens'][0]['rules']['actions'][0].update(nome='Unrelated name', tags=[])
        self.state['tokens'][1]['rules']['actions'][0]['id'] = 'other-action'
        self.start()
        self.invalid({'type': 'combat_attack', 'target_id': B, 'action_id': 'manual',
                      'hit': True, 'damage': 1, 'damage_type': 'fogo'})
        self.apply('combat_start_turn', actor_id=A)
        self.invalid({'type': 'combat_attack', 'target_id': B, 'action_id': 'other-action',
                      'hit': True, 'damage': 1, 'damage_type': 'fogo'})
        self.invalid({'type': 'combat_attack', 'target_id': B, 'action_id': 'manual',
                      'hit': True, 'damage': 1, 'damage_type': 'fogo', 'tags': POISON})
        self.attack()
        self.assertEqual(self.state['combat']['view']['conditions'][B], [])
        self.assertEqual(self.state['combat']['initial'][0]['rules']['actions'][0]['nome'], 'Unrelated name')
        self.invalid({'type': 'combat_heal', 'target_id': A, 'amount': 1})

    def test_strict_numeric_types_actor_membership_and_canonical_damage_vocabulary(self):
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        base = {'type': 'combat_attack', 'target_id': B, 'action_id': 'manual',
                'hit': True, 'damage': 5, 'damage_type': 'fogo'}
        for field, values in [('hit', [1, 1.0, 'true', None]),
                              ('damage', [True, 1.0, -1, 1_000_001]),
                              ('damage_type', ['fire', 'Fogo', ' fogo', '', None]),
                              ('target_id', [C, 1, '../bad'])]:
            for value in values:
                with self.subTest(field=field, value=value):
                    self.invalid({**base, field: value})
        self.invalid({**base, 'hit': False})
        for amount in (True, 1.0, -1, 1_000_001):
            self.invalid({'type': 'combat_heal', 'target_id': B, 'amount': amount})
        self.apply('combat_attack', target_id=B, action_id='manual', hit=False, damage=0, damage_type='fogo')
        self.assertEqual(self.hp(B), 30)

    def test_start_requires_valid_rules_living_actors_library_and_two_teams(self):
        command = {'type': 'combat_start', 'teams': {A: 'one', B: 'two'}}
        self.invalid(command)
        for field, value in [('hp', 0), ('max_hp', 0), ('hp', True), ('hp', 1.0), ('temp_hp', -1),
                             ('rules', None), ('rules', {}), ('max_hp', True)]:
            candidate = fixture()
            candidate['tokens'][0][field] = value
            with self.subTest(field=field, value=value):
                self.invalid(command, state=candidate, raw=self.raw)
        for teams in ({A: 'one'}, {A: 'one', B: 'one'}, {A: 'one', C: 'two'}, {A: 1, B: 'two'}):
            self.invalid({'type': 'combat_start', 'teams': teams}, raw=self.raw)
        self.start()
        self.invalid(command, raw=self.raw)

    def test_journal_entries_are_json_revalidated_and_terminal_state_cannot_be_bypassed(self):
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        for change in [dict(type='combat_heal', target_id=B, amount=True),
                       dict(type='combat_end_turn', injected='engine internals'),
                       dict(type='combat_attack', target_id=B, action_id='forged', hit=True, damage=1, damage_type='fogo')]:
            candidate = deepcopy(self.state)
            candidate['combat']['journal'].append(change)
            self.invalid({'type': 'combat_end'}, state=candidate)
        candidate = deepcopy(self.state)
        candidate['combat']['active'] = False
        self.invalid({'type': 'combat_start', 'teams': {A: 'one', B: 'two'}}, state=candidate, raw=self.raw)
        self.apply('combat_end')
        self.state['combat']['journal'].append({'type': 'combat_end_turn'})
        self.invalid({'type': 'combat_start', 'teams': {A: 'one', B: 'two'}}, raw=self.raw)

    def test_action_context_is_local_and_restored_even_if_attack_raises(self):
        self.state['tokens'][0]['rules']['tag_context'] = {'classlvl': 1}
        self.state['tokens'][0]['rules']['actions'][0]['context'] = {'classlvl': 7}
        self.state['tokens'][0]['rules']['actions'][0]['tags'] = POISON
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        captured = []
        original = CombatEncounter.attack
        def attack(encounter, *args, **kwargs):
            captured.append(encounter)
            self.assertEqual(encounter._combatants[A]['tag_context']['classlvl'], 7)
            self.assertEqual(encounter.conditions.context['classlvl'], 7)
            return original(encounter, *args, **kwargs)
        with patch.object(CombatEncounter, 'attack', attack):
            self.attack()
        self.assertEqual(captured[-1]._combatants[A]['tag_context']['classlvl'], 1)
        self.assertFalse(isinstance(captured[-1].conditions, adapter._ConditionContext))
        self.assertEqual(self.state['combat']['view']['conditions'][B], ['envenenado'])
        self.apply('combat_end_turn')
        self.apply('combat_start_turn', actor_id=A)
        def fail(encounter, *args, **kwargs):
            captured.append(encounter)
            raise ValueError('Engine rejection')
        with patch.object(CombatEncounter, 'attack', fail):
            self.invalid({'type': 'combat_attack', 'target_id': B, 'action_id': 'manual',
                          'hit': True, 'damage': 1, 'damage_type': 'fogo'})
        self.assertEqual(captured[-1]._combatants[A]['tag_context']['classlvl'], 1)
        self.assertFalse(isinstance(captured[-1].conditions, adapter._ConditionContext))

    def test_bounds_for_combatants_library_state_and_journal_leave_manual_exit(self):
        oversized = fixture()
        oversized['tokens'] = [dict(deepcopy(oversized['tokens'][0]), id=str(UUID(int=i))) for i in range(1, 34)]
        self.invalid({'type': 'combat_start', 'teams': {token['id']: str(i % 2)
                      for i, token in enumerate(oversized['tokens'])}}, state=oversized, raw=self.raw)
        raw = deepcopy(self.raw)
        raw['oversized'] = 'x' * adapter.MAX_LIBRARY_BYTES
        self.invalid({'type': 'combat_start', 'teams': {A: 'one', B: 'two'}}, raw=raw)
        self.start()
        with patch.object(adapter, 'MAX_JOURNAL', 5):
            for actor in (A, B):
                self.apply('combat_start_turn', actor_id=actor)
                self.apply('combat_end_turn')
            self.invalid({'type': 'combat_start_turn', 'actor_id': A})
            self.apply('combat_end')
            self.assertEqual(len(self.state['combat']['journal']), 5)
        oversized = deepcopy(self.state)
        oversized['payload'] = 'x' * adapter.MAX_STATE_BYTES
        self.invalid({'type': 'combat_end'}, state=oversized)
        self.assertLessEqual(len(self.state['combat']['view']['events']), 10)

    def test_engine_revision_is_stable_across_windows_line_endings(self):
        with patch.object(adapter.Path, 'read_bytes', return_value=b'line\nnext\n'):
            unix = adapter._engine_revision()
        with patch.object(adapter.Path, 'read_bytes', return_value=b'line\r\nnext\r\n'):
            windows = adapter._engine_revision()
        self.assertEqual(unix, windows)

    def walking(self, speed=30):
        for token in self.state['tokens']:
            token['movement'] = {'schema': 1, 'unit': 'ft', 'speeds': {'walk': speed}, 'warnings': []}

    def test_walk_preview_http_fixture_replay_and_caller_uuid_are_atomic(self):
        self.walking()
        self.state['board'].update(blocked_cells=[{'x': 0, 'y': 2}], terrain_cells={'0,1': 'difficult'})
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        destination = {'x': 0, 'y': 3, 'z': 0}
        before = deepcopy(self.state)
        plan = adapter.preview_movement(self.state, destination)
        self.assertEqual(self.state, before)
        self.assertEqual(plan['cost_units'], 72)
        self.assertEqual(plan['remaining_units'], 0)
        command = {'type': 'combat_move', **destination, 'command_id': C, 'expected_revision': 1}
        receipts = set()
        for _ in range(2):
            if command['command_id'] not in receipts:
                self.assertEqual(adapter.apply_combat(self.state, command), A)
                receipts.add(command['command_id'])
        view = self.state['combat']['view']
        self.assertEqual(view['positions'][A], destination)
        self.assertEqual(view['last_path'], plan['path'])
        self.assertEqual(view['movement'][A], {'budget_units': 72, 'spent_units': 72,
                                              'remaining_units': 0, 'available': False,
                                              'reason': 'movement_exhausted'})
        self.assertFalse(view['action_used'])
        self.assertEqual([self.state['tokens'][0][key] for key in ('x', 'y', 'z')], [0, 3, 0])
        self.assertEqual(len(self.state['combat']['journal']), 2)
        self.invalid({'type': 'combat_move', 'x': 0, 'y': 4, 'z': 0})
        # Exhausted movement does not consume or prohibit the ordinary action.
        self.attack()
        self.state = json.loads(json.dumps(self.state))
        self.apply('combat_end_turn')
        self.assertEqual(self.state['combat']['view']['movement'][A]['spent_units'], 72)
        self.apply('combat_start_turn', actor_id=A)
        self.assertEqual(self.state['combat']['view']['movement'][A]['remaining_units'], 72)
        self.assertEqual(self.state['combat']['view']['positions'][A], destination)

    def test_unknown_zero_or_other_mode_speed_does_not_block_combat_actions(self):
        for movement in (None, {'schema': 1, 'unit': 'ft', 'speeds': {}, 'warnings': []},
                         {'schema': 1, 'unit': 'ft', 'speeds': {'fly': 60}, 'warnings': []},
                         {'schema': 1, 'unit': 'ft', 'speeds': {'walk': 0}, 'warnings': []}):
            with self.subTest(movement=movement):
                self.state = fixture()
                self.state['tokens'][0]['movement'] = movement
                self.start()
                self.apply('combat_start_turn', actor_id=A)
                view = self.state['combat']['view']['movement'][A]
                self.assertFalse(view['available'])
                self.assertEqual(view['budget_units'], 0 if movement and movement['speeds'].get('walk') == 0 else None)
                self.invalid({'type': 'combat_move', 'x': 0, 'y': 1, 'z': 0})
                self.attack()
                self.assertEqual(self.hp(B), 28)

    def test_movement_requires_active_turn_strict_cells_and_sufficient_budget(self):
        self.walking(5)
        self.start()
        before = deepcopy(self.state)
        with self.assertRaises(ValueError):
            adapter.preview_movement(self.state, {'x': 0, 'y': 1, 'z': 0})
        self.assertEqual(self.state, before)
        self.invalid({'type': 'combat_move', 'x': 0, 'y': 1, 'z': 0})
        self.apply('combat_start_turn', actor_id=A)
        for changes in ({'x': True}, {'y': 1.0}, {'z': 1}, {'z': False}, {'x': -1}, {'actor_id': B}):
            self.invalid({'type': 'combat_move', 'x': 0, 'y': 1, 'z': 0, **changes})
        self.invalid({'type': 'combat_move', 'x': 0, 'y': 2, 'z': 0})
        self.apply('combat_move', x=0, y=1, z=0)
        self.assertFalse(self.state['combat']['view']['action_used'])
        self.apply('combat_end_turn')
        self.invalid({'type': 'combat_move', 'x': 0, 'y': 0, 'z': 0})

    def test_movement_caps_occupants_and_board_are_pinned_until_new_encounter(self):
        self.walking()
        self.state['tokens'].append({'id': C, 'x': 0, 'y': 2, 'z': 0})
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        self.state['tokens'][0]['movement']['speeds']['walk'] = 1000
        self.state['tokens'][2]['y'] = 4
        self.state['board']['blocked_cells'] = [{'x': 0, 'y': 1}]
        self.state['combat']['view'] = {'untrusted': True}
        plan = adapter.preview_movement(self.state, {'x': 0, 'y': 1, 'z': 0})
        self.assertEqual(plan['cost_units'], 12)
        self.invalid({'type': 'combat_move', 'x': 0, 'y': 2, 'z': 0})
        self.apply('combat_move', x=0, y=1, z=0)
        self.assertEqual(self.state['combat']['view']['movement'][A]['budget_units'], 72)
        self.assertEqual(self.state['tokens'][2]['y'], 2)
        self.assertNotIn('untrusted', self.state['combat']['view'])
        self.apply('combat_end')
        self.assertEqual(self.state['combat']['view']['positions'][A]['y'], 1)
        self.assertFalse(self.state['combat']['view']['movement'][A]['available'])
        self.state['board']['blocked_cells'] = []
        self.start()
        self.assertEqual(self.state['combat']['initial'][0]['position']['y'], 1)
        self.assertEqual(self.state['combat']['last_result']['view']['positions'][A]['y'], 1)
        self.assertEqual(self.state['combat']['view']['movement'][A]['budget_units'], 2400)

    def test_start_turn_resets_only_that_actor_and_active_condition_blocks_walking(self):
        self.walking()
        self.state['tokens'][0]['rules']['actions'][0]['tags'] = POISON
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        self.apply('combat_move', x=0, y=1, z=0)
        self.attack()
        self.apply('combat_end_turn')
        self.apply('combat_start_turn', actor_id=B)
        self.assertEqual(self.state['combat']['view']['movement'][B]['reason'], 'active_condition')
        self.invalid({'type': 'combat_move', 'x': 2, 'y': 0, 'z': 0})
        self.apply('combat_end_turn')
        self.apply('combat_start_turn', actor_id=A)
        self.assertEqual(self.state['combat']['view']['movement'][A]['spent_units'], 0)
        self.apply('combat_move', x=0, y=2, z=0)
        self.apply('combat_end_turn')
        self.apply('combat_start_turn', actor_id=B)
        self.apply('combat_move', x=2, y=0, z=0)
        self.assertEqual(self.state['combat']['view']['movement'][A]['spent_units'], 12)
        self.assertEqual(self.state['combat']['view']['movement'][B]['spent_units'], 12)
        self.apply('combat_end_turn')
        self.apply('combat_start_turn', actor_id=A)
        self.assertEqual(self.state['combat']['view']['movement'][A]['spent_units'], 0)
        self.assertEqual(self.state['combat']['view']['movement'][B]['spent_units'], 12)

    def test_replay_revalidates_moves_and_preserves_hp_resources_and_positions_on_error(self):
        self.walking()
        self.resource_attack()
        self.apply('combat_move', x=0, y=1, z=0)
        self.attack(hit=False, damage=0)
        self.state = json.loads(json.dumps(self.state))
        self.invalid({'type': 'combat_move', 'x': 0, 'y': 7, 'z': 0})
        for move in ({'type': 'combat_move', 'x': True, 'y': 2, 'z': 0},
                     {'type': 'combat_move', 'x': 0, 'y': 17, 'z': 0}):
            candidate = deepcopy(self.state)
            candidate['combat']['journal'].append(move)
            self.invalid({'type': 'combat_end'}, state=candidate)
        self.apply('combat_end_turn')
        self.assertEqual(self.state['tokens'][0]['resources']['tag:charges']['current'], 3)
        self.assertEqual(self.state['tokens'][0]['y'], 1)
        self.assertEqual(self.state['combat']['view']['movement'][A]['spent_units'], 12)

    def test_nonflat_snapshot_keeps_actions_and_movement_fingerprint_pins_dependency_version(self):
        self.walking()
        self.state['tokens'][1]['z'] = 1
        self.start()
        self.apply('combat_start_turn', actor_id=A)
        self.assertEqual(self.state['combat']['view']['movement'][A]['reason'], 'unsupported_flat_positions')
        self.invalid({'type': 'combat_move', 'x': 0, 'y': 1, 'z': 0})
        self.attack()
        original = adapter.Path.read_bytes
        def changed(path):
            value = original(path)
            return value + b'\n# movement changed\n' if path.name == 'vtt_lab_movement.py' else value
        with patch.object(adapter.Path, 'read_bytes', changed):
            self.assertNotEqual(adapter._engine_revision(), adapter.ENGINE_REVISION)
        with patch.object(adapter, 'networkx_version', return_value='different'):
            self.assertNotEqual(adapter._engine_revision(), adapter.ENGINE_REVISION)

    def test_caller_owns_uuid_idempotency_and_adapter_journal_has_only_domain_commands(self):
        self.start()
        receipts = set()
        command = {'type': 'combat_start_turn', 'actor_id': A, 'command_id': A, 'expected_revision': 0}
        def caller(value):
            if value['command_id'] not in receipts:
                adapter.apply_combat(self.state, value)
                receipts.add(value['command_id'])
        caller(command)
        before = deepcopy(self.state)
        caller(command)
        self.assertEqual(self.state, before)
        self.assertEqual(self.state['combat']['journal'], [{'type': 'combat_start_turn', 'actor_id': A, 'turn_id': 1}])


if __name__ == '__main__':
    unittest.main(verbosity=2)
