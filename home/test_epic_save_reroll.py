"""PostgreSQL-isolated coverage for the epic failed-save reroll runtime."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase

from home.content_versions import seal_ruleset
from home.epic_save_reroll import (
    REROLL_STATE_KEY,
    REROLL_TAG,
    release_reroll_on_turn_start,
    reroll_state,
    use_save_reroll,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import (
    TbOperacaoRecurso,
    TbPersonagem,
    TbPersonagemEstado,
    TbPersonagemTalento,
    TbTalento,
)
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_items import snapshot_magic_items
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins


class RerollSetup:
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        owner = get_user_model().objects.create_user(username=f"reroll-{uuid.uuid4()}")
        self.person = TbPersonagem.objects.create(dono=owner, nome="Portador")
        self.talent = TbTalento.objects.create(
            nome="Fonte sintética", slug=f"synthetic-save-reroll-{uuid.uuid4()}",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [REROLL_TAG])
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:SAB")

    def use(self, operation_id=None, **changes):
        payload = {"operation_id": operation_id or uuid.uuid4(), "save_kind": "dex",
                   "failed": True, "original_roll": 4}
        payload.update(changes)
        with patch("home.epic_save_reroll.secrets.randbelow", return_value=19):
            return use_save_reroll(self.person, **payload)

    def release(self, operation_id=None, **changes):
        payload = {"operation_id": operation_id or uuid.uuid4(),
                   "turn_ref": "combat-7:round-3:portador", "confirmed": True}
        payload.update(changes)
        return release_reroll_on_turn_start(self.person, **payload)


class RerollPersistenceTests(RerollSetup, TestCase):
    def test_failed_death_save_applies_only_new_d20_and_locks_the_turn(self):
        result = self.use(save_kind="death", original_roll=1)
        self.assertEqual(result["original_d20"], 1)
        self.assertEqual(result["applied_d20"], 20)
        self.assertEqual(set(result), {"ok", "operation_id", "save_kind", "original_d20",
                                       "applied_d20", "replayed"})
        self.assertFalse(reroll_state(self.person)["available"])
        state = TbPersonagemEstado.objects.get(chave=REROLL_STATE_KEY)
        self.assertEqual(state.ends_on_json, ["turn_start"])
        with self.assertRaises(ValueError):
            self.use(save_kind="con", original_roll=2)

    def test_confirmed_declared_turn_start_resets_and_unconfirmed_render_does_not(self):
        self.use()
        with self.assertRaises(ValueError):
            self.release(confirmed=False)
        self.assertFalse(reroll_state(self.person)["available"])
        released = self.release()
        self.assertTrue(released["released"])
        self.assertTrue(reroll_state(self.person)["available"])
        self.use(save_kind="wis")

    def test_replay_conflict_rollback_and_removed_source(self):
        operation = uuid.uuid4()
        first = self.use(operation)
        with patch("home.epic_save_reroll.secrets.randbelow",
                   side_effect=AssertionError("replay must not roll")):
            self.assertEqual(use_save_reroll(
                self.person, operation_id=operation, save_kind="dex",
                failed=True, original_roll=4), dict(first, replayed=True))
        with self.assertRaises(ValueError):
            self.use(operation, original_roll=18)
        self.release()
        with patch("home.epic_save_reroll.TbOperacaoRecurso.objects.create",
                   side_effect=RuntimeError("receipt")):
            with self.assertRaises(RuntimeError):
                self.use()
        self.assertFalse(TbPersonagemEstado.objects.filter(ativo=True).exists())
        self.owned.delete()
        self.assertIsNone(reroll_state(self.person))
        with self.assertRaises(ValueError):
            self.use()

    def test_pinned_ruleset_keeps_tag_when_live_source_changes(self):
        ruleset = seal_ruleset([snapshot_origins(), snapshot_magic_items(),
                                snapshot_options()], evaluator_version=EVALUATOR,
                               vocabulary_version=VOCABULARY)
        self.talent.tags_json = []
        self.talent.save(update_fields=["tags_json"])
        self.assertTrue(reroll_state(self.person, ruleset=ruleset)["available"])
        self.use(ruleset=ruleset)
        self.assertFalse(reroll_state(self.person, ruleset=ruleset)["available"])


class RerollConcurrencyTests(RerollSetup, TransactionTestCase):
    reset_sequences = True

    def test_simultaneous_same_command_creates_one_lock_and_one_receipt(self):
        operation = uuid.uuid4()
        barrier = Barrier(2)

        def run(_):
            close_old_connections()
            try:
                person = TbPersonagem.objects.get(pk=self.person.pk)
                barrier.wait(timeout=10)
                return use_save_reroll(
                    person, operation_id=operation, save_kind="death", failed=True,
                    original_roll=3)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run, range(2)))
        self.assertEqual(sum(row["replayed"] for row in results), 1)
        self.assertEqual(TbPersonagemEstado.objects.filter(ativo=True).count(), 1)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
