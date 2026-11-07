"""Focused death-seal lifecycle using existing persistent states."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from home.epic_death_seal import (
    DEATH_SEAL_TAG, record_death_seal, restoration_allowed,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import TbOperacaoRecurso, TbPersonagem, TbPersonagemEstado, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class DeathSealTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="seal-owner")
        self.person = TbPersonagem.objects.create(dono=owner, nome="Portador")
        self.talent = TbTalento.objects.create(
            nome="Fonte de selo", slug="synthetic-death-seal", tipo="geral",
            tags_json=ATTRIBUTE_TAGS + [DEATH_SEAL_TAG],
        )
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:CON",
        )

    def seal(self, operation_id=None, **changes):
        request = {"target": "Dragão Antigo", "operation_id": operation_id or uuid.uuid4(),
                   "caused_by_own_damage": True, "death_confirmed": True}
        request.update(changes)
        return record_death_seal(self.person, **request)

    def test_tag_validates_and_restrictions_survive_source_removal(self):
        diagnostics = validate_tags_json([DEATH_SEAL_TAG], Library())
        self.assertEqual([item for item in diagnostics if item.level == ERROR], [])
        self.assertTrue(restoration_allowed(self.person, "Dragão Antigo", method="resurrection"))
        result = self.seal()
        self.assertEqual(result["exceptions"], ["desejo", "ressurreicao_verdadeira"])
        self.assertFalse(restoration_allowed(self.person, "Dragão Antigo", method="resurrection"))
        self.assertFalse(restoration_allowed(self.person, "Dragão Antigo", method="undead_transformation"))
        self.assertTrue(restoration_allowed(self.person, "Dragão Antigo", method="desejo"))
        self.assertTrue(restoration_allowed(self.person, "Dragão Antigo", method="ressurreicao_verdadeira"))
        self.assertTrue(restoration_allowed(self.person, "Outra criatura", method="resurrection"))
        self.grant.delete()
        self.assertFalse(restoration_allowed(self.person, "Dragão Antigo", method="resurrection"))
        with self.assertRaises(ValueError):
            self.seal(target="Outra criatura")

    def test_choice_confirmation_idempotence_and_invalid_reuse(self):
        self.grant.detalhes = ""
        self.grant.save(update_fields=["detalhes"])
        with self.assertRaises(ValueError):
            self.seal()
        self.grant.detalhes = "talent_attr:CON"
        self.grant.save(update_fields=["detalhes"])
        for changes in ({"caused_by_own_damage": False}, {"death_confirmed": False},
                        {"target": ""}):
            with self.assertRaises(ValueError):
                self.seal(**changes)
        self.assertFalse(TbPersonagemEstado.objects.exists())
        self.assertFalse(TbOperacaoRecurso.objects.exists())

        operation = uuid.uuid4()
        self.seal(operation)
        self.assertTrue(self.seal(operation)["replayed"])
        self.assertEqual(TbPersonagemEstado.objects.count(), 1)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
        with self.assertRaises(ValueError):
            self.seal(operation, target="Outra criatura")
