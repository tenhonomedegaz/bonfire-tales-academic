"""Focused PostgreSQL coverage for the declared Soul Siphon runtime."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase

from home.content_versions import seal_ruleset
from home.epic_soul_siphon import SIPHON_KEY, SIPHON_TAG, siphon_state, use_siphon
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


class SiphonSetup:
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        owner = get_user_model().objects.create_user(username="soul-siphon")
        self.person = TbPersonagem.objects.create(
            dono=owner, nome="Portador", nivel=17,
            pv_maximo=100, pv_atual=10, pv_temporario=13,
        )
        self.talent = TbTalento.objects.create(
            nome="Fonte sintética de reação", slug="synthetic-soul-reaction",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [SIPHON_TAG],
        )
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:CON",
        )

    def use(self, operation_id=None, **changes):
        data = {
            "operation_id": operation_id or uuid.uuid4(),
            "distance_ft": 120,
            "enemy_at_zero": True,
            "reaction_available": True,
            "confirmed": True,
        }
        data.update(changes)
        return use_siphon(self.person, **data)


class SoulSiphonTests(SiphonSetup, TestCase):
    def test_declarative_tag_validates(self):
        diagnostics = validate_tags_json([SIPHON_TAG], Library())
        self.assertEqual([row for row in diagnostics if row.level == ERROR], [])

    def test_state_comes_from_active_tag_source_and_proficiency(self):
        state = siphon_state(self.person)
        self.assertEqual(state, {
            "key": SIPHON_KEY,
            "name": self.talent.nome,
            "current": 6,
            "maximum": 6,
            "heal": 50,
            "range_ft": 120,
        })
        self.assertFalse(TbPersonagemRecurso.objects.exists())

        self.talent.nome = "Nome editorial alterado"
        self.talent.save(update_fields=["nome"])
        self.assertEqual(siphon_state(self.person)["name"], self.talent.nome)

    def test_source_requires_its_talent_choice_and_tracks_removal(self):
        self.owned.detalhes = ""
        self.owned.save(update_fields=["detalhes"])
        self.assertIsNone(siphon_state(self.person))
        with self.assertRaises(ValueError):
            self.use()

        self.owned.detalhes = "talent_attr:SAB"
        self.owned.save(update_fields=["detalhes"])
        self.assertIsNotNone(siphon_state(self.person))
        self.owned.delete()
        self.assertIsNone(siphon_state(self.person))

    def test_pinned_ruleset_supplies_tags_but_current_selection_controls_ownership(self):
        ruleset = seal_ruleset(
            [snapshot_origins(), snapshot_options(), snapshot_magic_items()],
            evaluator_version=EVALUATOR,
            vocabulary_version=VOCABULARY,
        )
        self.talent.tags_json = []
        self.talent.nome = "Catálogo vivo alterado"
        self.talent.save(update_fields=["tags_json", "nome"])

        state = siphon_state(self.person, ruleset=ruleset)
        self.assertEqual(state["name"], "Fonte sintética de reação")
        self.assertEqual(state["heal"], 50)
        self.owned.delete()
        self.assertIsNone(siphon_state(self.person, ruleset=ruleset))

    def test_valid_use_heals_to_max_spends_and_preserves_coexisting_state(self):
        other = TbPersonagemRecurso.objects.create(
            id_personagem=self.person, chave="other:pool", nome="Outro",
            atual=3, maximo=4, reset="short_rest",
        )
        self.person.pv_atual = 80
        self.person.save(update_fields=["pv_atual"])

        result = self.use()
        self.person.refresh_from_db()
        other.refresh_from_db()
        resource = TbPersonagemRecurso.objects.get(chave=SIPHON_KEY)
        self.assertEqual((result["healed"], result["current"]), (20, 5))
        self.assertEqual(self.person.pv_atual, 100)
        self.assertEqual(self.person.pv_temporario, 13)
        self.assertEqual((other.atual, other.maximo), (3, 4))
        self.assertEqual(resource.reset, "long_rest")

    def test_event_range_reaction_confirmation_and_uses_are_enforced(self):
        invalid = [
            {"distance_ft": 121},
            {"distance_ft": -1},
            {"distance_ft": "NaN"},
            {"enemy_at_zero": False},
            {"reaction_available": False},
            {"confirmed": False},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.use(**changes)
        self.assertEqual(self.person.pv_atual, 10)
        self.assertFalse(TbPersonagemRecurso.objects.exists())
        self.assertFalse(TbOperacaoRecurso.objects.exists())

        for _ in range(6):
            self.use()
        with self.assertRaises(ValueError):
            self.use()
        self.assertEqual(siphon_state(self.person)["current"], 0)

    def test_operation_is_idempotent_and_payload_reuse_conflicts(self):
        operation = uuid.uuid4()
        first = self.use(operation)
        replay = self.use(operation)
        self.person.refresh_from_db()
        self.assertEqual(first["healed"], 50)
        self.assertTrue(replay["replayed"])
        self.assertEqual(self.person.pv_atual, 60)
        self.assertEqual(siphon_state(self.person)["current"], 5)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
        with self.assertRaises(ValueError):
            self.use(operation, distance_ft=119)

    def test_long_rest_restores_only_the_declared_pool(self):
        self.use()
        other = TbPersonagemRecurso.objects.create(
            id_personagem=self.person, chave="other:daily", nome="Outro",
            atual=1, maximo=3, reset="long_rest",
        )
        changed = reset_resources(self.person, "long_rest")
        other.refresh_from_db()
        self.assertEqual(siphon_state(self.person)["current"], 6)
        self.assertEqual(other.atual, 3)
        self.assertEqual({row["key"] for row in changed}, {SIPHON_KEY, "other:daily"})

    def test_receipt_failure_rolls_back_healing_and_spend(self):
        with patch.object(TbOperacaoRecurso.objects, "create",
                          side_effect=RuntimeError("receipt")):
            with self.assertRaises(RuntimeError):
                self.use()
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 10)
        self.assertFalse(TbPersonagemRecurso.objects.exists())


class SoulSiphonConcurrencyTests(SiphonSetup, TransactionTestCase):
    reset_sequences = True

    def test_simultaneous_duplicate_heals_and_spends_once(self):
        operation = uuid.uuid4()
        barrier = Barrier(2)

        def run(_index):
            close_old_connections()
            try:
                person = TbPersonagem.objects.get(pk=self.person.pk)
                barrier.wait(timeout=10)
                return use_siphon(
                    person, operation_id=operation, distance_ft=120,
                    enemy_at_zero=True, reaction_available=True, confirmed=True,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run, range(2)))
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 60)
        self.assertEqual(siphon_state(self.person)["current"], 5)
        self.assertEqual(sum(result["replayed"] for result in results), 1)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
