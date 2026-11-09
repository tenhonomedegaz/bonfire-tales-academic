import json
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from home import test_versioned_derive as fixtures
from home.class_revision_editor import create_class_revision
from home.hunter_rework import catalog
from home.versioned_classes import VersionedClassCatalog
from home.models import TbClassehabilidade


class HunterSecretReferenceTests(TestCase):
    def test_editorial_revision_contains_current_secrets_without_changing_mechanics(self):
        package = json.loads((Path(__file__).parent / 'content_packages' /
            'hunter_secrets_reference_20261109.json').read_text(encoding='utf-8'))
        self.assertEqual(len(package['changes']), 1)
        change = package['changes'][0]
        self.assertEqual(change['model'], 'home.tbclassehabilidade')
        self.assertEqual(change['action'], 'update')
        self.assertEqual(set(change['fields']), {'descricao'})
        markdown = change['fields']['descricao']
        data = catalog()
        self.assertEqual(markdown.count('::click '), len(data['secrets']))
        for secret in data['secrets']:
            self.assertEqual(markdown.count('::click ' + secret['name'] + '\n'), 1)
            self.assertIn(secret['text'].replace('Aprimoramento:',
                '\n\n**Aprimoramento:**'), markdown)
        for line in {s['line'] for s in data['secrets']}:
            self.assertIn('## ' + line + '\n', markdown)
        self.assertNotIn('::options=', markdown)

        fixtures.VersionedDeriveTests.setUp(self)
        original = self.feature.descricao
        mapped = dict(change, pk=self.feature.pk)
        revised = create_class_revision(self.ruleset.checksum, self.cl.pk, [mapped],
                                         presentation_source='catalog')
        self.feature.refresh_from_db()
        self.assertEqual(self.feature.descricao, original)
        old = VersionedClassCatalog(self.ruleset, self.cl.pk)
        new = VersionedClassCatalog(revised, self.cl.pk)
        before = old.collections[TbClassehabilidade][0]
        after = new.collections[TbClassehabilidade][0]
        self.assertEqual(after.tags_json, before.tags_json)
        self.assertEqual(after.descricao, markdown)
        with override_settings(CLASS_CATALOG_RULESETS={self.cl.slug: revised.checksum}):
            response = self.client.get(reverse('classe_detail', args=[self.cl.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '::click Granada de Luz')
        self.assertContains(response, '**Aprimoramento:**')
