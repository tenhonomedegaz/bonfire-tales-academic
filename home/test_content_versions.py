from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from home.content_versions import create_revision, seal_ruleset, resolve_content
from home.models import TbContentRevision, TbRuleset, TbRulesetContent


class ContentVersionTests(TestCase):
    def setUp(self):
        self.revision = create_revision('class:cacador', {'level': 1, 'die': 'd6'})
        self.ruleset = seal_ruleset([self.revision], evaluator_version='engine-v1', vocabulary_version='tags-v1')

    def resolve(self, ruleset=None):
        return resolve_content(ruleset or self.ruleset, 'class:cacador',
                               evaluator_version='engine-v1', vocabulary_version='tags-v1')

    def test_replay_and_new_revision_preserve_old_resolution(self):
        self.assertEqual(create_revision('class:cacador', {'die': 'd6', 'level': 1}).pk, self.revision.pk)
        newer = create_revision('class:cacador', {'level': 1, 'die': 'd8'})
        new_rules = seal_ruleset([newer], evaluator_version='engine-v1', vocabulary_version='tags-v1')
        self.assertEqual(self.resolve()['die'], 'd6')
        self.assertEqual(self.resolve(new_rules)['die'], 'd8')
        self.assertEqual(seal_ruleset([self.revision], evaluator_version='engine-v1', vocabulary_version='tags-v1').pk,
                         self.ruleset.pk)
        returned = self.resolve()
        returned['die'] = 'changed'
        self.assertEqual(self.resolve()['die'], 'd6')

    def test_update_delete_and_direct_sql_are_rejected(self):
        for model, pk in [(TbContentRevision, self.revision.pk), (TbRuleset, self.ruleset.pk),
                          (TbRulesetContent, self.ruleset.entries.get().pk)]:
            table = connection.ops.quote_name(model._meta.db_table)
            for sql in [f'UPDATE {table} SET id=id WHERE id=%s', f'DELETE FROM {table} WHERE id=%s']:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(sql, [pk])
        self.assertEqual(self.resolve()['die'], 'd6')

    def test_unresolved_dependencies_and_duplicate_identities_fail_atomically(self):
        dependent = create_revision('feature:mark', {}, dependencies=['spell:mark'])
        for rows in ([dependent], [self.revision, self.revision],
                     [self.revision, create_revision('class:cacador', {'changed': True})]):
            with self.assertRaises(ValueError):
                seal_ruleset(rows, evaluator_version='engine-v1', vocabulary_version='tags-v1')
        self.assertEqual(TbRuleset.objects.count(), 1)

    def test_wrong_semantics_or_missing_identity_never_fall_back(self):
        with self.assertRaises(ValueError):
            resolve_content(self.ruleset, 'class:cacador', evaluator_version='new', vocabulary_version='tags-v1')
        with self.assertRaises(TbRulesetContent.DoesNotExist):
            resolve_content(self.ruleset, 'class:missing', evaluator_version='engine-v1', vocabulary_version='tags-v1')

    def test_manifest_prevents_extra_bindings(self):
        other = create_revision('class:other', {})
        with self.assertRaises(DatabaseError), transaction.atomic():
            TbRulesetContent.objects.create(ruleset=self.ruleset, revision=other, identity=other.identity)

    def test_content_sync_preserves_sealed_models(self):
        from home.deploy_sync import MEMORY_MODELS, CONTENT_MODELS
        for name in ('TbContentRevision', 'TbRuleset', 'TbRulesetContent'):
            self.assertIn(name, MEMORY_MODELS)
            self.assertNotIn(name, CONTENT_MODELS)
