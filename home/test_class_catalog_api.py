"""Run: py -m home.test_class_catalog_api --isolated

Explicit in-memory SQLite only: no bonfire.settings, .env, migrations or live DB.
Fixtures reuse the existing isolated catalog API setup, not production fixtures.
"""
import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    from django.conf import settings

    settings.configure(
        SECRET_KEY='isolated-published-class-read-tests', USE_TZ=True,
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'], MIDDLEWARE=[],
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
        BASE_DIR=Path(__file__).resolve().parent.parent,
    )
    import django

    django.setup()

import copy
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import path

from home import db_access_api as api
from home.class_catalog_api import (
    DEFAULT_FIELDS, MAX_JSON_DEPTH, MAX_JSON_ITEMS, READABLE_FIELDS,
    SECTION_MODELS, class_catalog_read_operation,
)
from home.class_publication import published_catalog
from home.content_versions import create_revision, resolve_content, seal_ruleset
from home.db_access import ApiProblem, MAX_BODY_BYTES, MODEL_ALLOWLIST
from home.db_access_models import DbAccessAudit, DbAccessIdempotency
from home.models import (
    TbClassPublication, TbClassPublicationLog, TbClasse, TbClassehabilidade,
    TbContentRevision, TbRecursoclasse, TbRuleset, TbRulesetContent, TbSubclasse,
)
from home.test_class_catalog_api_read import ClassCatalogApiFixture, bootstrap_isolated_schema
from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class, seal_class_snapshot


urlpatterns = [
    path('api/db/v1/schema/', api.db_schema),
    path('api/db/v1/operations/<slug:handler_name>/', api.db_operation),
    path('api/db/v1/<str:model_name>/<str:object_pk>/', api.db_object),
]
OPERATION_URL = '/api/db/v1/operations/class-catalog-read/'


