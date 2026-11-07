"""Requisitos explícitos do catálogo épico no avaliador geral de talentos."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from home import views
from home.epic_talent_catalog import STAGING_PATH


class EpicPrerequisiteTests(SimpleTestCase):
    def test_marca_arcana_superior_exige_ambas_as_marcas_citadas(self):
        entries = json.loads(STAGING_PATH.read_text(encoding="utf-8"))["talentos"]
        entry = next(row for row in entries
                     if row["titulo"] == "Dádiva da Marca Arcana Superior")
        talent = SimpleNamespace(pre_requisito=entry["pre_requisito"])
        character = SimpleNamespace(nivel=20)
        context = {
            "owned": set(), "sources": {}, "choices": [],
            "proficiencias": set(), "conjura": False,
        }

        self.assertFalse(views._talento_prereq_ok(talent, character, {}, context))
        context["owned"].add("marca arcana maior")
        self.assertFalse(views._talento_prereq_ok(talent, character, {}, context))
        context["owned"].add("marca potente")
        self.assertTrue(views._talento_prereq_ok(talent, character, {}, context))

    def test_telepatia_requer_tag_passiva_de_origem_permitida(self):
        entries = json.loads(STAGING_PATH.read_text(encoding="utf-8"))["talentos"]
        entry = next(row for row in entries
                     if row["titulo"] == "Dádiva da Mente Desperta")
        talent = SimpleNamespace(pre_requisito=entry["pre_requisito"])
        character = SimpleNamespace(nivel=20)

        def feature(origin, tag):
            return (origin, "Fonte", SimpleNamespace(tags_json=[tag]), None)

        cases = [
            ([feature("talento", "telepathy:creature(range:60ft)")], True),
            ([feature("classe", "always_active{ telepathy:creature(range:60ft) }")], True),
            ([feature("linhagem", "telepathy:creature(range:30ft)")], True),
            ([feature("item", "telepathy:creature(range:120ft)")], False),
            ([feature("talento", "while_active{ telepathy:creature(range:60ft) }")], False),
            ([feature("talento", "cast{spell:telepatia}")], False),
            ([], False),
        ]
        for features, expected in cases:
            with self.subTest(features=features), patch(
                    "home.character_engine._features_do_personagem", return_value=features):
                self.assertEqual(views._talento_prereq_ok(talent, character, {}), expected)


class EpicPrerequisiteCharacterTests(TestCase):
    def test_telepatia_de_talento_persistido_libera_e_remocao_bloqueia(self):
        from django.contrib.auth import get_user_model
        from home.models import TbPersonagem, TbPersonagemTalento, TbTalento

        entries = json.loads(STAGING_PATH.read_text(encoding="utf-8"))["talentos"]
        entry = next(row for row in entries
                     if row["titulo"] == "Dádiva da Mente Desperta")
        talent = SimpleNamespace(pre_requisito=entry["pre_requisito"])
        owner = get_user_model().objects.create_user(username="epic-telepathy")
        character = TbPersonagem.objects.create(dono=owner, nome="Teste telepatia")
        source = TbTalento.objects.create(
            nome="Fonte telepática", slug="fonte-telepatica", tipo="geral",
            tags_json=["telepathy:creature(range:60ft)"],
        )
        owned = TbPersonagemTalento.objects.create(
            id_personagem=character, id_talento=source, nome=source.nome)

        self.assertTrue(views._talento_prereq_ok(talent, character, {}))
        owned.delete()
        self.assertFalse(views._talento_prereq_ok(talent, character, {}))
