"""Focused contracts for the generic tags used by the sky epic talent."""

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from home.character_engine import apply_tags, derive
from home.epic_sky_runtime import fall_distance_for_turn
from home.epic_talent_catalog import ATTRIBUTE_TAGS, PARTIAL_EFFECTS, epic_candidates
from home.models import TbMagia, TbPersonagem, TbPersonagemTalento, TbTalento
from home.tag_engine.combat_encounter import CombatEncounter
from home.views import (_innate_spell_uses, _magias_sheet_info,
                        _sync_magias_concedidas)


EFFECT_TAGS = tuple(PARTIAL_EFFECTS["dadiva-do-dominio-do-ceu"])
TAGS = tuple(ATTRIBUTE_TAGS) + EFFECT_TAGS


def base_state(speed=30):
    return {
        "_ctx": {"lvl": 20, "classlvl": 20, "pb": 6, "dex_mod": 0},
        "pv": {"maximo_calculado": 20},
        "ca": 10,
        "velocidade": "%g m / %d ft" % (round(speed * 0.3, 1), speed),
        "recursos": {},
    }


def feature(tags=EFFECT_TAGS):
    return SimpleNamespace(nome="Fonte sintética", tags_json=list(tags))


class EpicSkyMovementTests(SimpleTestCase):
    def test_talento_fora_da_carga_sem_consumer_do_site(self):
        self.assertNotIn("dadiva-do-dominio-do-ceu", {
            item["slug"] for item in epic_candidates()
        })

    @patch("home.character_engine._cond_nomes", return_value={})
    def test_applies_flight_hover_and_controlled_fall(self, _conditions):
        sheet = apply_tags(base_state(), [("talento", "épico", feature(), None)])

        self.assertEqual(sheet["movimento_modos"]["fly"], "walk")
        self.assertEqual(
            sheet["movimento_propriedades"], {"fly": {"hover": True}})
        self.assertEqual(sheet["queda_controlada"], {
            "threshold_ft": 5,
            "max_per_turn_ft": 60,
        })
        self.assertEqual(fall_distance_for_turn(sheet, 5), 5)
        self.assertEqual(fall_distance_for_turn(sheet, 120), 60)

    @patch("home.character_engine._cond_nomes", return_value={})
    def test_removal_recalculation_and_duplicate_tags(self, _conditions):
        removed = apply_tags(base_state(), [])
        self.assertNotIn("movimento_modos", removed)
        self.assertNotIn("movimento_propriedades", removed)
        self.assertNotIn("queda_controlada", removed)
        self.assertEqual(fall_distance_for_turn(removed, 120), 120)

        recalculated = apply_tags(
            base_state(40), [("talento", "épico", feature(), None)])
        self.assertEqual(recalculated["movimento_modos"]["fly"], "walk")
        self.assertEqual(recalculated["velocidade"], "12 m / 40 ft")

        duplicate = apply_tags(
            base_state(), [("talento", "épico", feature(EFFECT_TAGS * 2), None)])
        self.assertEqual(duplicate["movimento_propriedades"], {
            "fly": {"hover": True},
        })
        self.assertEqual(duplicate["queda_controlada"], {
            "threshold_ft": 5,
            "max_per_turn_ft": 60,
        })

    def test_encounter_consumes_fall_tags_once_per_turn(self):
        encounter = CombatEncounter([
            {"id": "sky", "team": "allies", "max_hp": 20,
             "defensive_tags": EFFECT_TAGS},
            {"id": "ordinary", "team": "enemies", "max_hp": 20},
        ])
        self.assertEqual(encounter.fall("sky", 5, turn_id="t1"), 5)
        self.assertEqual(encounter.fall("sky", 120, turn_id="t1"), 55)
        self.assertEqual(encounter.fall("sky", 60, turn_id="t1"), 0)
        self.assertEqual(encounter.fall("sky", 60, turn_id="t2"), 60)
        self.assertEqual(encounter.fall("ordinary", 120, turn_id="t2"), 120)
        self.assertEqual(encounter.events[-1],
                         ("fall", "ordinary", "t2", 120, 120))


class EpicSkySpellTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="epic-sky")
        self.character = TbPersonagem.objects.create(
            dono=owner, nome="Teste céu")
        self.spell = TbMagia.objects.create(
            nome="Caminhar Sobre os Ventos", nome_ingles="Wind Walk",
            slug="caminhar-no-vento", nivel=6, componentes="V, S, M")
        self.talent = TbTalento.objects.create(
            nome="Talento épico sintético", slug="talento-epico-ceu-teste",
            tipo="geral", etiqueta="exploracao", etiquetas_adicionais="epico",
            descricao="Fonte de teste.", tags_json=list(TAGS))
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=self.talent,
            categoria="epico", nome=self.talent.nome,
            detalhes="talent_attr:DES")

    def test_spell_application_is_componentless_slotless_and_long_rest_limited(self):
        _sync_magias_concedidas(self.character)
        granted = self.character.magias.get(id_magia=self.spell)
        self.assertTrue(granted.sempre_preparada)

        sheet = derive(self.character)
        meta = _innate_spell_uses(self.character, sheet)[
            (self.talent.nome, self.spell.slug)]
        self.assertEqual(meta["maximo"], 1)
        self.assertEqual(meta["reset"], "long_rest")
        self.assertTrue(meta["without_slot"])
        self.assertTrue(meta["without_components"])

        row = next(item for item in _magias_sheet_info(
            self.character, sheet, [])["lista"] if item["id"] == granted.id)
        self.assertEqual(row["componentes"], "—")
        self.assertTrue(row["innate_without_slot"])
        self.assertEqual(row["innate_max"], 1)

        from home.resource_engine import (ensure_resource, reset_resources,
                                          spend_resource)
        contract = {
            "key": row["innate_key"], "legacy_name": row["innate_key"],
            "name": granted.nome, "maximum": row["innate_max"],
            "reset": row["innate_reset"], "origin": "magia_inata",
        }
        ensure_resource(self.character, contract)
        resource = ensure_resource(self.character, contract)
        spent, snapshot = spend_resource(self.character, contract)
        self.assertTrue(spent)
        self.assertEqual(snapshot["current"], 0)
        reset_resources(self.character, "short_rest")
        resource.refresh_from_db()
        self.assertEqual(resource.atual, 0)
        reset_resources(self.character, "long_rest")
        resource.refresh_from_db()
        self.assertEqual(resource.atual, 1)

    def test_spell_sync_is_idempotent_and_removes_grant_with_source(self):
        _sync_magias_concedidas(self.character)
        _sync_magias_concedidas(self.character)
        self.assertEqual(
            self.character.magias.filter(id_magia=self.spell).count(), 1)

        self.owned.delete()
        _sync_magias_concedidas(self.character)
        self.assertFalse(
            self.character.magias.filter(id_magia=self.spell).exists())
        recalculated = derive(self.character)
        self.assertNotIn("movimento_modos", recalculated)
        self.assertNotIn("movimento_propriedades", recalculated)
        self.assertNotIn("queda_controlada", recalculated)
        self.assertEqual(_innate_spell_uses(
            self.character, recalculated), {})
