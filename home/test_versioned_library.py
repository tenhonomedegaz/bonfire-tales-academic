from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import patch
from django.test import TestCase, SimpleTestCase
from home.content_versions import seal_ruleset
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_library import snapshot_library, ruleset_evaluation
from home.tag_engine.library import Library, library_scope
from home.character_engine import _dado_de_vida_classe


class LibraryScopeTests(SimpleTestCase):
    def test_nested_exception_restores_context_and_copies_do_not_leak(self):
        raw = Library(prefer_db=False).raw
        with patch('home.tag_engine.library._active_database_library', side_effect=AssertionError('mutable read')):
            with library_scope(raw):
                first = Library()
                first.raw['primitives'].clear()
                self.assertEqual(Library().raw, raw)
                try:
                    with library_scope({'primitives': {}}):
                        self.assertEqual(Library().raw, {'primitives': {}})
                        raise RuntimeError('test')
                except RuntimeError:
                    pass
                self.assertEqual(Library().raw, raw)
            with self.assertRaisesMessage(AssertionError, 'mutable read'):
                Library()

    def test_independent_contexts_do_not_share_vocabularies(self):
        from contextvars import Context
        def read(raw):
            with library_scope(raw):
                return Library().raw
        one, two = Context(), Context()
        self.assertEqual(one.run(read, {'primitives': {'first': {}}}), {'primitives': {'first': {}}})
        self.assertEqual(two.run(read, {'primitives': {'second': {}}}), {'primitives': {'second': {}}})


class VersionedLibraryTests(TestCase):
    def test_numeric_reader_uses_pinned_vocabulary_without_live_reads(self):
        raw = Library(prefer_db=False).raw
        def seal(value):
            return seal_ruleset([snapshot_library(raw=value)], evaluator_version=EVALUATOR,
                                vocabulary_version=VOCABULARY)
        old = seal(raw)
        changed = deepcopy(raw)
        changed['tags_de_classe']['hit_dice']['target'] = 'changed.target'
        new = seal(changed)
        cl = NS(tags_json=['hit_dice:1d8'], dado_vida=None)
        with patch('home.tag_engine.library._active_database_library', side_effect=AssertionError('mutable read')):
            with ruleset_evaluation(old):
                with self.assertNumQueries(0):
                    self.assertEqual(_dado_de_vida_classe(cl), 8)
                with ruleset_evaluation(new):
                    self.assertIsNone(_dado_de_vida_classe(cl))
                self.assertEqual(_dado_de_vida_classe(cl), 8)

    def test_missing_vocabulary_refuses_fallback(self):
        from home.content_versions import create_revision
        ruleset = seal_ruleset([create_revision('unrelated', {})], evaluator_version=EVALUATOR,
                               vocabulary_version=VOCABULARY)
        from home.models import TbRulesetContent
        with self.assertRaises(TbRulesetContent.DoesNotExist):
            with ruleset_evaluation(ruleset):
                self.fail('Must refuse absent vocabulary')
