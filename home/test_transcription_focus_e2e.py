"""Prévia Q03 no template real, em desktop e celular."""
import os
from pathlib import Path
import subprocess
import unittest

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright para E2E.')
class TranscriptionFocusE2ETests(StaticLiveServerTestCase):
  def setUp(self):
    if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
      self.skipTest('Requer PostgreSQL isolado test_.')
    from home.test_transcription_focus import TranscriptionFocusTests
    TranscriptionFocusTests.setUp(self)
    TranscriptionFocusTests.source(self)
    self.personagem.inventario.create(nome='Pergaminho de Abjuração', qtd=1,
      tags_json=['spell_scroll{spell:fogo_de_teste, level:1}', 'consumable'])

  def test_quotes_in_workshop_and_sheet(self):
    root = Path(__file__).resolve().parent.parent
    environment = dict(os.environ,
      TRANSCRIPTION_ORIGIN=self.live_server_url,
      TRANSCRIPTION_WORKSHOP=reverse('oficina_magia') + '?personagem=%s&tab=transcription' % self.personagem.pk,
      TRANSCRIPTION_SHEET=reverse('ficha_detail', args=[self.personagem.pk]) + '?aba=magias',
      TRANSCRIPTION_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
      TRANSCRIPTION_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value)
    result = subprocess.run(['node', str(root / 'home/js_tests/transcription_focus.e2e.cjs')],
      env=environment, cwd=root, capture_output=True, encoding='utf-8', timeout=90)
    print(result.stdout)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    self.pc.refresh_from_db()
    self.assertEqual(self.pc.id_subclasse_id, self.subclass.pk)
