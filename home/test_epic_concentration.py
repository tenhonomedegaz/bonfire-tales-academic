"""Focused coverage for persistent spell concentration and tagged focus."""

import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from home.epic_concentration import (
    FOCUS_TAG, begin_concentration, resolve_concentration_event,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento
from home.resource_engine import activate_state
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class ConcentrationTests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.owner = get_user_model().objects.create_user(username=f"focus-{uuid.uuid4()}")
        self.other = get_user_model().objects.create_user(username=f"other-{uuid.uuid4()}")
        self.person = TbPersonagem.objects.create(dono=self.owner, nome="Concentrador")
        self.source = TbTalento.objects.create(
            nome="Fonte sintética", slug=f"focus-{uuid.uuid4()}",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [FOCUS_TAG])
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.source,
            nome=self.source.nome, detalhes="talent_attr:INT")
        activate_state(self.person, "spell:one", origin="magia:one",
                       payload={"concentration": True})
        activate_state(self.person, "spell:plain", origin="magia:plain",
                       payload={"concentration": False})

    def test_tag_and_replacement_leave_other_effects(self):
        diagnostics = validate_tags_json([FOCUS_TAG], Library())
        self.assertFalse([d for d in diagnostics if d.level == ERROR], diagnostics)
        self.assertEqual(begin_concentration(self.person, "spell:two"), ["spell:one"])
        activate_state(self.person, "spell:two", origin="magia:two",
                       payload={"concentration": True})
        self.assertTrue(self.person.estados.get(chave="spell:plain").ativo)
        self.assertEqual(begin_concentration(self.person, "spell:two"), [])

    def test_damage_retains_with_active_choice_and_requires_save_without_it(self):
        operation = uuid.uuid4()
        result = resolve_concentration_event(
            self.person, operation_id=operation, event="damage")
        self.assertEqual(result["outcome"], "retained")
        self.assertTrue(resolve_concentration_event(
            self.person, operation_id=operation, event="damage")["replayed"])
        with self.assertRaises(ValueError):
            resolve_concentration_event(
                self.person, operation_id=operation, event="death")
        self.owned.detalhes = ""
        self.owned.save(update_fields=["detalhes"])
        self.assertEqual(resolve_concentration_event(
            self.person, operation_id=uuid.uuid4(), event="damage")["outcome"],
            "save_required")
        self.assertTrue(self.person.estados.get(chave="spell:one").ativo)

    def test_hard_breaks_end_concentration_and_route_checks_owner(self):
        url = reverse("oficina_evento_concentracao", args=[self.person.pk])
        form = {"operation_id": str(uuid.uuid4()), "event": "petrified"}
        self.client.force_login(self.other)
        self.assertNotEqual(self.client.post(url, form).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, form).status_code, 302)
        self.assertFalse(self.person.estados.get(chave="spell:one").ativo)
        self.assertTrue(self.person.estados.get(chave="spell:plain").ativo)
        self.assertEqual(self.client.post(url, form).status_code, 302)
        self.assertFalse(self.person.estados.get(chave="spell:one").ativo)

    def test_source_removal_disables_focus(self):
        self.owned.delete()
        self.assertEqual(resolve_concentration_event(
            self.person, operation_id=uuid.uuid4(), event="damage")["outcome"],
            "save_required")
