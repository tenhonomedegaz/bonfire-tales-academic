"""PostgreSQL-isolated coverage for attack-accuracy epic tags."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase

from home.content_versions import seal_ruleset
from home.epic_battle_accuracy import (
    AUTO_HIT_STATE_KEY,
    AUTO_HIT_TAG,
    NO_DISADVANTAGE_TAG,
    attack_accuracy_state,
    convert_tagged_miss,
    release_auto_hit_on_turn_start,
    roll_tagged_attack,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import (TbOperacaoRecurso, TbPersonagem, TbPersonagemEstado,
                         TbPersonagemTalento, TbTalento)
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_items import snapshot_magic_items
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins


class AccuracySetup:
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        owner = get_user_model().objects.create_user(username=f"accuracy-{uuid.uuid4()}")
        self.person = TbPersonagem.objects.create(dono=owner, nome="Atacante")
        self.talent = TbTalento.objects.create(
            nome="Fonte sintética", slug=f"synthetic-accuracy-{uuid.uuid4()}",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [NO_DISADVANTAGE_TAG, AUTO_HIT_TAG])
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:DES")

    def attack(self, operation_id=None, **changes):
        payload = {"operation_id": operation_id or uuid.uuid4()}
        payload.update(changes)
        return roll_tagged_attack(self.person, **payload)

    def convert(self, attack_operation_id, operation_id=None, **changes):
        payload = {"operation_id": operation_id or uuid.uuid4(),
                   "attack_operation_id": attack_operation_id, "miss_confirmed": True}
        payload.update(changes)
        return convert_tagged_miss(self.person, **payload)


class AccuracyPersistenceTests(AccuracySetup, TestCase):
    def test_no_disadvantage_preserves_advantage_and_rolls_on_server(self):
        with patch("home.epic_battle_accuracy.secrets.randbelow", side_effect=[2, 18]) as roll:
            result = self.attack(advantage=True, disadvantage=True)
        self.assertEqual(result["rolls"], [3, 19])
        self.assertEqual(result["applied_d20"], 19)
        self.assertEqual(result["mode"], "advantage")
        self.assertEqual(roll.call_count, 2)

    def test_confirmed_recorded_miss_converts_once_then_turn_start_releases(self):
        attack = self.attack()
        converted = self.convert(attack["operation_id"])
        self.assertTrue(converted["hit"])
        self.assertFalse(attack_accuracy_state(self.person)["auto_hit_available"])
        state = TbPersonagemEstado.objects.get(chave=AUTO_HIT_STATE_KEY)
        self.assertEqual(state.ends_on_json, ["turn_start"])
        with self.assertRaises(ValueError):
            self.convert(attack["operation_id"])
        with self.assertRaises(ValueError):
            release_auto_hit_on_turn_start(self.person, operation_id=uuid.uuid4(),
                                           turn_ref="combat-1:round-2", confirmed=False)
        released = release_auto_hit_on_turn_start(
            self.person, operation_id=uuid.uuid4(), turn_ref="combat-1:round-2", confirmed=True)
        self.assertTrue(released["released"])
        self.assertTrue(attack_accuracy_state(self.person)["auto_hit_available"])

    def test_receipts_are_idempotent_and_conversion_requires_own_attack(self):
        operation = uuid.uuid4()
        with patch("home.epic_battle_accuracy.secrets.randbelow", return_value=8):
            first = self.attack(operation)
        with patch("home.epic_battle_accuracy.secrets.randbelow",
                   side_effect=AssertionError("replay must not roll")):
            self.assertEqual(self.attack(operation), dict(first, replayed=True))
        with self.assertRaises(ValueError):
            self.attack(operation, advantage=True)
        with self.assertRaises(ValueError):
            self.convert(uuid.uuid4())
        with self.assertRaises(ValueError):
            self.convert(first["operation_id"], miss_confirmed=False)
        with patch("home.epic_battle_accuracy.TbOperacaoRecurso.objects.create",
                   side_effect=RuntimeError("receipt")):
            with self.assertRaises(RuntimeError):
                self.convert(first["operation_id"])
        self.assertFalse(TbPersonagemEstado.objects.filter(ativo=True).exists())
        converted = self.convert(first["operation_id"])
        replay = convert_tagged_miss(self.person, operation_id=converted["operation_id"],
                                     attack_operation_id=first["operation_id"], miss_confirmed=True)
        self.assertEqual(replay, dict(converted, replayed=True))

    def test_selected_attribute_and_pinned_ruleset_control_active_tags(self):
        self.owned.detalhes = ""
        self.owned.save(update_fields=["detalhes"])
        self.assertIsNone(attack_accuracy_state(self.person))
        self.owned.detalhes = "talent_attr:DES"
        self.owned.save(update_fields=["detalhes"])
        ruleset = seal_ruleset([snapshot_origins(), snapshot_magic_items(), snapshot_options()],
                               evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.talent.tags_json = []
        self.talent.save(update_fields=["tags_json"])
        self.assertTrue(attack_accuracy_state(self.person, ruleset=ruleset)["active"])
        self.assertIsNone(attack_accuracy_state(self.person))


class AccuracyConcurrencyTests(AccuracySetup, TransactionTestCase):
    reset_sequences = True

    def test_simultaneous_conversion_creates_one_lock_and_one_receipt(self):
        attack = self.attack()
        barrier = Barrier(2)

        def run(_):
            close_old_connections()
            try:
                person = TbPersonagem.objects.get(pk=self.person.pk)
                barrier.wait(timeout=10)
                try:
                    return convert_tagged_miss(person, operation_id=uuid.uuid4(),
                                               attack_operation_id=attack["operation_id"],
                                               miss_confirmed=True)
                except ValueError as exc:
                    return exc
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run, range(2)))
        self.assertEqual(sum(isinstance(row, dict) and row["hit"] for row in results), 1)
        self.assertEqual(sum(isinstance(row, ValueError) for row in results), 1)
        self.assertEqual(TbPersonagemEstado.objects.filter(ativo=True).count(), 1)
        self.assertEqual(TbOperacaoRecurso.objects.filter(
            id_personagem=self.person).count(), 2)
