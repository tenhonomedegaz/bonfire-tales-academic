import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.db_access import OPERATION_HANDLERS, register_operation_handler
from home.db_access_models import DbAccessAudit, ManagedApiKey
from home.models import TbLinhagem, TbRaca, TbRegra


class ApiKeyLifecycleTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser('root', 'root@example.test', 'pw')
        self.user = User.objects.create_user('regular', 'regular@example.test', 'pw')

    def test_only_superuser_can_create_and_secret_is_returned_once(self):
        self.client.force_login(self.user)
        denied = self.client.post(
            reverse('managed_api_keys'),
            data=json.dumps({'name': 'denied', 'scopes': ['read']}),
            content_type='application/json',
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.superuser)
        created = self.client.post(
            reverse('managed_api_keys'),
            data=json.dumps({'name': 'integration', 'scopes': ['read', 'write']}),
            content_type='application/json',
        )
        self.assertEqual(created.status_code, 201)
        secret = created.json()['secret']
        key = ManagedApiKey.objects.get()
        self.assertTrue(secret.startswith('bfd_'))
        self.assertTrue(key.matches(secret))
        self.assertNotEqual(key.secret_hash, secret)

        listed = self.client.get(reverse('managed_api_keys'))
        serialized = json.dumps(listed.json())
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn(secret, serialized)
        self.assertNotIn(key.secret_hash, serialized)
        self.assertNotIn('secret_hash', serialized)
        audit = DbAccessAudit.objects.get(action='key_create')
        self.assertEqual(audit.object_pk, str(key.pk))
        self.assertIsNone(audit.api_key_id)

    def test_invalid_scope_type_is_rejected_without_server_error(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('managed_api_keys'),
            data=json.dumps({'name': 'invalid', 'scopes': [{}]}),
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ManagedApiKey.objects.exists())

    def test_key_console_is_superuser_only_and_exposes_no_secret(self):
        url = reverse('managed_api_key_console')
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.superuser)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Criar chave')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn('secret_hash', response.content.decode())

    def test_admin_key_list_rejects_staff_with_explicit_view_permission(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.user.user_permissions.add(Permission.objects.get(codename='view_managedapikey'))
        self.client.force_login(self.user)
        denied = self.client.get('/admin/home/managedapikey/')
        self.assertEqual(denied.status_code, 302)
        self.assertTrue(denied['Location'].startswith('/admin/login/'))
        self.assertEqual(self.client.get(reverse('managed_api_keys')).status_code, 403)
        self.client.force_login(self.superuser)
        listing = self.client.get('/admin/home/managedapikey/')
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, reverse('managed_api_key_console'))

    def test_rotation_revokes_old_key_and_returns_new_secret(self):
        self.client.force_login(self.superuser)
        created = self.client.post(
            reverse('managed_api_keys'),
            data=json.dumps({'name': 'rotate-me', 'scopes': ['read']}),
            content_type='application/json',
        )
        old = ManagedApiKey.objects.get(pk=created.json()['item']['id'])

        rotated = self.client.post(
            reverse('managed_api_key_rotate', args=[old.pk]),
            data='{}', content_type='application/json',
        )
        self.assertEqual(rotated.status_code, 201)
        old.refresh_from_db()
        new = ManagedApiKey.objects.get(pk=rotated.json()['item']['id'])
        self.assertIsNotNone(old.revoked_at)
        self.assertEqual(new.rotated_from, old)
        self.assertTrue(new.matches(rotated.json()['secret']))

    def test_revoke_is_idempotent(self):
        self.client.force_login(self.superuser)
        created = self.client.post(
            reverse('managed_api_keys'),
            data=json.dumps({'name': 'revoke-me', 'scopes': ['read']}),
            content_type='application/json',
        )
        url = reverse('managed_api_key_revoke', args=[created.json()['item']['id']])
        self.assertEqual(self.client.post(url).status_code, 200)
        revoked_at = ManagedApiKey.objects.get().revoked_at
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(ManagedApiKey.objects.get().revoked_at, revoked_at)


