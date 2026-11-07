"""End-to-end damage and long-rest behavior for the tagged survival effect."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_recovery_pool import (
    SURVIVAL_KEY, SURVIVAL_TAG, apply_incoming_damage, survival_state,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import TbPersonagem, TbPersonagemRecurso, TbPersonagemTalento, TbTalento
from home.resource_engine import reset_resources


class EpicSurvivalTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="epic-survivor")
        self.other = get_user_model().objects.create_user(username="epic-survival-other")
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome="Sobrevivente", pv_maximo=40,
            pv_atual=20, pv_temporario=5)
        self.talent = TbTalento.objects.create(
            nome="Fonte sintética de sobrevivência", slug="synthetic-survival",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [SURVIVAL_TAG])
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:CON")
        self.url = reverse("personagem_registrar_dano_sobrevivencia", args=[self.person.pk])

    def apply(self, damage, *, use=True, operation_id=None):
        return apply_incoming_damage(
            self.person, operation_id=operation_id or uuid.uuid4(),
            damage=damage, use_survival=use, confirmed=True)

    def test_nonlethal_damage_absorbs_temp_hp_without_spending_use(self):
        result = self.apply(8)
        self.assertEqual((result["absorbed"], result["hp_after"],
                          result["temp_hp_after"], result["survival_triggered"]),
                         (5, 17, 0, False))
        self.assertEqual(survival_state(self.person), {"available": 1})

    def test_lethal_damage_triggers_once_and_long_rest_restores_use(self):
        first = self.apply(30)
        self.assertEqual((first["hp_after"], first["survival_triggered"]), (21, True))
        self.assertEqual(survival_state(self.person), {"available": 0})
        with self.assertRaises(ValueError):
            self.apply(30)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 21)
        self.assertEqual(reset_resources(self.person, "short_rest"), [])
        self.assertEqual(survival_state(self.person), {"available": 0})
        self.assertEqual([row["key"] for row in reset_resources(
            self.person, "long_rest")], [SURVIVAL_KEY])
        self.assertEqual(survival_state(self.person), {"available": 1})
        self.person.pv_atual = 20
        self.person.save(update_fields=["pv_atual"])
        self.assertTrue(self.apply(30)["survival_triggered"])

    def test_declined_benefit_and_replay_are_stable(self):
        operation = uuid.uuid4()
        result = self.apply(30, use=False, operation_id=operation)
        self.assertEqual(result["hp_after"], 0)
        self.assertEqual(survival_state(self.person), {"available": 1})
        self.assertTrue(self.apply(30, use=False, operation_id=operation)["replayed"])
        with self.assertRaises(ValueError):
            self.apply(30, use=True, operation_id=operation)

    def test_half_maximum_includes_bonus_from_another_source(self):
        bonus = TbTalento.objects.create(
            nome="PV de outra fonte", slug="survival-other-max-hp", tipo="geral",
            tags_json=["always_active{buff:max_hp:+100}"])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=bonus, nome=bonus.nome)
        result = self.apply(30)
        self.assertEqual(result["hp_after"], 51)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, result["hp_after"])

    def test_choice_and_source_removal_disable_effect_without_affecting_other_resources(self):
        other = TbPersonagemRecurso.objects.create(
            id_personagem=self.person, chave="other:use", nome="Outro",
            atual=2, maximo=3, reset="long_rest")
        self.grant.detalhes = ""
        self.grant.save(update_fields=["detalhes"])
        self.assertIsNone(survival_state(self.person))
        with self.assertRaises(ValueError):
            self.apply(30)
        self.grant.detalhes = "talent_attr:CON"
        self.grant.save(update_fields=["detalhes"])
        self.apply(30)
        other.refresh_from_db()
        self.assertEqual(other.atual, 2)
        self.grant.delete()
        self.assertIsNone(survival_state(self.person))

    def test_sheet_owner_permissions_and_post(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, {
            "operation_id": str(uuid.uuid4()), "damage": "30",
            "use_survival": "on", "confirmed": "on"}).status_code, 404)
        self.client.force_login(self.owner)
        sheet = reverse("ficha_detail", args=[self.person.pk])
        self.assertContains(self.client.get(sheet), "Sobrevivência do Mais Forte")
        data = {"operation_id": str(uuid.uuid4()), "damage": "30",
                "use_survival": "on", "confirmed": "on"}
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual((self.person.pv_atual, self.person.pv_temporario), (21, 0))
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 21)
