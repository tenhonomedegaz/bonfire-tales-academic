import json
from pathlib import Path

from django.test import SimpleTestCase
from django.conf import settings

from home.tag_engine.combat_conditions import CombatConditions
from home.management.commands.importar_bestiario_csv import CSV_PATH, _read_rows, _slug_criatura, _split_secao


BEARD = (
    "instant{attack:melee, attack:+5, reach:5ft, dmg:1d8+3(perfurante), "
    "instant{trigger=hit, apply:envenenado(duration:until_source_turn_start)}, "
    "while_active{requires:target{condition{envenenado, source:self}}, "
    "restricts{heal,target}}}"
)


def active(result, verb):
    return [op for op in result.operations if op.active and op.verb == verb]


class CombatConditionTurnTests(SimpleTestCase):
    def test_acerto_cura_e_inicio_do_turno_da_fonte(self):
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

        combat.start_turn("alvo", "turno-1")  # repeated event is idempotent
        self.assertEqual(len(active(combat.resolve(
            [BEARD], event="healing", source="diabo", target="alvo"), "restricts")), 1)
        combat.start_turn("alvo", "turno-2")
        self.assertEqual(combat.facts("alvo", "diabo"), {"envenenado": {"self"}})
        combat.start_turn("diabo", "turno-1")
        self.assertEqual(combat.facts("alvo", "diabo"), {})
        self.assertFalse(active(combat.resolve(
            [BEARD], event="healing", source="diabo", target="alvo"), "restricts"))

    def test_fontes_independentes_e_reaplicacao(self):
        combat = CombatConditions()
        combat.resolve([BEARD], event="hit", source="diabo-a", target="alvo")
        combat.start_turn("alvo", 1)
        combat.resolve([BEARD], event="hit", source="diabo-b", target="alvo")
        self.assertEqual(combat.facts("alvo", "diabo-a"), {"envenenado": {"self", "other"}})
        self.assertEqual(combat.facts("alvo", "diabo-b"), {"envenenado": {"self", "other"}})
        combat.start_turn("diabo-a", 1)
        self.assertEqual(combat.facts("alvo", "diabo-b"), {"envenenado": {"self"}})
        combat.start_turn("diabo-b", 1)
        self.assertEqual(combat.facts("alvo", "diabo-b"), {})

    def test_sem_condicao_na_falha_do_ataque(self):
        combat = CombatConditions()
        combat.resolve([BEARD], event="attack", source="diabo", target="alvo")
        self.assertEqual(combat.facts("alvo", "diabo"), {})

    def test_condicao_em_self_expira_no_turno_da_fonte(self):
        for operand in ("target:self", "self"):
            with self.subTest(operand=operand):
                combat = CombatConditions()
                combat.resolve([
                    "instant{trigger=hit, apply:incorporeo(%s, duration:until_turn_start)}"
                    % operand
                ], event="hit", source="fantasma", target="aventureiro")
                self.assertEqual(combat.facts("fantasma", "fantasma"),
                                 {"incorporeo": {"self"}})
                self.assertEqual(combat.facts("aventureiro", "fantasma"), {})
                combat.start_turn("aventureiro", 1)
                self.assertEqual(combat.facts("fantasma", "fantasma"),
                                 {"incorporeo": {"self"}})
                combat.start_turn("fantasma", 1)
                self.assertEqual(combat.facts("fantasma", "fantasma"), {})

    def test_seletor_nao_resolvido_nao_aplica_condicao_ao_alvo_errado(self):
        combat = CombatConditions()
        combat.resolve([
            "instant{trigger=hit, apply:envenenado(target:ally, duration:until_turn_start)}"
        ], event="hit", source="monstro", target="aventureiro")
        self.assertEqual(combat.facts("aventureiro", "monstro"), {})
        self.assertEqual(combat.facts("monstro", "monstro"), {})

    def test_replay_de_turno_antigo_nao_expira_condicao_nova(self):
        combat = CombatConditions()
        combat.start_turn("diabo", "turno-1")
        combat.start_turn("diabo", "turno-2")
        combat.resolve([BEARD], event="hit", source="diabo", target="alvo")
        combat.start_turn("diabo", "turno-1")
        self.assertEqual(combat.facts("alvo", "diabo"), {"envenenado": {"self"}})
        combat.start_turn("diabo", "turno-3")
        self.assertEqual(combat.facts("alvo", "diabo"), {})

    def test_tres_acoes_de_veneno_reais_liberam_cura_apos_turno(self):
        manifest = Path(settings.BASE_DIR) / "ref/bestiario/retagging_veneno_turno_fonte_20261001.json"
        rows = json.loads(manifest.read_text(encoding="utf-8"))["rows"]
        source_rows = {_slug_criatura(row["Name"].strip()): row
                       for row in _read_rows(CSV_PATH, [])}
        checked = 0
        source_backed = 0
        for row in rows:
            originals = _split_secao(source_rows[row["slug"]]["Actions"], {})
            for feature in row["features"]:
                tags = feature["tags"]
                source_text = " ".join(originals[feature["index"]]["entries"])
                self.assertRegex(source_text,
                                 r"Poisoned condition until the start of the [^.]+'s next turn")
                self.assertTrue(all("duration:until_source_turn_start" in tag
                                    for tag in tags))
                source_backed += 1
                if not any("restricts{heal,target}" in tag for tag in tags):
                    continue
                checked += 1
                combat = CombatConditions()
                source = row["slug"]
                combat.resolve(tags, event="hit", source=source, target="alvo")
                self.assertTrue(active(combat.resolve(
                    tags, event="healing", source=source, target="alvo"), "restricts"))
                combat.start_turn("alvo", 1)
                self.assertTrue(active(combat.resolve(
                    tags, event="healing", source=source, target="alvo"), "restricts"))
                combat.start_turn(source, 1)
                self.assertFalse(active(combat.resolve(
                    tags, event="healing", source=source, target="alvo"), "restricts"))
        self.assertEqual(checked, 3)
        self.assertEqual(source_backed, 10)
