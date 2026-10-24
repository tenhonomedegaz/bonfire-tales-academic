"""The real sheet records confirmed death restrictions by active tags."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_death_seal import DEATH_SEAL_TAG, restoration_allowed
from home.epic_talent_catalog import ATTRIBUTE_TAGS
from home.models import TbPersonagem, TbPersonagemEstado, TbPersonagemTalento, TbTalento


class DeathSealViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="seal-view-owner")
        self.other = get_user_model().objects.create_user(username="seal-view-other")
        self.person = TbPersonagem.objects.create(dono=self.owner, nome="Ceifador")
        self.talent = TbTalento.objects.create(
            nome="Fonte de selo", slug="synthetic-death-seal-view", tipo="geral",
            tags_json=ATTRIBUTE_TAGS + [DEATH_SEAL_TAG],
        )
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, detalhes="talent_attr:CON",
        )
        self.url = reverse("personagem_registrar_morte_selada", args=[self.person.pk])

    def payload(self, operation_id=None):
        return {"target": "Dragão Antigo", "operation_id": str(operation_id or uuid.uuid4()),
                "caused_by_own_damage": "on", "death_confirmed": "on"}

    def test_owner_records_once_and_sheet_shows_target(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("ficha_detail", args=[self.person.pk])),
                            "Registrar morte selada")
        data = self.payload()
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(TbPersonagemEstado.objects.count(), 1)
        self.assertFalse(restoration_allowed(self.person, "Dragão Antigo", method="resurrection"))
        self.assertContains(self.client.get(reverse("ficha_detail", args=[self.person.pk])),
                            "Dragão Antigo")
        self.grant.delete()
        after_removal = self.client.get(reverse("ficha_detail", args=[self.person.pk]))
        self.assertNotContains(after_removal, "Registrar morte selada")
        self.assertContains(after_removal, "Dragão Antigo")
        self.assertFalse(restoration_allowed(self.person, "Dragão Antigo", method="resurrection"))

    def test_unowned_or_unconfirmed_event_never_records(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 404)
        self.client.force_login(self.owner)
        data = self.payload()
        data.pop("death_confirmed")
        self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.assertFalse(TbPersonagemEstado.objects.exists())
