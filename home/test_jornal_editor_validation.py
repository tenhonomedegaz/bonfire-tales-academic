"""Jornal editor must reject invalid changes without damaging published articles."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import TbJornal


class JornalEditorValidationTests(TestCase):
    def setUp(self):
        editor = get_user_model().objects.create_superuser(
            'jornal-validation-editor', 'jornal-validation@example.invalid', 'test-pass'
        )
        self.client.force_login(editor)

    def post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json')

    def test_create_rejects_invalid_title_and_layout(self):
        url = reverse('jornal_create')
        for payload in (
            {'titulo': '   ', 'layout': 'padrao'},
            {'titulo': 'Artigo valido', 'layout': 'desconhecido'},
            {'titulo': 42, 'layout': 'padrao'},
            {'titulo': 'Artigo valido', 'layout': ['atlas']},
            {'titulo': '✨✨', 'layout': 'padrao'},
            {'titulo': 'A' * 201, 'layout': 'padrao'},
            ['Artigo invalido'],
        ):
            with self.subTest(payload=payload):
                response = self.post_json(url, payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json())
        self.assertFalse(TbJornal.objects.exists())

    def test_invalid_update_preserves_published_article(self):
        article = TbJornal.objects.create(
            titulo='Artigo publicado', slug='artigo-publicado',
            layout='atlas', conteudo_markdown='Texto publicado',
        )
        url = reverse('jornal_update', args=[article.slug])
        for payload in (
            {'titulo': '  ', 'conteudo_markdown': 'Texto perdido'},
            {'layout': 'desconhecido', 'conteudo_markdown': 'Texto perdido'},
            {'titulo': None, 'conteudo_markdown': 'Texto perdido'},
            ['Artigo invalido'],
        ):
            with self.subTest(payload=payload):
                response = self.post_json(url, payload)
                self.assertEqual(response.status_code, 400)
                article.refresh_from_db()
                self.assertEqual(article.titulo, 'Artigo publicado')
                self.assertEqual(article.layout, 'atlas')
                self.assertEqual(article.conteudo_markdown, 'Texto publicado')

        response = self.post_json(url, {
            'titulo': 'Artigo revisado', 'layout': 'colunas',
            'conteudo_markdown': 'Texto revisado',
        })
        self.assertEqual(response.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.titulo, 'Artigo revisado')
        self.assertEqual(article.layout, 'colunas')
        self.assertEqual(article.conteudo_markdown, 'Texto revisado')
        public = self.client.get(reverse('jornal_detail', args=[article.slug]))
        self.assertEqual(public.status_code, 200)
        self.assertContains(public, 'Artigo revisado')
