"""Focused PostgreSQL coverage for Dádiva da Recuperação's usable pool."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase

from home.content_versions import seal_ruleset
from home.epic_recovery_pool import (
    RECOVERY_POOL_KEY,
    RECOVERY_POOL_TAG,
    recovery_pool_state,
    use_recovery_pool,
)
from home.epic_healing_bonus import begin_healing_turn, healing_turn_state
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import (
    TbOperacaoRecurso,
    TbPersonagem,
    TbPersonagemRecurso,
    TbPersonagemTalento,
    TbTalento,
)
from home.resource_engine import reset_resources
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_items import snapshot_magic_items
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins


@skipUnless(connection.vendor == "postgresql", "requires isolated PostgreSQL")
class RecoveryPoolSetup:
    def setUp(self):
        owner = get_user_model().objects.create_user(username="recovery-pool")
        self.person = TbPersonagem.objects.create(
            dono=owner, nome="Portador", pv_maximo=100, pv_atual=10)
        self.talent = TbTalento.objects.create(
            nome="Fonte sintética de recuperação", slug="synthetic-recovery-pool",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [RECOVERY_POOL_TAG])
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:CON")

    def use(self, operation_id=None, **changes):
        data = {"operation_id": operation_id or uuid.uuid4(), "dice_count": 2,
                "bonus_action_available": True, "confirmed": True}
        data.update(changes)
        return use_recovery_pool(self.person, **data)


class RecoveryPoolTests(RecoveryPoolSetup, TestCase):
    def test_tag_validates_and_state_requires_selected_active_source(self):
        diagnostics = validate_tags_json([RECOVERY_POOL_TAG], Library())
        self.assertEqual([row for row in diagnostics if row.level == ERROR], [])
        self.assertEqual(recovery_pool_state(self.person), {"available": 10, "max": 10})
        self.owned.detalhes = ""
        self.owned.save(update_fields=["detalhes"])
        self.assertIsNone(recovery_pool_state(self.person))
        self.owned.detalhes = "talent_attr:SAB"
        self.owned.save(update_fields=["detalhes"])
        self.owned.delete()
        self.assertIsNone(recovery_pool_state(self.person))

    def test_pinned_revision_keeps_the_tag_and_current_choice_controls_source(self):
        ruleset = seal_ruleset(
            [snapshot_origins(), snapshot_options(), snapshot_magic_items()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.talent.tags_json = []
        self.talent.save(update_fields=["tags_json"])
        self.assertEqual(recovery_pool_state(self.person, ruleset),
                         {"available": 10, "max": 10})
        self.owned.delete()
        self.assertIsNone(recovery_pool_state(self.person, ruleset))

    def test_use_rolls_spends_caps_healing_and_keeps_other_resources(self):
        other = TbPersonagemRecurso.objects.create(
            id_personagem=self.person, chave="other:pool", nome="Outro",
            atual=3, maximo=4, reset="short_rest")
        self.person.pv_atual = 97
        self.person.save(update_fields=["pv_atual"])
        with patch("home.epic_recovery_pool.secrets.randbelow", side_effect=[9, 4]):
            result = self.use()
        self.person.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(result["rolls"], [10, 5])
        self.assertEqual((result["rolled_total"], result["healed"]), (15, 3))
        self.assertEqual((result["hp_before"], result["hp_after"]), (97, 100))
        self.assertEqual(result["resource_remaining"], 8)
        self.assertEqual(self.person.pv_atual, 100)
        self.assertEqual((other.atual, other.maximo), (3, 4))

    def test_generic_healing_tags_are_preserved(self):
        self.person.constituicao = 16
        self.person.save(update_fields=["constituicao"])
        bonus_source = TbTalento.objects.create(
            nome="Bônus de cura", slug="recovery-pool-healing-bonus", tipo="geral",
            tags_json=["always_active{trigger=healing, instant{heal:+con_mod}}"])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=bonus_source, nome=bonus_source.nome)
        with patch("home.epic_recovery_pool.secrets.randbelow", return_value=0):
            result = self.use(dice_count=1)
        # The selected +2 CON makes the generic tag add +4 to the rolled 1.
        self.assertEqual((result["rolled_total"], result["healed"], result["hp_after"]),
                         (1, 5, 15))

    def test_turn_limited_healing_applies_once_then_releases_on_next_turn(self):
        self.person.constituicao = 16
        self.person.save(update_fields=["constituicao"])
        bonus_source = TbTalento.objects.create(
            nome="Cura limitada", slug="recovery-pool-limited-heal", tipo="geral",
            tags_json=["always_active{trigger=healing, 1/turn, instant{heal:+con_mod}}"])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=bonus_source, nome=bonus_source.nome)
        with patch("home.epic_recovery_pool.secrets.randbelow", return_value=0):
            first = self.use(dice_count=1)
            second = self.use(dice_count=1)
        self.assertEqual((first["rolled_total"], first["healed"]), (1, 5))
        self.assertEqual((second["rolled_total"], second["healed"]), (1, 1))
        self.assertTrue(healing_turn_state(self.person))
        released = begin_healing_turn(
            self.person, operation_id=uuid.uuid4(), turn_ref="round-2",
            confirmed=True)
        self.assertEqual(released["released"], 1)
        self.assertFalse(healing_turn_state(self.person))
        with self.assertRaises(ValueError):
            begin_healing_turn(self.person, operation_id=uuid.uuid4(),
                               turn_ref="round-2", confirmed=True)
        with patch("home.epic_recovery_pool.secrets.randbelow", return_value=0):
            third = self.use(dice_count=1)
        self.assertEqual(third["healed"], 5)

    def test_input_availability_idempotency_and_rollback(self):
        for changes in ({"dice_count": 0}, {"dice_count": 11},
                        {"bonus_action_available": False}, {"confirmed": False}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.use(**changes)
        operation = uuid.uuid4()
        with patch("home.epic_recovery_pool.secrets.randbelow", return_value=0):
            first = self.use(operation, dice_count=1)
            replay = self.use(operation, dice_count=1)
        self.assertTrue(replay["replayed"])
        self.assertEqual(first["rolls"], [1])
        with self.assertRaises(ValueError):
            self.use(operation, dice_count=2)
        with patch.object(TbOperacaoRecurso.objects, "create", side_effect=RuntimeError("receipt")):
            with self.assertRaises(RuntimeError):
                self.use(dice_count=1)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 11)
        self.assertEqual(recovery_pool_state(self.person)["available"], 9)

    def test_short_and_long_rest_reset_only_declared_pool(self):
        self.use(dice_count=3)
        other = TbPersonagemRecurso.objects.create(
            id_personagem=self.person, chave="other:dawn", nome="Outro",
            atual=1, maximo=3, reset="dawn")
        short = reset_resources(self.person, "short_rest")
        other.refresh_from_db()
        self.assertEqual(recovery_pool_state(self.person), {"available": 10, "max": 10})
        self.assertEqual([row["key"] for row in short], [RECOVERY_POOL_KEY])
        self.assertEqual(other.atual, 1)
        self.use(dice_count=1)
        long = reset_resources(self.person, "long_rest")
        self.assertEqual([row["key"] for row in long], [RECOVERY_POOL_KEY])


class RecoveryPoolConcurrencyTests(RecoveryPoolSetup, TransactionTestCase):
    reset_sequences = True

    def test_simultaneous_duplicate_operation_rolls_and_spends_once(self):
        operation = uuid.uuid4()
        barrier = Barrier(2)

        def run(_index):
            close_old_connections()
            try:
                person = TbPersonagem.objects.get(pk=self.person.pk)
                barrier.wait(timeout=10)
                return use_recovery_pool(
                    person, operation_id=operation, dice_count=2,
                    bonus_action_available=True, confirmed=True)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run, range(2)))
        self.person.refresh_from_db()
        self.assertEqual(recovery_pool_state(self.person)["available"], 8)
        self.assertEqual(sum(result["replayed"] for result in results), 1)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
