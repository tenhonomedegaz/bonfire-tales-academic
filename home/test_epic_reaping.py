"""Focused pure and PostgreSQL tests for damage-die maximization."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from home.epic_reaping import (
    DamageComponent,
    DamageDie,
    REAPING_STATE_KEY,
    REAPING_TAG,
    maximize_damage_type,
    reaping_state,
    release_reaping_on_death,
    use_reaping,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import (
    TbOperacaoRecurso,
    TbPersonagem,
    TbPersonagemEstado,
    TbPersonagemTalento,
    TbTalento,
)
from home.resource_engine import end_states_on
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class ReapingCalculationTests(SimpleTestCase):
    def test_declarative_tag_has_no_validation_errors(self):
        diagnostics = validate_tags_json([REAPING_TAG], Library())
        self.assertEqual(
            [row for row in diagnostics if row.level == ERROR], [])

    def test_only_chosen_type_dice_are_maximized_and_fixed_values_survive(self):
        components = (
            DamageComponent("Cortante", (DamageDie(8, 2), DamageDie(8, 7),
                                          DamageDie(8, 4)), fixed=3),
            DamageComponent("Necrótico", (DamageDie(6, 1), DamageDie(6, 5)),
                            fixed=-1),
            DamageComponent("necrótico", (DamageDie(4, 2),), fixed=2),
        )
        result = maximize_damage_type(components, " NECRÓTICO ")
        self.assertEqual(result.chosen_type, "necrótico")
        self.assertEqual(result.components[0].applied_rolls, (2, 7, 4))
        self.assertEqual(result.components[0].total, 16)
        self.assertFalse(result.components[0].maximized)
        self.assertEqual(result.components[1].applied_rolls, (6, 6))
        self.assertEqual(result.components[1].total, 11)
        self.assertEqual(result.components[2].applied_rolls, (4,))
        self.assertEqual(result.components[2].total, 6)
        self.assertEqual(result.total, 33)
        self.assertEqual(components[1].dice[0].rolled, 1)

    def test_rejects_absent_type_and_invalid_die_without_inventing_a_roll(self):
        components = (DamageComponent("fogo", (DamageDie(6, 3),)),)
        with self.assertRaises(ValueError):
            maximize_damage_type(components, "frio")
        with self.assertRaises(ValueError):
            maximize_damage_type(
                (DamageComponent("fogo", (DamageDie(6, 7),)),), "fogo")


class ReapingSetup:
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        owner = get_user_model().objects.create_user(username=f"reaper-{uuid.uuid4()}")
        self.person = TbPersonagem.objects.create(dono=owner, nome="Portador")
        self.talent = TbTalento.objects.create(
            nome="Fonte sintética de maximização",
            slug=f"synthetic-reaping-{uuid.uuid4()}",
            tipo="geral",
            tags_json=ATTRIBUTE_TAGS + [REAPING_TAG],
        )
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person,
            id_talento=self.talent,
            nome=self.talent.nome,
            detalhes="talent_attr:SAB",
        )

    @staticmethod
    def components():
        return (
            DamageComponent("cortante", (DamageDie(8, 3), DamageDie(8, 5))),
            DamageComponent("necrótico", (DamageDie(6, 2), DamageDie(6, 4)),
                            fixed=1),
        )

    def use(self, operation_id=None, **changes):
        data = {
            "operation_id": operation_id or uuid.uuid4(),
            "creature_ref": "encounter-7:creature-12",
            "source_kind": "attack",
            "components": self.components(),
            "chosen_type": "necrótico",
        }
        data.update(changes)
        return use_reaping(self.person, **data)


class ReapingPersistenceTests(ReapingSetup, TestCase):
    def test_active_source_is_discovered_by_mechanism_tag_not_name(self):
        state = reaping_state(self.person)
        self.assertTrue(state["available"])
        self.assertEqual(state["sources"], ["attack", "feature", "spell"])
        self.talent.nome = "Nome editorial completamente diferente"
        self.talent.save(update_fields=["nome"])
        self.assertEqual(reaping_state(self.person)["name"], self.talent.nome)
        self.owned.delete()
        self.assertIsNone(reaping_state(self.person))

    def test_use_maximizes_damage_and_locks_until_matching_death(self):
        result = self.use()
        self.assertEqual(result["damage"]["total"], 21)
        self.assertEqual(result["damage"]["components"][0]["applied_rolls"], [3, 5])
        self.assertEqual(result["damage"]["components"][1]["applied_rolls"], [6, 6])
        self.assertFalse(reaping_state(self.person)["available"])
        state = TbPersonagemEstado.objects.get(chave=REAPING_STATE_KEY)
        self.assertEqual(
            state.ends_on_json, ["target_death", "short_rest", "long_rest"])
        self.assertNotIn("creature-12", str(state.payload_json))

        with self.assertRaises(ValueError):
            self.use(creature_ref="another-creature")
        unrelated = release_reaping_on_death(
            self.person, operation_id=uuid.uuid4(), creature_ref="another-creature",
            current_hp=0, dead=True)
        self.assertFalse(unrelated["released"])
        self.assertFalse(reaping_state(self.person)["available"])
        released = release_reaping_on_death(
            self.person, operation_id=uuid.uuid4(),
            creature_ref="encounter-7:creature-12", current_hp=0, dead=True)
        self.assertTrue(released["released"])
        self.assertTrue(reaping_state(self.person)["available"])
        self.use(creature_ref="another-creature")

    def test_short_and_long_rest_each_release_lock_and_preserve_other_state(self):
        other = TbPersonagemEstado.objects.create(
            id_personagem=self.person, chave="other:state", origem="test",
            ativo=True, ends_on_json=["dawn"])
        self.use()
        changed = end_states_on(self.person, "short_rest")
        other.refresh_from_db()
        self.assertTrue(reaping_state(self.person)["available"])
        self.assertTrue(other.ativo)
        self.assertEqual(changed, [REAPING_STATE_KEY])

        self.use(operation_id=uuid.uuid4())
        end_states_on(self.person, "long_rest")
        self.assertTrue(reaping_state(self.person)["available"])

    def test_source_kind_death_facts_and_talent_choice_are_enforced(self):
        with self.assertRaises(ValueError):
            self.use(source_kind="item")
        with self.assertRaises(ValueError):
            release_reaping_on_death(
                self.person, operation_id=uuid.uuid4(), creature_ref="target",
                current_hp=1, dead=True)
        self.owned.detalhes = ""
        self.owned.save(update_fields=["detalhes"])
        with self.assertRaises(ValueError):
            self.use()
        self.assertFalse(TbPersonagemEstado.objects.exists())

    def test_use_and_death_are_idempotent_and_payload_reuse_conflicts(self):
        operation = uuid.uuid4()
        first = self.use(operation)
        replay = self.use(operation)
        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(dict(first, replayed=True), replay)
        self.assertEqual(TbPersonagemEstado.objects.filter(ativo=True).count(), 1)
        with self.assertRaises(ValueError):
            self.use(operation, chosen_type="cortante")

        death_operation = uuid.uuid4()
        args = dict(operation_id=death_operation,
                    creature_ref="encounter-7:creature-12",
                    current_hp=0, dead=True)
        release_reaping_on_death(self.person, **args)
        replay = release_reaping_on_death(self.person, **args)
        self.assertTrue(replay["replayed"])
        self.assertEqual(TbOperacaoRecurso.objects.count(), 2)

    def test_receipt_failure_rolls_back_target_lock(self):
        with patch.object(TbOperacaoRecurso.objects, "create",
                          side_effect=RuntimeError("receipt")):
            with self.assertRaises(RuntimeError):
                self.use()
        self.assertFalse(TbPersonagemEstado.objects.exists())


class ReapingConcurrencyTests(ReapingSetup, TransactionTestCase):
    reset_sequences = True

    def test_simultaneous_duplicate_creates_one_lock_and_one_receipt(self):
        operation = uuid.uuid4()
        barrier = Barrier(2)

        def run(_index):
            close_old_connections()
            try:
                person = TbPersonagem.objects.get(pk=self.person.pk)
                barrier.wait(timeout=10)
                return use_reaping(
                    person, operation_id=operation,
                    creature_ref="encounter-7:creature-12",
                    source_kind="spell", components=self.components(),
                    chosen_type="necrótico")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run, range(2)))
        self.assertEqual(sum(result["replayed"] for result in results), 1)
        self.assertEqual(TbPersonagemEstado.objects.filter(ativo=True).count(), 1)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
