"""The character sheet consumes and releases tag-declared Soul Reaping."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_reaping import REAPING_TAG, reaping_state
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento


class ReapingViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="reaping-view-owner")
        self.other = get_user_model().objects.create_user(username="reaping-view-other")
        self.person = TbPersonagem.objects.create(dono=self.owner, nome="Ceifador")
        self.talent = TbTalento.objects.create(
            nome="Fonte de Ceifa", slug="synthetic-reaping-view", tipo="geral",
            tags_json=ATTRIBUTE_TAGS + [REAPING_TAG],
        )
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:CON",
        )
        self.use_url = reverse("personagem_ceifar_dano", args=[self.person.pk])
        self.death_url = reverse("personagem_liberar_ceifa", args=[self.person.pk])

    def damage(self, operation_id=None):
        return {"operation_id": str(operation_id or uuid.uuid4()),
                "creature_ref": "encontro:alvo-1", "source_kind": "spell",
                "chosen_type": "necrótico", "damage_type": ["cortante", "necrótico"],
                "dice_expression": ["3d8", "2d6"],
                "rolled_values": ["1,4,8", "2,5"], "fixed_damage": ["2", "0"]}

    def death(self, operation_id=None):
        return {"operation_id": str(operation_id or uuid.uuid4()),
                "creature_ref": "encontro:alvo-1", "current_hp": "0", "dead": "on"}

    def test_owner_can_use_replay_and_release_after_matching_death(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("ficha_detail", args=[self.person.pk])),
                            "Aplicar Ceifa")
        data = self.damage()
        self.assertEqual(self.client.post(self.use_url, data).status_code, 302)
        self.assertEqual(self.client.post(self.use_url, data).status_code, 302)
        self.assertFalse(reaping_state(self.person)["available"])
        page = self.client.get(reverse("ficha_detail", args=[self.person.pk]))
        self.assertContains(page, "Confirmar morte e liberar Ceifa")

        wrong = self.death()
        wrong["creature_ref"] = "encontro:outro"
        self.assertEqual(self.client.post(self.death_url, wrong).status_code, 400)
        self.assertFalse(reaping_state(self.person)["available"])
        self.assertEqual(self.client.post(self.death_url, self.death()).status_code, 302)
        self.assertTrue(reaping_state(self.person)["available"])

    def test_unowned_invalid_and_removed_source_do_not_lock(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.use_url, self.damage()).status_code, 404)
        self.client.force_login(self.owner)
        data = self.damage()
        data["rolled_values"] = ["1,4", "2,5"]
        self.assertEqual(self.client.post(self.use_url, data).status_code, 400)
        self.assertTrue(reaping_state(self.person)["available"])
        self.grant.delete()
        self.assertEqual(self.client.post(self.use_url, self.damage()).status_code, 400)
        self.assertNotContains(self.client.get(reverse("ficha_detail", args=[self.person.pk])),
                               "Aplicar Ceifa")
