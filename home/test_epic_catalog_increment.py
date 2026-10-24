"""Regression coverage for the current importable epic catalog increment."""

from django.test import SimpleTestCase

from home.epic_heroic_inspiration import TABLE_HEROIC_INSPIRATION_GRANT_TAG
from home.epic_talent_catalog import (ATTRIBUTE_TAGS, DECLARATIVE_EFFECTS,
                                      epic_candidates)
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class EpicCatalogIncrementTests(SimpleTestCase):
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
        self.assertEqual(set(DECLARATIVE_EFFECTS), {
            "dadiva-da-maestria-de-escola-arcana",
            "dadiva-da-marca-arcana-superior",
            "dadiva-da-manipulacao-corporea",
            "dadiva-do-alvorecer-ardente",
        })
        for slug in DECLARATIVE_EFFECTS:
            self.assertEqual([issue for issue in validate_tags_json(
                entries[slug]["tags_json"], Library()) if issue.level == ERROR], [])
