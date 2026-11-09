"""The point-stepper preserves the existing two-attribute ASI contract."""
from django.db import transaction

from . import test_levelup_multiclass_flow as multiclass_flow
from .character_engine import derive
from .test_criador import _CriadorBase
from .views import _lvl_aplicar_asi


class AttributeAllocationTests(_CriadorBase):
    setUp = multiclass_flow.MulticlassFlowTests.setUp

    def test_two_points_split_or_together_persist_once_and_reject_invalid_attribute(self):
        self.person.classes.filter(id_classe=self.fighter).update(nivel=4)
        self.person.nivel = 4
        self.person.save(update_fields=['nivel'])
        for second, strength, dexterity in [('FOR', 17, 15), ('DES', 16, 16)]:
            with self.subTest(second=second), transaction.atomic():
                self.assertTrue(_lvl_aplicar_asi(self.person, {'asi_attr_1': 'INVALID', 'asi_attr_2': second}))
                self.assertFalse(self.person.atributo_bonus.exists())
                self.assertEqual(_lvl_aplicar_asi(self.person, {'asi_attr_1': 'FOR', 'asi_attr_2': second}), [])
                self.person.refresh_from_db()
                attributes = derive(self.person)['atributos']
                self.assertEqual(attributes['FOR']['valor'], strength)
                self.assertEqual(attributes['DES']['valor'], dexterity)
                before = list(self.person.atributo_bonus.values_list('atributo', 'valor'))
                self.assertTrue(_lvl_aplicar_asi(self.person, {'asi_attr_1': 'FOR', 'asi_attr_2': second}))
                self.assertEqual(list(self.person.atributo_bonus.values_list('atributo', 'valor')), before)
                transaction.set_rollback(True)
