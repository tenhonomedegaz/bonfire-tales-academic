import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from django.core import serializers
from django.test import TestCase
from django.urls import reverse

from home.db_access_models import DbAccessAudit, ManagedApiKey
from home.models import TbRegra


class CatalogSyncApiTests(TestCase):
    def setUp(self):
        # Seed migrations include a core rule; isolate this one-model fixture.
        TbRegra.objects.all().delete()
        secret = ManagedApiKey.new_secret()
        self.key = ManagedApiKey.objects.create(
            name='catalog-qa', prefix=secret[:16],
            secret_hash=ManagedApiKey.digest(secret), scopes=['read', 'publish'])
        self.secret = secret
        incoming = TbRegra(id_regra=7, slug='regra-catalogo', nome='Versao nova',
                           categoria='core')
        self.fixture = serializers.serialize('json', [incoming])
        self.package_hash = hashlib.sha256(self.fixture.encode()).hexdigest()

    def post(self, operation, payload, key):
        return self.client.post(
            reverse('db_access_operation', args=[operation]),
            data=json.dumps(payload), content_type='application/json', secure=True,
            HTTP_AUTHORIZATION='Bearer ' + self.secret,
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_preview_is_read_only_and_requires_exact_installed_package_hash(self):
        with patch('home.catalog_sync_api._local_postgres', return_value=True), \
                patch('home.catalog_sync_api._package', return_value=(
                    self.fixture, self.package_hash, json.loads(self.fixture))):
            wrong = self.post('catalog-sync-preview', {'package_sha256': '0' * 64}, 'wrong')
            self.assertEqual(wrong.status_code, 409)
            response = self.post('catalog-sync-preview',
                                 {}, 'preview')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['package_sha256'], self.package_hash)
        self.assertEqual(response.json()['models']['TbRegra']['new'], 1)
        self.assertEqual(response.json()['unsafe_deletions'], 0)
        self.assertFalse(TbRegra.objects.exists())

    def test_apply_requires_current_state_and_backup_then_replays_idempotently(self):
        with patch('home.catalog_sync_api._local_postgres', return_value=True), \
                patch('home.catalog_sync_api._package', return_value=(
                    self.fixture, self.package_hash, json.loads(self.fixture))), \
                patch('home.catalog_sync_api._protected_directory', return_value=Path('backup')), \
                patch('home.catalog_sync_api._fresh_backup', return_value=Path('backup/verified.dump')) as backup, \
                patch('home.catalog_sync_api._audit') as audit:
            preview = self.post('catalog-sync-preview',
                                {'package_sha256': self.package_hash}, 'preview')
            stale = self.post('catalog-sync',
                              {'package_sha256': self.package_hash,
                               'base_version': '0' * 64}, 'stale')
            self.assertEqual(stale.status_code, 409)
            self.assertFalse(TbRegra.objects.exists())
            body = {'package_sha256': self.package_hash,
                    'base_version': preview.json()['base_version']}
            first = self.post('catalog-sync', body, 'apply')
            self.assertEqual(first.status_code, 200, first.content)
            self.assertEqual(TbRegra.objects.get(slug='regra-catalogo').nome, 'Versao nova')
            self.assertTrue(first.json()['memory_preserved'])
            self.assertEqual(first.json()['backup_file'], 'verified.dump')
            second = self.post('catalog-sync', body, 'apply')
            self.assertEqual(second.status_code, 200)
            self.assertEqual(second.json(), first.json())
            backup.assert_called_once()
            self.assertEqual(audit.call_count, 1)
            after_preview = self.post('catalog-sync-preview', {}, 'after-preview')
            self.assertEqual(after_preview.json()['models']['TbRegra']['changed_records'], 0)
            self.assertTrue(DbAccessAudit.objects.filter(
                model_label='operation:catalog-sync', status_code=200).exists())

    def test_apply_blocks_unreviewed_deletion_and_read_scope(self):
        TbRegra.objects.create(slug='regra-antiga', nome='Preservar', categoria='core')
        with patch('home.catalog_sync_api._local_postgres', return_value=True), \
                patch('home.catalog_sync_api._package', return_value=(
                    self.fixture, self.package_hash, json.loads(self.fixture))):
            preview = self.post('catalog-sync-preview',
                                {'package_sha256': self.package_hash}, 'preview')
            self.assertGreater(preview.json()['unsafe_deletions'], 0)
            denied = self.post('catalog-sync',
                               {'package_sha256': self.package_hash,
                                'base_version': preview.json()['base_version']}, 'blocked')
        self.assertEqual(denied.status_code, 409)
        self.assertTrue(TbRegra.objects.filter(slug='regra-antiga').exists())
        self.key.scopes = ['read']
        self.key.save(update_fields=['scopes'])
        denied_scope = self.post('catalog-sync',
                                 {'package_sha256': self.package_hash,
                                  'base_version': preview.json()['base_version']}, 'scope')
        self.assertEqual(denied_scope.status_code, 403)

    def test_backup_failure_prevents_merge(self):
        with patch('home.catalog_sync_api._local_postgres', return_value=True), \
                patch('home.catalog_sync_api._package', return_value=(
                    self.fixture, self.package_hash, json.loads(self.fixture))), \
                patch('home.catalog_sync_api._protected_directory', return_value=Path('backup')), \
                patch('home.catalog_sync_api._fresh_backup', side_effect=ValueError('backup failed')):
            preview = self.post('catalog-sync-preview', {}, 'preview')
            response = self.post('catalog-sync',
                                 {'package_sha256': self.package_hash,
                                  'base_version': preview.json()['base_version']}, 'backup-fails')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(TbRegra.objects.exists())

    def test_preview_reports_field_changes_without_exposing_values(self):
        TbRegra.objects.create(pk=7, slug='regra-catalogo', nome='Versao antiga',
                               categoria='core')
        with patch('home.catalog_sync_api._local_postgres', return_value=True), \
                patch('home.catalog_sync_api._package', return_value=(
                    self.fixture, self.package_hash, json.loads(self.fixture))):
            response = self.post('catalog-sync-preview', {}, 'field-diff')
        self.assertEqual(response.status_code, 200)
        diff = response.json()['models']['TbRegra']
        self.assertEqual(diff['changed_records'], 1)
        self.assertEqual(diff['changed_fields'], {'nome': 1})
        self.assertNotIn('Versao antiga', response.content.decode())
