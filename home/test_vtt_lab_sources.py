"""Plain-object VTT projections: no Django setup, environment, or database."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from home.vtt_lab_sources import character_resources, character_rules, creature_rules, creature_snapshot


class TbTalento(SimpleNamespace):
    pass


def creature(**changes):
    values = dict(pk=1, nome='Criatura de teste', slug='criatura-de-teste',
                  pv='30', ca='13', escala_com_dono=False,
                  tags_json=['always_active', 'resist:fogo'],
                  statblock_json={'hp': {'average': 30},
                                  'actions': [{'name': 'Golpe', 'tags_json': []}]})
    values.update(changes)
    return SimpleNamespace(**values)


def exported(**changes):
    values = {
        'versao_contrato': 1, 'versao_menor': 1,
        'personagem': {'pk': 7, 'nivel_total': 8,
                       'classes': [{'classe_pk': 1, 'nivel': 8}]},
        'derive': {'pv_max': 30, 'ca': 13, 'pb': 3,
                   'atributos': {'FOR': {'valor': 16, 'mod': 3},
                                 'SAB': {'valor': 14, 'mod': 2}}},
        'habilidades': [{'fonte': 'TbTalento:1', 'nome': 'Fonte real'}],
    }
    values.update(changes)
    return values


def feature(tags, pk=1, level=None, **changes):
    values = {'pk': pk, 'nome': 'Fonte real', 'tags_json': tags}
    values.update(changes)
    return ('talento', 'Catalogo', TbTalento(**values), level)


def project(features, data=None, choices=None, lists=None, substitute=None):
    with patch('home.vtt_lab_sources._character_features', return_value=features), patch(
            'home.vtt_lab_sources._character_choices', return_value=(choices or {}, lists or {})):
        if substitute is None:
            return character_rules(SimpleNamespace(pk=7), data or exported())
        with patch('home.vtt_lab_sources._choice_subs', side_effect=substitute):
            return character_rules(SimpleNamespace(pk=7), data or exported())


class CreatureSnapshotTests(unittest.TestCase):
    def test_exact_fixture_contract_and_no_mutation(self):
        obj = creature()
        before = deepcopy(vars(obj))
        self.assertEqual(creature_snapshot(obj), {
            'versao_contrato': 1, 'versao_menor': 1,
            'criatura': {'pk': 1, 'nome': obj.nome, 'slug': obj.slug},
            'derive': {'pv_max': 30, 'ca': 13},
            'estado_mesa': {'pv_atual': 30}, 'avisos': [],
        })
        self.assertEqual(vars(obj), before)

    def test_hp_average_wins_over_numeric_field_and_formula(self):
        obj = creature(pv='99', statblock_json={'hp': {'average': 24, 'formula': '4d8+6'}})
        self.assertEqual(creature_snapshot(obj)['derive']['pv_max'], 24)

    def test_hp_falls_back_only_to_positive_fixed_numeric_field(self):
        for value in ('1', '56', 21):
            self.assertEqual(creature_snapshot(creature(pv=value, statblock_json={}))['derive']['pv_max'], int(value))
        for value in ('3d8+4', '30 (4d8)', '', None, True, False, 0, -1,
                      3.5, float('nan'), float('inf'), '9' * 100):
            with self.subTest(value=value), self.assertRaises(ValueError):
                creature_snapshot(creature(pv=value, statblock_json={}))

    def test_malformed_average_and_owner_scaling_are_rejected(self):
        for value in (True, 0, -1, '30', 2.5, None, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                creature_snapshot(creature(statblock_json={'hp': {'average': value}}))
        with self.assertRaises(ValueError):
            creature_snapshot(creature(escala_com_dono=True))

    def test_fixed_ac_shapes_and_ambiguous_ac_warning(self):
        for ac in (15, '15', [15], [{'ac': 15}]):
            self.assertEqual(creature_snapshot(creature(statblock_json={'ac': ac}))['derive']['ca'], 15)
        for ac in ([13, 17], {'special': '13 + PB'}, True, float('nan')):
            result = creature_snapshot(creature(statblock_json={'ac': ac}))
            self.assertNotIn('ca', result['derive'])
            self.assertTrue(result['avisos'])

    def test_invalid_identity_or_statblock_fails_closed(self):
        for changes in ({'pk': True}, {'nome': ''}, {'slug': None},
                        {'statblock_json': []}, {'statblock_json': 'not-json'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                creature_snapshot(creature(**changes))


class CreatureRuleTests(unittest.TestCase):
    def test_no_tag_action_is_explicitly_manual_with_partial_warning(self):
        result = creature_rules(creature())
        self.assertEqual(result['defensive_tags'], ['always_active', 'resist:fogo'])
        self.assertEqual(result['offensive_tags'], result['defensive_tags'])
        self.assertEqual(result['actions'], [{'id': 'manual', 'nome': 'Ataque declarado', 'tags': []}])
        self.assertTrue(any('partial' in warning for warning in result['warnings']))

    def test_preserves_full_real_action_program_and_legacy_tags_alias(self):
        tag = 'instant{trigger=hit, apply:envenenado(target:target,duration:until_turn_start)}'
        obj = creature(statblock_json={'action': [{'name': 'Mordida', 'tags': [tag]}]})
        result = creature_rules(obj)
        self.assertEqual(result['actions'][0]['tags'], [tag])
        self.assertEqual(result['actions'][0]['nome'], 'Mordida')
        self.assertNotIn(tag, result['offensive_tags'])

    def test_traits_with_on_hit_are_not_flattened_to_global_passives(self):
        tag = 'on:hit{apply:caido(duration:until_turn_start)}'
        obj = creature(statblock_json={'traits': [
            {'name': 'Defesa real', 'tags_json': ['immune:frio']},
            {'name': 'Efeito real', 'tags_json': [tag]},
        ]})
        result = creature_rules(obj)
        self.assertIn('immune:frio', result['defensive_tags'])
        self.assertNotIn(tag, result['defensive_tags'])
        self.assertEqual(result['actions'][0]['tags'], [tag])

    def test_prose_type_and_challenge_rating_do_not_create_mechanics(self):
        obj = creature(tags_json=[], statblock_json={
            'type': 'dragon', 'cr': '20', 'resist': ['fire'],
            'actions': [{'name': 'Fire attack', 'entries': ['Deals 50 fire damage.']}],
        })
        result = creature_rules(obj)
        self.assertEqual(result['defensive_tags'], [])
        self.assertEqual(result['offensive_tags'], [])
        self.assertEqual(result['actions'][0]['id'], 'manual')

    def test_mixed_root_is_preserved_whole_with_partial_warning(self):
        tags = ['resist:fogo', 'on:hit{apply:caido(duration:until_turn_start)}']
        result = creature_rules(creature(tags_json=tags, statblock_json={}))
        self.assertEqual(result['actions'][0]['tags'], tags)
        self.assertEqual(result['defensive_tags'], [])
        self.assertTrue(any('mixed source' in message for message in result['warnings']))

    def test_bad_fields_and_bounded_tags_do_not_automate(self):
        for tags in ('resist:fogo', [True], ['instant{'], ['x' * 4097], ['resist:fogo'] * 129):
            with self.subTest(tags=str(tags)[:60]):
                result = creature_rules(creature(tags_json=tags))
                self.assertEqual(result['defensive_tags'], [])
                self.assertTrue(result['warnings'])
        result = creature_rules(creature(statblock_json={'actions': [None, {'name': 'Bad', 'tags_json': 'x'}]}))
        self.assertEqual(result['actions'][0]['id'], 'manual')

    def test_root_alias_deduplicates_without_mutating_source(self):
        obj = creature(statblock_json={'tags': ['resist:fogo', 'ignore:resist(frio)']})
        before = deepcopy(vars(obj))
        result = creature_rules(obj)
        self.assertEqual(result['defensive_tags'].count('resist:fogo'), 1)
        self.assertEqual(vars(obj), before)


class CharacterRuleTests(unittest.TestCase):
    def test_resource_cost_alone_makes_a_source_an_action_not_a_passive(self):
        tags = ['resource_cost:furias:1', 'crit_dmg:pb']
        result = project([feature(tags)])
        self.assertEqual(result['actions'][0]['tags'], tags)
        self.assertEqual(result['actions'][0]['id'], 'TbTalento:1')
        self.assertEqual(result['defensive_tags'], [])
        self.assertEqual(result['offensive_tags'], [])
        self.assertNotIn('resources', result)

    def test_creature_resource_cost_is_not_global(self):
        result = creature_rules(creature(tags_json=['resource_cost:reserva'], statblock_json={}))
        self.assertEqual(result['actions'][0]['tags'], ['resource_cost:reserva'])
        self.assertEqual(result['offensive_tags'], [])

    def test_unsupported_uses_defines_and_conditional_costs_remain_manual(self):
        for tags in (['action.uses:1'], ['action{uses:1}'],
                     ['define{reserva{max:pb,reset:long_rest}}', 'resource_cost:reserva'],
                     ['requires:equipped{shield}', 'resource_cost:reserva']):
            with self.subTest(tags=tags):
                result = project([feature(tags)])
                self.assertEqual(result['actions'][0],
                                 {'id': 'manual', 'nome': 'Ataque declarado', 'tags': []})
                self.assertEqual(result['defensive_tags'], [])
                self.assertTrue(result['warnings'])

    def test_only_exported_source_identities_are_projected(self):
        result = project([feature(['resist:fogo']), feature(['immune:frio'], pk=2)])
        self.assertEqual(result['defensive_tags'], ['resist:fogo'])
        self.assertNotIn('immune:frio', result['offensive_tags'])
        self.assertEqual(result['actions'][0]['id'], 'manual')

    def test_action_has_exported_context_and_source_specific_class_level(self):
        data = exported(personagem={'nivel_total': 8, 'classes': [{'nivel': 5}, {'nivel': 3}]})
        tags = ['instant{attack:melee,reach:classlvl+pb}']
        result = project([feature(tags, level=3)], data)
        action = result['actions'][0]
        self.assertEqual(action['id'], 'TbTalento:1')
        self.assertEqual(action['tags'], tags)
        self.assertEqual(action['context']['classlvl'], 3)
        self.assertEqual(action['context']['lvl'], 8)
        self.assertEqual(action['context']['pb'], 3)
        self.assertEqual(action['context']['str_mod'], 3)
        self.assertNotIn('classlvl', result['tag_context'])

    def test_ambiguous_class_level_passive_does_not_get_total_level(self):
        data = exported(personagem={'nivel_total': 8, 'classes': [{'nivel': 5}, {'nivel': 3}]})
        result = project([feature(['crit_dmg:classlvl'], level=3)], data)
        self.assertEqual(result['offensive_tags'], [])
        self.assertEqual(result['actions'][0]['id'], 'manual')
        self.assertTrue(any('classlvl' in warning for warning in result['warnings']))

    def test_missing_action_class_level_context_is_manual(self):
        data = exported(personagem={'nivel_total': 8, 'classes': [{'nivel': 5}, {'nivel': 3}]})
        result = project([feature(['instant{reach:classlvl}'])], data)
        self.assertEqual(result['actions'][0]['id'], 'manual')
        self.assertTrue(result['warnings'])

    def test_resolved_choice_uses_existing_substitution_helper_without_mutation(self):
        original = feature(['resist:pick:elemento'])
        before = deepcopy(original[2].tags_json)
        result = project([original], choices={'elemento': 'fogo'}, lists={'elemento': ['fogo']},
                         substitute=lambda tag, values: tag.replace('pick:elemento', values['elemento']))
        self.assertEqual(result['defensive_tags'], ['resist:fogo'])
        self.assertEqual(original[2].tags_json, before)

    def test_unresolved_or_ambiguous_choices_and_gates_remain_manual(self):
        for tag in ('resist:pick:elemento', 'match(elemento){fogo{resist:fogo}}',
                    'requires:equipped{shield},resist:fogo'):
            result = project([feature([tag])], substitute=lambda tag, values: tag)
            self.assertEqual(result['defensive_tags'], [])
            self.assertEqual(result['actions'][0]['id'], 'manual')
            self.assertTrue(result['warnings'])
        result = project([feature(['resist:pick:elemento'])],
                         choices={'elemento': 'fogo'}, lists={'elemento': ['fogo', 'frio']})
        self.assertEqual(result['defensive_tags'], [])

    def test_duplicate_and_table_only_features_are_not_projected_twice(self):
        first = feature(['resist:fogo'])
        data = exported(habilidades=[{'fonte': 'TbTalento:1'}, {'fonte': 'TbTalento:2'}])
        result = project([first, first, feature(['immune:frio'], pk=2, table_only=True)], data)
        self.assertEqual(result['defensive_tags'], ['resist:fogo'])
        self.assertTrue(result['warnings'])

    def test_static_derived_hp_and_ac_are_not_applied_again(self):
        data = exported()
        before = deepcopy(data)
        result = project([feature(['hp:+100', 'ca:+10', 'resist:fogo'])], data)
        self.assertEqual(data, before)
        self.assertNotIn('derive', result)
        self.assertNotIn('hp', result['tag_context'])
        self.assertEqual(data['derive']['pv_max'], 30)
        self.assertEqual(data['derive']['ca'], 13)

    def test_actor_context_is_bounded_finite_and_not_shared_with_action(self):
        data = exported()
        data['derive']['atributos']['FOR']['mod'] = True
        data['derive']['atributos']['SAB']['mod'] = float('inf')
        result = project([feature(['instant{attack:melee}'])], data)
        self.assertNotIn('str_mod', result['tag_context'])
        self.assertNotIn('wis_mod', result['tag_context'])
        result['actions'][0]['context']['pb'] = 99
        self.assertEqual(result['tag_context']['pb'], 3)

    def test_malformed_export_and_feature_limits_fail_closed(self):
        for data in (None, [], {'versao_contrato': 2}, exported(versao_contrato=True), exported(habilidades='bad')):
            with self.subTest(data=data), self.assertRaises(ValueError):
                character_rules(SimpleNamespace(), data)
        with self.assertRaises(ValueError):
            project([feature([])] * 129)


class CharacterResourceTests(unittest.TestCase):
    def pool(self, **changes):
        row = {'id_fonte': 'TbRecursoclasse:12', 'nome': 'Furias',
               'max': 3, 'reset': 'long-rest'}
        row.update(changes)
        return row

    def test_neutral_resource_contract_uses_original_id_and_canonical_aliases(self):
        row = self.pool(nome='F\u00farias', slug='furia-da-classe', current=1)
        before = deepcopy(row)
        result = character_resources({'recursos': [row]})
        self.assertEqual(result, {'TbRecursoclasse:12': {
            'nome': 'F\u00farias', 'max': 3, 'current': 3, 'reset': 'long-rest',
            'aliases': ['furias', 'tbrecursoclasse:12', 'furia_da_classe'],
        }})
        self.assertEqual(row, before)

    def test_missing_or_empty_resources_are_empty_and_missing_reset_is_manual(self):
        self.assertEqual(character_resources({}), {})
        self.assertEqual(character_resources({'recursos': []}), {})
        row = self.pool()
        del row['reset']
        self.assertEqual(character_resources({'recursos': [row]})[row['id_fonte']]['reset'], 'manual')

    def test_zero_and_maximum_integer_bounds_are_valid(self):
        for value in (0, 1000000):
            row = self.pool(max=value)
            result = character_resources({'recursos': [row]})[row['id_fonte']]
            self.assertEqual(result['max'], value)
            self.assertEqual(result['current'], value)

    def test_noninteger_nonfinite_and_out_of_bounds_maxima_fail_closed(self):
        for value in (True, False, None, '3', 3.0, -1, 1000001,
                      float('nan'), float('inf'), float('-inf'), {}, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                character_resources({'recursos': [self.pool(max=value)]})

    def test_missing_opaque_and_malformed_ids_are_not_invented(self):
        for value in (None, '', '?', 'TbRecursoclasse:?', 'tag:?recurso',
                      12, True, [], 'pool/name', 'x' * 181):
            with self.subTest(value=value), self.assertRaises(ValueError):
                character_resources({'recursos': [self.pool(id_fonte=value)]})
        row = self.pool()
        del row['id_fonte']
        with self.assertRaises(ValueError):
            character_resources({'recursos': [row]})
        resource_id = 'x' * 180
        self.assertIn(resource_id, character_resources({'recursos': [self.pool(id_fonte=resource_id)]}))

    def test_duplicate_ids_raise_instead_of_overwriting_or_merging(self):
        first = self.pool()
        for second in (self.pool(max=9), self.pool(id_fonte=' TbRecursoclasse:12 ')):
            with self.subTest(second=second), self.assertRaises(ValueError):
                character_resources({'recursos': [first, second]})

    def test_alias_collisions_remain_on_both_distinct_pools(self):
        rows = [self.pool(nome='F\u00faria'), self.pool(id_fonte='TbRecursoclasse:13', nome='Furia')]
        result = character_resources({'recursos': rows})
        self.assertEqual(len(result), 2)
        self.assertIn('furia', result['TbRecursoclasse:12']['aliases'])
        self.assertIn('furia', result['TbRecursoclasse:13']['aliases'])

    def test_only_explicit_name_id_and_slug_are_aliases(self):
        row = self.pool(id_fonte='tag:poder', nome='Reserva Magica', aliases=['inventado'])
        result = character_resources({'recursos': [row]})['tag:poder']
        self.assertEqual(result['aliases'], ['reserva_magica', 'tag:poder'])
        row['slug'] = 'Reserva-Magica'
        self.assertEqual(character_resources({'recursos': [row]})['tag:poder']['aliases'], result['aliases'])

    def test_bounded_malformed_payloads_and_text_fail_closed(self):
        for payload in (None, [], {'recursos': None}, {'recursos': {}},
                        {'recursos': [None]}, {'recursos': [self.pool()] * 129}):
            with self.subTest(payload=str(payload)[:60]), self.assertRaises(ValueError):
                character_resources(payload)
        for field, values in {'nome': ['', None, 'x' * 201, 'nome\nnovo', '?'],
                              'slug': [True, [], 'x' * 161],
                              'reset': [True, None, '', 'x' * 81]}.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    character_resources({'recursos': [self.pool(**{field: value})]})

    def test_projection_never_calls_official_resource_ledger(self):
        with patch('home.resource_engine.ensure_resource', side_effect=AssertionError('ledger write')), patch(
                'home.resource_engine.preview_resource', side_effect=AssertionError('ledger read')):
            result = character_resources({'recursos': [self.pool()]})
        self.assertEqual(result['TbRecursoclasse:12']['current'], 3)


if __name__ == '__main__':
    unittest.main()
