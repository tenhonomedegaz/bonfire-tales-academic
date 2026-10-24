"""Focused pure contracts for the generic tags of Dadiva da Velocidade."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from home.character_engine import apply_tags
from home.epic_talent_catalog import PARTIAL_EFFECTS
from home.views import _innate_spell_uses_from_features


SPEED_TAGS = tuple(PARTIAL_EFFECTS["dadiva-da-velocidade"])


def state(speed=30):
    return {
        "_ctx": {"lvl": 20, "classlvl": 20, "pb": 6, "dex_mod": 0},
        "pv": {"maximo_calculado": 20},
        "ca": 10,
        "velocidade": "%g m / %d ft" % (round(speed * 0.3, 1), speed),
        "recursos": {},
    }


def feature(name="Fonte sintetica", tags=SPEED_TAGS):
    return SimpleNamespace(nome=name, tags_json=list(tags))


class EpicSpeedPassiveTests(SimpleTestCase):
    @patch("home.character_engine._cond_nomes", return_value={
        "paralisado": "Paralisado", "restringido": "Restringido"})
    def test_applies_removes_coexists_and_deduplicates_passives(self, _conditions):
        applied = apply_tags(state(), [("talento", "Fonte", feature(), None)])
        self.assertEqual(applied["velocidade"], "18 m / 60 ft")
        self.assertEqual(
            {row["slug"] for row in applied["imunidades_condicao"]},
            {"paralisado", "restringido"})

        removed = apply_tags(state(), [])
        self.assertEqual(removed["velocidade"], "9 m / 30 ft")
        self.assertEqual(removed["imunidades_condicao"], [])

        coexists = apply_tags(state(), [
            ("talento", "Fonte", feature(), None),
            ("origem", "Outra", feature("Outra", ("speed:+10", "cond_immune:agarrado")), None),
        ])
        self.assertEqual(coexists["velocidade"], "21 m / 70 ft")
        self.assertEqual(
            {row["slug"] for row in coexists["imunidades_condicao"]},
            {"agarrado", "paralisado", "restringido"})

        duplicate = apply_tags(state(), [
            ("talento", "Fonte", feature(tags=SPEED_TAGS * 2), None)])
        self.assertEqual(duplicate["velocidade"], "18 m / 60 ft")
        self.assertEqual(
            {row["slug"] for row in duplicate["imunidades_condicao"]},
            {"paralisado", "restringido"})


class EpicSpeedInnateSpellTests(SimpleTestCase):
    def test_compiles_slotless_componentless_short_or_long_haste_once(self):
        uses = _innate_spell_uses_from_features(
            [("talento", "Fonte", feature(), None)], {"velocidade"}, state())
        meta = uses[("Fonte sintetica", "velocidade")]
        self.assertEqual(meta["maximo"], 1)
        self.assertEqual(meta["reset"], "short_or_long")
        self.assertEqual(meta["label"], "1/rest")
        self.assertTrue(meta["without_slot"])
        self.assertTrue(meta["without_components"])
        self.assertTrue(meta["without_lethargy"])

    def test_spell_contract_is_idempotent_and_source_scoped(self):
        duplicate = _innate_spell_uses_from_features(
            [("talento", "Fonte", feature(tags=SPEED_TAGS * 2), None)],
            {"velocidade"}, state())
        self.assertEqual(len(duplicate), 1)

        coexists = _innate_spell_uses_from_features([
            ("talento", "Fonte", feature(), None),
            ("origem", "Outra", feature("Outra", (
                "cast{spell:velocidade, uses{1, reset:long_rest}, without{slot}}",)), None),
        ], {"velocidade"}, state())
        self.assertEqual(coexists[("Fonte sintetica", "velocidade")]["reset"], "short_or_long")
        self.assertEqual(coexists[("Outra", "velocidade")]["reset"], "long_rest")
