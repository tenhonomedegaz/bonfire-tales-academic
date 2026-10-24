"""The character sheet spends recovery dice granted by a tagged source."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_recovery_pool import RECOVERY_POOL_TAG, recovery_pool_state
from home.epic_talent_catalog import ATTRIBUTE_TAGS, PARTIAL_EFFECTS, epic_candidates
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class RecoveryPoolViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="recovery-pool-owner")
        self.other = get_user_model().objects.create_user(username="recovery-pool-other")
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome="Recuperador", pv_maximo=30, pv_atual=10)
        self.talent = TbTalento.objects.create(
            nome="Fonte sintética de recuperação", slug="synthetic-recovery-pool",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [RECOVERY_POOL_TAG],
        )
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:CON",
        )
        self.use_url = reverse("personagem_recuperar_vitalidade", args=[self.person.pk])
        self.sheet_url = reverse("ficha_detail", args=[self.person.pk])

    def payload(self, operation_id=None, count="2"):
        return {"operation_id": str(operation_id or uuid.uuid4()),
                "dice_count": count, "bonus_action_available": "on",
                "confirmed": "on"}

    def test_owner_spends_dice_and_heals_without_duplicate_replay(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.sheet_url), "Recuperar Vitalidade")
        data = self.payload()
        with patch("home.epic_recovery_pool.secrets.randbelow", return_value=4):
            self.assertEqual(self.client.post(self.use_url, data).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 20)
        self.assertEqual(recovery_pool_state(self.person)["available"], 8)
        with patch("home.epic_recovery_pool.secrets.randbelow",
                   side_effect=AssertionError("replay must not roll")):
            self.assertEqual(self.client.post(self.use_url, data).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 20)

    def test_owner_gate_choice_and_removed_source(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.use_url, self.payload()).status_code, 404)
        self.client.force_login(self.owner)
        self.grant.detalhes = ""
        self.grant.save(update_fields=["detalhes"])
        self.assertNotContains(self.client.get(self.sheet_url), "Gastar dados e recuperar PV")
        self.assertEqual(self.client.post(self.use_url, self.payload()).status_code, 400)
        self.grant.detalhes = "talent_attr:CON"
        self.grant.save(update_fields=["detalhes"])
        data = self.payload(count="0")
        self.assertEqual(self.client.post(self.use_url, data).status_code, 400)
        self.grant.delete()
        self.assertIsNone(recovery_pool_state(self.person))
        self.assertNotContains(self.client.get(self.sheet_url), "Recuperar Vitalidade")

    def test_effect_stays_partial_until_zero_hp_survival_is_implemented(self):
        self.assertEqual(PARTIAL_EFFECTS["dadiva-da-recuperacao"], [RECOVERY_POOL_TAG])
        self.assertNotIn("dadiva-da-recuperacao",
                         {row["slug"] for row in epic_candidates()})
        self.assertEqual([issue for issue in validate_tags_json(
            ATTRIBUTE_TAGS + [RECOVERY_POOL_TAG], Library())
            if issue.level == ERROR], [])
