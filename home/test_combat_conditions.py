import json
from pathlib import Path

from django.test import SimpleTestCase
from django.conf import settings

from home.tag_engine.combat_conditions import CombatConditions


BEARD = (
    "instant{attack:melee, attack:+5, reach:5ft, dmg:1d8+3(perfurante), "
    "instant{trigger=hit, apply:envenenado(duration:until_turn_start)}, "
    "while_active{requires:target{condition{envenenado, source:self}}, "
    "restricts{heal,target}}}"
)


def active(result, verb):
    return [op for op in result.operations if op.active and op.verb == verb]


class CombatConditionTurnTests(SimpleTestCase):
    def test_acerto_cura_e_inicio_do_turno_do_alvo(self):
        combat = CombatConditions()
        combat.start_turn("alvo", "turno-1")
        self.assertFalse(active(combat.resolve(
            [BEARD], event="attack", source="diabo", target="alvo"), "apply"))
        self.assertFalse(active(combat.resolve(
            [BEARD], event="healing", source="diabo", target="alvo"), "restricts"))

        hit = combat.resolve([BEARD], event="hit", source="diabo", target="alvo")
        self.assertEqual(len(active(hit, "apply")), 1)
        self.assertEqual(combat.facts("alvo", "diabo"), {"envenenado": {"self"}})
        self.assertEqual(len(active(combat.resolve(
            [BEARD], event="healing", source="diabo", target="alvo"), "restricts")), 1)
        self.assertFalse(active(combat.resolve(
            [BEARD], event="healing", source="outro", target="alvo"), "restricts"))

        combat.start_turn("diabo", "turno-1")
        combat.start_turn("alvo", "turno-1")  # repeated event is idempotent
        self.assertEqual(len(active(combat.resolve(
            [BEARD], event="healing", source="diabo", target="alvo"), "restricts")), 1)
        combat.start_turn("alvo", "turno-2")
        self.assertEqual(combat.facts("alvo", "diabo"), {})
        self.assertFalse(active(combat.resolve(
            [BEARD], event="healing", source="diabo", target="alvo"), "restricts"))

    def test_fontes_independentes_e_reaplicacao(self):
        combat = CombatConditions()
        combat.resolve([BEARD], event="hit", source="diabo-a", target="alvo")
        combat.start_turn("alvo", 1)
        combat.resolve([BEARD], event="hit", source="diabo-b", target="alvo")
        self.assertEqual(combat.facts("alvo", "diabo-a"), {"envenenado": {"other"}})
        self.assertEqual(combat.facts("alvo", "diabo-b"), {"envenenado": {"self"}})
        combat.start_turn("alvo", 2)
        self.assertEqual(combat.facts("alvo", "diabo-b"), {})

    def test_sem_condicao_na_falha_do_ataque(self):
        combat = CombatConditions()
        combat.resolve([BEARD], event="attack", source="diabo", target="alvo")
        self.assertEqual(combat.facts("alvo", "diabo"), {})

    def test_tres_acoes_de_veneno_reais_liberam_cura_apos_turno(self):
        manifest = Path(settings.BASE_DIR) / "ref/bestiario/retagging_veneno_condicional_20261001.json"
        rows = json.loads(manifest.read_text(encoding="utf-8"))["rows"]
        checked = 0
        for row in rows:
            for feature in row["features"]:
                tags = feature["tags"]
                if not any("restricts{heal,target}" in tag for tag in tags):
                    continue
                checked += 1
                combat = CombatConditions()
                source = row["slug"]
                combat.resolve(tags, event="hit", source=source, target="alvo")
                self.assertTrue(active(combat.resolve(
                    tags, event="healing", source=source, target="alvo"), "restricts"))
                combat.start_turn("alvo", 1)
                self.assertFalse(active(combat.resolve(
                    tags, event="healing", source=source, target="alvo"), "restricts"))
        self.assertEqual(checked, 3)