@override_settings(ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'])
class ClassCatalogReadTests(ClassCatalogApiFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.resource, self.base_resource, self.other_resource = TbRecursoclasse.objects.bulk_create([
            TbRecursoclasse(id_classe=self.classe, id_subclasse=self.subclasse,
                           nome='Charges', slug='charges', nivel=3, valor='2',
                           valores_json={'3': '2', '7': '3'}, tipo='consumable', reset='long-rest'),
            TbRecursoclasse(id_classe=self.classe, nome='Base resource', slug='base', nivel=None),
            TbRecursoclasse(id_classe=self.other_classe, nome='Other resource', slug='other'),
        ])

    def request(self, payload=None, *, key=None, headers=None):
        if payload is None:
            payload = {'class_id': self.classe.pk, 'section': 'habilidade'}
        return self.client.post(OPERATION_URL, data=json.dumps(payload),
            content_type='application/json', **dict(self.headers if headers is None else headers,
                                                   HTTP_IDEMPOTENCY_KEY=key or str(uuid4())))

    def read(self, section='habilidade', **options):
        return class_catalog_read_operation(
            dict(class_id=self.classe.pk, section=section, **options), self.key)

    def publish(self, transform=None):
        payload = inventory_class(self.classe.pk)
        payload['presentation_source'] = 'catalog'
        for model in SECTION_MODELS.values():
            for row in payload['collections'][model._meta.label_lower]:
                row['nome'] = 'Pinned ' + row['nome']
                if 'tags_json' in row:
                    row['tags_json'] = ['source:pinned']
                if 'descricao' in row:
                    row['descricao'] = 'Published **description**\nNot the mutable source.'
        if transform:
            transform(payload)
        revision = create_revision('class-catalog:%s' % self.classe.pk, payload)
        # Another class and unrelated data in this ruleset must never be emitted.
        other = create_revision('class-catalog:%s' % self.other_classe.pk,
                                inventory_class(self.other_classe.pk))
        unrelated = create_revision('unrelated-test', {'private': 'DO-NOT-EMIT'})
        ruleset = seal_ruleset([revision, other, unrelated], evaluator_version=EVALUATOR,
                              vocabulary_version=VOCABULARY)
        TbClassPublication.objects.create(id_classe=self.classe, ruleset=ruleset)
        return ruleset

    def assert_problem(self, response, status, code):
        self.assertEqual(response.status_code, status, response.content)
        self.assertEqual(response.json()['error']['code'], code)

    def test_configured_snapshot_without_publication_is_read_not_live_source(self):
        ruleset = self.publish()
        TbClassPublication.objects.filter(id_classe=self.classe).delete()
        TbClassehabilidade.objects.filter(pk=self.ability.pk).update(nome='Unpublished source edit')
        with override_settings(CLASS_CATALOG_RULESETS={self.classe.slug: ruleset.checksum}):
            result = self.read()
        self.assertEqual(result['mode'], 'configured')
        self.assertEqual(result['ruleset_checksum'], ruleset.checksum)
        self.assertTrue(result['rows'][0]['nome'].startswith('Pinned '))
        self.assertEqual(TbClassPublication.objects.count(), 0)

    def test_publication_precedes_configured_checksum_and_never_falls_back(self):
        ruleset = self.publish()
        with override_settings(CLASS_CATALOG_RULESETS={self.classe.slug: '0' * 64}):
            self.assertEqual(self.read()['ruleset_checksum'], ruleset.checksum)
        with patch('home.class_catalog_api.published_catalog', side_effect=ValueError('invalid')):
            with override_settings(CLASS_CATALOG_RULESETS={self.classe.slug: ruleset.checksum}):
                self.assert_problem(self.request(), 409, 'invalid_published_catalog')

    def test_invalid_missing_or_foreign_configured_snapshot_is_fail_closed(self):
        other = seal_class_snapshot(self.other_classe.pk)
        for value in ('', 'bad', '0' * 64, other.checksum, 123):
            with self.subTest(value=value):
                with override_settings(CLASS_CATALOG_RULESETS={self.classe.slug: value}):
                    self.assert_problem(self.request(), 409, 'invalid_published_catalog')

    def test_mapping_for_another_class_does_not_select_a_snapshot(self):
        with override_settings(CLASS_CATALOG_RULESETS={self.other_classe.slug: '0' * 64}):
            self.assertEqual(self.read()['mode'], 'source')

    def test_schema_registration_read_scope_and_no_base_version(self):
        response = self.client.get('/api/db/v1/schema/', **self.headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['operations']['class-catalog-read'],
                         {'scope': 'read', 'base_version_required': False})
        response = self.request()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn('version', response.json())
        self.assertNotIn('ETag', response)

    def test_source_all_sections_preserve_ids_fields_and_nullable_parents(self):
        expected_ids = {
            'classe': [self.classe.pk], 'subclasse': [self.subclasse.pk],
            'habilidade': [self.ability.pk, self.later.pk, self.base.pk],
            'recurso': [self.resource.pk, self.base_resource.pk],
        }
        for section, ids in expected_ids.items():
            with self.subTest(section=section):
                response = self.request({'class_id': self.classe.pk, 'section': section})
                self.assertEqual(response.status_code, 200, response.content)
                body = response.json()
                self.assertEqual(set(body), {'mode', 'ruleset_checksum', 'class_id', 'section',
                                             'total', 'offset', 'limit', 'rows'})
                self.assertEqual((body['mode'], body['ruleset_checksum']), ('source', None))
                self.assertEqual((body['total'], body['offset'], body['limit']), (len(ids), 0, 25))
                pk = SECTION_MODELS[section]._meta.pk.name
                self.assertEqual([row[pk] for row in body['rows']], sorted(ids))
                for row in body['rows']:
                    self.assertEqual(set(row), set(DEFAULT_FIELDS[section]))
                    self.assertEqual(row['id_classe'], self.classe.pk)
                    self.assertNotIn('descricao', row)
        base = next(row for row in self.read()['rows'] if row['id_habilidade'] == self.base.pk)
        self.assertIsNone(base['id_subclasse'])
        self.assertIsNone(base['nome_ingles'])
        self.assertEqual(base['tags_json'], [])
        resource = self.read('recurso')['rows'][1]
        self.assertIsNone(resource['id_subclasse'])
        self.assertIsNone(resource['nivel'])

    def test_fields_and_scalar_fk_values_match_existing_get_api(self):
        for section, model_name, row in (
            ('classe', 'classe', self.classe), ('subclasse', 'subclasse', self.subclasse),
            ('habilidade', 'classe_habilidade', self.ability),
        ):
            fields = list(MODEL_ALLOWLIST[model_name].readable)
            response = self.client.get('/api/db/v1/%s/%s/' % (model_name, row.pk),
                                       {'fields': ','.join(fields)}, **self.headers)
            self.assertEqual(response.status_code, 200, response.content)
            projected = self.read(section, fields=fields)['rows'][0]
            self.assertEqual(projected, response.json()['item'])
            for name in ('id_classe', 'id_subclasse'):
                if name in projected and projected[name] is not None:
                    self.assertIs(type(projected[name]), int)

    def test_source_projection_does_not_fetch_excluded_description(self):
        with CaptureQueriesContext(connection) as queries:
            self.read(fields=['id_habilidade', 'tags_json'])
        ability_sql = [q['sql'] for q in queries if 'TB_ClasseHabilidade' in q['sql']]
        self.assertTrue(ability_sql)
        self.assertFalse(any('Descricao' in sql for sql in ability_sql))

    def test_published_all_sections_ignore_live_edits_and_exclude_other_content(self):
        ruleset = self.publish()
        TbClasse.objects.filter(pk=self.classe.pk).update(nome='Live class', tags_json=['source:live'])
        TbSubclasse.objects.filter(pk=self.subclasse.pk).update(nome='Live subclass')
        TbClassehabilidade.objects.filter(id_classe=self.classe).update(
            nome='Live ability', descricao='Live description', tags_json=['source:live'])
        TbRecursoclasse.objects.filter(id_classe=self.classe).update(nome='Live resource', valor='99')
        for section, model in SECTION_MODELS.items():
            with self.subTest(section=section):
                response = self.request({'class_id': self.classe.pk, 'section': section,
                                         'fields': list(READABLE_FIELDS[section])})
                self.assertEqual(response.status_code, 200, response.content)
                body = response.json()
                self.assertEqual((body['mode'], body['ruleset_checksum']), ('published', ruleset.checksum))
                self.assertEqual(body['total'], len(self.read(section)['rows']))
                self.assertTrue(all(row['nome'].startswith('Pinned ') for row in body['rows']))
                self.assertTrue(all(row['id_classe'] == self.classe.pk for row in body['rows']))
                self.assertNotIn('manifest', body)
                self.assertNotIn('DO-NOT-EMIT', response.content.decode())
                if section in ('classe', 'habilidade'):
                    self.assertEqual(body['rows'][0]['tags_json'], ['source:pinned'])
                if section == 'habilidade':
                    self.assertEqual(body['rows'][0]['descricao'],
                                     'Published **description**\nNot the mutable source.')
                if section == 'recurso':
                    self.assertEqual(body['rows'][0]['valor'], '2')

    def test_unpublished_other_class_uses_only_its_own_source(self):
        self.publish()
        response = self.request({'class_id': self.other_classe.pk, 'section': 'habilidade'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['mode'], 'source')
        self.assertIsNone(response.json()['ruleset_checksum'])
        self.assertEqual([row['id_habilidade'] for row in response.json()['rows']], [self.other_ability.pk])

    def test_pagination_is_stable_in_both_modes_and_empty_beyond_total(self):
        for mode in ('source', 'published'):
            if mode == 'published':
                self.publish()
            body = self.read(offset=1, limit=1, fields=['id_habilidade'])
            self.assertEqual((body['mode'], body['offset'], body['limit'], body['total']), (mode, 1, 1, 3))
            self.assertEqual(body['rows'], [{'id_habilidade': self.later.pk}])
            self.assertEqual(self.read(offset=100, limit=100)['rows'], [])

    def test_validation_rejects_unknown_missing_wrong_typed_and_cross_section_fields(self):
        invalid = [
            ({}, 'invalid_class_catalog'),
            ({'class_id': True, 'section': 'classe'}, 'invalid_class_catalog'),
            ({'class_id': 1.0, 'section': 'classe'}, 'invalid_class_catalog'),
            ({'class_id': '1', 'section': 'classe'}, 'invalid_class_catalog'),
            ({'class_id': 0, 'section': 'classe'}, 'invalid_class_catalog'),
        ]
        base = {'class_id': self.classe.pk, 'section': 'habilidade'}
        invalid += [(dict(base, section=value), 'invalid_class_catalog')
                    for value in ('magia', 'classe_habilidade', None, [], 1)]
        invalid += [(dict(base, **{name: value}), 'invalid_class_catalog')
                    for name, value in (('base_version', 'x'), ('ruleset', 1), ('filter', {}))]
        invalid += [(dict(base, **{name: value}), 'invalid_pagination')
                    for name, values in (('offset', (-1, True, 1.0, '0', None)),
                                         ('limit', (0, 101, True, 1.0, '1', None)))
                    for value in values]
        invalid += [(dict(base, fields=value), 'invalid_fields') for value in (
            [], None, 'nome', {}, ['nome', 'nome'], [None], [[]], [1],
            ['id_classe_id'], ['id_subclasse_id'], ['nome__icontains'],
            ['ruleset'], ['payload'], ['valores_json'],
        )]
        for payload, code in invalid:
            with self.subTest(payload=payload):
                self.assert_problem(self.request(payload), 400, code)
        self.assertEqual(DbAccessIdempotency.objects.count(), 0)

    def test_missing_class_is_404(self):
        self.assert_problem(self.request({'class_id': 2147483647, 'section': 'classe'}),
                            404, 'class_not_found')

    def test_common_auth_https_methods_and_idempotency_requirements(self):
        self.assert_problem(self.request(headers={'secure': True}), 401, 'unauthorized')
        self.assert_problem(self.request(headers=dict(self.headers, secure=False)), 400, 'https_required')
        for scopes in ([], ['write'], ['publish'], ['write', 'publish']):
            self.key.scopes = scopes
            self.key.save(update_fields=['scopes'])
            self.assert_problem(self.request(), 403, 'insufficient_scope')
        self.key.scopes = ['read']
        self.key.save(update_fields=['scopes'])
        response = self.client.post(OPERATION_URL, data='{}', content_type='application/json', **self.headers)
        self.assert_problem(response, 400, 'idempotency_required')
        self.assertEqual(self.client.get(OPERATION_URL, **self.headers).status_code, 405)

    def test_common_audit_replay_and_conflict_preserve_original_read(self):
        first = self.request(key='same-read')
        self.assertEqual(first.status_code, 200, first.content)
        TbClassehabilidade.objects.filter(pk=self.ability.pk).update(nome='Changed after read')
        replay = self.request(key='same-read')
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(DbAccessIdempotency.objects.count(), 1)
        conflict = self.request({'class_id': self.classe.pk, 'section': 'classe'}, key='same-read')
        self.assert_problem(conflict, 409, 'idempotency_conflict')
        self.assertEqual(list(DbAccessAudit.objects.order_by('pk').values_list('action', 'status_code')),
                         [('operation', 200), ('operation_replay', 200), ('operation', 409)])

    def test_successful_direct_reads_never_write_or_mutate_snapshot_objects(self):
        self.assert_no_catalog_writes()
        ruleset = self.publish()
        _, catalog = published_catalog(self.classe)
        objects = [row for rows in catalog.collections.values() for row in rows]
        before = copy.deepcopy([{f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields}
                                for row in objects])
        with patch('home.class_catalog_api.published_catalog', return_value=(ruleset, catalog)):
            self.assert_no_catalog_writes()
        after = [{f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields} for row in objects]
        self.assertEqual(before, after)
        identity = 'class-catalog:%s' % self.classe.pk
        original = resolve_content(ruleset, identity, evaluator_version=EVALUATOR,
                                   vocabulary_version=VOCABULARY)
        self.assertEqual(original['collections'][TbClassehabilidade._meta.label_lower][0]['tags_json'],
                         ['source:pinned'])

    def assert_no_catalog_writes(self):
        with CaptureQueriesContext(connection) as queries:
            for section, fields in READABLE_FIELDS.items():
                self.read(section, fields=list(fields))
        self.assertFalse([q['sql'] for q in queries
                          if q['sql'].lstrip().split()[0].upper() not in ('SELECT', 'SAVEPOINT', 'RELEASE')])

    def test_api_writes_only_shared_audit_rate_and_idempotency_state(self):
        self.publish()
        models = (TbClasse, TbSubclasse, TbClassehabilidade, TbRecursoclasse,
                  TbContentRevision, TbRuleset, TbRulesetContent, TbClassPublication, TbClassPublicationLog)
        before = {model: list(model.objects.order_by('pk').values()) for model in models}
        with CaptureQueriesContext(connection) as queries:
            response = self.request()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(before, {model: list(model.objects.order_by('pk').values()) for model in models})
        for query in queries:
            sql = query['sql']
            if sql.lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE'):
                self.assertTrue(any(table in sql for table in (
                    'home_managed_api_key', 'home_db_access_audit', 'home_db_access_idempotency')), sql)

    def test_legacy_or_corrupted_publication_is_never_source_fallback(self):
        ruleset = seal_class_snapshot(self.classe.pk)  # No catalog presentation marker.
        TbClassPublication.objects.create(id_classe=self.classe, ruleset=ruleset)
        self.assert_problem(self.request(), 409, 'invalid_published_catalog')
        TbRuleset.objects.filter(pk=ruleset.pk).update(checksum='0' * 64)
        self.assert_problem(self.request(), 409, 'invalid_published_catalog')
        self.assertEqual(DbAccessIdempotency.objects.count(), 0)

    def test_missing_published_revision_binding_is_fail_closed(self):
        ruleset = self.publish()
        TbRulesetContent.objects.filter(ruleset=ruleset, identity='class-catalog:%s' % self.classe.pk).delete()
        self.assert_problem(self.request(), 409, 'invalid_published_catalog')

    def test_well_sealed_but_malformed_published_snapshot_is_fail_closed(self):
        self.publish(lambda payload: payload['collections'].pop(TbRecursoclasse._meta.label_lower))
        self.assert_problem(self.request(), 409, 'invalid_published_catalog')

    def test_foreign_class_rows_in_published_snapshot_are_fail_closed(self):
        def foreign(payload):
            payload['collections'][TbClassehabilidade._meta.label_lower][0]['id_classe_id'] = self.other_classe.pk
        self.publish(foreign)
        self.assert_problem(self.request(), 409, 'invalid_published_catalog')

    def test_unselected_large_description_is_safe_but_selected_response_is_rejected(self):
        TbClassehabilidade.objects.filter(pk=self.ability.pk).update(descricao='x' * (MAX_BODY_BYTES + 1))
        self.assertEqual(self.request().status_code, 200)
        for mode in ('source', 'published'):
            if mode == 'published':
                def large(payload):
                    payload['collections'][TbClassehabilidade._meta.label_lower][0]['descricao'] = 'x' * (MAX_BODY_BYTES + 1)
                self.publish(large)
            response = self.request({'class_id': self.classe.pk, 'section': 'habilidade',
                                     'limit': 1, 'fields': ['descricao']})
            self.assert_problem(response, 413, 'class_catalog_result_too_large')
            self.assertIn('limit', response.json()['error']['message'])
            self.assertEqual(response.json()['error']['details']['max_bytes'], MAX_BODY_BYTES)
            self.assertEqual(self.request().status_code, 200)

    def test_actual_utf8_envelope_size_is_enforced_without_truncation(self):
        # The text alone fits; UTF-8 plus JSON escaping and envelope do not.
        text = '\u00e9"' * (MAX_BODY_BYTES // 4)
        TbClassehabilidade.objects.filter(pk=self.ability.pk).update(descricao=text)
        response = self.request({'class_id': self.classe.pk, 'section': 'habilidade',
                                 'limit': 1, 'fields': ['descricao']})
        self.assert_problem(response, 413, 'class_catalog_result_too_large')
        smaller = self.request({'class_id': self.classe.pk, 'section': 'habilidade',
                                'offset': 1, 'limit': 1, 'fields': ['descricao']})
        self.assertEqual(smaller.status_code, 200, smaller.content)
        self.assertEqual(smaller.json()['rows'], [{'descricao': 'Later'}])

    def test_json_count_and_depth_are_bounded_even_when_byte_size_fits(self):
        TbClassehabilidade.objects.filter(pk=self.ability.pk).update(tags_json=[''] * MAX_JSON_ITEMS)
        self.assert_problem(self.request(), 413, 'class_catalog_json_too_large')
        self.assertEqual(self.read(fields=['nome'])['rows'][0]['nome'], self.ability.nome)
        nested = 'value'
        for _ in range(MAX_JSON_DEPTH + 1):
            nested = [nested]
        TbRecursoclasse.objects.filter(pk=self.resource.pk).update(valores_json={'1': nested})
        response = self.request({'class_id': self.classe.pk, 'section': 'recurso'})
        self.assert_problem(response, 413, 'class_catalog_json_too_large')
        self.assertEqual(DbAccessIdempotency.objects.count(), 0)


if ISOLATED:
    bootstrap_isolated_schema()
    unittest.main(argv=[sys.argv[0]], verbosity=2)