class StructuredDbApiTests(TestCase):
    def make_key(self, scopes=('read', 'write'), **kwargs):
        secret = ManagedApiKey.new_secret()
        key = ManagedApiKey.objects.create(
            name='test-key', prefix=secret[:16],
            secret_hash=ManagedApiKey.digest(secret), scopes=list(scopes), **kwargs,
        )
        return key, secret

    def request_headers(self, secret, **extra):
        return {'HTTP_AUTHORIZATION': 'Bearer ' + secret, 'secure': True, **extra}

    def test_https_scope_expiry_and_revocation_are_enforced(self):
        key, secret = self.make_key(scopes=('read',))
        url = reverse('db_access_schema')
        self.assertEqual(self.client.get(url, HTTP_AUTHORIZATION='Bearer ' + secret).status_code, 400)
        self.assertEqual(self.client.get(url, **self.request_headers(secret)).status_code, 200)

        write = self.client.post(
            reverse('db_access_collection', args=['regra']),
            data=json.dumps({'slug': 'x', 'nome': 'X'}), content_type='application/json',
            **self.request_headers(secret, HTTP_IDEMPOTENCY_KEY='one'),
        )
        self.assertEqual(write.status_code, 403)

        key.expires_at = timezone.now() - timedelta(seconds=1)
        key.save(update_fields=('expires_at',))
        self.assertEqual(self.client.get(url, **self.request_headers(secret)).status_code, 401)
        key.expires_at = None
        key.revoked_at = timezone.now()
        key.save(update_fields=('expires_at', 'revoked_at'))
        self.assertEqual(self.client.get(url, **self.request_headers(secret)).status_code, 401)

    def test_schema_exposes_only_allowlisted_models_and_no_user_data(self):
        _key, secret = self.make_key(scopes=('read',))
        response = self.client.get(reverse('db_access_schema'), **self.request_headers(secret))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()['models']),
            {'regra', 'idioma', 'condicao', 'raca', 'linhagem'},
        )
        self.assertNotIn('user', json.dumps(response.json()).lower())

    def test_read_filters_columns_pagination_and_rejects_escape_from_allowlist(self):
        _key, secret = self.make_key(scopes=('read',))
        TbRegra.objects.create(slug='acao', nome='Acao', categoria='core')
        TbRegra.objects.create(slug='perigo', nome='Perigo', categoria='hazard')
        url = reverse('db_access_collection', args=['regra'])
        response = self.client.get(
            url + '?filter[categoria]=core&fields=slug,nome&page_size=1&ordering=nome',
            **self.request_headers(secret),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['items'], [{'slug': 'acao', 'nome': 'Acao'}])
        self.assertEqual(response.json()['total'], 1)

        bad_filter = self.client.get(
            url + '?filter[nome__contains]=A', **self.request_headers(secret),
        )
        self.assertEqual(bad_filter.status_code, 400)
        unknown_model = self.client.get(
            reverse('db_access_collection', args=['user']), **self.request_headers(secret),
        )
        self.assertEqual(unknown_model.status_code, 404)

    def test_create_is_typed_idempotent_and_audited_without_values(self):
        _key, secret = self.make_key()
        url = reverse('db_access_collection', args=['regra'])
        payload = {'slug': 'acao-bonus', 'nome': 'Acao bonus', 'categoria': 'core'}
        headers = self.request_headers(secret, HTTP_IDEMPOTENCY_KEY='create-rule-1')
        first = self.client.post(url, data=json.dumps(payload), content_type='application/json', **headers)
        replay = self.client.post(url, data=json.dumps(payload), content_type='application/json', **headers)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(TbRegra.objects.filter(slug='acao-bonus').count(), 1)

        conflict = self.client.post(
            url, data=json.dumps({'slug': 'different', 'nome': 'Different'}),
            content_type='application/json', **headers,
        )
        self.assertEqual(conflict.status_code, 409)
        audit = DbAccessAudit.objects.filter(action='create', status_code=201).latest('occurred_at')
        self.assertEqual(audit.field_names, ['categoria', 'nome', 'slug'])
        self.assertNotIn('Acao bonus', json.dumps({
            'action': audit.action, 'model': audit.model_label,
            'pk': audit.object_pk, 'fields': audit.field_names,
        }))

    def test_update_requires_current_version_and_is_idempotent(self):
        _key, secret = self.make_key()
        rule = TbRegra.objects.create(slug='before', nome='Before')
        url = reverse('db_access_object', args=['regra', rule.pk])
        read = self.client.get(url, **self.request_headers(secret))
        version = read.json()['version']

        missing = self.client.patch(
            url, data=json.dumps({'nome': 'After'}), content_type='application/json',
            **self.request_headers(secret, HTTP_IDEMPOTENCY_KEY='update-missing'),
        )
        self.assertEqual(missing.status_code, 428)
        updated = self.client.patch(
            url, data=json.dumps({'nome': 'After'}), content_type='application/json',
            **self.request_headers(
                secret, HTTP_IDEMPOTENCY_KEY='update-1', HTTP_IF_MATCH='"%s"' % version,
            ),
        )
        self.assertEqual(updated.status_code, 200)
        stale = self.client.patch(
            url, data=json.dumps({'nome': 'Stale'}), content_type='application/json',
            **self.request_headers(
                secret, HTTP_IDEMPOTENCY_KEY='update-2', HTTP_IF_MATCH='"%s"' % version,
            ),
        )
        self.assertEqual(stale.status_code, 412)
        rule.refresh_from_db()
        self.assertEqual(rule.nome, 'After')

    def test_foreign_key_is_validated_and_serialized_as_primary_key(self):
        _key, secret = self.make_key()
        race = TbRaca.objects.create(nome='Humano', slug='humano')
        url = reverse('db_access_collection', args=['linhagem'])
        payload = {'id_raca': race.pk, 'nome': 'Versatil', 'slug': 'versatil'}
        created = self.client.post(
            url, data=json.dumps(payload), content_type='application/json',
            **self.request_headers(secret, HTTP_IDEMPOTENCY_KEY='lineage-1'),
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()['item']['id_raca'], race.pk)
        self.assertTrue(TbLinhagem.objects.filter(id_raca=race).exists())

        invalid = self.client.post(
            url, data=json.dumps({'id_raca': 999999, 'nome': 'X', 'slug': 'x'}),
            content_type='application/json',
            **self.request_headers(secret, HTTP_IDEMPOTENCY_KEY='lineage-2'),
        )
        self.assertEqual(invalid.status_code, 400)

    def test_basic_rate_limit(self):
        key, secret = self.make_key(scopes=('read',))
        key.rate_window_started = timezone.now()
        key.rate_count = 60
        key.save(update_fields=('rate_window_started', 'rate_count'))
        response = self.client.get(reverse('db_access_schema'), **self.request_headers(secret))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '60')


