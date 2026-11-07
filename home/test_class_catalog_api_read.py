"""Read-only classes/subclasses and bounded edits to mutable source abilities.

Run ``py -m home.test_class_catalog_api_read --isolated`` for SQLite memory only,
without bonfire.settings, project URLs, .env loading, or migrations.
The API's ``version``/ETag hashes the current readable row, not a ruleset.
Source writes do not publish/revise rulesets or alter pinned characters.
Foreign keys are accepted on CREATE only; PATCH edits content, never ownership.
"""

import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    from django.conf import settings

    settings.configure(
        SECRET_KEY='isolated-class-catalog-tests', USE_TZ=True,
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'], MIDDLEWARE=[],
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
        BASE_DIR=Path(__file__).resolve().parent.parent,
    )
    import django

    django.setup()

import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import path, reverse

from home import db_access_api as api
from home.db_access import ApiProblem, MODEL_ALLOWLIST, clean_values
from home.db_access_models import DbAccessAudit, DbAccessIdempotency, ManagedApiKey
from home.models import (
    TbClassPublication, TbClassPublicationLog, TbClasse, TbClassehabilidade,
    TbContentRevision, TbRecursoclasse, TbRegra, TbRuleset, TbRulesetContent, TbSubclasse,
)


urlpatterns = [
    path('api/db/schema/', api.db_schema, name='db_access_schema'),
    path('api/db/<str:model_name>/', api.db_collection, name='db_access_collection'),
    path('api/db/<str:model_name>/<str:object_pk>/', api.db_object, name='db_access_object'),
]

CATALOG_FIELDS = {
    'classe': ('id_classe', 'slug', 'nome', 'tagline', 'tags_json'),
    'subclasse': ('id_subclasse', 'id_classe', 'slug', 'nome', 'tagline'),
    'classe_habilidade': ('id_habilidade', 'id_classe', 'id_subclasse', 'niveladquirido',
                         'nome', 'nome_ingles', 'descricao', 'table_only', 'tags_json'),
}
ABILITY_WRITABLE = ('nome', 'nome_ingles', 'descricao', 'niveladquirido', 'table_only', 'tags_json')
ABILITY_CREATE_ONLY = ('id_classe', 'id_subclasse')


class ClassCatalogApiFixture:
    def setUp(self):
        self.secret = ManagedApiKey.new_secret()
        self.key = ManagedApiKey.objects.create(
            name='isolated-class-read', prefix=self.secret[:16],
            secret_hash=ManagedApiKey.digest(self.secret), scopes=['read'])
        self.headers = {'HTTP_AUTHORIZATION': 'Bearer ' + self.secret, 'secure': True}
        # Insert fixtures without triggering unrelated editorial publication signals.
        self.classe, self.other_classe = TbClasse.objects.bulk_create([
            TbClasse(nome='Catalog class', slug='catalog-class', tagline='Class summary',
                     tags_json=['spellcasting:catalog-source']),
            TbClasse(nome='Other class', slug='other-class'),
        ])
        self.subclasse, self.other_subclasse = TbSubclasse.objects.bulk_create([
            TbSubclasse(id_classe=self.classe, nome='Catalog subclass', slug='shared-slug',
                        tagline='Subclass summary'),
            TbSubclasse(id_classe=self.other_classe, nome='Other subclass', slug='shared-slug'),
        ])
        self.description = '**Spells**\n\nFull source text.\n\n- Grant at the specified level.'
        self.tags = ['source:test', 'spell-grant:catalog-spell']
        self.ability, self.later, self.base, self.other_ability = TbClassehabilidade.objects.bulk_create([
            TbClassehabilidade(id_classe=self.classe, id_subclasse=self.subclasse,
                               nome='Early grant', nome_ingles='Early grant EN',
                               descricao=self.description, niveladquirido=3, tags_json=self.tags),
            TbClassehabilidade(id_classe=self.classe, id_subclasse=self.subclasse,
                               nome='Later grant', descricao='Later', niveladquirido=7,
                               table_only=True),
            TbClassehabilidade(id_classe=self.classe, nome='Base feature',
                               descricao='No subclass', niveladquirido=1),
            TbClassehabilidade(id_classe=self.other_classe, id_subclasse=self.other_subclasse,
                               nome='Other grant', descricao='Other', niveladquirido=3),
        ])
        self.rows = {'classe': self.classe, 'subclasse': self.subclasse,
                     'classe_habilidade': self.ability}

    def collection(self, name):
        return reverse('db_access_collection', args=[name])

    def detail(self, name, row):
        return reverse('db_access_object', args=[name, row.pk])


