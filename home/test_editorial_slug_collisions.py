"""Editorial submissions keep distinct public addresses when titles collide."""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from home.models import TbCronica, TbJornal


class EditorialSlugCollisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.author = user.objects.create_user('collision-author', password='test')
        cls.editor = user.objects.create_user('collision-editor', password='test', is_staff=True)
        cls.editor.user_permissions.add(Permission.objects.get(
            codename='add_tbjornal', content_type__app_label='home',
        ))
        cls.reviewer = user.objects.create_user('collision-reviewer', password='test', is_staff=True)
        cls.reviewer.user_permissions.add(Permission.objects.get(
            codename='change_tbcronica', content_type__app_label='home',
        ))

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def test_jornal_race_retries_unique_slug_and_keeps_both_articles(self):
        self.client.force_login(self.editor)
        url = reverse('jornal_create')
        original_filter = TbJornal.objects.filter
        original_create = TbJornal.objects.create
        inserted = False

        def competing_insert(**lookup):
            nonlocal inserted
            query = original_filter(**lookup)
            if not inserted and lookup.get('slug') == 'mesmo-titulo':
                inserted = True
                original_create(titulo='Artigo concorrente', slug='mesmo-titulo', autor=self.editor)
                query.exists = lambda: False  # competing insert happened after our existence check
            return query

        with patch.object(TbJornal.objects, 'filter', side_effect=competing_insert):
            response = self.post_json(url, {
                'titulo': 'Mesmo título', 'conteudo_markdown': 'Texto do editor',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['slug'], 'mesmo-titulo-1')
        self.assertEqual(TbJornal.objects.filter(slug__startswith='mesmo-titulo').count(), 2)
        self.assertContains(self.client.get(reverse('jornal_detail', args=['mesmo-titulo-1'])),
                            'Texto do editor')

    def test_cronica_race_retries_unique_slug_without_publishing_draft(self):
        self.client.force_login(self.author)
        url = reverse('cronica_create')
        original_filter = TbCronica.objects.filter
        original_create = TbCronica.objects.create
        inserted = False

        def competing_insert(**lookup):
            nonlocal inserted
            query = original_filter(**lookup)
            if not inserted and lookup.get('slug') == 'mesmo-relato':
                inserted = True
                original_create(titulo='Rascunho concorrente', slug='mesmo-relato',
                                conteudo_markdown='Primeiro texto', autor=self.author, status='pendente')
                query.exists = lambda: False
            return query

        with patch.object(TbCronica.objects, 'filter', side_effect=competing_insert):
            response = self.post_json(url, {
                'titulo': 'Mesmo relato', 'conteudo_markdown': 'Texto do autor',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['slug'], 'mesmo-relato-1')
        self.assertEqual(TbCronica.objects.filter(slug__startswith='mesmo-relato').count(), 2)
        self.assertEqual(TbCronica.objects.get(slug='mesmo-relato-1').status, 'pendente')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('cronica_detail', args=['mesmo-relato-1'])).status_code, 404)
        self.client.force_login(self.reviewer)
        story = TbCronica.objects.get(slug='mesmo-relato-1')
        self.assertEqual(self.post_json(reverse('cronica_review_action', args=[story.pk]), {
            'action': 'aprovar',
        }).status_code, 200)
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=['mesmo-relato-1'])),
                            'Texto do autor')

    def test_preexisting_slug_uses_next_suffix(self):
        self.client.force_login(self.editor)
        for slug in ('mesmo-titulo', 'mesmo-titulo-1'):
            TbJornal.objects.create(titulo='Existente', slug=slug, autor=self.editor)
        response = self.post_json(reverse('jornal_create'), {
            'titulo': 'Mesmo título', 'conteudo_markdown': 'Terceiro artigo',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['slug'], 'mesmo-titulo-2')
