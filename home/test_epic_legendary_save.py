"""Focused PostgreSQL tests for a tagged automatic saving throw success."""

import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from home.epic_legendary_save import (
    LEGENDARY_SAVE_STATE_KEY, LEGENDARY_SAVE_TAG,
    legendary_save_state, use_legendary_save,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS, epic_candidates
from home.models import TbOperacaoRecurso, TbPersonagem, TbPersonagemTalento, TbTalento
from home.resource_engine import end_states_on
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class LegendarySaveTests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.owner = get_user_model().objects.create_user(username=f"hero-{uuid.uuid4()}")
        self.other = get_user_model().objects.create_user(username=f"other-{uuid.uuid4()}")
        self.person = TbPersonagem.objects.create(dono=self.owner, nome="Hero")
        self.source = TbTalento.objects.create(
            nome="Fonte de teste", slug=f"heroic-save-{uuid.uuid4()}",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [LEGENDARY_SAVE_TAG])
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.source,
            nome=self.source.nome, detalhes="talent_attr:SAB")

    def test_tag_is_valid_but_talent_remains_outside_ready_catalog(self):
        self.assertFalse([d for d in validate_tags_json(
            [LEGENDARY_SAVE_TAG], Library()) if d.level == ERROR])
        self.assertNotIn("dadiva-da-resistencia-heroica",
                         {row["slug"] for row in epic_candidates()})

    def test_failed_save_success_receipt_rest_and_source_removal(self):
        operation = uuid.uuid4()
        result = use_legendary_save(
            self.person, operation_id=operation, save_kind="wis", failed=True)
        self.assertEqual(result["result"], "success")
        self.assertFalse(legendary_save_state(self.person)["available"])
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
        self.assertTrue(use_legendary_save(
            self.person, operation_id=operation, save_kind="wis", failed=True)["replayed"])
        with self.assertRaises(ValueError):
            use_legendary_save(self.person, operation_id=operation,
                               save_kind="dex", failed=True)
        with self.assertRaises(ValueError):
            use_legendary_save(self.person, operation_id=uuid.uuid4(),
                               save_kind="wis", failed=True)
        end_states_on(self.person, "short_rest")
        self.assertTrue(legendary_save_state(self.person)["available"])
        use_legendary_save(self.person, operation_id=uuid.uuid4(),
                           save_kind="con", failed=True)
        end_states_on(self.person, "long_rest")
        self.assertTrue(legendary_save_state(self.person)["available"])
        self.owned.delete()
        self.assertIsNone(legendary_save_state(self.person))
        with self.assertRaises(ValueError):
            use_legendary_save(self.person, operation_id=uuid.uuid4(),
                               save_kind="wis", failed=True)

    def test_invalid_failure_and_owner_gate(self):
        with self.assertRaises(ValueError):
            use_legendary_save(self.person, operation_id=uuid.uuid4(),
                               save_kind="wis", failed=False)
        self.assertFalse(self.person.estados.filter(
            chave=LEGENDARY_SAVE_STATE_KEY, ativo=True).exists())
        url = reverse("personagem_resistir_salvaguarda", args=[self.person.pk])
        payload = {"operation_id": str(uuid.uuid4()), "save_kind": "wis", "failed": "on"}
        self.client.force_login(self.other)
        response = self.client.post(url, payload)
        self.assertNotEqual(response.status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 0)
        self.client.force_login(self.owner)
        sheet = self.client.get(reverse("ficha_detail", args=[self.person.pk]))
        self.assertContains(sheet, reverse("personagem_resistir_salvaguarda",
                                           args=[self.person.pk]))
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
