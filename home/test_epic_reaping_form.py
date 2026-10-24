"""Readable sheet damage rows preserve each die and each damage type."""

from django.http import QueryDict
from django.test import SimpleTestCase

from home.epic_reaping import maximize_damage_type
from home.epic_reaping_form import parse_reaping_form


class ReapingFormTests(SimpleTestCase):
    def payload(self):
        query = QueryDict(mutable=True)
        query.update({"creature_ref": "encontro:alvo", "source_kind": "spell",
                      "chosen_type": "necrótico"})
        query.setlist("damage_type", ["cortante", "necrótico"])
        query.setlist("dice_expression", ["3d8", "2d6"])
        query.setlist("rolled_values", ["1,4,8", "2,5"])
        query.setlist("fixed_damage", ["2", "0"])
        return query

    def test_selected_type_maximizes_only_its_dice(self):
        data = parse_reaping_form(self.payload())
        resolved = maximize_damage_type(data["components"], data["chosen_type"])
        self.assertEqual(resolved.total, 27)
        self.assertEqual(resolved.components[0].applied_rolls, (1, 4, 8))
        self.assertEqual(resolved.components[1].applied_rolls, (6, 6))
        self.assertEqual(resolved.components[0].fixed, 2)

    def test_missing_roll_or_malformed_row_is_rejected(self):
        data = self.payload()
        data.setlist("rolled_values", ["1,4", "2,5"])
        with self.assertRaises(ValueError):
            parse_reaping_form(data)
        data = self.payload()
        data.setlist("dice_expression", ["3d8+2", "2d6"])
        with self.assertRaises(ValueError):
            parse_reaping_form(data)
