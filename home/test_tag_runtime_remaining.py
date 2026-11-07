"""Database-free coverage for the remaining epic tag consumers."""

import uuid
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from home import epic_death_seal as seal
from home import epic_legendary_save as legendary
from home import epic_save_reroll as reroll
from home import epic_storm_save as storm


class RemainingTagRuntimeTests(SimpleTestCase):
    def source(self, module, tag):
        source = SimpleNamespace(tags_json=[tag], pk=876, nome="Unrelated source")
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(module, "_talent_attr_map", return_value={}))
        stack.enter_context(patch.object(module, "_features_do_personagem",
                                        return_value=[("feature", source.nome, source, 1)]))
        if hasattr(module, "_feature_identity"):
            stack.enter_context(patch.object(module, "_feature_identity", return_value="feature:876"))
        return source

    def command(self, module):
        stack = ExitStack()
        self.addCleanup(stack.close)
        person = SimpleNamespace(pk=123)
        lock = stack.enter_context(patch.object(module.TbPersonagem.objects, "select_for_update"))
        lock.return_value.get.return_value = person
        receipt = stack.enter_context(patch.object(module.TbOperacaoRecurso.objects, "filter"))
        receipt.return_value.first.return_value = None
        create = stack.enter_context(patch.object(module.TbOperacaoRecurso.objects, "create"))
        state = stack.enter_context(patch.object(module.TbPersonagemEstado.objects, "filter"))
        state.return_value.exists.return_value = False
        activate = stack.enter_context(patch.object(module, "activate_state"))
        return person, receipt, create, activate

    def use(self, module, person, **changes):
        kwargs = dict(operation_id=uuid.uuid4(), save_kind="death", failed=True)
        kwargs.update(changes)
        if module is reroll:
            kwargs["original_roll"] = 4
            return reroll.use_save_reroll.__wrapped__(person, **kwargs)
        return legendary.use_legendary_save.__wrapped__(person, **kwargs)

    def test_existing_death_exceptions_are_already_parameters(self):
        self.source(seal, seal.DEATH_SEAL_TAG.replace(
            "desejo|ressurreicao_verdadeira", "ritual|milagre"))
        self.assertEqual(seal._exceptions(object()), ["ritual", "milagre"])

    def test_existing_storm_types_are_already_parameters(self):
        self.source(storm, "dadv:spell_save{damage:fogo|frio}")
        self.assertEqual(storm.storm_save_types(object()), ["fogo", "frio"])

    def test_save_kind_subsets_are_enforced_by_both_operations(self):
        for module, tag in ((reroll, reroll.REROLL_TAG),
                            (legendary, legendary.LEGENDARY_SAVE_TAG)):
            with self.subTest(module=module.__name__):
                self.source(module, tag.replace("any|death", "dex|death"))
                person, _, create, activate = self.command(module)
                with patch.object(reroll.secrets, "randbelow", return_value=19):
                    result = self.use(module, person)
                self.assertEqual(result["save_kind"], "death")
                self.assertFalse(result["replayed"])
                create.reset_mock()
                activate.reset_mock()
                with self.assertRaises(ValueError):
                    self.use(module, person, save_kind="wis")
                activate.assert_not_called()
                create.assert_not_called()

    def test_legendary_rest_subsets_drive_persisted_end_events(self):
        source = self.source(legendary, legendary.LEGENDARY_SAVE_TAG)
        person, _, create, activate = self.command(legendary)
        for reset in ("short_rest", "long_rest", "long_rest|short_rest"):
            with self.subTest(reset=reset):
                source.tags_json = [legendary.LEGENDARY_SAVE_TAG.replace(
                    "short_rest|long_rest", reset)]
                self.use(legendary, person)
                self.assertEqual(activate.call_args.args,
                                 (person, legendary.LEGENDARY_SAVE_STATE_KEY))
                self.assertEqual(activate.call_args.kwargs,
                                 {"origin": "feature:876", "payload": {"save_kind": "death"},
                                  "ends_on": reset.split("|")})
                self.assertEqual(create.call_args.kwargs["status_http"], 200)

    def test_original_reroll_preserves_die_state_payload_and_receipt(self):
        self.source(reroll, reroll.REROLL_TAG)
        person, _, create, activate = self.command(reroll)
        operation = uuid.uuid4()
        with patch.object(reroll.secrets, "randbelow", return_value=19) as random:
            result = self.use(reroll, person, operation_id=operation, save_kind="dex")
        random.assert_called_once_with(20)
        self.assertEqual(result, {"ok": True, "operation_id": str(operation),
                                 "save_kind": "dex", "original_d20": 4,
                                 "applied_d20": 20, "replayed": False})
        activate.assert_called_once_with(
            person, reroll.REROLL_STATE_KEY, origin="feature:876",
            payload={"save_kind": "dex"}, ends_on=["turn_start"])
        self.assertEqual(create.call_args.kwargs["resposta"], result)
        self.assertEqual(create.call_args.kwargs["fingerprint"], reroll._fingerprint(
            "use", {"save_kind": "dex", "failed": True, "original_roll": 4}))

    def test_original_legendary_preserves_result_and_reset(self):
        self.source(legendary, legendary.LEGENDARY_SAVE_TAG)
        person, _, create, activate = self.command(legendary)
        operation = uuid.uuid4()
        result = self.use(legendary, person, operation_id=operation, save_kind="wis")
        self.assertEqual(result, {"ok": True, "operation_id": str(operation),
                                 "save_kind": "wis", "result": "success", "replayed": False})
        self.assertEqual(activate.call_args.kwargs["ends_on"], ["short_rest", "long_rest"])
        self.assertEqual(create.call_args.kwargs["resposta"], result)

    def test_replay_precedes_changed_or_removed_source_and_conflicts_reject(self):
        for module in (reroll, legendary):
            with self.subTest(module=module.__name__):
                person, receipt, create, activate = self.command(module)
                receipt.return_value.first.return_value = SimpleNamespace(
                    fingerprint="same", resposta={"ok": True})
                with patch.object(module.hashlib, "sha256") as digest:
                    digest.return_value.hexdigest.return_value = "same"
                    with patch.object(module, "_definition", side_effect=AssertionError("source read")):
                        self.assertEqual(self.use(module, person), {"ok": True, "replayed": True})
                    digest.return_value.hexdigest.return_value = "other"
                    with self.assertRaises(ValueError):
                        self.use(module, person)
                create.assert_not_called()
                activate.assert_not_called()

    def test_no_new_mechanics_or_unknown_kinds_are_accepted(self):
        for module, tag in ((reroll, reroll.REROLL_TAG),
                            (legendary, legendary.LEGENDARY_SAVE_TAG)):
            source = self.source(module, tag)
            variants = [tag.replace("any|death", "unknown"),
                        tag.replace("self", "ally"), tag + ", extra:1"]
            if module is reroll:
                variants += [tag.replace("d20", "d8"), tag.replace("keep:new", "keep:best"),
                             tag.replace("turn_start", "long_rest")]
            else:
                variants += [tag.replace("result:success", "result:critical"),
                             tag.replace("short_rest|long_rest", "turn_start")]
            for variant in variants:
                with self.subTest(tag=variant):
                    source.tags_json = [variant]
                    self.assertIsNone(module._definition(object()))
