"""The character sheet consumes the declared healing reaction through its POST route."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_soul_siphon import SIPHON_TAG, siphon_state
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento


class SoulSiphonViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="siphon-owner")
        self.other = get_user_model().objects.create_user(username="siphon-other")
        self.character = TbPersonagem.objects.create(
            dono=self.owner, nome="Sifonador", pv_maximo=100, pv_atual=20,
        )
        self.talent = TbTalento.objects.create(
            nome="Talento épico sintético", slug="epic-siphon-view",
            tipo="geral", etiquetas_adicionais="epico",
            tags_json=ATTRIBUTE_TAGS + [SIPHON_TAG],
        )
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=self.talent,
            categoria="epico", nome=self.talent.nome, detalhes="talent_attr:CON",
        )
        self.url = reverse("personagem_usar_reacao_cura", args=[self.character.pk])

    def payload(self, operation_id=None):
        return {
            "operation_id": str(operation_id or uuid.uuid4()),
            "distance_ft": "120", "enemy_at_zero": "on",
            "reaction_available": "on", "confirmed": "on",
        }

    def test_owner_sees_reaction_and_confirmed_post_heals_once(self):
        self.client.force_login(self.owner)
        page = self.client.get(reverse("ficha_detail", args=[self.character.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, self.url)
        self.assertContains(page, "Usar reação e recuperar PV")

        payload = self.payload()
        result = self.client.post(self.url, payload)
        self.assertEqual(result.status_code, 302)
        self.character.refresh_from_db()
        self.assertEqual(self.character.pv_atual, 70)
        self.assertEqual(siphon_state(self.character)["current"], 1)

        replay = self.client.post(self.url, payload)
        self.assertEqual(replay.status_code, 302)
        self.character.refresh_from_db()
        self.assertEqual(self.character.pv_atual, 70)
        self.assertEqual(siphon_state(self.character)["current"], 1)

    def test_invalid_or_unowned_requests_do_not_consume(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 404)
        self.client.force_login(self.owner)
        no_reaction = self.payload()
        no_reaction.pop("reaction_available")
        self.assertEqual(self.client.post(self.url, no_reaction).status_code, 400)
        too_far = self.payload()
        too_far["distance_ft"] = "121"
        self.assertEqual(self.client.post(self.url, too_far).status_code, 400)
        self.character.refresh_from_db()
        self.assertEqual(self.character.pv_atual, 20)
        self.assertEqual(siphon_state(self.character)["current"], 2)

        self.owned.delete()
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 400)
        page = self.client.get(reverse("ficha_detail", args=[self.character.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Usar reação e recuperar PV")
        self.character.refresh_from_db()
        self.assertEqual(self.character.pv_atual, 20)
