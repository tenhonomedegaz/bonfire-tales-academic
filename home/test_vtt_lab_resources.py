"""Pure resource activation tests; no Django settings, model or database setup."""

import unittest
from copy import deepcopy
from unittest.mock import patch

from home.tag_engine.library import Library
from home.vtt_lab_resources import action_costs, apply_costs, validate_pools


def pools():
    return {'TbRecursoclasse:12': {'nome': 'An arbitrary pool', 'max': 10, 'current': 8,
                                  'aliases': ['ki', 'pontos_de_ki'], 'reset': 'short-rest'},
            'tag:charges': {'nome': 'Another arbitrary label', 'max': 4, 'current': 3,
                            'aliases': ['charges']}}


class VttLabResourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = Library(prefer_db=False).raw

    def setUp(self):
        self.enterContext(patch('home.tag_engine.library._active_database_library',
                                side_effect=AssertionError('No DB library access')))

    def costs(self, tags, rulescontext=None, resources=None, **extra):
        return action_costs({'tags': tags, **extra}, rulescontext or {},
                            pools() if resources is None else resources, self.raw)

    def test_one_two_dotted_action_and_unconditional_instant(self):
        for tags, amount in [(['resource_cost:ki'], 1), (['resource_cost:ki:2'], 2),
                             (['action.resource_cost:ki'], 1),
                             (['instant{resource_cost:pontos_de_ki:2}'], 2),
                             (['action{resource_cost:ki:2}'], 2)]:
            with self.subTest(tags=tags):
                self.assertEqual(self.costs(tags), {'TbRecursoclasse:12': amount})

    def test_real_evaluator_formulas_and_action_context_override(self):
        self.assertEqual(self.costs(['resource_cost:ki:pb'], {'pb': 3}), {'TbRecursoclasse:12': 3})
        self.assertEqual(self.costs(['resource_cost:ki:roundup(pb/2)'], {'pb': 3}), {'TbRecursoclasse:12': 2})
        self.assertEqual(self.costs(['resource_cost:ki:classlvl'], {'classlvl': 1},
                                   context={'classlvl': 4}), {'TbRecursoclasse:12': 4})

    def test_cost_aggregation_multiple_pools_and_atomic_debit(self):
        before = pools()
        costs = self.costs(['resource_cost:ki', 'resource_cost:ki:2', 'resource_cost:charges:2'])
        self.assertEqual(costs, {'TbRecursoclasse:12': 3, 'tag:charges': 2})
        actual = apply_costs(before, costs)
        self.assertEqual(actual['TbRecursoclasse:12']['current'], 5)
        self.assertEqual(actual['tag:charges']['current'], 1)
        self.assertEqual(before, pools())
        with self.assertRaises(ValueError):
            apply_costs(before, {'TbRecursoclasse:12': 1, 'tag:charges': 4})
        self.assertEqual(before, pools())

    def test_no_display_name_matching_or_ambiguous_alias_fallback(self):
        self.assertEqual(self.costs(['resource_cost:ki']), {'TbRecursoclasse:12': 1})
        for tags in (['resource_cost:unknown'], ['resource_cost:arbitrary_pool']):
            with self.assertRaisesRegex(ValueError, 'missing or ambiguous'):
                self.costs(tags)
        ambiguous = pools()
        ambiguous['tag:charges']['aliases'].append('ki')
        with self.assertRaisesRegex(ValueError, 'missing or ambiguous'):
            self.costs(['resource_cost:ki'], resources=ambiguous)

    def test_aliases_reuse_resource_engine_canonical_key(self):
        resources = {'Tag:Pontos de Ki': {'nome': 'Unrelated label', 'max': 4, 'current': 4,
                                         'aliases': ['Pontos-de-Ki']}}
        self.assertEqual(self.costs(['resource_cost:pontos_de_ki'], resources=resources),
                         {'Tag:Pontos de Ki': 1})
        normalized = validate_pools(resources)
        self.assertEqual(normalized['Tag:Pontos de Ki']['aliases'], ['pontos_de_ki'])
        resources['Tag:Pontos de Ki']['aliases'] = ['x' * 200]
        self.assertEqual(self.costs(['resource_cost:' + 'x' * 200], resources=resources),
                         {'Tag:Pontos de Ki': 1})
        resources['Tag:Pontos de Ki']['aliases'] = ['x' * 201]
        with self.assertRaises(ValueError):
            validate_pools(resources)

    def test_alternatives_ranges_uses_restoration_opaque_and_conditional_are_refused(self):
        unsupported = [
            'resource_cost:{ki|charges}', 'resource_cost:ki:1..3', 'resource_cost:ki:1..all',
            'uses:1/rest', 'uses{max:2}', 'resource_restore:ki:1',
            'instant{trigger=hit,resource_cost:ki}', 'if(in_dim_light){resource_cost:ki}',
            'requires:in_dim_light,resource_cost:ki', 'while_active{resource_cost:ki}',
            'resource_cost:ki(per:turn)', 'cast{resource_cost:ki}',
            'ability:foo{resource_cost:ki}', 'define{nested:resource_cost:ki}',
            'metadata:resource_cost:ki', 'label:"resource_cost:ki"',
            'resource_cost:ki=2', 'resource_cost:ki:all',
        ]
        for tag in unsupported:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.costs([tag], {'in_dim_light': True})

    def test_rejects_unresolved_boolean_fractional_and_out_of_bounds_costs(self):
        for formula in ('0', '-1', '1000001', '1/2', 'missing', 'true', 'True+1', 'pb'):
            with self.subTest(formula=formula), self.assertRaises(ValueError):
                self.costs(['resource_cost:ki:' + formula], {'pb': True})
        for context in ({'pb': 2.0}, {'pb': False}):
            with self.assertRaises(ValueError):
                self.costs(['resource_cost:ki:pb'], context)

    def test_resource_free_actions_stay_free_but_unknown_cost_vocabulary_is_rejected(self):
        self.assertEqual(self.costs([]), {})
        self.assertEqual(self.costs(['instant{attack:melee,dmg:1d6(fogo)}']), {})
        raw = deepcopy(self.raw)
        raw['primitives'].pop('resource_cost')
        with self.assertRaisesRegex(ValueError, 'pinned vocabulary'):
            action_costs({'tags': ['resource_cost:ki']}, {}, pools(), raw)

    def test_pool_schema_and_strict_integer_validation(self):
        for field, value in [('max', True), ('max', 1.0), ('max', -1), ('max', 1_000_001),
                             ('current', True), ('current', 1.0), ('current', 11),
                             ('aliases', 'ki'), ('aliases', ['']), ('reset', {}), ('nome', '')]:
            candidate = pools()
            candidate['TbRecursoclasse:12'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_pools(candidate)
        with self.assertRaises(ValueError):
            validate_pools(None)
        self.assertEqual(validate_pools({}), {})
        original = pools()
        cloned = validate_pools(original)
        cloned['TbRecursoclasse:12']['current'] = 0
        self.assertEqual(original, pools())


if __name__ == '__main__':
    unittest.main(verbosity=2)
