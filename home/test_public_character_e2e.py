"""Página pública real em desktop e celular, sem dados de jogo privados."""
import os
from pathlib import Path
import subprocess
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from .models import TbClasse, TbPersonagem, TbPersonagemClasse


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright.')
class PublicCharacterBrowserTests(StaticLiveServerTestCase):
    def test_public_projection_on_desktop_and_mobile(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        user = get_user_model().objects.create_user('public-browser-owner')
        klass = TbClasse.objects.create(nome='Guerreiro', slug='guerreiro-public-browser')
        p = TbPersonagem.objects.create(
            dono=user, nome='Guardião da Aurora', publico=True,
            descricao_publica='Lenda compartilhada pela jogadora.',
            anotacoes='Segredo privado da personagem',
            mostrar_atributos_publicos=True,
            mostrar_pericias_publicas=True,
            mostrar_resumo_mecanico_publico=True,
        )
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=klass, nivel=1, principal=True)
        env = dict(os.environ, PUBLIC_CHARACTER_ORIGIN=self.live_server_url,
                   PUBLIC_CHARACTER_PATH=reverse('ficha_publica', args=[p.pk]))
        result = subprocess.run(
            ['node', str(Path(__file__).parent / 'js_tests/public_character.e2e.cjs')],
            env=env, capture_output=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
