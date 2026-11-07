"""Regression coverage for the current importable epic catalog increment."""

import copy
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from home.epic_heroic_inspiration import TABLE_HEROIC_INSPIRATION_GRANT_TAG
from home.epic_talent_catalog import (ATTRIBUTE_TAGS, DECLARATIVE_GAPS,
                                      VTT_DECLARATIVE_TAGS, epic_candidates,
                                      TAG_PACKAGE_PATH, _tag_package)
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class EpicCatalogIncrementTests(SimpleTestCase):
    def test_per_talent_tags_are_loaded_from_data_package(self):
        data = json.loads(TAG_PACKAGE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(_tag_package(), data)
        self.assertEqual(data["common_tags"], ATTRIBUTE_TAGS)
        for candidate in epic_candidates():
            self.assertEqual(candidate["tags_json"],
                             data["common_tags"] + data["effects"].get(candidate["slug"], []))

    def test_package_rejects_invalid_shapes_and_unexplained_gaps(self):
        original = _tag_package()
        for key, value in (("schema", 2), ("common_tags", [5]),
                           ("effects", {"any": "not-a-list"}),
                           ("declarative_gaps", {})):
            data = copy.deepcopy(original)
            data[key] = value
            with self.subTest(key=key), patch("home.epic_talent_catalog.Path") as path:
                path.return_value.read_text.return_value = json.dumps(data)
                with self.assertRaises(ValueError):
                    _tag_package("invalid-package")

    def test_candidates_use_explicit_epic_category(self):
        for entry in epic_candidates():
            self.assertEqual(entry["tipo"], "epico")
            self.assertEqual(entry["etiquetas_adicionais"], "epico")

    def test_newly_importable_entries_keep_only_valid_dsl_declarations(self):
        entries = {entry["slug"]: entry for entry in epic_candidates()}
        expected = {
            "dadiva-do-reforco-mistico",
            "dadiva-da-mente-desperta",
            "dadiva-da-resistencia-heroica",
            "dadiva-da-folia",
        }
        self.assertTrue(expected.issubset(entries))
        for slug in expected:
            self.assertEqual([issue for issue in validate_tags_json(
                entries[slug]["tags_json"], Library()) if issue.level == ERROR], [])
        self.assertIn(TABLE_HEROIC_INSPIRATION_GRANT_TAG,
                      entries["dadiva-da-resistencia-heroica"]["tags_json"])
        self.assertEqual(entries["dadiva-do-reforco-mistico"]["tags_json"][:2],
                         ATTRIBUTE_TAGS)

    def test_all_staged_entries_are_cataloged_with_explicit_declarative_gaps(self):
        entries = {entry["slug"]: entry for entry in epic_candidates()}
        self.assertEqual(len(entries), 31)
        self.assertEqual(set(VTT_DECLARATIVE_TAGS), {
            "dadiva-da-maestria-de-escola-arcana",
            "dadiva-da-marca-arcana-superior",
            "dadiva-da-manipulacao-corporea",
            "dadiva-do-alvorecer-ardente",
        })
        self.assertEqual(set(DECLARATIVE_GAPS), set(VTT_DECLARATIVE_TAGS))
        for slug, tags in VTT_DECLARATIVE_TAGS.items():
            self.assertEqual([issue for issue in validate_tags_json(
                tags, Library()) if issue.level == ERROR], [])
            self.assertEqual(entries[slug]["tags_json"], ATTRIBUTE_TAGS)