@override_settings(ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'])
class ClassCatalogApiReadTests(ClassCatalogApiFixture, TestCase):
    def test_schema_lists_exact_fields_relations_and_method_specific_write_contract(self):
        response = self.client.get(reverse('db_access_schema'), **self.headers)
        self.assertEqual(response.status_code, 200, response.content)
        schema = response.json()['models']
        for name, expected in CATALOG_FIELDS.items():
            with self.subTest(name=name):
                access = MODEL_ALLOWLIST[name]
                writable = ABILITY_WRITABLE if name == 'classe_habilidade' else ()
                create_only = ABILITY_CREATE_ONLY if name == 'classe_habilidade' else ()
                self.assertEqual(access.writable, writable)
                self.assertEqual(access.create_only, create_only)
                fields = schema[name]['fields']
                self.assertEqual(set(fields), set(expected))
                for field_name, metadata in fields.items():
                    self.assertEqual(metadata['writable'], field_name in writable + create_only)
                    self.assertEqual(metadata['create_only'], field_name in create_only)
                    self.assertEqual(metadata['filterable'], field_name in access.filterable)
                    self.assertEqual(metadata['sortable'], field_name in access.sortable)
                self.assertTrue(fields[access.model._meta.pk.name]['primary_key'])
        self.assertEqual(schema['subclasse']['fields']['id_classe']['relation'], 'home.tbclasse')
        self.assertEqual(schema['classe_habilidade']['fields']['id_subclasse']['relation'],
                         'home.tbsubclasse')
        self.assertTrue(schema['classe_habilidade']['fields']['id_subclasse']['nullable'])
        self.assertIn('magia', schema)
        self.assertNotIn('user', schema)

    def test_reads_preserve_source_text_tags_and_scalar_nullable_foreign_keys(self):
        for name, row in self.rows.items():
            with self.subTest(name=name):
                response = self.client.get(self.detail(name, row), **self.headers)
                self.assertEqual(response.status_code, 200, response.content)
                data = response.json()
                self.assertEqual(set(data['item']), set(CATALOG_FIELDS[name]))
                self.assertEqual(len(data['version']), 64)
                self.assertEqual(response['ETag'], '"%s"' % data['version'])
                self.assertEqual(response['Cache-Control'], 'no-store')
        data = self.client.get(self.detail('classe_habilidade', self.ability), **self.headers).json()
        self.assertEqual(data['item'], {
            'id_habilidade': self.ability.pk, 'id_classe': self.classe.pk,
            'id_subclasse': self.subclasse.pk, 'niveladquirido': 3,
            'nome': 'Early grant', 'nome_ingles': 'Early grant EN',
            'descricao': self.description, 'table_only': False, 'tags_json': self.tags,
        })
        base = self.client.get(self.detail('classe_habilidade', self.base), **self.headers).json()['item']
        self.assertIsNone(base['id_subclasse'])
        self.assertIsNone(base['nome_ingles'])
        self.assertEqual(base['tags_json'], [])

    def test_class_and_subclass_identity_filters_do_not_assume_global_subclass_slugs(self):
        for name, filters, row in (
            ('classe', {'filter[slug]': self.classe.slug}, self.classe),
            ('subclasse', {'filter[id_classe]': self.classe.pk,
                           'filter[slug]': self.subclasse.slug}, self.subclasse),
        ):
            with self.subTest(name=name):
                pk = row._meta.pk.name
                response = self.client.get(self.collection(name),
                    dict(filters, fields=pk + ',nome', ordering='-nome'), **self.headers)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['total'], 1)
                self.assertEqual(response.json()['items'], [{pk: row.pk, 'nome': row.nome}])

    def test_ability_link_and_level_filters_ordering_projection_and_pagination(self):
        filters = {'filter[id_classe]': self.classe.pk,
                   'filter[id_subclasse]': self.subclasse.pk,
                   'fields': 'id_habilidade,niveladquirido,tags_json',
                   'ordering': '-niveladquirido', 'page_size': 1}
        for page, row in ((1, self.later), (2, self.ability)):
            response = self.client.get(self.collection('classe_habilidade'),
                                       dict(filters, page=page), **self.headers)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()['total'], 2)
            self.assertEqual(response.json()['items'], [{'id_habilidade': row.pk,
                'niveladquirido': row.niveladquirido, 'tags_json': row.tags_json}])
        response = self.client.get(self.collection('classe_habilidade'),
            dict(filters, **{'filter[niveladquirido]': 3}), **self.headers)
        self.assertEqual(response.json()['total'], 1)
        self.assertEqual(response.json()['items'][0]['id_habilidade'], self.ability.pk)

    def test_unlisted_fields_filters_relation_traversal_and_ordering_are_denied(self):
        for name in self.rows:
            for query, code in (
                ({'fields': 'publication'}, 'invalid_fields'),
                ({'filter[tags_json]': 'source:test'}, 'invalid_filter'),
                ({'filter[id_classe__slug]': self.classe.slug}, 'invalid_filter'),
                ({'filter[nome__icontains]': 'grant'}, 'invalid_filter'),
                ({'ordering': 'tags_json'}, 'invalid_ordering'),
                ({'ordering': 'id_classe__nome'}, 'invalid_ordering'),
            ):
                with self.subTest(name=name, query=query):
                    response = self.client.get(self.collection(name), query, **self.headers)
                    self.assertEqual(response.status_code, 400, response.content)
                    self.assertEqual(response.json()['error']['code'], code)
            denied = self.client.get(self.detail(name, self.rows[name]),
                                     {'fields': 'publication'}, **self.headers)
            self.assertEqual(denied.status_code, 400)

    def test_read_scope_cannot_post_or_patch(self):
        for name, row in self.rows.items():
            for method, url in (('post', self.collection(name)), ('patch', self.detail(name, row))):
                with self.subTest(name=name, method=method):
                    response = getattr(self.client, method)(url, data=json.dumps({'nome': 'Denied'}),
                        content_type='application/json', **self.headers)
                    self.assertEqual(response.status_code, 403, response.content)
                    self.assertEqual(response.json()['error']['code'], 'insufficient_scope')

    def test_classes_and_subclasses_still_cannot_mutate_even_with_write_and_publish_scopes(self):
        self.key.scopes = ['read', 'write', 'publish']
        self.key.save(update_fields=['scopes'])
        for name, row in self.rows.items():
            if name == 'classe_habilidade':
                continue
            url = self.detail(name, row)
            before = self.client.get(url, **self.headers).json()
            count = type(row).objects.count()
            for payload in ({}, {'nome': 'Denied'}, {row._meta.pk.name: row.pk}, {'tags_json': []}):
                for method, target in (('post', self.collection(name)), ('patch', url)):
                    with self.subTest(name=name, method=method, payload=payload):
                        headers = dict(self.headers, HTTP_IF_MATCH=before['version'],
                                       HTTP_IDEMPOTENCY_KEY=str(uuid4()))
                        response = getattr(self.client, method)(target, data=json.dumps(payload),
                            content_type='application/json', **headers)
                        self.assertEqual(response.status_code, 400, response.content)
                        self.assertEqual(response.json()['error']['code'],
                                         'invalid_field' if payload else 'empty_mutation')
            self.assertEqual(type(row).objects.count(), count)
            self.assertEqual(self.client.get(url, **self.headers).json(), before)
        self.assertFalse(DbAccessIdempotency.objects.exists())
        self.assertEqual(DbAccessAudit.objects.filter(
            action__in=['create', 'update'], status_code=400).count(), 16)

    def test_read_only_fields_are_rejected_by_the_shared_mutation_validator(self):
        for name, fields in CATALOG_FIELDS.items():
            for field in fields:
                for partial in (False, True):
                    access = MODEL_ALLOWLIST[name]
                    allowed = access.writable + (() if partial else access.create_only)
                    if field in allowed:
                        continue
                    with self.subTest(name=name, field=field, partial=partial):
                        with self.assertRaises(ApiProblem) as raised:
                            clean_values(access, {field: None}, partial=partial)
                        self.assertEqual(raised.exception.code, 'invalid_field')

    def test_no_delete_put_or_unauthenticated_reads(self):
        for name, row in self.rows.items():
            for method in ('delete', 'put'):
                response = getattr(self.client, method)(self.detail(name, row), **self.headers)
                self.assertEqual(response.status_code, 405)
            response = self.client.get(self.collection(name), secure=True)
            self.assertEqual(response.status_code, 401)
            response = self.client.get(self.collection(name),
                HTTP_AUTHORIZATION=self.headers['HTTP_AUTHORIZATION'])
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['error']['code'], 'https_required')

    def test_version_tracks_live_source_changes_without_claiming_a_published_revision(self):
        url = self.detail('classe_habilidade', self.ability)
        before = self.client.get(url, **self.headers).json()
        # Simulate an independent editorial change, not an API write or publication.
        TbClassehabilidade.objects.filter(pk=self.ability.pk).update(descricao='Unpublished edit')
        response = self.client.get(url, {'fields': 'id_habilidade'}, **self.headers)
        self.assertEqual(response.status_code, 200, response.content)
        after = response.json()
        self.assertNotEqual(after['version'], before['version'])
        self.assertEqual(after['item'], {'id_habilidade': self.ability.pk})
        self.assertEqual(response['ETag'], '"%s"' % after['version'])


