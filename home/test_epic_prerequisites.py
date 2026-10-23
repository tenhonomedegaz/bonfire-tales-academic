"""Requisitos explícitos do catálogo épico no avaliador geral de talentos."""

import json
from types import SimpleNamespace

from django.test import SimpleTestCase

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
