"""Editorial publication dates must match the date accepted by the Jornal."""

import json
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.admin.models import CHANGE, LogEntry
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
        self.assertNotContains(public, 'Editado em')
        self.assertFalse(LogEntry.objects.filter(object_id=str(article.pk), action_flag=CHANGE).exists())

        changed = self.post_json(reverse('jornal_update', args=[article.slug]), {
            'data_publicacao': '2024-05-20T12:00',
            'expected_edit': article.data_edicao.isoformat(),
        })
        self.assertEqual(changed.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(timezone.localtime(article.data_publicacao).replace(tzinfo=None),
                         datetime(2024, 5, 20, 12, 0))
        self.assertEqual(LogEntry.objects.filter(object_id=str(article.pk), action_flag=CHANGE).count(), 1)
        self.assertContains(self.client.get(reverse('jornal_detail', args=[article.slug])), 'Editado em')

    def test_inline_editor_changes_layout_and_date_without_rewriting_unchanged_date(self):
        article = TbJornal.objects.create(
            titulo='Edicao especial', slug='edicao-especial',
            layout='padrao', conteudo_markdown='Texto original',
            data_publicacao=timezone.make_aware(datetime(2024, 4, 15, 10, 30, 47)),
        )
        detail_url = reverse('jornal_detail', args=[article.slug])
        update_url = reverse('jornal_update', args=[article.slug])
        detail = self.client.get(detail_url)
        self.assertNotContains(detail, 'Editado em')
        self.assertContains(detail, '<select name="layout">', html=False)
        self.assertContains(detail, '<option value="padrao" selected>', html=False)
        self.assertContains(detail, 'type="datetime-local" name="data_publicacao"', html=False)
        self.assertContains(detail, "layout: fd.get('layout')", html=False)
        self.assertContains(detail, "data_publicacao: fd.get('data_publicacao')", html=False)

        original_date = article.data_publicacao
        original_version = article.data_edicao.isoformat()
        changed = self.post_json(update_url, {
            'layout': 'colunas', 'data_publicacao': '',
            'expected_edit': original_version,
        })
        self.assertEqual(changed.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.layout, 'colunas')
        self.assertEqual(article.data_publicacao, original_date)
        self.assertContains(self.client.get(detail_url), 'data-artigo-layout="colunas"')

        version = article.data_edicao.isoformat()
        changed = self.post_json(update_url, {
            'layout': 'atlas', 'data_publicacao': '2024-05-20T12:00',
            'expected_edit': version,
        })
        self.assertEqual(changed.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.layout, 'atlas')
        self.assertEqual(timezone.localtime(article.data_publicacao).replace(tzinfo=None),
                         datetime(2024, 5, 20, 12, 0))
        public = self.client.get(detail_url)
        self.assertContains(public, 'data-artigo-layout="atlas"')
        self.assertContains(public, '<option value="atlas" selected>', html=False)
        listing = self.client.get(reverse('mundo_jornal'))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.context['artigos'][0].data_publicacao, article.data_publicacao)

        stale = self.post_json(update_url, {
            'layout': 'padrao', 'data_publicacao': '2024-06-01T09:00',
            'expected_edit': version,
        })
        self.assertEqual(stale.status_code, 409)
        article.refresh_from_db()
        self.assertEqual(article.layout, 'atlas')
        self.assertEqual(timezone.localtime(article.data_publicacao).replace(tzinfo=None),
                         datetime(2024, 5, 20, 12, 0))