@override_settings(ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'])
class ClassAbilityApiWriteTests(ClassCatalogApiFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.key.scopes = ['read', 'write']
        self.key.save(update_fields=['scopes'])
        from home.tag_engine.library import Library
        self.enterContext(patch('home.tag_engine.library.Library',
                               side_effect=lambda: Library(prefer_db=False)))

    def payload(self):
        return dict(id_classe=self.classe.pk, id_subclasse=self.subclasse.pk,
                    nome='New source grant', nome_ingles='Source grant EN',
                    descricao='**New source**\n\nFull grant description.',
                    niveladquirido=3, table_only=False, tags_json=['speed:+10'])

    def mutate(self, method, payload, *, row=None, version=None, operation=None):
        url = self.detail('classe_habilidade', row) if row else self.collection('classe_habilidade')
        headers = dict(self.headers, HTTP_IDEMPOTENCY_KEY=operation or str(uuid4()))
        if version is not None:
            headers['HTTP_IF_MATCH'] = version
        return getattr(self.client, method)(url, data=json.dumps(payload),
                                           content_type='application/json', **headers)

    def current(self, row=None):
        return self.client.get(self.detail('classe_habilidade', row or self.ability),
                               **self.headers).json()

    def test_create_and_replay_preserve_content_links_and_tags_without_publish_scope(self):
        count = TbClassehabilidade.objects.count()
        payload = self.payload()
        first = self.mutate('post', payload, operation='create-source')
        self.assertEqual(first.status_code, 201, first.content)
        replay = self.mutate('post', payload, operation='create-source')
        self.assertEqual(replay.status_code, 201, replay.content)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(TbClassehabilidade.objects.count(), count + 1)
        item = first.json()['item']
        self.assertEqual({key: item[key] for key in payload}, payload)
        self.assertEqual(first['ETag'], '"%s"' % first.json()['version'])
        self.assertEqual(DbAccessIdempotency.objects.count(), 1)
        self.assertEqual(DbAccessAudit.objects.filter(action='create', status_code=201).count(), 1)

    def test_create_allows_omitted_or_null_subclass_and_inclusive_level_boundaries(self):
        for level, null_subclass in ((1, False), (20, True)):
            payload = self.payload()
            payload.update(nome='Base source %s' % level, niveladquirido=level)
            if null_subclass:
                payload['id_subclasse'] = None
            else:
                del payload['id_subclasse']
            response = self.mutate('post', payload)
            self.assertEqual(response.status_code, 201, response.content)
            self.assertIsNone(response.json()['item']['id_subclasse'])
            self.assertEqual(response.json()['item']['niveladquirido'], level)

    def test_patch_all_content_fields_and_replay_without_relinking(self):
        before = self.current()
        payload = {'nome': 'Edited source', 'nome_ingles': None, 'descricao': '**Edited**\n\nComplete.',
                   'niveladquirido': 20, 'table_only': True, 'tags_json': ['speed:+20']}
        response = self.mutate('patch', payload, row=self.ability,
                               version=before['version'], operation='edit-source')
        self.assertEqual(response.status_code, 200, response.content)
        replay = self.mutate('patch', payload, row=self.ability,
                            version=before['version'], operation='edit-source')
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertEqual(replay.json(), response.json())
        self.assertNotEqual(response.json()['version'], before['version'])
        self.ability.refresh_from_db()
        for name, value in payload.items():
            self.assertEqual(getattr(self.ability, name), value)
        self.assertEqual(self.ability.id_classe_id, self.classe.pk)
        self.assertEqual(self.ability.id_subclasse_id, self.subclasse.pk)
        self.assertEqual(DbAccessIdempotency.objects.count(), 1)

    def test_patch_rejects_all_link_fields_even_if_unchanged_or_null(self):
        before = self.current()
        for payload in ({'id_classe': self.classe.pk}, {'id_classe': self.other_classe.pk},
                        {'id_subclasse': self.subclasse.pk}, {'id_subclasse': self.other_subclasse.pk},
                        {'id_subclasse': None}, {'id_classe_id': self.other_classe.pk},
                        {'id_subclasse_id': None}):
            with self.subTest(payload=payload):
                response = self.mutate('patch', dict(payload, descricao='Must not persist'),
                                       row=self.ability, version=before['version'])
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(response.json()['error']['code'], 'invalid_field')
        self.assertEqual(self.current(), before)
        self.assertFalse(DbAccessIdempotency.objects.exists())

    def test_create_rejects_missing_null_nonexistent_and_foreign_class_links(self):
        payloads = []
        for links in ({'id_classe': None}, {'id_classe': 999999}, {'id_subclasse': 999999},
                      {'id_subclasse': self.other_subclasse.pk}):
            payloads.append(dict(self.payload(), **links))
        missing = self.payload()
        del missing['id_classe']
        payloads.append(missing)
        count = TbClassehabilidade.objects.count()
        for payload in payloads:
            with self.subTest(links=(payload.get('id_classe'), payload.get('id_subclasse'))):
                response = self.mutate('post', payload)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn(response.json()['error']['code'], ('invalid_value', 'validation_error'))
        self.assertEqual(TbClassehabilidade.objects.count(), count)
        self.assertFalse(DbAccessIdempotency.objects.exists())

    def test_create_and_patch_reject_levels_outside_one_to_twenty(self):
        before = self.current()
        count = TbClassehabilidade.objects.count()
        for level in (-1, 0, 21, 100):
            payload = dict(self.payload(), niveladquirido=level)
            for method, values in (('post', payload), ('patch', {'niveladquirido': level})):
                with self.subTest(method=method, level=level):
                    response = self.mutate(method, values,
                        row=self.ability if method == 'patch' else None, version=before['version'])
                    self.assertEqual(response.status_code, 400, response.content)
                    self.assertEqual(response.json()['error']['code'], 'validation_error')
                    self.assertIn('niveladquirido', response.json()['error']['details'])
        self.assertEqual(TbClassehabilidade.objects.count(), count)
        self.assertEqual(self.current(), before)

    def test_create_and_patch_reuse_tag_shape_and_dsl_validation_atomically(self):
        before = self.current()
        count = TbClassehabilidade.objects.count()
        for tags in ({}, [123], ['always_active{']):
            for method in ('post', 'patch'):
                with self.subTest(method=method, tags=tags):
                    payload = dict(self.payload(), tags_json=tags) if method == 'post' else {
                        'descricao': 'Must not persist', 'tags_json': tags}
                    response = self.mutate(method, payload,
                        row=self.ability if method == 'patch' else None, version=before['version'])
                    self.assertEqual(response.status_code, 400, response.content)
                    self.assertIn('tags_json', response.json()['error']['details'])
        self.assertEqual(TbClassehabilidade.objects.count(), count)
        self.assertEqual(self.current(), before)
        self.assertFalse(DbAccessIdempotency.objects.exists())

    def test_invalid_level_types_are_rejected_instead_of_truncated_or_coerced(self):
        before = self.current()
        for level in (None, True, 1.5, 20.9, 'not-a-level'):
            for method in ('post', 'patch'):
                with self.subTest(method=method, level=level):
                    payload = dict(self.payload(), niveladquirido=level) if method == 'post' else {
                        'niveladquirido': level}
                    response = self.mutate(method, payload,
                        row=self.ability if method == 'patch' else None, version=before['version'])
                    self.assertEqual(response.status_code, 400, response.content)
                    self.assertEqual(response.json()['error']['code'], 'invalid_value')
                    self.assertIn('niveladquirido', response.json()['error']['details'])
        self.assertEqual(self.current(), before)

    def test_patch_revalidates_subclass_membership_for_legacy_inconsistent_source(self):
        TbClassehabilidade.objects.filter(pk=self.ability.pk).update(id_subclasse=self.other_subclasse)
        before = self.current()
        response = self.mutate('patch', {'descricao': 'Must not persist'},
                               row=self.ability, version=before['version'])
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['error']['code'], 'validation_error')
        self.assertIn('id_subclasse', response.json()['error']['details'])
        self.assertEqual(self.current(), before)

    def test_description_patch_does_not_require_rewriting_untouched_legacy_tags(self):
        TbClassehabilidade.objects.filter(pk=self.ability.pk).update(tags_json=['always_active{'])
        response = self.mutate('patch', {'descricao': 'Source text corrected'},
                               row=self.ability, version=self.current()['version'])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['item']['tags_json'], ['always_active{'])

    def test_idempotency_and_if_match_guards_are_unchanged(self):
        url = self.detail('classe_habilidade', self.ability)
        before = self.current()
        no_key = self.client.post(self.collection('classe_habilidade'), data=json.dumps(self.payload()),
                                 content_type='application/json', **self.headers)
        self.assertEqual(no_key.status_code, 400)
        self.assertEqual(no_key.json()['error']['code'], 'idempotency_required')
        no_version = self.mutate('patch', {'descricao': 'Denied'}, row=self.ability)
        self.assertEqual(no_version.status_code, 428)
        no_patch_key = self.client.patch(url, data=json.dumps({'descricao': 'Denied'}),
            content_type='application/json', HTTP_IF_MATCH=before['version'], **self.headers)
        self.assertEqual(no_patch_key.status_code, 400)
        self.assertEqual(no_patch_key.json()['error']['code'], 'idempotency_required')
        accepted = self.mutate('patch', {'descricao': 'Accepted'}, row=self.ability,
                               version=before['version'], operation='guarded-edit')
        self.assertEqual(accepted.status_code, 200, accepted.content)
        stale = self.mutate('patch', {'descricao': 'Stale'}, row=self.ability, version=before['version'])
        self.assertEqual(stale.status_code, 412)
        conflict = self.mutate('patch', {'descricao': 'Conflicting replay'}, row=self.ability,
                               version=accepted.json()['version'], operation='guarded-edit')
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()['error']['code'], 'idempotency_conflict')
        self.assertEqual(self.current(), accepted.json())

    def test_publish_scope_alone_does_not_authorize_source_writes(self):
        self.key.scopes = ['read', 'publish']
        self.key.save(update_fields=['scopes'])
        response = self.mutate('post', self.payload())
        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()['error']['code'], 'insufficient_scope')

    def test_primary_key_and_unlisted_fields_are_never_editable(self):
        before = self.current()
        for field in ('id_habilidade', 'slug', 'ruleset', 'publication', 'id_classe_id'):
            for method in ('post', 'patch'):
                with self.subTest(field=field, method=method):
                    values = dict(self.payload(), **{field: 999}) if method == 'post' else {field: 999}
                    response = self.mutate(method, values,
                        row=self.ability if method == 'patch' else None, version=before['version'])
                    self.assertEqual(response.status_code, 400, response.content)
                    self.assertEqual(response.json()['error']['code'], 'invalid_field')
        self.assertEqual(self.current(), before)

    def test_duplicate_source_create_is_rejected_without_extra_rows(self):
        payload = dict(self.payload(), nome=self.ability.nome, niveladquirido=self.ability.niveladquirido)
        count = TbClassehabilidade.objects.count()
        response = self.mutate('post', payload)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['error']['code'], 'validation_error')
        self.assertEqual(TbClassehabilidade.objects.count(), count)

    def test_unrelated_standard_catalog_create_and_patch_keep_existing_contract(self):
        self.assertEqual(MODEL_ALLOWLIST['regra'].create_only, ())
        headers = dict(self.headers, HTTP_IDEMPOTENCY_KEY='other-create')
        created = self.client.post(self.collection('regra'),
            data=json.dumps({'nome': 'Other catalog', 'slug': 'other-catalog', 'definicao': 'Before'}),
            content_type='application/json', **headers)
        self.assertEqual(created.status_code, 201, created.content)
        row = TbRegra.objects.get(pk=created.json()['item']['id_regra'])
        headers.update(HTTP_IDEMPOTENCY_KEY='other-edit', HTTP_IF_MATCH=created.json()['version'])
        edited = self.client.patch(self.detail('regra', row), data=json.dumps({'definicao': 'After'}),
                                   content_type='application/json', **headers)
        self.assertEqual(edited.status_code, 200, edited.content)
        row.refresh_from_db()
        self.assertEqual(row.definicao, 'After')

    def test_source_writes_do_not_modify_sealed_snapshot_or_publication(self):
        from home.content_versions import resolve_content
        from home.versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog, seal_class_snapshot

        ruleset = seal_class_snapshot(self.classe.pk)
        publication = TbClassPublication.objects.create(id_classe=self.classe, ruleset=ruleset)
        identity = 'class-catalog:%s' % self.classe.pk
        before = resolve_content(ruleset, identity, evaluator_version=EVALUATOR,
                                 vocabulary_version=VOCABULARY)
        counts = [model.objects.count() for model in (
            TbContentRevision, TbRuleset, TbRulesetContent, TbClassPublication, TbClassPublicationLog)]
        patched = self.mutate('patch', {'descricao': 'Unpublished live source edit'},
                              row=self.ability, version=self.current()['version'])
        self.assertEqual(patched.status_code, 200, patched.content)
        created = self.mutate('post', self.payload())
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(resolve_content(ruleset, identity, evaluator_version=EVALUATOR,
                                       vocabulary_version=VOCABULARY), before)
        publication.refresh_from_db()
        self.assertEqual(publication.ruleset_id, ruleset.pk)
        self.assertEqual(counts, [model.objects.count() for model in (
            TbContentRevision, TbRuleset, TbRulesetContent, TbClassPublication, TbClassPublicationLog)])
        pinned = VersionedClassCatalog(ruleset, self.classe.pk).collections[TbClassehabilidade]
        self.assertEqual(next(row for row in pinned if row.pk == self.ability.pk).descricao,
                         self.description)
        self.assertNotIn(created.json()['item']['id_habilidade'], [row.pk for row in pinned])


def bootstrap_isolated_schema():
    database = connection.settings_dict
    if database['ENGINE'] != 'django.db.backends.sqlite3' or database['NAME'] != ':memory:':
        raise RuntimeError('Class catalog tests only bootstrap in-memory SQLite')
    if 'bonfire.settings' in sys.modules:
        raise RuntimeError('Isolated class catalog tests must not load production settings')
    with connection.schema_editor() as editor:
        for model in (ContentType, Permission, Group, get_user_model(),
                      TbClasse, TbSubclasse, TbClassehabilidade, TbRecursoclasse, TbRegra,
                      TbContentRevision, TbRuleset, TbRulesetContent,
                      TbClassPublication, TbClassPublicationLog,
                      ManagedApiKey, DbAccessIdempotency, DbAccessAudit):
            editor.create_model(model)


if ISOLATED:
    bootstrap_isolated_schema()
    unittest.main(argv=[sys.argv[0]], verbosity=2)
