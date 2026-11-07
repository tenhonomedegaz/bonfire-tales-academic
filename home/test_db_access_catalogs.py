"""Catalog GET/POST/PATCH coverage through the actual authenticated API."""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

from django.db import IntegrityError
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from home.db_access import MODEL_ALLOWLIST
from home.db_access_models import ManagedApiKey
from home.models import TbBestiario, TbClasse, TbItemMagico, TbItemMundano, TbMagia, TbTalento


CATALOGS = (
    ('talento', TbTalento, 'descricao'),
    ('magia', TbMagia, 'descricao'),
    ('bestiario', TbBestiario, 'descricao_markdown'),
    ('item_mundano', TbItemMundano, 'descricao_markdown'),
    ('item_magico', TbItemMagico, 'descricao_markdown'),
)


class CatalogDbApiTests(TestCase):
    def setUp(self):
        self.secret = ManagedApiKey.new_secret()
        self.key = ManagedApiKey.objects.create(
            name='catalog-tests', prefix=self.secret[:16],
            secret_hash=ManagedApiKey.digest(self.secret), scopes=['read', 'write'])
        self.headers = {'HTTP_AUTHORIZATION': 'Bearer ' + self.secret, 'secure': True}

    def collection(self, name):
        return reverse('db_access_collection', args=[name])

    def detail(self, name, pk):
        return reverse('db_access_object', args=[name, pk])

    def mutate(self, method, url, data, *, version=None, operation=None):
        headers = dict(self.headers, HTTP_IDEMPOTENCY_KEY=operation or str(uuid.uuid4()))
        if version:
            headers['HTTP_IF_MATCH'] = version
        return getattr(self.client, method)(url, data=json.dumps(data),
                                           content_type='application/json', **headers)

    def test_schema_exposes_descriptions_tags_choices_and_no_accounts(self):
        response = self.client.get(reverse('db_access_schema'), **self.headers)
        self.assertEqual(response.status_code, 200)
        models = response.json()['models']
        for name, model, description in CATALOGS:
            fields = models[name]['fields']
            self.assertIn(description, fields)
            self.assertIn('tags_json', fields)
            self.assertFalse(fields[model._meta.pk.name]['writable'])
            self.assertTrue(fields[description]['writable'])
        self.assertIn(['epico', 'Épico'], models['talento']['fields']['tipo']['choices'])
        self.assertNotIn('autor', models['bestiario']['fields'])
        self.assertNotIn('user', models)
        self.assertNotIn('personagem', models)
        self.assertNotIn(self.secret, response.content.decode())

    def test_catalog_reads_preserve_full_markdown_and_structured_json(self):
        description = '**Descricao**\n\nSegundo paragrafo.\n\n- Regra'
        for name, model, field in CATALOGS:
            with self.subTest(name=name):
                values = {'nome': name, 'slug': name, field: description,
                          'tags_json': ['speed:+10']}
                if name == 'talento':
                    values['tipo'] = 'epico'
                if name == 'magia':
                    values['em_niveis_superiores'] = 'Aumenta por circulo.'
                if name == 'bestiario':
                    values['statblock_json'] = {'action': [{'name': 'Ataque', 'entries': ['1d6']}]}
                row = model.objects.create(**values)
                selected = self.client.get(self.collection(name),
                    {'filter[slug]': name, 'fields': f'{model._meta.pk.name},{field},tags_json'},
                    **self.headers)
                self.assertEqual(selected.status_code, 200)
                self.assertEqual(selected.json()['items'], [{model._meta.pk.name: row.pk,
                    field: description, 'tags_json': ['speed:+10']}])
                full = self.client.get(self.detail(name, row.pk), **self.headers).json()
                self.assertEqual(full['item'][field], description)
                if name == 'bestiario':
                    self.assertEqual(full['item']['statblock_json'], values['statblock_json'])
                if name == 'magia':
                    self.assertEqual(full['item']['em_niveis_superiores'], values['em_niveis_superiores'])
                self.assertEqual(len(full['version']), 64)

    def test_epic_filter_and_pagination_are_server_side(self):
        for slug, kind in [('epic-a', 'epico'), ('epic-b', 'epico'), ('ordinary', 'geral')]:
            TbTalento.objects.create(nome=slug, slug=slug, tipo=kind)
        pages = [self.client.get(self.collection('talento'), {
            'filter[tipo]': 'epico', 'fields': 'slug,tipo', 'ordering': 'slug',
            'page_size': 1, 'page': page}, **self.headers).json() for page in (1, 2)]
        self.assertEqual([page['total'] for page in pages], [2, 2])
        self.assertEqual([page['items'][0]['slug'] for page in pages], ['epic-a', 'epic-b'])

    def test_create_and_replay_use_existing_api_keys_for_each_catalog(self):
        for name, model, field in CATALOGS:
            with self.subTest(name=name):
                data = {'nome': name, 'slug': name, field: '**Novo**', 'tags_json': []}
                if name == 'talento':
                    data['tipo'] = 'epico'
                first = self.mutate('post', self.collection(name), data, operation=name)
                self.assertEqual(first.status_code, 201, first.content)
                replay = self.mutate('post', self.collection(name), data, operation=name)
                self.assertEqual(replay.status_code, 201, replay.content)
                self.assertEqual(first.json(), replay.json())
                self.assertEqual(model.objects.filter(slug=name).count(), 1)
        self.key.refresh_from_db()
        self.assertTrue(self.key.matches(self.secret))

    def test_patch_replay_and_version_conflict_preserve_pk(self):
        for name, model, field in CATALOGS:
            with self.subTest(name=name):
                row = model.objects.create(nome=name, slug=name, **{field: 'Antes'})
                url = self.detail(name, row.pk)
                version = self.client.get(url, **self.headers).json()['version']
                data = {field: '**Depois**\n\nCompleto.', 'tags_json': ['speed:+10']}
                first = self.mutate('patch', url, data, version=version, operation=name)
                self.assertEqual(first.status_code, 200, first.content)
                replay = self.mutate('patch', url, data, version=version, operation=name)
                self.assertEqual(replay.json(), first.json())
                stale = self.mutate('patch', url, {field: 'Conflito'}, version=version)
                self.assertEqual(stale.status_code, 412)
                row.refresh_from_db()
                self.assertEqual(getattr(row, field), data[field])
                self.assertEqual(row.pk, first.json()['item'][model._meta.pk.name])

    def test_read_only_key_cannot_write_catalogs(self):
        self.key.scopes = ['read']
        self.key.save(update_fields=['scopes'])
        for name, _model, _field in CATALOGS:
            self.assertEqual(self.client.get(self.collection(name), **self.headers).status_code, 200)
            denied = self.mutate('post', self.collection(name), {'nome': name, 'slug': name})
            self.assertEqual(denied.status_code, 403)

    def test_invalid_json_tags_and_primary_keys_are_rejected(self):
        row = TbTalento.objects.create(nome='Original', slug='original')
        url = self.detail('talento', row.pk)
        version = self.client.get(url, **self.headers).json()['version']
        for data in ({'id_talento': row.pk + 1}, {'tags_json': {}},
                     {'tags_json': [123]}, {'tags_json': ['always_active{']},
                     {'tipo': 'nonexistent'}, {'unexpected': 'value'}):
            with self.subTest(data=data):
                response = self.mutate('patch', url, data, version=version)
                self.assertEqual(response.status_code, 400, response.content)
        row.refresh_from_db()
        self.assertEqual(row.nome, 'Original')
        self.assertEqual(row.tags_json, [])
        bad = self.mutate('post', self.collection('bestiario'),
                         {'nome': 'Bad', 'slug': 'bad', 'statblock_json': []})
        self.assertEqual(bad.status_code, 400)

    def test_editing_description_does_not_require_rewriting_legacy_tags(self):
        row = TbTalento.objects.create(nome='Legacy', slug='legacy', tags_json=['always_active{'])
        url = self.detail('talento', row.pk)
        version = self.client.get(url, **self.headers).json()['version']
        response = self.mutate('patch', url, {'descricao': 'Revisada'}, version=version)
        self.assertEqual(response.status_code, 200, response.content)
        row.refresh_from_db()
        self.assertEqual(row.tags_json, ['always_active{'])

    def test_mundane_unknown_field_and_bestiary_author_are_not_writable(self):
        for name, values in [('item_mundano', {'nome_ingles': 'Invalid'}),
                             ('bestiario', {'autor': 1})]:
            response = self.mutate('post', self.collection(name),
                                   dict(nome=name, slug=name, **values))
            self.assertEqual(response.status_code, 400)

    def test_model_signal_validation_is_a_structured_error(self):
        response = self.mutate('post', self.collection('talento'), {
            'nome': 'Blocked', 'slug': 'blocked', 'descricao': 'DROP TABLE example;'})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['error']['code'], 'validation_error')
        self.assertFalse(TbTalento.objects.filter(slug='blocked').exists())

    def test_concurrent_constraint_failure_is_a_structured_conflict(self):
        with patch.object(TbTalento, 'save', side_effect=IntegrityError('private SQL detail')):
            response = self.mutate('post', self.collection('talento'),
                                   {'nome': 'Conflict', 'slug': 'conflict',
                                    'descricao': 'Descricao', 'tags_json': []})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error']['code'], 'constraint_conflict')
        self.assertNotIn('private SQL detail', response.content.decode())
        self.assertFalse(TbTalento.objects.filter(slug='conflict').exists())

    def test_all_configured_fields_exist_and_primary_keys_are_immutable(self):
        for name, access in MODEL_ALLOWLIST.items():
            with self.subTest(name=name):
                for field in set(access.readable + access.writable + access.filterable + access.sortable):
                    access.model._meta.get_field(field)
                self.assertNotIn(access.model._meta.pk.name, access.writable)

    def test_json_class_references_are_validated_without_rewriting_display_text(self):
        classe = TbClasse.objects.create(nome='Classe de teste', slug='classe-teste')
        data = {'nome': 'Magia', 'slug': 'magia', 'classes_slugs': [classe.slug],
                'classes': 'Rotulo editorial', 'tags_json': []}
        response = self.mutate('post', self.collection('magia'), data)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['item']['classes_slugs'], [classe.slug])
        self.assertEqual(response.json()['item']['classes'], 'Rotulo editorial')
        for references in (['unknown'], [classe.slug, classe.slug], [{}]):
            with self.subTest(references=references):
                data['slug'] = 'invalid-' + str(uuid.uuid4())
                data['classes_slugs'] = references
                invalid = self.mutate('post', self.collection('magia'), data)
                self.assertEqual(invalid.status_code, 400, invalid.content)

    def test_generic_upsert_preview_compares_without_writing_content(self):
        self.key.scopes = ['read']
        self.key.save(update_fields=['scopes'])
        unchanged = TbTalento.objects.create(nome='Existing', slug='existing',
                                             tipo='epico', descricao='Igual')
        changed = TbTalento.objects.create(nome='Changed', slug='changed', descricao='Antes')
        payload = {'model': 'talento', 'items': [
            {'slug': 'existing', 'descricao': 'Igual'},
            {'slug': 'changed', 'descricao': 'Depois'},
            {'slug': 'new', 'nome': 'New', 'tipo': 'epico', 'descricao': 'Nova', 'tags_json': []},
        ]}
        url = reverse('db_access_operation', args=['catalog-upsert-preview'])
        response = self.mutate('post', url, payload)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertEqual(result['counts'], {'create': 1, 'update': 1, 'unchanged': 1})
        self.assertFalse(result['content_mutated'])
        self.assertEqual(result['operations'][0]['pk'], unchanged.pk)
        self.assertEqual(result['operations'][1]['pk'], changed.pk)
        self.assertEqual(result['operations'][1]['changes']['descricao'],
                         {'before': 'Antes', 'after': 'Depois'})
        self.assertEqual(len(result['operations'][1]['version']), 64)
        changed.refresh_from_db()
        self.assertEqual(changed.descricao, 'Antes')
        self.assertEqual(TbTalento.objects.count(), 2)

    def test_decimal_prices_survive_receipts_replays_and_preview(self):
        data = {'nome': 'Preco', 'slug': 'preco', 'preco': '1234.56', 'tags_json': []}
        created = self.mutate('post', self.collection('item_magico'), data, operation='decimal')
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()['item']['preco'], '1234.56')
        replay = self.mutate('post', self.collection('item_magico'), data, operation='decimal')
        self.assertEqual(replay.json(), created.json())
        url = reverse('db_access_operation', args=['catalog-upsert-preview'])
        preview = self.mutate('post', url, {'model': 'item_magico',
                              'items': [{'slug': 'preco', 'preco': '2345.67'}]})
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()['operations'][0]['changes']['preco'],
                         {'before': '1234.56', 'after': '2345.67'})

    def test_preview_rejects_duplicates_account_models_pks_and_read_only_models(self):
        url = reverse('db_access_operation', args=['catalog-upsert-preview'])
        for payload in ({'model': 'user', 'items': [{'slug': 'x'}]},
                        {'model': 'opcao_jogo', 'items': [{'slug': 'x'}]},
                        {'model': 'talento', 'items': []},
                        {'model': 'talento', 'items': [{'slug': 'x'}, {'slug': 'x'}]},
                        {'model': 'talento', 'items': [{'slug': 'x', 'id_talento': 10}]},
                        {'model': 'talento', 'items': [{'slug': 'x'}] * 11}):
            with self.subTest(payload=payload):
                response = self.mutate('post', url, payload)
                self.assertIn(response.status_code, (400, 404))
        self.assertFalse(TbTalento.objects.exists())

    def test_prepared_epic_manifest_validates_as_seven_read_only_previews(self):
        from home.epic_talent_catalog import epic_candidates
        manifest = json.loads((Path(settings.BASE_DIR) /
            'docs/integracao/talentos-epicos-api-plan.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['state'], 'desired-not-applied')
        self.assertEqual(manifest['count'], 31)
        self.assertEqual(len(manifest['batches']), 7)
        url = reverse('db_access_operation', args=['catalog-upsert-preview'])
        planned = []
        for batch in manifest['batches']:
            self.assertEqual(batch['model'], 'talento')
            response = self.mutate('post', url, batch)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()['counts']['create'], len(batch['items']))
            self.assertFalse(response.json()['content_mutated'])
            planned.extend(row['slug'] for row in batch['items'])
        self.assertEqual(len(set(planned)), 31)
        self.assertEqual([item for batch in manifest['batches'] for item in batch['items']],
                         epic_candidates())
        self.assertFalse(TbTalento.objects.exists())
