"""Fortitude healing bonus across the actual character-sheet healing consumers."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_healing_bonus import begin_healing_turn, healing_turn_state
from home.epic_recovery_pool import RECOVERY_POOL_TAG, use_recovery_pool
from home.epic_soul_siphon import SIPHON_TAG, use_siphon
from home.epic_talent_catalog import ATTRIBUTE_TAGS, epic_candidates
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento


def pin_current_origins(profile):
    """Create a test-only linked ruleset containing newly granted talent content."""
    from home.content_versions import seal_ruleset
    from home.versioned_origins import snapshot_origins
    revisions = [entry.revision for entry in profile.ruleset.entries.all()
                 if entry.identity != 'origin-catalog']
    revisions.append(snapshot_origins())
    profile.ruleset = seal_ruleset(
        revisions, evaluator_version=profile.ruleset.evaluator_version,
        vocabulary_version=profile.ruleset.vocabulary_version)
    profile.save(update_fields=['ruleset'])


class FortitudeHealingTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="fortitude-owner")
        self.other = get_user_model().objects.create_user(username="fortitude-other")
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome="Curandeiro", constituicao=16,
            pv_maximo=200, pv_atual=10)
        fortitude = TbTalento.objects.create(**next(
            row for row in epic_candidates() if row["slug"] == "dadiva-da-fortitude"))
        self.fortitude_grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=fortitude,
            nome=fortitude.nome, detalhes="talent_attr:CON")
        recovery = TbTalento.objects.create(
            nome="Reserva", slug="fortitude-recovery-source", tipo="geral",
            tags_json=ATTRIBUTE_TAGS + [RECOVERY_POOL_TAG])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=recovery,
            nome=recovery.nome, detalhes="talent_attr:SAB")
        siphon = TbTalento.objects.create(
            nome="Sifão", slug="fortitude-siphon-source", tipo="geral",
            tags_json=ATTRIBUTE_TAGS + [SIPHON_TAG])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=siphon,
            nome=siphon.nome, detalhes="talent_attr:CAR")

    def pool(self):
        with patch("home.epic_recovery_pool.secrets.randbelow", return_value=0):
            return use_recovery_pool(
                self.person, operation_id=uuid.uuid4(), dice_count=1,
                bonus_action_available=True, confirmed=True)

    def siphon(self):
        return use_siphon(
            self.person, operation_id=uuid.uuid4(), distance_ft=10,
            enemy_at_zero=True, reaction_available=True, confirmed=True)

    def test_once_per_turn_across_pool_and_siphon_then_source_removal(self):
        first = self.pool()
        self.assertEqual(first["healed"], 5)
        self.assertTrue(healing_turn_state(self.person))
        second = self.siphon()
        self.assertEqual(second["healed"], 50)
        begin_healing_turn(self.person, operation_id=uuid.uuid4(),
                           turn_ref="turn-2", confirmed=True)
        self.assertFalse(healing_turn_state(self.person))
        third = self.pool()
        self.assertEqual(third["healed"], 5)
        self.fortitude_grant.delete()
        fourth = self.pool()
        self.assertEqual(fourth["healed"], 1)

    def test_turn_start_owner_gate_and_duplicate_turn_reference(self):
        self.pool()
        url = reverse("personagem_iniciar_turno_cura", args=[self.person.pk])
        data = {"operation_id": str(uuid.uuid4()),
                "turn_ref": "turn-2", "confirmed": "on"}
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, data).status_code, 404)
        self.client.force_login(self.owner)
        sheet = reverse("ficha_detail", args=[self.person.pk])
        self.assertContains(self.client.get(sheet), "Bônus de cura por turno")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertFalse(healing_turn_state(self.person))
        self.assertEqual(self.client.post(url, {
            **data, "operation_id": str(uuid.uuid4())}).status_code, 400)
