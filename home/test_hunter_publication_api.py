"""Boundary checks for the fixed Hunter publication maintenance endpoint."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from .hunter_publication_api import (
    BASE_CHECKSUM, SQL_SHA256, _artifact_statements, _fresh_backup,
)


URL = '/admin/server-logs/hunter-publication-maintenance/'
TOKEN = 't' * 48


@override_settings(DEBUG=True)
class HunterPublicationAPITests(SimpleTestCase):
    def test_requires_configured_bearer_token(self):
        with patch.dict(os.environ, {'HUNTER_MAINTENANCE_TOKEN': TOKEN}):
            self.assertEqual(self.client.get(URL).status_code, 403)
            self.assertEqual(self.client.get(URL, HTTP_AUTHORIZATION='Bearer wrong').status_code, 403)
        with patch.dict(os.environ, {'HUNTER_MAINTENANCE_TOKEN': ''}):
            self.assertEqual(self.client.get(URL, HTTP_AUTHORIZATION='Bearer ' + TOKEN).status_code, 403)

    def test_requires_https_in_production(self):
        with (patch.dict(os.environ, {'HUNTER_MAINTENANCE_TOKEN': TOKEN}),
              override_settings(DEBUG=False)):
            response = self.client.get(URL, HTTP_AUTHORIZATION='Bearer ' + TOKEN)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'https_required')

    def test_status_is_minimal_and_read_only(self):
        with (patch.dict(os.environ, {'HUNTER_MAINTENANCE_TOKEN': TOKEN}),
              patch('home.hunter_publication_api._local_postgres', return_value=True),
              patch('home.hunter_publication_api._publication_state', return_value={
                  'base_present': True, 'target_present': False,
                  'revision_present': False, 'target_entries': 0,
                  'configured_target': False,
              })):
            response = self.client.get(URL, HTTP_AUTHORIZATION='Bearer ' + TOKEN)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 'ok')
        self.assertNotIn('password', response.content.decode())

    def test_rejects_arbitrary_payload_before_backup(self):
        with (patch.dict(os.environ, {'HUNTER_MAINTENANCE_TOKEN': TOKEN}),
              patch('home.hunter_publication_api._local_postgres', return_value=True),
              patch('home.hunter_publication_api._fresh_backup') as backup):
            response = self.client.post(URL, data=json.dumps({'sql': 'DELETE FROM auth_user'}),
                                        content_type='application/json',
                                        HTTP_AUTHORIZATION='Bearer ' + TOKEN)
        self.assertEqual(response.status_code, 400)
        backup.assert_not_called()

    def test_requires_current_base_configuration(self):
        with (patch.dict(os.environ, {'HUNTER_MAINTENANCE_TOKEN': TOKEN}),
              override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='wrong'),
              patch('home.hunter_publication_api._local_postgres', return_value=True),
              patch('home.hunter_publication_api._fresh_backup') as backup):
            response = self.client.post(
                URL, data=json.dumps({'action': 'apply', 'expected_current_checksum': BASE_CHECKSUM}),
                content_type='application/json', HTTP_AUTHORIZATION='Bearer ' + TOKEN)
        self.assertEqual(response.status_code, 409)
        backup.assert_not_called()

    def test_backup_failure_prevents_any_sql(self):
        with (patch.dict(os.environ, {'HUNTER_MAINTENANCE_TOKEN': TOKEN}),
              override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=BASE_CHECKSUM),
              patch('home.hunter_publication_api._local_postgres', return_value=True),
              patch('home.hunter_publication_api._publication_state', return_value={'base_present': True}),
              patch('home.hunter_publication_api._fresh_backup', side_effect=ValueError('missing'))):
            response = self.client.post(
                URL, data=json.dumps({'action': 'apply', 'expected_current_checksum': BASE_CHECKSUM}),
                content_type='application/json', HTTP_AUTHORIZATION='Bearer ' + TOKEN)
        self.assertEqual(response.status_code, 409)

    def test_artifact_is_fixed_and_reviewed(self):
        statements = _artifact_statements()
        self.assertEqual(len(statements), 11)
        self.assertIn('hunter_markdown_expected_r221', statements[3])
        self.assertEqual(len(SQL_SHA256), 64)

    def test_backup_requires_preexisting_directory(self):
        with patch.dict(os.environ, {'HUNTER_MAINTENANCE_BACKUP_DIR': ''}):
            with self.assertRaises(ValueError):
                _fresh_backup()
        with TemporaryDirectory() as directory:
            missing = Path(directory) / 'missing'
            with patch.dict(os.environ, {'HUNTER_MAINTENANCE_BACKUP_DIR': str(missing)}):
                with self.assertRaises(ValueError):
                    _fresh_backup()
