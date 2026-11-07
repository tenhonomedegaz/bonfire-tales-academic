"""Browser regression for the last valid character-creation preview."""
import os
from pathlib import Path
import subprocess
import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.db import connection
from django.urls import reverse
from home.models import TbRegra


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright for browser QA.')
class CreatorPreviewRetentionBrowserTests(StaticLiveServerTestCase):
    def test_failed_refresh_keeps_last_valid_sheet_until_recovery(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires isolated PostgreSQL test_ database.')
        TbRegra.objects.filter(slug='aumento-de-atributo').delete()
        call_command('loaddata', 'home/fixtures/conteudo.json', verbosity=0)
        user = get_user_model().objects.create_user(username='preview-retention')
        self.client.force_login(user)
        root = Path(__file__).resolve().parent.parent
        env = dict(os.environ,
            PREVIEW_ORIGIN=self.live_server_url,
            PREVIEW_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
            PREVIEW_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value)
        with self.settings(HUNTER_CREATOR_RULESET_CHECKSUM=''):
            for route in ('criacao_ficha', 'pathbuilder'):
                env['PREVIEW_PAGE'] = reverse(route)
                result = subprocess.run(
                    ['node', str(root / 'home/js_tests/creator_preview_retention.e2e.cjs')],
                    cwd=root, env=env, capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(result.returncode, 0, route + ': ' + result.stdout + result.stderr)
