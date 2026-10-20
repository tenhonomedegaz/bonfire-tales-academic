import json
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from home.db_access_models import ManagedApiKey
from home.models import TbBestiario


class BestiaryPatchApiTests(TestCase):
    def setUp(self):
        secret = ManagedApiKey.new_secret()
        self.key = ManagedApiKey.objects.create(
            name='bestiary-patch-qa', prefix=secret[:16],
            secret_hash=ManagedApiKey.digest(secret), scopes=['read', 'publish'])
        self.secret = secret
        for pk, slug in ((15, 'ajudante-da-natureza'), (40, 'espirito-bestial'),
                         (45, 'preservar-quarenta-cinco')):
            TbBestiario.objects.update_or_create(
                pk=pk, defaults={'slug': slug, 'nome': slug, 'comunidade': False})
        self.rows = [
            {'pk': 15, 'slug': 'ajudante-da-natureza', 'fields': {
                'tipo': 'planta ou besta', 'tamanho': 'M', 'alinhamento': 'neutro',
                'ca': '13', 'pv': '15', 'statblock_json': {'abilities': {'str': 10}},
                'descricao_markdown': 'Ajuda a natureza.'}},
            {'pk': 40, 'slug': 'espirito-bestial', 'fields': {
                'tamanho': 'S', 'ca': '11', 'pv': '20',
                'statblock_json': {'abilities': {'str': 12}}}},
        ]

    def post(self, operation, payload, key):
        return self.client.post(
            reverse('db_access_operation', args=[operation]),
            data=json.dumps(payload), content_type='application/json', secure=True,
            HTTP_AUTHORIZATION='Bearer ' + self.secret, HTTP_IDEMPOTENCY_KEY=key)

    def test_preview_apply_and_idempotent_replay_preserve_other_pk(self):
        original_45 = TbBestiario.objects.get(pk=45).statblock_json
        original_count = TbBestiario.objects.count()
        with patch('home.catalog_sync_api._local_postgres', return_value=True), \
                patch('home.catalog_sync_api._backup_ready', return_value=True), \
                patch('home.catalog_sync_api._protected_directory', return_value=Path('backup')), \
                patch('home.catalog_sync_api._fresh_backup', return_value=Path('backup/verified.dump')) as backup:
            preview = self.post('bestiary-patch-preview', {'rows': self.rows}, 'preview')
            self.assertEqual(preview.status_code, 200, preview.content)
            self.assertEqual(preview.json()['changed_records'], 2)
            self.assertEqual([c['pk'] for c in preview.json()['changes']], [15, 40])
            self.assertEqual(TbBestiario.objects.get(pk=15).tipo, None)
            body = {'rows': self.rows, 'base_version': preview.json()['base_version'],
                    'package_sha256': preview.json()['package_sha256']}
            stale = self.post('bestiary-patch', {**body, 'base_version': '0' * 64}, 'stale')
            self.assertEqual(stale.status_code, 409)
            first = self.post('bestiary-patch', body, 'apply')
            self.assertEqual(first.status_code, 200, first.content)
            second = self.post('bestiary-patch', body, 'apply')
            self.assertEqual(second.json(), first.json())
            backup.assert_called_once()
        self.assertEqual(TbBestiario.objects.count(), original_count)
        self.assertEqual(TbBestiario.objects.get(pk=15).tipo, 'planta ou besta')
        self.assertEqual(TbBestiario.objects.get(pk=45).statblock_json, original_45)

    def test_rejects_extra_field_and_unpublished_scope(self):
        extra = json.loads(json.dumps(self.rows))
        extra[0]['fields']['slug'] = 'other'
        with patch('home.catalog_sync_api._local_postgres', return_value=True):
            denied = self.post('bestiary-patch-preview', {'rows': extra}, 'extra')
            self.assertEqual(denied.status_code, 400)
            preview = self.post('bestiary-patch-preview', {'rows': self.rows}, 'preview')
            self.assertEqual(preview.status_code, 200)
            self.key.scopes = ['read']
            self.key.save(update_fields=['scopes'])
            denied = self.post('bestiary-patch', {
                'rows': self.rows, 'base_version': preview.json()['base_version'],
                'package_sha256': preview.json()['package_sha256']}, 'no-publish')
            self.assertEqual(denied.status_code, 403)

    def test_changed_package_or_failed_backup_never_updates_records(self):
        before = TbBestiario.objects.get(pk=15).tipo
        with patch('home.catalog_sync_api._local_postgres', return_value=True), \
                patch('home.catalog_sync_api._backup_ready', return_value=True), \
                patch('home.catalog_sync_api._protected_directory', return_value=Path('backup')), \
                patch('home.catalog_sync_api._fresh_backup', side_effect=ValueError('backup failed')) as backup:
            preview = self.post('bestiary-patch-preview', {'rows': self.rows}, 'preview')
            self.assertEqual(preview.status_code, 200)
            body = {'rows': self.rows, 'base_version': preview.json()['base_version'],
                    'package_sha256': preview.json()['package_sha256']}
            changed = json.loads(json.dumps(body))
            changed['rows'][0]['fields']['tipo'] = 'aberracao'
            rejected = self.post('bestiary-patch', changed, 'changed')
            self.assertEqual(rejected.status_code, 409)
            backup.assert_not_called()
            failed = self.post('bestiary-patch', body, 'backup-fails')
            self.assertEqual(failed.status_code, 409)
            backup.assert_called_once()
        self.assertEqual(TbBestiario.objects.get(pk=15).tipo, before)
