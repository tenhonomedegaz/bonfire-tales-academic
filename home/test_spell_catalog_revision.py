"""Bounded revision tests; --isolated bootstraps only in-memory SQLite."""
import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    from django.conf import settings
    settings.configure(SECRET_KEY='isolated-spell-revision', USE_TZ=True,
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'], MIDDLEWARE=[],
        BASE_DIR=Path(__file__).resolve().parents[1], DEFAULT_AUTO_FIELD='django.db.models.AutoField')
    import django
    django.setup()

import json
import unittest
from uuid import uuid4
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import path
from home import db_access_api as api
from home.content_versions import create_revision, resolve_content, seal_ruleset
from home.db_access import ApiProblem, MODEL_ALLOWLIST, row_version
from home.db_access_models import ManagedApiKey
from home.models import TbContentRevision, TbMagia, TbRuleset, TbClassPublication
from home.spell_catalog_revision import spell_catalog_revision_operation, spell_catalog_revision_preview_operation
from home.test_class_catalog_api_read import bootstrap_isolated_schema
from home.versioned_classes import EVALUATOR, VOCABULARY, _fields
from home.versioned_library import snapshot_library
from home.tag_engine.library import Library

urlpatterns = [path('api/db/v1/operations/<slug:handler_name>/', api.db_operation)]


