"""Editorial publication dates must match the date accepted by the Jornal."""

import json
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import TbJornal


class JornalPublicationDateTests(TestCase):
    def setUp(self):
        editor = get_user_model().objects.create_superuser(
            'jornal-date-editor', 'jornal-date-editor@example.invalid', 'test-pass'
        )
        self.client.force_login(editor)

    def post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json')

    def test_invalid_date_rejects_create_and_preserves_existing_article(self):
        create = reverse('jornal_create')
        for value in ('data invalida', '2026-99-99T25:90', 123):
            with self.subTest(value=value):
                response = self.post_json(create, {
                    'titulo': 'Artigo novo', 'data_publicacao': value,
                })
                self.assertEqual(response.status_code, 400)
                self.assertIn('data', response.json()['error'].lower())
        self.assertFalse(TbJornal.objects.exists())

        article = TbJornal.objects.create(
            titulo='Artigo publicado', slug='artigo-publicado',
            conteudo_markdown='Texto anterior',
        )
        original_date = article.data_publicacao
        response = self.post_json(reverse('jornal_update', args=[article.slug]), {
            'titulo': 'Titulo perdido', 'conteudo_markdown': 'Texto perdido',
            'data_publicacao': 'sem data',
        })
        self.assertEqual(response.status_code, 400)
        article.refresh_from_db()
        self.assertEqual(article.titulo, 'Artigo publicado')
        self.assertEqual(article.conteudo_markdown, 'Texto anterior')
        self.assertEqual(article.data_publicacao, original_date)

    def test_valid_retroactive_date_is_saved_and_shown_to_readers(self):
        response = self.post_json(reverse('jornal_create'), {
            'titulo': 'Edicao retroativa', 'conteudo_markdown': 'Conteudo historico',
            'data_publicacao': '2024-04-15T10:30',
        })
        self.assertEqual(response.status_code, 200)
        article = TbJornal.objects.get(slug='edicao-retroativa')
        self.assertTrue(timezone.is_aware(article.data_publicacao))
        local = timezone.localtime(article.data_publicacao)
        self.assertEqual(local.replace(tzinfo=None), datetime(2024, 4, 15, 10, 30))
        public = self.client.get(reverse('jornal_detail', args=[article.slug]))
        self.assertEqual(public.status_code, 200)
        self.assertContains(public, 'Edicao retroativa')
        self.assertContains(public, '2024')

        changed = self.post_json(reverse('jornal_update', args=[article.slug]), {
            'data_publicacao': '2024-05-20T12:00',
        })
        self.assertEqual(changed.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(timezone.localtime(article.data_publicacao).replace(tzinfo=None),
                         datetime(2024, 5, 20, 12, 0))
