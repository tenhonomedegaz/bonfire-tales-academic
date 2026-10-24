"""Conjuração Livre in the real workshop casting path."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_free_cast import FREE_CAST_TAG, free_cast_available
from home.models import (
    TbClasse, TbClassehabilidade, TbMagia, TbPersonagem,
    TbPersonagemClasse, TbPersonagemTalento, TbRecursoclasse, TbTalento,
)
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json
from home.resource_engine import mutate_resource


class EpicFreeCastTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="free-cast-owner")
        self.other = get_user_model().objects.create_user(username="free-cast-other")
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome="Conjuradora", nivel=3, inteligencia=16)
        caster = TbClasse.objects.create(nome="Classe arcana", slug="classe-arcana")
        TbClassehabilidade.objects.create(
            id_classe=caster, nome="Conjuração", niveladquirido=1,
            tags_json=["spellcasting{ability:int, slots{progression:full}, "
                       "list:classe_arcana, mode:prepared, pool:spellbook}"])
        TbRecursoclasse.objects.create(
            id_classe=caster, nome="1º", slug="1o", nivel=1, valor="4",
            valores_json={"3": "4"}, tipo="table-only")
        TbPersonagemClasse.objects.create(
            id_personagem=self.person, id_classe=caster, nivel=3, principal=True)
        self.spell = TbMagia.objects.create(
            nome="Selo arcano", slug="selo-arcano", nivel=1,
            duracao="Até ser dissipado", classes=caster.nome,
            classes_slugs=[caster.slug])
        self.owned = self.person.magias.create(
            id_magia=self.spell, nivel=1, nome=self.spell.nome,
            preparada=True, origem=caster.nome)
        self.talent = TbTalento.objects.create(
            nome="Fonte arcana", slug="fonte-arcana",
            tags_json=["attr:talent_attr_score+2",
                       "attr_max:talent_attr_score=30", FREE_CAST_TAG])
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            nome=self.talent.nome, categoria="epico", detalhes="talent_attr:INT")
        self.url = reverse("oficina_conjurar_magia", args=[self.person.pk])

    def cast(self):
        return self.client.post(self.url, {
            "magia_personagem": self.owned.pk, "slot": 1})

    def test_tag_and_choice_gate(self):
        self.assertEqual([issue for issue in validate_tags_json(
            self.talent.tags_json, Library()) if issue.level == ERROR], [])
        self.assertTrue(free_cast_available(self.person, 1))
        self.assertFalse(free_cast_available(self.person, 5))
        self.grant.detalhes = ""
        self.grant.save(update_fields=["detalhes"])
        self.assertFalse(free_cast_available(self.person, 1))
        self.grant.detalhes = "talent_attr:INT"
        self.grant.save(update_fields=["detalhes"])
        self.grant.delete()
        self.assertFalse(free_cast_available(self.person, 1))

    def test_workshop_roll_preserves_or_spends_slot_and_owner_gate(self):
        self.client.force_login(self.other)
        self.assertEqual(self.cast().status_code, 404)
        self.client.force_login(self.owner)
        with patch("home.epic_free_cast.secrets.randbelow", return_value=0):
            self.assertIn("status=conjurada", self.cast()["Location"])
        first = self.person.transacoes.order_by("-pk").first()
        self.assertEqual(first.detalhes_json["gasto"]["free_cast_roll"], 1)
        self.assertTrue(first.detalhes_json["gasto"]["preserved"])
        self.assertFalse(self.person.recursos.filter(chave="spell_slot:1").exists())
        with patch("home.epic_free_cast.secrets.randbelow", return_value=1):
            self.assertIn("status=conjurada", self.cast()["Location"])
        second = self.person.transacoes.order_by("-pk").first()
        self.assertEqual(second.detalhes_json["gasto"]["free_cast_roll"], 2)
        self.assertNotIn("preserved", second.detalhes_json["gasto"])
        self.assertEqual(self.person.recursos.get(chave="spell_slot:1").atual, 3)
        self.grant.delete()
        with patch("home.epic_free_cast.secrets.randbelow",
                   side_effect=AssertionError("removed source must not roll")):
            self.assertIn("status=conjurada", self.cast()["Location"])
        third = self.person.transacoes.order_by("-pk").first()
        self.assertNotIn("free_cast_roll", third.detalhes_json["gasto"])

    def test_matching_roll_cannot_cast_with_exhausted_slot(self):
        mutate_resource(self.person, {
            "key": "spell-slot:1", "name": "spell-slot:1",
            "maximum": 4, "reset": "long_rest", "origin": "spellcasting",
        }, -4)
        self.client.force_login(self.owner)
        with patch("home.epic_free_cast.secrets.randbelow", return_value=0):
            self.assertIn("status=slot_gasto", self.cast()["Location"])
        self.assertFalse(self.person.transacoes.exists())
