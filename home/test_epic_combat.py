"""Integração de tags épicas do catálogo ao consumidor de encontros."""

from django.test import SimpleTestCase

from home.epic_talent_catalog import epic_candidates
from home.tag_engine.combat_encounter import CombatEncounter


class EpicCombatTests(SimpleTestCase):
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
