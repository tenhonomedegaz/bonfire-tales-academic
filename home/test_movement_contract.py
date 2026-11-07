"""Pure movement and mocked additive export contracts; no project DB/setup."""
import ast
from copy import deepcopy
from contextlib import ExitStack
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from home.movement_contract import character_movement, creature_movement


class CharacterMovementTests(unittest.TestCase):
    def test_whole_legacy_grammar_and_game_conversion(self):
        for text in ('30ft', '30 ft', '9m', '9 m', '9 m / 30 ft',
                     '30ft/9m', ' 9 m / 30 ft ', '30 FT'):
            with self.subTest(text=text):
                self.assertEqual(character_movement(text, {}), {
                    'schema': 1, 'unit': 'ft', 'speeds': {'walk': 30}, 'warnings': []})
        self.assertAlmostEqual(character_movement('10 m', {})['speeds']['walk'], 100 / 3)
        self.assertEqual(character_movement('9,15m / 30.5ft', {})['speeds']['walk'], 30.5)

    def test_aggregated_bonus_applies_once_and_ignores_display(self):
        state = {'velocidade': '12 m / 40 ft', 'velocidade_bonus': 10}
        before = deepcopy(state)
        self.assertEqual(character_movement('9 m / 30 ft', state)['speeds']['walk'], 40)
        self.assertEqual(state, before)
        state['velocidade'] = 'untrusted final prose 999 ft'
        self.assertEqual(character_movement('30ft', state)['speeds']['walk'], 40)

    def test_negative_bonus_and_zero_are_not_replaced_with_defaults(self):
        self.assertEqual(character_movement('30ft', {'velocidade_bonus': -10})['speeds']['walk'], 20)
        self.assertEqual(character_movement('30ft', {'velocidade_bonus': -30})['speeds']['walk'], 0)
        self.assertEqual(character_movement('0ft', {})['speeds']['walk'], 0)
        self.assertNotIn('walk', character_movement('30ft', {'velocidade_bonus': -31})['speeds'])

    def test_ambiguous_or_arbitrary_prose_never_yields_walk(self):
        for base in ('walk 30 ft', '30 ft while unarmored', '30 ft + 10 ft',
                     '9 metros', '30 feet', '30ft/30ft', '9m/10m', '30',
                     '30ft / 9m / 30ft', '30ft\n', '30\tft', '1e3ft',
                     '-30ft', '+30ft', '', 'x' * 81, None, True, 30):
            with self.subTest(base=base):
                result = character_movement(base, {'velocidade_bonus': 10})
                self.assertNotIn('walk', result['speeds'])
                self.assertTrue(result['warnings'])

    def test_inconsistent_dual_is_not_rounded_into_consistency(self):
        for base in ('9m / 40ft', '9.2m / 30.5ft',
                     '9m/30.000000000000000000000000000001ft'):
            with self.subTest(base=base):
                self.assertNotIn('walk', character_movement(base, {})['speeds'])

    def test_nonfinite_boolean_and_out_of_bounds_delta_are_excluded(self):
        for delta in (True, False, '10', None, [], {}, float('nan'),
                      float('inf'), float('-inf'), 10001, -10001, 10**400):
            with self.subTest(delta=delta):
                result = character_movement('30ft', {'velocidade_bonus': delta})
                self.assertNotIn('walk', result['speeds'])
                json.dumps(result, allow_nan=False)
        self.assertNotIn('walk', character_movement('10001ft', {})['speeds'])
        self.assertEqual(character_movement('10000ft', {})['speeds']['walk'], 10000)

    def test_mode_atoms_references_and_override_limits(self):
        state = {'velocidade_bonus': 10, 'movimento_modos': {
            'fly': '60ft', 'climb': 'walk', 'swim': '15.5ft', 'burrow': '0ft', 'walk': '90ft'}}
        result = character_movement('30ft', state)
        self.assertEqual(result['speeds'], {'walk': 40, 'fly': 60, 'climb': 40, 'swim': 15.5, 'burrow': 0})
        self.assertTrue(result['warnings'])

    def test_unknown_walk_does_not_invent_a_reference_but_keeps_independent_modes(self):
        result = character_movement('unknown', {'movimento_modos': {'fly': '60ft', 'swim': 'walk', 'walk': '30ft'}})
        self.assertEqual(result['speeds'], {'fly': 60})
        self.assertTrue(result['warnings'])

    def test_bad_or_conditional_modes_fail_closed(self):
        for value in ('30 ft', '9m', '30ft when active', '-10ft', 'NaNft',
                      '10001ft', 30, True, None, {'number': 30}, []):
            with self.subTest(value=value):
                result = character_movement('30ft', {'movimento_modos': {'fly': value}})
                self.assertNotIn('fly', result['speeds'])
                self.assertTrue(result['warnings'])
        for modes in (None, [], {str(i): '30ft' for i in range(9)}, {'teleport': '30ft'}):
            result = character_movement('30ft', {'movimento_modos': modes})
            self.assertEqual(result['speeds'], {'walk': 30})
            self.assertTrue(result['warnings'])

    def test_hover_and_falling_metadata_are_copied_without_mutating_state(self):
        state = {'movimento_modos': {'fly': 'walk'},
                 'movimento_propriedades': {'fly': {'hover': True}},
                 'queda_controlada': {'threshold_ft': 10, 'max_per_turn_ft': 60}}
        before = deepcopy(state)
        result = character_movement('30ft', state)
        self.assertEqual(result['properties'], {'fly': {'hover': True}})
        self.assertEqual(result['fall'], state['queda_controlada'])
        result['properties']['fly']['hover'] = False
        result['fall']['threshold_ft'] = 0
        self.assertEqual(state, before)

    def test_bad_or_conditional_metadata_is_excluded(self):
        for props in ({'fly': {'hover': 1}}, {'fly': {'hover': True, 'requires': 'active'}},
                      {'unknown': {'hover': True}}, [], 'hover'):
            result = character_movement('30ft', {'movimento_modos': {'fly': '40ft'}, 'movimento_propriedades': props})
            self.assertNotIn('properties', result)
            self.assertTrue(result['warnings'])
        for fall in ({'threshold_ft': True, 'max_per_turn_ft': 30},
                     {'threshold_ft': 0, 'max_per_turn_ft': 0},
                     {'threshold_ft': 0, 'max_per_turn_ft': float('nan')},
                     {'threshold_ft': 0, 'max_per_turn_ft': 30, 'requires': 'active'}, []):
            result = character_movement('30ft', {'queda_controlada': fall})
            self.assertNotIn('fall', result)
            self.assertTrue(result['warnings'])

    def test_missing_state_is_not_treated_as_a_known_zero_bonus(self):
        result = character_movement('30ft', None)
        self.assertEqual(result['speeds'], {})
        self.assertTrue(result['warnings'])

    def test_derive_projects_only_at_the_end_after_all_movement_writers(self):
        tree = ast.parse((Path(__file__).parent / 'character_engine.py').read_text(encoding='utf-8'))
        derive = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_derive')
        projection = next(node for node in derive.body if isinstance(node, ast.Assign)
                          and isinstance(node.value, ast.Call)
                          and isinstance(node.value.func, ast.Name)
                          and node.value.func.id == 'character_movement')
        writers = [node for node in ast.walk(derive) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name)
                   and node.func.id in {'apply_hunter_passives', 'apply_mutagen_movement'}]
        self.assertEqual(len(writers), 2)
        self.assertTrue(all(writer.lineno < projection.lineno for writer in writers))
        self.assertEqual(ast.unparse(projection.value.args[0]), 'personagem.velocidade')


