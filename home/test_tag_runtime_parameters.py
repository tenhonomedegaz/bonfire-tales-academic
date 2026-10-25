"""Focused, database-free regressions for data-driven runtime operands."""

import uuid
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.template import Engine
from django.test import SimpleTestCase

from home import epic_fate, epic_free_cast, epic_recovery_pool
from home import epic_relentless_resistance as resistance
from home import epic_spell_damage
from home.tag_engine.runtime_values import d20_adjustment, dice_spec, roll_dice, slot_preservation


class RuntimeParameterTests(SimpleTestCase):
    def source(self, module, tags):
        stack = ExitStack()
        self.addCleanup(stack.close)
        source = SimpleNamespace(tags_json=tags, nome="Unrelated source", pk=876)
        stack.enter_context(patch.object(module, "_talent_attr_map", return_value={}))
        stack.enter_context(patch.object(module, "_features_do_personagem",
                                        return_value=[("feature", "Unrelated source", source, 1)]))
        if hasattr(module, "_feature_identity"):
            stack.enter_context(patch.object(module, "_feature_identity", return_value="feature:876"))
        return source

    def test_dice_operands_and_bounds(self):
        for value, expected in (("3d12", (3, 12)), ("d8", (1, 8)), ("2D6", (2, 6))):
            self.assertEqual(dice_spec(value), expected)
        for value in ("0d6", "1d0", "101d6", "1d1001", "2d6+3", "2d6;delete"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                dice_spec(value)
        random = MagicMock(side_effect=[0, 7])
        self.assertEqual(roll_dice("2d8", random), [1, 8])
        self.assertEqual([call.args for call in random.call_args_list], [(8,), (8,)])

    def test_intervention_uses_tag_range_and_dice_not_talent_name(self):
        tag = epic_fate.ALTER_FATE_TAG.replace("60ft", "90ft").replace("2d4", "3d6")
        self.assertEqual(d20_adjustment(tag), {"range_ft": 90, "dice": "3d6"})
        self.source(epic_fate, [tag])
        definition = epic_fate._definition(object())
        self.assertEqual(definition["origin"], "feature:876")
        self.assertEqual(definition["dice"], "3d6")
        self.assertFalse(definition["recover_on_critical"])
        self.assertIsNone(epic_fate._source(object(), recovery=True))

    def test_intervention_rejects_inconsistent_or_unsupported_contracts(self):
        for tag in (epic_fate.ALTER_FATE_TAG.replace("roll:2d4", "roll:3d8"),
                    epic_fate.ALTER_FATE_TAG + ", range:200ft",
                    epic_fate.ALTER_FATE_TAG.replace("uses{1", "uses{2"),
                    epic_fate.ALTER_FATE_TAG.replace("2d4", "101d6")):
            with self.subTest(tag=tag):
                self.assertIsNone(d20_adjustment(tag))

    def test_free_cast_levels_and_die_are_configurable(self):
        tag = "cast{spell_level:2|5, roll:d8, match_level:without_slot}"
        self.assertEqual(slot_preservation(tag), {"levels": (2, 5), "faces": 8})
        self.source(epic_free_cast, [tag])
        self.assertFalse(epic_free_cast.free_cast_available(object(), 1))
        self.assertTrue(epic_free_cast.free_cast_available(object(), 5))
        with patch.object(epic_free_cast.secrets, "randbelow", return_value=4) as random:
            self.assertEqual(epic_free_cast.roll_free_cast(object(), 5),
                             {"die": 5, "slot_preserved": True})
        random.assert_called_once_with(8)

    def test_free_cast_original_and_invalid_contracts(self):
        self.assertEqual(slot_preservation(epic_free_cast.FREE_CAST_TAG),
                         {"levels": (1, 2, 3, 4), "faces": 4})
        for tag in ("cast{spell_level:9, roll:d4, match_level:without_slot}",
                    "cast{spell_level:1, roll:2d4, match_level:without_slot}",
                    "cast{spell_level:0, roll:d4, match_level:without_slot}"):
            self.assertIsNone(slot_preservation(tag))

    def test_resistance_definition_reads_new_dice_and_range(self):
        tag = resistance.ALTER_RUIN_TAG.replace("3d12", "2d8").replace("60ft", "120ft")
        self.source(resistance, [resistance.RESISTANCE_TAG, tag])
        definition = resistance._definition(object())
        self.assertEqual((definition["dice"], definition["range_ft"]), ("2d8", 120))

    def test_resistance_choice_count_and_types_are_data(self):
        tag = "pick:damage_resistance:1(from:fogo|frio, upgrade:resist_to_immune, swap:long_rest)"
        self.source(resistance, [tag, resistance.ALTER_RUIN_TAG])
        definition = resistance._definition(object())
        self.assertEqual((definition["count"], definition["types"]), (1, ("fogo", "frio")))

    def test_recovery_pool_size_faces_and_reset_come_from_tag(self):
        tag = epic_recovery_pool.RECOVERY_POOL_TAG.replace("10", "6").replace("short_or_long", "long_rest")
        self.source(epic_recovery_pool, [tag])
        definition = epic_recovery_pool._definition(object())
        self.assertEqual((definition["maximum"], definition["faces"], definition["reset"]),
                         (6, 6, "long_rest"))
        self.assertEqual(epic_recovery_pool._dice_count(12), 12)
        # The selected pool, rather than a fixed ten, enforces its actual maximum.

    def test_spell_damage_floor_and_trigger_are_configurable(self):
        self.source(epic_spell_damage,
                    ["trigger=cast_spell(circle:3+), damage_die_floor:4(roll:1|2|3)"])
        self.assertEqual(epic_spell_damage._definition(object()),
                         {"circle": 3, "floor": 4, "rolls": {1, 2, 3}})

    def test_ruin_command_rolls_declared_dice(self):
        person = SimpleNamespace(pk=123, nivel=17, classes=SimpleNamespace(all=lambda: []))
        definition = {"origin": "feature:876", "range_ft": 120, "dice": "2d8"}
        with ExitStack() as stack:
            stack.enter_context(patch.object(resistance.TbPersonagem.objects, "select_for_update",
                                             return_value=MagicMock(get=lambda **kw: person)))
            stack.enter_context(patch.object(resistance, "_receipt", return_value=("fp", None)))
            stack.enter_context(patch.object(resistance, "_definition", return_value=definition))
            stack.enter_context(patch.object(resistance, "_choice_state", return_value=(None, ["fogo"])))
            state = stack.enter_context(patch.object(resistance.TbPersonagemEstado.objects, "filter"))
            state.return_value.exists.return_value = False
            stack.enter_context(patch.object(resistance, "_declared_modifier", return_value=("constitution", 3)))
            stack.enter_context(patch.object(resistance, "activate_state"))
            stack.enter_context(patch.object(resistance.TbOperacaoRecurso.objects, "create"))
            random = stack.enter_context(patch.object(resistance.secrets, "randbelow", side_effect=[0, 2, 6]))
            result = resistance.alter_ruin.__wrapped__(
                person, operation_id=uuid.uuid4(), round_ref="round:1", damage_type="fogo",
                damage_received=True, target_distance_ft=100, target_visible=True,
                target_has_total_cover=False, target_save_modifier=0, declared_modifier="constitution")
        self.assertEqual(result["dice"], [3, 7])
        self.assertEqual(result["damage"], 13)
        self.assertEqual([call.args for call in random.call_args_list], [(20,), (8,), (8,)])

    def test_fate_command_uses_declared_range_and_dice(self):
        person = SimpleNamespace(pk=123)
        definition = {"origin": "feature:876", "range_ft": 90, "dice": "3d6"}
        with ExitStack() as stack:
            stack.enter_context(patch.object(epic_fate.TbPersonagem.objects, "select_for_update",
                                             return_value=MagicMock(get=lambda **kw: person)))
            stack.enter_context(patch.object(epic_fate, "_receipt", return_value=("fp", None)))
            stack.enter_context(patch.object(epic_fate, "_definition", return_value=definition))
            query = stack.enter_context(patch.object(epic_fate.TbOperacaoRecurso.objects, "filter"))
            query.return_value.exists.return_value = False
            stack.enter_context(patch.object(epic_fate, "fate_state",
                                             return_value={"available": True, "direction": None}))
            stack.enter_context(patch.object(epic_fate, "activate_state"))
            stack.enter_context(patch.object(epic_fate, "end_state"))
            stack.enter_context(patch.object(epic_fate, "_save_receipt", side_effect=lambda *a: a[-1]))
            random = stack.enter_context(patch.object(epic_fate.secrets, "randbelow", side_effect=[0, 2, 5]))
            result = epic_fate.alter_fate.__wrapped__(
                person, operation_id=uuid.uuid4(), roll_ref="roll:1", distance_ft=80,
                direction="increase", d20_result_confirmed=True)
        self.assertEqual((result["dice"], result["modifier"]), ([1, 3, 6], 10))
        self.assertEqual([call.args for call in random.call_args_list], [(6,), (6,), (6,)])

    def test_recovery_command_rolls_declared_pool_faces(self):
        person = MagicMock(pk=123, pv_atual=10, pv_maximo=100)
        definition = {"origin": "feature:876", "maximum": 6, "faces": 8,
                      "reset": "long_rest", "name": "Unrelated source"}
        with ExitStack() as stack:
            stack.enter_context(patch.object(epic_recovery_pool.TbPersonagem.objects, "select_for_update",
                                             return_value=MagicMock(get=lambda **kw: person)))
            stack.enter_context(patch.object(epic_recovery_pool, "_receipt", return_value=None))
            stack.enter_context(patch.object(epic_recovery_pool, "_definition", return_value=definition))
            stack.enter_context(patch.object(epic_recovery_pool, "spend_resource",
                                             return_value=(True, {"current": 4})))
            stack.enter_context(patch.object(epic_recovery_pool, "derive",
                                             return_value={"pv": {"maximo_calculado": 100}}))
            stack.enter_context(patch.object(epic_recovery_pool, "healing_bonus", return_value=(0, [])))
            stack.enter_context(patch.object(epic_recovery_pool, "mark_healing_bonuses"))
            stack.enter_context(patch.object(epic_recovery_pool.TbOperacaoRecurso.objects, "create"))
            random = stack.enter_context(patch.object(epic_recovery_pool.secrets, "randbelow", side_effect=[2, 7]))
            result = epic_recovery_pool.use_recovery_pool.__wrapped__(
                person, operation_id=uuid.uuid4(), dice_count=2,
                bonus_action_available=True, confirmed=True)
        self.assertEqual((result["rolls"], result["hp_after"]), ([3, 8], 21))
        self.assertEqual([call.args for call in random.call_args_list], [(8,), (8,)])

    def test_spell_damage_command_applies_declared_floor(self):
        person = SimpleNamespace(pk=123)
        spell = SimpleNamespace(nivel=3)
        owned = SimpleNamespace(pk=99, id_magia=spell, preparada=True)
        with ExitStack() as stack:
            stack.enter_context(patch.object(epic_spell_damage.TbPersonagem.objects, "select_for_update",
                                             return_value=MagicMock(get=lambda **kw: person)))
            receipt = stack.enter_context(patch.object(epic_spell_damage.TbOperacaoRecurso.objects, "filter"))
            receipt.return_value.first.return_value = None
            stack.enter_context(patch.object(epic_spell_damage, "_definition",
                                             return_value={"circle": 3, "floor": 4, "rolls": {1, 2, 3}}))
            rows = stack.enter_context(patch.object(epic_spell_damage.TbPersonagemMagia.objects, "select_related"))
            rows.return_value.filter.return_value.first.return_value = owned
            stack.enter_context(patch.object(epic_spell_damage, "_spell_damage_types", return_value=["fogo"]))
            stack.enter_context(patch.object(epic_spell_damage.TbOperacaoRecurso.objects, "create"))
            result = epic_spell_damage.resolve_spell_damage.__wrapped__(
                person, operation_id=uuid.uuid4(), owned_spell_id=99, damage_type="fogo",
                dice=[(8, 1), (8, 3), (8, 6)])
        self.assertEqual((result["applied_dice"], result["total"]), ([4, 4, 6], 14))

    def test_sheet_template_balances_control_blocks(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        engine = Engine(dirs=[str(root / "home/templates")], libraries={
            "static": "django.templatetags.static",
            "distance_display": "home.templatetags.distance_display",
            "editorial_images": "home.templatetags.editorial_images",
            "commerce_presentation": "home.templatetags.commerce_presentation",
            "market_display": "home.templatetags.market_display",
            "cosmetic_packages": "home.templatetags.cosmetic_packages",
        })
        engine.get_template("home/pages/ficha_detail.html")
