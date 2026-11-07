import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .content_versions import create_revision, digest, seal_ruleset
from .models import TbClasse, TbContentRevision, TbRuleset
from .versioned_classes import EVALUATOR, VOCABULARY, inventory_class


class HunterMulticlassRulesetTests(TestCase):
    def setUp(self):
        self.hunter = TbClasse.objects.create(nome='Caçador', slug='cacador')
        self.other = TbClasse.objects.create(nome='Outra Classe', slug='outra-classe')
        self.base = seal_ruleset([
            create_revision('hunter-rework', {'schema': 1}),
            create_revision(f'class-catalog:{self.hunter.pk}', inventory_class(self.hunter.pk)),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        identity = f'class-catalog:{self.other.pk}'
        expected_revision = digest({'identity': identity,
                                    'payload': inventory_class(self.other.pk), 'dependencies': []})
        manifest = {**self.base.manifest, identity: expected_revision}
        self.expected = digest({'manifest': manifest, 'evaluator': EVALUATOR,
                                'vocabulary': VOCABULARY})

    def run_command(self, *, checksum=None, apply=False):
        output = StringIO()
        args = ['--base-checksum', self.base.checksum,
                '--expected-checksum', checksum or self.expected]
        if apply:
            args.append('--apply')
        call_command('compose_hunter_multiclass_ruleset', *args, stdout=output)
        return json.loads(output.getvalue())

    def test_dry_run_apply_and_reexecution_preserve_content_identity(self):
        revisions_before = TbContentRevision.objects.count()
        rulesets_before = TbRuleset.objects.count()
        dry = self.run_command()
        self.assertFalse(dry['persisted'])
        self.assertEqual((TbContentRevision.objects.count(), TbRuleset.objects.count()),
                         (revisions_before, rulesets_before))
        first = self.run_command(apply=True)
        second = self.run_command(apply=True)
        self.assertEqual(first['checksum'], self.expected)
        self.assertEqual(first['ruleset_id'], second['ruleset_id'])
        self.assertEqual(first['entries'], 3)
        self.assertEqual(first['characters_converted'], 0)
        self.assertEqual(TbContentRevision.objects.count(), revisions_before + 1)
        self.assertEqual(TbRuleset.objects.count(), rulesets_before + 1)

    def test_unexpected_checksum_rolls_back_all_additions(self):
        revisions_before = TbContentRevision.objects.count()
        rulesets_before = TbRuleset.objects.count()
        with self.assertRaises(CommandError):
            self.run_command(checksum='0' * 64, apply=True)
        self.assertEqual((TbContentRevision.objects.count(), TbRuleset.objects.count()),
                         (revisions_before, rulesets_before))
