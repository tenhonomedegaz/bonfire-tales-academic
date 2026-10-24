"""The site grant uses the same generic operation as the encounter engine."""

from django.test import SimpleTestCase

from home.epic_talent_catalog import PARTIAL_EFFECTS
from home.tag_engine import evaluate_tags
from home.temporary_hp import received_temporary_hp


class TemporaryHpGrantTests(SimpleTestCase):
    def operations(self, *tags):
        return [vars(op) for op in evaluate_tags(
            tags, {'resolve_runtime': True, 'event': 'receive_temp_hp'}).operations]

    def test_health_bonus_stacks_with_other_sources_only_on_positive_grant(self):
        operations = self.operations(
            *PARTIAL_EFFECTS['dadiva-da-saude-abundante'],
            'always_active{temp_hp:+2}',
        )
        self.assertEqual(received_temporary_hp(7, operations), 14)
        self.assertEqual(received_temporary_hp(0, operations), 0)
        self.assertEqual(received_temporary_hp(7, []), 7)

    def test_inactive_and_unrelated_operations_do_not_change_grant(self):
        operations = self.operations('while_active{requires:self{sangrando}, temp_hp:+5}',
                                     'always_active{buff:max_hp:+40}')
        self.assertEqual(received_temporary_hp(7, operations), 7)
        with self.assertRaises(ValueError):
            received_temporary_hp(-1, operations)

    def test_unrelated_event_does_not_apply_temporary_hp_bonus(self):
        operations = self.operations('always_active{trigger=healing, temp_hp:+5}')
        self.assertEqual(received_temporary_hp(7, operations), 7)
