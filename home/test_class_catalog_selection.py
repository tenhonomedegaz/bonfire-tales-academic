"""Run: py -m home.test_class_catalog_selection --isolated

In-memory SQLite only: no project settings, .env, migrations or live database.
"""
import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    from django.conf import settings

    settings.configure(
        SECRET_KEY='isolated-class-selection', USE_TZ=True,
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
        BASE_DIR=Path(__file__).resolve().parent.parent,
    )
    import django

    django.setup()

import ast
import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils.text import slugify

from home.class_catalog_api import class_catalog_read_operation
from home.class_publication import (
    CATALOG_ERRORS, publication_preview, resolve_class_catalog,
)
from home.content_versions import create_revision, seal_ruleset
from home.db_access import ApiProblem
from home.hunter_publication_diagnostic import publication_status, resolve_publication
from home.hunter_regularization import REQUIRED_REPLACEMENTS
from home.hunter_rework import catalog as hunter_catalog
from home.hunter_views import laboratory, regularization_preview
from home.models import (
    TbClassPublication, TbClasse, TbClassehabilidade, TbRecursoclasse, TbSubclasse,
)
from home.test_class_catalog_api_read import bootstrap_isolated_schema
from home.versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog, inventory_class


@override_settings(CLASS_CATALOG_RULESETS={}, HUNTER_CREATOR_RULESET_CHECKSUM='')
class ClassCatalogSelectionTests(TestCase):
    def setUp(self):
        self.classes = TbClasse.objects.bulk_create([
            TbClasse(nome='Other class', slug='other-class'),
            TbClasse(nome='Hunter', slug='cacador'),
            TbClasse(nome='Andromeda', slug='andromeda'),
        ])
        self.hunter = self.classes[1]
        self.data = hunter_catalog()
        self.orders = TbSubclasse.objects.bulk_create([
            TbSubclasse(id_classe=self.hunter, nome=row['name'], slug=row['id'])
            for row in self.data['orders']
        ])
        TbClassehabilidade.objects.bulk_create([
            TbClassehabilidade(id_classe=classe, nome='Source feature', niveladquirido=1)
            for classe in self.classes
        ])
        TbRecursoclasse.objects.bulk_create([
            TbRecursoclasse(id_classe=self.hunter, nome='Dado de Cacador', slug='hunter-die')
        ])

    def target(self, classe, *, presentation='catalog', transform=None):
        payload = inventory_class(classe.pk)
        if presentation:
            payload['presentation_source'] = presentation
        for row in payload['collections'][TbClassehabilidade._meta.label_lower]:
            row['nome'] = 'Frozen feature'
        revisions = []
        if classe.pk == self.hunter.pk:
            source = self.data['source_sha256']
            for key in REQUIRED_REPLACEMENTS:
                payload[key] = {'source_sha256': source}
            payload['hunter_mark_replacement'].update(version=1, duration_seconds=3600)
            payload['hunter_order_replacements']['order_ids'] = {
                slugify(row.nome): row.pk for row in self.orders}
            revisions.append(create_revision('hunter-rework', self.data))
        if transform:
            transform(payload)
        revisions.append(create_revision('class-catalog:%s' % classe.pk, payload))
        return seal_ruleset(revisions, evaluator_version=EVALUATOR,
                            vocabulary_version=VOCABULARY)

    def read(self, classe):
        return class_catalog_read_operation(
            {'class_id': classe.pk, 'section': 'habilidade'}, None)

    def lab(self):
        request = RequestFactory().get('/laboratory/')
        request.user = SimpleNamespace(is_authenticated=True)
        with patch('home.hunter_views.render', return_value=HttpResponse()) as render:
            laboratory(request)
        return render.call_args

    def test_same_priority_for_every_class_and_legacy_configured_snapshots(self):
        for classe in self.classes:
            with self.subTest(slug=classe.slug):
                self.assertEqual(resolve_class_catalog(classe).mode, 'source')
                legacy = self.target(classe, presentation=None)
                current = self.target(classe)
                with override_settings(CLASS_CATALOG_RULESETS={classe.slug: legacy.checksum}):
                    selection = resolve_class_catalog(classe)
                    self.assertEqual((selection.mode, selection.ruleset), ('configured', legacy))
                    self.assertIsNone(selection.catalog.presentation_source)
                    self.assertEqual(self.read(classe)['rows'][0]['nome'], 'Frozen feature')
                    TbClassPublication.objects.create(id_classe=classe, ruleset=current)
                    self.assertEqual(self.read(classe)['ruleset_checksum'], current.checksum)
                    self.assertEqual(resolve_class_catalog(classe).mode, 'published')
                # An unrelated/invalid configuration must not override a valid pointer.
                with override_settings(CLASS_CATALOG_RULESETS=[]):
                    self.assertEqual(resolve_class_catalog(classe).ruleset, current)

    def test_invalid_selected_configuration_never_falls_back_to_source(self):
        for classe in self.classes:
            foreign = self.target(self.classes[(self.classes.index(classe) + 1) % 3])
            for value in ('', 'invalid', '0' * 64, 123, None, foreign.checksum):
                with self.subTest(slug=classe.slug, value=value):
                    with override_settings(CLASS_CATALOG_RULESETS={classe.slug: value}):
                        with self.assertRaises(CATALOG_ERRORS):
                            resolve_class_catalog(classe)
                        with self.assertRaises(ApiProblem) as error:
                            self.read(classe)
                        self.assertEqual(error.exception.code, 'invalid_published_catalog')

    def test_invalid_pointer_never_uses_valid_configuration_or_source(self):
        good = self.target(self.hunter)
        bad = self.target(self.hunter, presentation=None)
        TbClassPublication.objects.create(id_classe=self.hunter, ruleset=bad)
        with override_settings(CLASS_CATALOG_RULESETS={self.hunter.slug: good.checksum},
                               HUNTER_CREATOR_RULESET_CHECKSUM=good.checksum):
            with self.assertRaises(ValueError):
                resolve_class_catalog(self.hunter)
            with self.assertRaises(ApiProblem):
                self.read(self.hunter)
            status = publication_status()
            self.assertEqual(status['code'], 'class_snapshot_invalid')
            self.assertIsNone(status['checksum_prefix'])
            self.assertEqual(self.lab().kwargs['status'], 503)

    def test_invalid_mapping_is_not_absence_and_other_class_mapping_is_ignored(self):
        for mapping in (None, [], 'invalid'):
            with override_settings(CLASS_CATALOG_RULESETS=mapping):
                with self.assertRaises(ValueError):
                    resolve_class_catalog(self.hunter)
        with override_settings(CLASS_CATALOG_RULESETS={'another-class': '0' * 64}):
            self.assertEqual(resolve_class_catalog(self.hunter).mode, 'source')

    def test_duplicate_ids_are_rejected_for_every_consumer_and_preflight(self):
        def duplicate(payload):
            rows = payload['collections'][TbSubclasse._meta.label_lower]
            rows.append(copy.deepcopy(rows[0]))
        bad = self.target(self.hunter, transform=duplicate)
        for mode in ('configured', 'published'):
            if mode == 'published':
                TbClassPublication.objects.create(id_classe=self.hunter, ruleset=bad)
            with override_settings(CLASS_CATALOG_RULESETS={self.hunter.slug: bad.checksum}):
                with self.assertRaises(ValueError):
                    resolve_class_catalog(self.hunter)
                with self.assertRaises(ApiProblem):
                    self.read(self.hunter)
                self.assertEqual(publication_status()['code'], 'class_snapshot_invalid')
                self.assertEqual(self.lab().kwargs['status'], 503)
        with self.assertRaises(ValueError):
            publication_preview(self.hunter.pk, bad.checksum, bad.checksum)

    def test_diagnostic_lab_and_api_observe_pointer_change_without_repinning(self):
        configured = self.target(self.hunter, presentation=None)
        first = self.target(self.hunter)
        second = self.target(self.hunter, transform=lambda p: p.update(editorial_note='revision two'))
        pointer = TbClassPublication.objects.create(id_classe=self.hunter, ruleset=first)
        pinned = VersionedClassCatalog(configured, self.hunter.pk)
        before = copy.deepcopy(pinned.collections[TbClassehabilidade][0].tags_json)
        with override_settings(CLASS_CATALOG_RULESETS={self.hunter.slug: configured.checksum}):
            for target in (first, second):
                TbClassPublication.objects.filter(pk=pointer.pk).update(ruleset=target)
                with CaptureQueriesContext(connection) as queries:
                    self.assertEqual(resolve_publication()['ruleset'], target)
                    self.assertEqual(publication_status()['checksum_prefix'], target.checksum[:12])
                    self.assertEqual(self.read(self.hunter)['ruleset_checksum'], target.checksum)
                    self.assertEqual(self.lab().args[2]['ruleset_checksum'], target.checksum)
                self.assertTrue(all(q['sql'].lstrip().upper().startswith('SELECT') for q in queries))
        self.assertEqual(pinned.collections[TbClassehabilidade][0].tags_json, before)
        self.assertEqual(VersionedClassCatalog(configured, self.hunter.pk).contracts, {})

    def test_configured_legacy_remains_readable_in_diagnostic_and_lab(self):
        legacy = self.target(self.hunter, presentation=None)
        with override_settings(CLASS_CATALOG_RULESETS={self.hunter.slug: legacy.checksum}):
            resolved = resolve_publication()
            self.assertEqual((resolved['mode'], resolved['ruleset']), ('configured', legacy))
            self.assertEqual(publication_status()['code'], 'ok')
            self.assertEqual(self.lab().args[2]['ruleset_checksum'], legacy.checksum)

    def test_source_lab_is_available_but_not_reported_as_reviewed_publication(self):
        self.assertEqual(self.lab().args[2]['ruleset_checksum'], '')
        self.assertEqual(publication_status()['code'], 'config_missing')

    def test_regularization_uses_general_mapping_without_implicit_application(self):
        legacy = self.target(self.hunter, presentation=None)
        person = SimpleNamespace(pk=42)
        pc = SimpleNamespace(id_classe=self.hunter)
        request = RequestFactory().get('/regularization/')
        request.user = SimpleNamespace(pk=7, is_authenticated=True)
        with override_settings(CLASS_CATALOG_RULESETS={self.hunter.slug: legacy.checksum}):
            with patch('home.hunter_views.get_object_or_404', side_effect=[person, pc]), \
                    patch('home.hunter_regularization.preview_legacy_hunter', return_value={}) as preview, \
                    patch('home.hunter_regularization.apply_regularization') as apply, \
                    patch('home.hunter_views.render', return_value=HttpResponse()):
                regularization_preview(request, person.pk)
        self.assertEqual(preview.call_args.args[2], legacy)
        apply.assert_not_called()

    def test_database_failure_during_initial_identity_read_is_sanitized(self):
        with patch('home.models.TbClasse.objects.get', side_effect=DatabaseError('private DB details')):
            self.assertEqual(publication_status(), {
                'schema': 1, 'published': False, 'code': 'database_unavailable',
                'checksum_prefix': None})

    def test_settings_alias_is_preserved_without_overriding_explicit_mapping(self):
        # Execute only the catalog configuration block, never settings/.env startup.
        path = Path(__file__).resolve().parent.parent / 'bonfire/settings.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        start = next(i for i, node in enumerate(tree.body)
                     if isinstance(node, ast.Assign)
                     and any(isinstance(n, ast.Name) and n.id == 'HUNTER_CREATOR_RULESET_CHECKSUM'
                             for n in node.targets))
        block = ast.Module(body=tree.body[start:start + 4], type_ignores=[])
        for mapping, expected in (({}, 'a' * 64), ({'cacador': 'b' * 64}, 'b' * 64)):
            namespace = {'os': os, 'json': json, 'ImproperlyConfigured': ImproperlyConfigured}
            with patch.dict(os.environ, {'HUNTER_CREATOR_RULESET_CHECKSUM': 'a' * 64,
                                        'CLASS_CATALOG_RULESETS': json.dumps(mapping)}):
                exec(compile(block, str(path), 'exec'), namespace)
            self.assertEqual(namespace['HUNTER_CREATOR_RULESET_CHECKSUM'], 'a' * 64)
            self.assertEqual(namespace['CLASS_CATALOG_RULESETS']['cacador'], expected)


if ISOLATED:
    bootstrap_isolated_schema()
    unittest.main(argv=[sys.argv[0]], verbosity=2)
