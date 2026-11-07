"""Integração de tags épicas do catálogo ao consumidor de encontros."""

from django.test import SimpleTestCase
from unittest.mock import patch

from home.epic_talent_catalog import epic_candidates
from home.character_engine import apply_tags
from home.tag_engine.combat_encounter import CombatEncounter
from types import SimpleNamespace


class EpicCombatTests(SimpleTestCase):
    @patch("home.character_engine._cond_nomes", return_value={})
    def test_fortitude_aplica_remove_e_reaplica_bonus_de_pv_maximo(self, _conditions):
        talent = next(row for row in epic_candidates()
                      if row["slug"] == "dadiva-da-fortitude")

        def state():
            return {
                "_ctx": {"lvl": 20, "classlvl": 20, "pb": 6, "dex_mod": 0,
                         "con_mod": 3},
                "pv": {"maximo_calculado": 100}, "ca": 10,
                "velocidade": "9 m / 30 ft", "recursos": {},
            }

        feature = SimpleNamespace(nome=talent["nome"], slug=talent["slug"],
                                  tags_json=talent["tags_json"])
        with patch("home.character_engine._talent_attr_map",
                   return_value={("slug", talent["slug"]): "CON"}):
            applied = apply_tags(state(), [("talento", feature.nome, feature, None)])
            removed = apply_tags(state(), [])
            reapplied = apply_tags(state(), [("talento", feature.nome, feature, None)])

        self.assertEqual(applied["pv"]["maximo_calculado"], 140)
        self.assertEqual(removed["pv"]["maximo_calculado"], 100)
        self.assertEqual(reapplied["pv"]["maximo_calculado"], 140)

    def test_fortitude_adiciona_cura_uma_vez_ate_o_inicio_do_proprio_turno(self):
        talent = next(row for row in epic_candidates()
                      if row["slug"] == "dadiva-da-fortitude")
        encounter = CombatEncounter([
            {"id": "aliado", "team": "grupo", "max_hp": 20},
            {"id": "heroi", "team": "grupo", "max_hp": 140, "hp": 100,
             "defensive_tags": talent["tags_json"], "tag_context": {"con_mod": 3}},
            {"id": "inimigo", "team": "oponentes", "max_hp": 20},
        ])

        encounter.start_turn("aliado", 1)
        self.assertTrue(encounter.heal("heroi", 5))
        self.assertEqual(encounter.combatants["heroi"]["hp"], 108)
        encounter.end_turn()

        encounter.start_turn("inimigo", 1)
        encounter.end_turn()
        encounter.start_turn("aliado", 2)
        self.assertTrue(encounter.heal("heroi", 5))
        self.assertEqual(encounter.combatants["heroi"]["hp"], 113)
        encounter.end_turn()

        encounter.start_turn("heroi", 1)
        encounter.end_turn()
        encounter.start_turn("aliado", 3)
        self.assertTrue(encounter.heal("heroi", 5))
        self.assertEqual(encounter.combatants["heroi"]["hp"], 121)

    def test_fortitude_nao_gasta_bonus_sem_cura_recebida(self):
        talent = next(row for row in epic_candidates()
                      if row["slug"] == "dadiva-da-fortitude")
        encounter = CombatEncounter([
            {"id": "aliado", "team": "grupo", "max_hp": 20},
            {"id": "heroi", "team": "grupo", "max_hp": 140, "hp": 100,
             "defensive_tags": talent["tags_json"], "tag_context": {"con_mod": 3}},
            {"id": "inimigo", "team": "oponentes", "max_hp": 20},
        ])
        encounter.start_turn("aliado", 1)
        encounter.heal("heroi", 0)
        self.assertEqual(encounter.combatants["heroi"]["hp"], 100)
        encounter.end_turn()
        encounter.start_turn("inimigo", 1)
        encounter.end_turn()
        encounter.start_turn("aliado", 2)
        encounter.heal("heroi", 5)
        self.assertEqual(encounter.combatants["heroi"]["hp"], 108)

    def test_resiliencia_sangrenta_do_catalogo_reduz_dano_no_encontro(self):
        talent = next(row for row in epic_candidates()
                      if row["slug"] == "dadiva-da-resiliencia-sangrenta")
        encounter = CombatEncounter([
            {"id": "inimigo", "team": "oponentes", "max_hp": 20},
            {"id": "heroi", "team": "grupo", "max_hp": 20, "hp": 10,
             "defensive_tags": talent["tags_json"]},
        ])

        encounter.start_turn("inimigo", 1)
        encounter.attack("heroi", [], hit=True, damage=7, damage_type="frio")
        self.assertEqual(encounter.combatants["heroi"]["hp"], 7)
        encounter.end_turn()

        encounter.start_turn("inimigo", 2)
        encounter.attack("heroi", [], hit=True, damage=7, damage_type="forca")
        self.assertEqual(encounter.combatants["heroi"]["hp"], 0)
