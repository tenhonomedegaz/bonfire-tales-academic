"""The complete Fool's Luck source is eligible for the protected catalog."""

from django.test import SimpleTestCase

from home.epic_save_reroll import REROLL_TAG
from home.epic_talent_catalog import ATTRIBUTE_TAGS, epic_candidates
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class FoolsLuckCandidateTests(SimpleTestCase):
    def test_rule_and_markdown_match_source_candidate(self):
        candidate = next(row for row in epic_candidates()
                         if row["slug"] == "dadiva-da-sorte-tola")
        self.assertEqual(candidate["tags_json"], ATTRIBUTE_TAGS + [REROLL_TAG])
        self.assertIn("**Aumento de Atributo:**", candidate["descricao"])
        self.assertIn("teste de resistência", candidate["descricao"].lower())
        self.assertEqual([row for row in validate_tags_json(
            candidate["tags_json"], Library()) if row.level == ERROR], [])
