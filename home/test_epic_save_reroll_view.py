"""The character sheet consumes a declared save reroll once per turn."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_save_reroll import REROLL_TAG, reroll_state
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento


class SaveRerollViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="reroll-view-owner")
        self.other = get_user_model().objects.create_user(username="reroll-view-other")
        self.person = TbPersonagem.objects.create(dono=self.owner, nome="Sortudo")
        self.talent = TbTalento.objects.create(
            nome="Fonte de nova rolagem", slug="synthetic-save-reroll-view",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [REROLL_TAG],
        )
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:CON",
        )
        self.use_url = reverse("personagem_rerolar_salvaguarda", args=[self.person.pk])
        self.turn_url = reverse("personagem_iniciar_turno_rerrolagem", args=[self.person.pk])
        self.sheet_url = reverse("ficha_detail", args=[self.person.pk])

    def use_payload(self, operation_id=None):
        return {"operation_id": str(operation_id or uuid.uuid4()),
                "save_kind": "death", "failed": "on",
                "original_roll": "4"}

    def turn_payload(self, operation_id=None):
        return {"operation_id": str(operation_id or uuid.uuid4()),
                "turn_ref": "encontro-1:turno-2", "confirmed": "on"}

    def test_owner_rerolls_death_save_once_and_resets_on_next_turn(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.sheet_url), "Usar nova rolagem")
        data = self.use_payload()
        self.assertEqual(self.client.post(self.use_url, data).status_code, 302)
        self.assertEqual(self.client.post(self.use_url, data).status_code, 302)
        self.assertFalse(reroll_state(self.person)["available"])
        self.assertContains(self.client.get(self.sheet_url), "Iniciar próximo turno")
        self.assertEqual(self.client.post(self.use_url, self.use_payload()).status_code, 400)
        self.assertEqual(self.client.post(self.turn_url, self.turn_payload()).status_code, 302)
        self.assertTrue(reroll_state(self.person)["available"])

    def test_permission_invalid_failure_and_source_removal(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.use_url, self.use_payload()).status_code, 404)
        self.client.force_login(self.owner)
        data = self.use_payload()
        data.pop("failed")
        self.assertEqual(self.client.post(self.use_url, data).status_code, 400)
        self.assertTrue(reroll_state(self.person)["available"])
        self.grant.delete()
        self.assertEqual(self.client.post(self.use_url, self.use_payload()).status_code, 400)
        self.assertNotContains(self.client.get(self.sheet_url), "Usar nova rolagem")

    def test_sheet_rolls_server_side_and_ignores_posted_result(self):
        self.client.force_login(self.owner)
        data = self.use_payload()
        data["new_roll"] = "20"
        with patch("home.epic_save_reroll.secrets.randbelow", return_value=0) as roll:
            response = self.client.post(self.use_url, data, follow=True)
        self.assertContains(response, "Use o novo resultado do d20: 1.")
        roll.assert_called_once_with(20)
        self.assertNotContains(response, 'name="new_roll"')
