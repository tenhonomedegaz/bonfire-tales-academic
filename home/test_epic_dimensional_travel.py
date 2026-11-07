"""Passos Lampejantes and Porta Dimensional from the real epic candidate."""

import uuid

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from home.epic_talent_catalog import ATTRIBUTE_TAGS, VERIFIED_EFFECTS, epic_candidates
from home.models import TbMagia, TbOperacaoRecurso, TbPersonagem, TbPersonagemTalento, TbTalento
from home.resource_engine import reset_resources
from home.tag_engine.combat_encounter import CombatEncounter
from home.tag_engine.library import Library
from home.tag_engine.validator import validate_tags_json
from home.views import _innate_spell_uses, _sync_magias_concedidas


SLUG = "dadiva-da-viagem-dimensional"
EFFECTS = tuple(VERIFIED_EFFECTS[SLUG])


def encounter(tags=EFFECTS):
    return CombatEncounter([
        {"id": "traveler", "team": "allies", "max_hp": 30,
         "defensive_tags": tags, "offensive_tags": tags},
        {"id": "enemy", "team": "enemies", "max_hp": 30},
    ])


def teleport(game, *, phase, action_kind="attack", **changes):
    request = dict(action_kind=action_kind, phase=phase, distance_ft=30,
                   destination_ref="encontro:quadrado-7", visible=True,
                   unoccupied=True)
    request.update(changes)
    return game.teleport_around_action("traveler", **request)


class DimensionalTravelEncounterTests(SimpleTestCase):
    def test_candidate_and_tags_match_source(self):
        candidate = next(row for row in epic_candidates() if row["slug"] == SLUG)
        self.assertEqual(candidate["tags_json"], ATTRIBUTE_TAGS + list(EFFECTS))
        self.assertIn("Passos Lampejantes", candidate["descricao"])
        self.assertIn("Janela Espacial", candidate["descricao"])
        self.assertEqual(validate_tags_json(EFFECTS, Library()), [])

    def test_before_attack_teleport_requires_action_and_rejects_invalid_spaces(self):
        game = encounter()
        game.start_turn("traveler", "t1")
        for changes in ({"distance_ft": 31}, {"visible": False},
                        {"unoccupied": False}, {"destination_ref": ""}):
            with self.assertRaises(ValueError):
                teleport(game, phase="before", **changes)
        self.assertEqual(teleport(game, phase="before"), 30)
        with self.assertRaises(ValueError):
            game.end_turn()
        with self.assertRaises(ValueError):
            game.register_action("traveler", "action", action_kind="magic")
        game.attack("enemy", (), hit=True, damage=1)
        with self.assertRaises(ValueError):
            teleport(game, phase="after")
        game.end_turn()
        game.start_turn("traveler", "t2")
        self.assertEqual(teleport(game, phase="before", action_kind="magic"), 30)
        game.register_action("traveler", "action", action_kind="magic")
        game.end_turn()

    def test_after_action_magic_and_other_sources(self):
        game = encounter()
        game.start_turn("traveler", "t1")
        with self.assertRaises(ValueError):
            teleport(game, phase="after")
        game.register_action("traveler", "action", action_kind="magic")
        with self.assertRaises(ValueError):
            teleport(game, phase="after", action_kind="attack")
        self.assertEqual(teleport(game, phase="after", action_kind="magic"), 30)
        with self.assertRaises(ValueError):
            teleport(game, phase="after", action_kind="magic")
        game.end_turn()
        game.start_turn("traveler", "t2")
        game.attack("enemy", (), hit=True, damage=1)
        self.assertEqual(teleport(game, phase="after"), 30)
        game.end_turn()

        without = encounter(())
        without.start_turn("traveler", "t1")
        with self.assertRaises(ValueError):
            teleport(without, phase="before")
        with_other = encounter((
            "teleport:60ft(dest:unoccupied_visible, "
            "timing:before_or_after_attack_or_magic_action)",))
        with_other.start_turn("traveler", "t1")
        self.assertEqual(teleport(with_other, phase="before", distance_ft=60), 60)

    def test_after_finishing_attack_can_still_teleport(self):
        game = encounter()
        game.start_turn("traveler", "t1")
        game.attack("enemy", (), hit=True, damage=30)
        self.assertTrue(game.finished)
        self.assertEqual(teleport(game, phase="after"), 30)

    def test_after_window_closes_when_another_action_intervenes(self):
        game = encounter()
        game.start_turn("traveler", "t1")
        game.register_action("traveler", "action", action_kind="magic")
        game.register_action("traveler", "bonus_action")
        with self.assertRaises(ValueError):
            teleport(game, phase="after", action_kind="magic")


class DimensionalTravelSpellTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="dimensional-owner")
        self.other = get_user_model().objects.create_user(username="dimensional-other")
        self.person = TbPersonagem.objects.create(dono=self.owner, nome="Viajante")
        self.spell = TbMagia.objects.create(nome="Porta Dimensional",
                                            slug="porta-dimensional", nivel=4,
                                            componentes="V")
        self.talent = TbTalento.objects.create(**next(
            row for row in epic_candidates() if row["slug"] == SLUG))
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            categoria="epico", nome=self.talent.nome, detalhes="talent_attr:DES")

    def test_innate_spell_is_idempotent_resets_on_short_rest_and_requires_source(self):
        _sync_magias_concedidas(self.person)
        granted = self.person.magias.get(id_magia=self.spell)
        self.assertTrue(granted.sempre_preparada)
        metadata = _innate_spell_uses(self.person)[(self.talent.nome, self.spell.slug)]
        self.assertEqual(metadata["maximo"], 1)
        self.assertEqual(metadata["reset"], "short_or_long")
        self.assertTrue(metadata["without_slot"])
        self.assertTrue(metadata["without_components"])

        url = reverse("personagem_usar_magia_inata", args=[self.person.pk, granted.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {"operation_id": str(uuid.uuid4())}).status_code, 404)
        self.client.force_login(self.owner)
        operation_id = str(uuid.uuid4())
        payload = {"operation_id": operation_id}
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        receipt = TbOperacaoRecurso.objects.get(operation_id=operation_id)
        self.assertEqual(receipt.resposta["remaining"], 0)
        self.assertEqual(self.client.post(url, {"operation_id": str(uuid.uuid4())}).status_code, 400)
        reset_resources(self.person, "short_rest")
        self.assertEqual(self.client.post(url, {"operation_id": str(uuid.uuid4())}).status_code, 302)
        reset_resources(self.person, "long_rest")
        self.assertEqual(self.client.post(url, {"operation_id": str(uuid.uuid4())}).status_code, 302)
        self.owned.detalhes = ""
        self.owned.save(update_fields=["detalhes"])
        self.assertEqual(self.client.post(url, {"operation_id": str(uuid.uuid4())}).status_code, 400)
        self.owned.detalhes = "talent_attr:DES"
        self.owned.save(update_fields=["detalhes"])
        self.owned.delete()
        self.assertEqual(self.client.post(url, {"operation_id": str(uuid.uuid4())}).status_code, 400)
        _sync_magias_concedidas(self.person)
        self.assertFalse(self.person.magias.filter(id_magia=self.spell).exists())
