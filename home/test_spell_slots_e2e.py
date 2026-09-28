"""Q02 em Chromium, com autenticação, template, derivação e PostgreSQL reais."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from home.models import (TbClasse, TbClassehabilidade, TbRecursoclasse,
                         TbPersonagem, TbPersonagemClasse, TbOperacaoRecurso)


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright para E2E.')
class SpellSlotsRealE2ETests(StaticLiveServerTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('E2E requer PostgreSQL isolado test_.')
        self.user = get_user_model().objects.create_user(username='slot-e2e')
        classe = TbClasse.objects.create(nome='Arquivista', slug='arquivista-e2e')
        TbClassehabilidade.objects.create(
            id_classe=classe, nome='Conjuração', niveladquirido=1,
            tags_json=['spellcasting{ability:int, slots{progression:full}, '
                       'list:arquivista, mode:prepared, spell_limit{formula:classlvl+int_mod}}'])
        TbRecursoclasse.objects.create(id_classe=classe, nome='1º', slug='1o',
                                      nivel=1, valor='2', valores_json={'1': '2'}, tipo='table-only')
        self.character = TbPersonagem.objects.create(dono=self.user, nome='E2E dos Slots', inteligencia=16)
        TbPersonagemClasse.objects.create(id_personagem=self.character, id_classe=classe,
                                          nivel=1, principal=True)
        self.client.force_login(self.user)

    def test_consume_restore_two_tabs_reload_and_html_fallback(self):
        root = Path(__file__).resolve().parent.parent
        environment = os.environ.copy()
        environment.update({
            'SLOTS_E2E_ORIGIN': self.live_server_url,
            'SLOTS_E2E_PATH': reverse('ficha_detail', args=[self.character.pk]) + '?aba=magias',
            'SLOTS_E2E_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
            'SLOTS_E2E_COOKIE_VALUE': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
        })
        node = shutil.which('node')
        if not node:
            self.skipTest('Node indisponível.')
        try:
            result = subprocess.run([node, str(root / 'home/js_tests/spell_slots.e2e.cjs')],
                                    cwd=root, env=environment, capture_output=True,
                                    encoding='utf-8', timeout=90)
        except subprocess.TimeoutExpired as error:
            self.fail('E2E excedeu 90s. Etapas observadas: %r; erros: %r' %
                      (error.stdout, error.stderr))
        print(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.character.recursos.get(nome='spell-slot:1').atual, 1)
        self.assertEqual(TbOperacaoRecurso.objects.filter(id_personagem=self.character).count(), 4)