class CreatureMovementTests(unittest.TestCase):
    def test_numeric_and_explicit_mode_speeds(self):
        for speed in (0, 30, 10000, 30.5):
            result = creature_movement(SimpleNamespace(statblock_json={'speed': speed}))
            self.assertEqual(result['speeds'], {'walk': speed})
            self.assertFalse(result['warnings'])
        result = creature_movement(SimpleNamespace(statblock_json={'speed': {
            'walk': 30, 'fly': {'number': 60}, 'swim': 10.5, 'canHover': True}}))
        self.assertEqual(result['speeds'], {'walk': 30, 'fly': 60, 'swim': 10.5})
        self.assertEqual(result['properties'], {'fly': {'hover': True}})

    def test_owner_and_whole_speed_conditions_do_not_guess(self):
        obj = SimpleNamespace(escala_com_dono=True, statblock_json={'speed': 30})
        self.assertEqual(creature_movement(obj)['speeds'], {})
        for key in ('condition', 'requires', 'special', 'choose'):
            result = creature_movement(SimpleNamespace(statblock_json={'speed': {'walk': 30, key: 'active'}}))
            self.assertEqual(result['speeds'], {})
            self.assertTrue(result['warnings'])

    def test_conditional_mode_is_excluded_without_discarding_independent_speed(self):
        result = creature_movement(SimpleNamespace(statblock_json={'speed': {
            'walk': 30, 'fly': {'number': 60, 'condition': 'during combat'}}}))
        self.assertEqual(result['speeds'], {'walk': 30})
        self.assertTrue(result['warnings'])

    def test_bad_speed_types_and_unknown_modes_are_bounded(self):
        for speed in (True, False, -1, 10001, float('inf'), float('nan'), '30ft', None, [], {}):
            result = creature_movement(SimpleNamespace(statblock_json={'speed': speed}))
            self.assertEqual(result['speeds'], {})
            self.assertTrue(result['warnings'])
            json.dumps(result, allow_nan=False)
        result = creature_movement(SimpleNamespace(statblock_json={'speed': {'walk': 30, 'teleport': 999}}))
        self.assertEqual(result['speeds'], {'walk': 30})
        self.assertTrue(result['warnings'])


