"""Jornal metadata remains valid and rejected edits leave public content intact."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import TbJornal


class JornalContentFieldsTests(TestCase):
    def setUp(self):
        editor = get_user_model().objects.create_superuser(
            'jornal-content-editor', 'jornal-content@example.invalid', 'test-pass'
        )
        self.client.force_login(editor)
        self.article = TbJornal.objects.create(
            titulo='Artigo existente', slug='artigo-existente',
            resumo='Resumo anterior', imagem_url='/static/assets/logo.png',
            conteudo_markdown='Texto anterior', destaque=False,
        )

    def post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json')

    def test_invalid_metadata_rejects_create_and_preserves_existing_article(self):
        invalid_fields = (
            {'resumo': 'R' * 301},
            {'resumo': {'texto': 'inesperado'}},
            {'imagem_url': '/static/' + 'a' * 500},
            {'imagem_url': ['https://example.org/capa.png']},
            {'conteudo_markdown': {'texto': 'inesperado'}},
            {'destaque': 'false'},
        )
        create_url = reverse('jornal_create')
        update_url = reverse('jornal_update', args=[self.article.slug])
        for fields in invalid_fields:
            with self.subTest(fields=fields):
                response = self.post_json(create_url, {'titulo': 'Artigo novo', **fields})
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json())
                response = self.post_json(update_url, {
                    'titulo': 'Titulo perdido', 'conteudo_markdown': 'Texto perdido', **fields,
                })
                self.assertEqual(response.status_code, 400)
                self.article.refresh_from_db()
                self.assertEqual(self.article.titulo, 'Artigo existente')
                self.assertEqual(self.article.resumo, 'Resumo anterior')
                self.assertEqual(self.article.imagem_url, '/static/assets/logo.png')
                self.assertEqual(self.article.conteudo_markdown, 'Texto anterior')
                self.assertFalse(self.article.destaque)
        self.assertFalse(TbJornal.objects.filter(slug='artigo-novo').exists())

    def test_valid_metadata_is_saved_and_read_publicly(self):
        response = self.post_json(reverse('jornal_update', args=[self.article.slug]), {
            'resumo': 'Resumo atualizado', 'imagem_url': '/static/assets/logo.png',
            'conteudo_markdown': 'Texto atualizado', 'destaque': True,
        })
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.resumo, 'Resumo atualizado')
        self.assertEqual(self.article.conteudo_markdown, 'Texto atualizado')
        self.assertTrue(self.article.destaque)
        detail = self.client.get(reverse('jornal_detail', args=[self.article.slug]))
        listing = self.client.get(reverse('mundo_jornal'))
        self.assertContains(detail, 'Texto atualizado')
        self.assertContains(listing, 'Resumo atualizado')
        self.assertContains(listing, 'Destaque')