class StructuredOperationHandlerTests(StructuredDbApiTests):
    handler_name = 'test-class-revision'

    def tearDown(self):
        OPERATION_HANDLERS.pop(self.handler_name, None)
        super().tearDown()

    def test_code_allowlisted_handler_requires_version_and_is_idempotent(self):
        _key, secret = self.make_key(scopes=('write',))

        def handler(payload, api_key):
            rule, _created = TbRegra.objects.get_or_create(
                slug=payload['operation']['slug'],
                defaults={'nome': payload['operation']['nome']},
            )
            return {'revision_id': rule.pk, 'base_version': payload['base_version']}

        register_operation_handler(self.handler_name, handler)
        url = reverse('db_access_operation', args=[self.handler_name])
        no_version = self.client.post(
            url, data=json.dumps({'operation': {'slug': 'rev', 'nome': 'Revision'}}),
            content_type='application/json',
            **self.request_headers(secret, HTTP_IDEMPOTENCY_KEY='op-no-version'),
        )
        self.assertEqual(no_version.status_code, 428)

        payload = {
            'base_version': 'snapshot-sha256',
            'operation': {'slug': 'rev', 'nome': 'Revision'},
        }
        headers = self.request_headers(secret, HTTP_IDEMPOTENCY_KEY='op-1')
        first = self.client.post(url, data=json.dumps(payload), content_type='application/json', **headers)
        replay = self.client.post(url, data=json.dumps(payload), content_type='application/json', **headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(TbRegra.objects.filter(slug='rev').count(), 1)
        self.assertEqual(
            DbAccessAudit.objects.filter(model_label='operation:' + self.handler_name).count(),
            3,
        )