class MovementExportTests(unittest.TestCase):
    def test_export_block_is_additive_and_does_not_parse_display(self):
        from home.management.commands.export_personagem_vtt import _bloco_derive, VERSAO_CONTRATO, VERSAO_MENOR
        movement = character_movement('30ft', {'velocidade_bonus': 10})
        state = {'movimento': movement, 'velocidade': 'kept final display'}
        block = _bloco_derive(state)
        self.assertEqual((VERSAO_CONTRATO, VERSAO_MENOR), (1, 3))
        self.assertEqual(block['movimento'], movement)
        self.assertEqual(block['deslocamento'], 'kept final display')
        block['movimento']['speeds']['walk'] = 99
        self.assertEqual(state['movimento']['speeds']['walk'], 40)
        old = _bloco_derive({'velocidade': '30ft'})
        self.assertEqual(old['movimento']['speeds'], {})
        self.assertTrue(old['movimento']['warnings'])

    def test_mocked_full_export_keeps_resource_paths_and_neutral_state(self):
        from home.management.commands import export_personagem_vtt as exporter
        class Rows(list):
            def select_related(self, *args):
                return self
            def order_by(self, *args):
                return self
        ledger = SimpleNamespace(exists=lambda: False)
        ledger.exclude = lambda **kw: ledger
        person = SimpleNamespace(pk=7, nome='Teste', nivel=1, id_raca_id=None,
                                 id_essencia_id=None, classes=Rows(),
                                 recursos=SimpleNamespace(filter=lambda **kw: ledger))
        movement = character_movement('30ft', {'velocidade_bonus': 10})
        state = {'nivel_total': 1, 'pv': {'maximo_calculado': 30}, 'ca': 13,
                 'velocidade': '12 m / 40 ft', 'movimento': movement, 'carteira': {}}
        resources = {
            '_recursos_espacos_magia': [{'id_fonte': 'espaco-magia:1', 'max': 2}],
            '_recursos_dados_de_vida': [{'id_fonte': 'dado-de-vida:d8', 'max': 1}],
            '_recursos_consumiveis_export': [{'id_fonte': 'TbRecursoclasse:2', 'max': 3}],
        }
        for entries in resources.values():
            entries[0].update(nome='Pool real', reset='long-rest')
        fake_engine = SimpleNamespace(derive=lambda obj: state)
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {'home.character_engine': fake_engine}))
            mocks = [stack.enter_context(patch.object(exporter, name, return_value=entries))
                     for name, entries in resources.items()]
            stack.enter_context(patch.object(exporter, '_habilidades', return_value=[]))
            stack.enter_context(patch.object(exporter, '_magias', return_value=[]))
            data = exporter.exportar_personagem(person, gerado_de='isolated-test')
        self.assertEqual(data['versao_menor'], 3)
        self.assertEqual(data['derive']['movimento']['speeds'], {'walk': 40})
        self.assertEqual(data['derive']['deslocamento'], '12 m / 40 ft')
        self.assertEqual({row['id_fonte'] for row in data['recursos']},
                         {'espaco-magia:1', 'dado-de-vida:d8', 'TbRecursoclasse:2'})
        self.assertEqual(data['estado_mesa']['pv_atual'], 30)
        self.assertTrue(all(mock.call_count == 1 for mock in mocks))


if __name__ == '__main__':
    unittest.main()
