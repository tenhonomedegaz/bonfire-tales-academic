"""Security and dispatch tests for allowlisted content publication."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .content_maintenance import (_artifact_statements, _load_package,
                                  _protected_directory, _audit)


ID = 'hunter-markdown-20260930'
URL = '/admin/content-maintenance/' + ID + '/'
READ = 'r' * 48
APPLY = 'a' * 48
TOKENS = {'CONTENT_MAINTENANCE_READ_TOKEN': READ,
          'CONTENT_MAINTENANCE_APPLY_TOKEN': APPLY}


@contextmanager
def lock(acquired):
    yield acquired


def state(**changes):
    result = {'base_present': True, 'target_present': False,
              'target_integrity': False, 'target_entries': 0,
              'revision_present': False, 'base_active': True, 'activated': False}
    result.update(changes)
    return result


@override_settings(DEBUG=True)
class ContentMaintenanceTests(SimpleTestCase):
    def test_disabled_and_separate_read_apply_tokens(self):
        self.assertEqual(self.client.get(URL, HTTP_AUTHORIZATION='Bearer ' + READ).status_code, 403)
        with patch.dict(os.environ, TOKENS):
            self.assertEqual(self.client.get(URL, HTTP_AUTHORIZATION='Bearer ' + APPLY).status_code, 403)
            self.assertEqual(self.client.post(URL, HTTP_AUTHORIZATION='Bearer ' + READ).status_code, 403)
        with patch.dict(os.environ, {'CONTENT_MAINTENANCE_READ_TOKEN': READ,
                                    'CONTENT_MAINTENANCE_APPLY_TOKEN': READ}):
            self.assertEqual(self.client.get(URL, HTTP_AUTHORIZATION='Bearer ' + READ).status_code, 403)

    def test_https_required_outside_debug(self):
        with patch.dict(os.environ, TOKENS), override_settings(DEBUG=False):
            response = self.client.get(URL, HTTP_AUTHORIZATION='Bearer ' + READ)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'https_required')

    def test_unknown_and_tampered_package(self):
        with patch.dict(os.environ, TOKENS):
            unknown = self.client.get('/admin/content-maintenance/not-registered/',
                                      HTTP_AUTHORIZATION='Bearer ' + READ)
            with patch('home.content_maintenance.PACKAGES', {ID: ('hunter_markdown_20260930.json', '0' * 64)}):
                altered = self.client.get(URL, HTTP_AUTHORIZATION='Bearer ' + READ)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(altered.status_code, 409)
        self.assertEqual(altered.json()['code'], 'package_invalid')

    def test_second_definition_needs_only_registry_entry_and_manifest(self):
        example = _load_package(ID).copy()
        example.pop('artifact_path')
        example.update(id='fixture-other-content', artifact='tests/placeholder.sql')
        raw = json.dumps(example, ensure_ascii=False).encode('utf-8')
        with TemporaryDirectory() as directory:
            Path(directory, 'fixture.json').write_bytes(raw)
            with (patch('home.content_maintenance.PACKAGE_DIR', Path(directory)),
                  patch('home.content_maintenance.PACKAGES', {
                      'fixture-other-content': ('fixture.json', hashlib.sha256(raw).hexdigest())}),
                  patch('home.content_maintenance._local_postgres', return_value=True),
                  patch('home.content_maintenance._artifact_statements', return_value=['SELECT 1']),
                  patch('home.content_maintenance._package_state', return_value=state()),
                  patch.dict(os.environ, TOKENS)):
                loaded = _load_package('fixture-other-content')
                response = self.client.get('/admin/content-maintenance/fixture-other-content/',
                                           HTTP_AUTHORIZATION='Bearer ' + READ)
        self.assertEqual(loaded['id'], 'fixture-other-content')
        self.assertEqual(loaded['artifact_path'].name, 'placeholder.sql')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['package'], 'fixture-other-content')

    def test_artifact_hash_is_pinned(self):
        package = _load_package(ID)
        self.assertEqual(len(_artifact_statements(package)), 11)
        with TemporaryDirectory() as directory:
            fake = Path(directory, 'altered.sql')
            fake.write_text('SELECT 1;', encoding='utf-8')
            package['artifact_path'] = fake
            with self.assertRaises(ValueError):
                _artifact_statements(package)

    def test_preview_is_read_only_and_minimal(self):
        with (patch.dict(os.environ, TOKENS),
              patch('home.content_maintenance._local_postgres', return_value=True),
              patch('home.content_maintenance._package_state', return_value=state()),
              patch('home.content_maintenance._fresh_backup') as backup):
            response = self.client.get(URL, HTTP_AUTHORIZATION='Bearer ' + READ)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['artifact_verified'])
        self.assertNotIn('password', response.content.decode())
        backup.assert_not_called()

    def test_rejects_payload_and_base_mismatch(self):
        with (patch.dict(os.environ, TOKENS),
              patch('home.content_maintenance._local_postgres', return_value=True),
              patch('home.content_maintenance._package_state', return_value=state()),
              patch('home.content_maintenance._fresh_backup') as backup):
            bad = self.client.post(URL, data=json.dumps({'sql': 'DELETE FROM auth_user'}),
                                   content_type='application/json', HTTP_AUTHORIZATION='Bearer ' + APPLY)
            mismatch = self.client.post(URL, data=json.dumps({
                'action': 'apply', 'expected_base_checksum': '0' * 64}),
                content_type='application/json', HTTP_AUTHORIZATION='Bearer ' + APPLY)
        self.assertEqual((bad.status_code, mismatch.status_code), (400, 400))
        backup.assert_not_called()

    def test_replay_does_not_backup_or_write(self):
        current = state(target_present=True, target_integrity=True, target_entries=21,
                        revision_present=True)
        package = _load_package(ID)
        payload = {'action': 'apply', 'expected_base_checksum': package['base_ruleset_checksum']}
        with (patch.dict(os.environ, TOKENS),
              patch('home.content_maintenance._local_postgres', return_value=True),
              patch('home.content_maintenance._package_state', return_value=current),
              patch('home.content_maintenance._exclusive_application', return_value=lock(True)),
              patch('home.content_maintenance._fresh_backup') as backup):
            response = self.client.post(URL, data=json.dumps(payload), content_type='application/json',
                                        HTTP_AUTHORIZATION='Bearer ' + APPLY)
        self.assertEqual(response.json()['code'], 'already_installed')
        backup.assert_not_called()

    def test_concurrent_application_is_rejected_before_backup(self):
        package = _load_package(ID)
        payload = {'action': 'apply', 'expected_base_checksum': package['base_ruleset_checksum']}
        with (patch.dict(os.environ, TOKENS),
              patch('home.content_maintenance._local_postgres', return_value=True),
              patch('home.content_maintenance._package_state', return_value=state()),
              patch('home.content_maintenance._exclusive_application', return_value=lock(False)),
              patch('home.content_maintenance._fresh_backup') as backup):
            response = self.client.post(URL, data=json.dumps(payload), content_type='application/json',
                                        HTTP_AUTHORIZATION='Bearer ' + APPLY)
        self.assertEqual(response.json()['code'], 'busy')
        backup.assert_not_called()

    def test_backup_preflight_failure_prevents_transaction(self):
        package = _load_package(ID)
        payload = {'action': 'apply', 'expected_base_checksum': package['base_ruleset_checksum']}
        with (patch.dict(os.environ, TOKENS),
              override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=package['base_ruleset_checksum']),
              patch('home.content_maintenance._local_postgres', return_value=True),
              patch('home.content_maintenance._package_state', return_value=state()),
              patch('home.content_maintenance._exclusive_application', return_value=lock(True)),
              patch('home.content_maintenance._protected_directory', side_effect=ValueError('missing')),
              patch('home.content_maintenance.transaction.atomic') as atomic):
            response = self.client.post(URL, data=json.dumps(payload), content_type='application/json',
                                        HTTP_AUTHORIZATION='Bearer ' + APPLY)
        self.assertEqual(response.json()['code'], 'apply_failed')
        atomic.assert_not_called()

    def test_missing_backup_directory_fails_closed_and_audit_omits_secrets(self):
        with patch.dict(os.environ, {'CONTENT_MAINTENANCE_BACKUP_DIR': ''}):
            with self.assertRaises(ValueError):
                _protected_directory()
        with TemporaryDirectory() as directory:
            _audit(Path(directory), 'started', ID, 'op123')
            audit = Path(directory, 'content_maintenance_audit.jsonl').read_text(encoding='utf-8')
        self.assertIn('op123', audit)
        self.assertNotIn(READ, audit)
        self.assertNotIn(APPLY, audit)
