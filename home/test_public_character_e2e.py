"""Página pública real em desktop e celular, sem dados de jogo privados."""
import os
from pathlib import Path
import subprocess
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from .cosmetics import invalidate_cosmetic_cache
from .models import TbClasse, TbCosmetico, TbPersonagem, TbPersonagemClasse


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright.')
class PublicCharacterBrowserTests(StaticLiveServerTestCase):
    def test_public_projection_on_desktop_and_mobile(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        user = get_user_model().objects.create_user('public-browser-owner')
        klass = TbClasse.objects.create(nome='Guerreiro', slug='guerreiro-public-browser')
        TbCosmetico.objects.create(
            slug='tema-ember', tipo='tema', nome='Brasas',
            css_class='theme-ember', origem='livre', escopo='ficha')
        TbCosmetico.objects.create(
            slug='efeito-soft-glow', tipo='efeito', nome='Brilho',
            css_class='effect-soft-glow', origem='livre', escopo='ficha')
        TbCosmetico.objects.create(
            slug='moldura-gold-trim', tipo='moldura', nome='Dourada',
            css_class='frame-gold-trim', origem='livre', escopo='ficha')
        invalidate_cosmetic_cache()
        p = TbPersonagem.objects.create(
            dono=user, nome='Guardião da Aurora', publico=True,
            ficha_theme='ember', ficha_effect='soft-glow', foto_frame='gold-trim',
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
        invalidate_cosmetic_cache()