@override_settings(ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'])
class SpellCatalogRevisionTests(TestCase):
    def setUp(self):
        self.old, self.new = TbMagia.objects.bulk_create([
            TbMagia(nome='Old', slug='old', nivel=1),
            TbMagia(nome='New', nome_ingles='New', slug='new', nivel=2, tags_json=[])])
        self.original = {'schema': 1, 'spells': [_fields(self.old)], 'class_scopes': {'any': 'Any'}}
        spell = create_revision('spell-catalog', self.original)
        other = create_revision('unrelated', {'preserved': True})
        self.vocabulary = snapshot_library(raw=Library(prefer_db=False).raw)
        self.base = seal_ruleset([spell, other, self.vocabulary], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.secret = ManagedApiKey.new_secret()
        self.key = ManagedApiKey.objects.create(name='Isolated revision', prefix=self.secret[:16],
            secret_hash=ManagedApiKey.digest(self.secret), scopes=['read', 'write'])
        self.payload = {'base_version': self.base.checksum, 'spells': [self.entry(self.new)]}

    def entry(self, spell):
        return {'id': spell.pk, 'version': row_version(spell, MODEL_ALLOWLIST['magia'])}

    def call(self, payload=None, *, apply=False):
        handler = spell_catalog_revision_operation if apply else spell_catalog_revision_preview_operation
        return handler(self.payload if payload is None else payload, self.key)

    def content(self, checksum):
        target = TbRuleset.objects.get(checksum=checksum)
        return resolve_content(target, 'spell-catalog', evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)

    def assert_error(self, status, code, payload=None, *, apply=False):
        with self.assertRaises(ApiProblem) as raised:
            self.call(payload, apply=apply)
        self.assertEqual((raised.exception.status, raised.exception.code), (status, code))

    def test_preview_has_no_writes_and_apply_preserves_base_and_other_content(self):
        before = self.base.manifest.copy()
        with CaptureQueriesContext(connection) as queries:
            preview = self.call()
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in queries))
        self.assertFalse(preview['activated'])
        target = self.call(apply=True)
        self.assertEqual(target, preview)
        self.assertEqual(self.content(self.base.checksum), self.original)
        self.assertEqual(self.content(target['ruleset_checksum'])['spells'], [_fields(self.old), _fields(self.new)])
        created = TbRuleset.objects.get(checksum=target['ruleset_checksum'])
        self.assertEqual(created.manifest['unrelated'], before['unrelated'])
        self.assertEqual(TbClassPublication.objects.count(), 0)
        self.assertEqual(TbMagia.objects.count(), 2)

    def test_repeated_add_to_target_is_unchanged_and_returns_existing_checksum(self):
        result = self.call(apply=True)
        count = TbContentRevision.objects.count(), TbRuleset.objects.count()
        payload = {**self.payload, 'base_version': result['ruleset_checksum']}
        repeated = self.call(payload, apply=True)
        self.assertEqual(repeated['ruleset_checksum'], result['ruleset_checksum'])
        self.assertEqual(repeated['added'], 0)
        self.assertEqual(count, (TbContentRevision.objects.count(), TbRuleset.objects.count()))

    def test_source_version_must_match(self):
        TbMagia.objects.filter(pk=self.new.pk).update(nome='Concurrent edit')
        self.assert_error(412, 'spell_source_changed', apply=True)
        self.assertEqual(TbRuleset.objects.count(), 1)

    def test_added_spell_must_pass_the_base_vocabulary_validator(self):
        self.new.tags_json = ['instant{broken']
        self.new.save(update_fields=['tags_json'])
        self.assert_error(400, 'invalid_pinned_spell_tags',
                          {**self.payload, 'spells': [self.entry(self.new)]}, apply=True)
        self.assertEqual(TbRuleset.objects.count(), 1)

    def test_new_source_lists_and_size_are_bounded(self):
        self.new.tags_json = {'invalid': 'shape'}
        self.new.save(update_fields=['tags_json'])
        self.assert_error(400, 'invalid_source_spell',
                          {**self.payload, 'spells': [self.entry(self.new)]}, apply=True)
        self.new.tags_json = []
        self.new.descricao = 'x' * 65536
        self.new.save(update_fields=['tags_json', 'descricao'])
        self.assert_error(413, 'spell_source_too_large',
                          {**self.payload, 'spells': [self.entry(self.new)]}, apply=True)

    def test_existing_pk_cannot_be_overwritten(self):
        self.old.nome = 'Changed source'
        self.old.save(update_fields=['nome'])
        self.assert_error(409, 'spell_identity_conflict',
                          {**self.payload, 'spells': [self.entry(self.old)]}, apply=True)
        self.assertEqual(self.content(self.base.checksum), self.original)

    def test_existing_slug_cannot_be_rebound_to_another_pk(self):
        self.old.slug = 'old-renamed'
        self.old.save(update_fields=['slug'])
        self.new.slug = 'old'
        self.new.save(update_fields=['slug'])
        self.assert_error(409, 'spell_identity_conflict',
                          {**self.payload, 'spells': [self.entry(self.new)]}, apply=True)

    def test_invalid_payload_and_duplicate_or_too_many_spells_are_rejected(self):
        bad = [None, {}, {**self.payload, 'extra': 1}, {**self.payload, 'base_version': 'bad'},
               {**self.payload, 'spells': []}, {**self.payload, 'spells': [None]},
               {**self.payload, 'spells': [{'id': True, 'version': '0'*64}]},
               {**self.payload, 'spells': [self.entry(self.new)] * 2},
               {**self.payload, 'spells': [{'id': n+1, 'version': '0'*64} for n in range(11)]}]
        for payload in bad:
            with self.subTest(payload=payload):
                # None is the helper's default sentinel, use the handler directly.
                if payload is None:
                    with self.assertRaises(ApiProblem):
                        spell_catalog_revision_preview_operation(payload, self.key)
                else:
                    self.assert_error(400, 'invalid_spell_revision', payload)

    def test_missing_base_or_source_is_explicit_and_never_fallback(self):
        self.assert_error(404, 'base_not_found', {**self.payload, 'base_version': '0'*64})
        self.assert_error(404, 'spell_not_found',
                          {**self.payload, 'spells': [{'id': 999999, 'version': '0'*64}]})

    def test_malformed_selected_catalog_is_refused(self):
        broken = create_revision('spell-catalog', {**self.original, 'spells': [{'id_magia': 1}]})
        target = seal_ruleset([broken], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.assert_error(409, 'invalid_spell_catalog', {**self.payload, 'base_version': target.checksum})

    def test_partial_failure_creates_no_revision(self):
        self.old.nome = 'Different'
        self.old.save(update_fields=['nome'])
        before = TbRuleset.objects.count(), TbContentRevision.objects.count()
        self.assert_error(409, 'spell_identity_conflict',
                          {**self.payload, 'spells': [self.entry(self.new), self.entry(self.old)]}, apply=True)
        self.assertEqual(before, (TbRuleset.objects.count(), TbContentRevision.objects.count()))

    def test_http_scopes_idempotency_and_no_activation(self):
        headers = {'HTTP_AUTHORIZATION': 'Bearer '+self.secret, 'HTTP_IDEMPOTENCY_KEY': str(uuid4()), 'secure': True}
        url = '/api/db/v1/operations/spell-catalog-revision/'
        response = self.client.post(url, json.dumps(self.payload), content_type='application/json', **headers)
        self.assertEqual(response.status_code, 200, response.content)
        counts = TbRuleset.objects.count(), TbContentRevision.objects.count()
        replay = self.client.post(url, json.dumps(self.payload), content_type='application/json', **headers)
        self.assertEqual(replay.json(), response.json())
        self.assertEqual(counts, (TbRuleset.objects.count(), TbContentRevision.objects.count()))
        self.assertFalse(response.json()['activated'])
        self.key.scopes = ['read']
        self.key.save(update_fields=['scopes'])
        headers['HTTP_IDEMPOTENCY_KEY'] = str(uuid4())
        refused = self.client.post(url, json.dumps(self.payload), content_type='application/json', **headers)
        self.assertEqual(refused.status_code, 403)
        preview = self.client.post(url.replace('revision/', 'revision-preview/'), json.dumps(self.payload),
                                   content_type='application/json', **headers)
        self.assertEqual(preview.status_code, 200, preview.content)


if ISOLATED:
    bootstrap_isolated_schema()
    with connection.schema_editor() as editor:
        editor.create_model(TbMagia)
    unittest.main(argv=[sys.argv[0]], verbosity=2)
