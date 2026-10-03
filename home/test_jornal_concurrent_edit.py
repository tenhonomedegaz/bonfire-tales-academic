"""Stale Jornal editors cannot silently replace another editor's publication."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from home.models import TbJornal


class JornalConcurrentEditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.editor = user.objects.create_user('jornal-concurrent-editor', password='test', is_staff=True)
        cls.editor.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbjornal',
        ))
        cls.article = TbJornal.objects.create(
            titulo='Publicado', slug='publicado-concorrente',
            conteudo_markdown='Texto original', resumo='Resumo original',
        )

    def post_json(self, payload):
        return self.client.post(reverse('jornal_update', args=[self.article.slug]),
                                data=json.dumps(payload), content_type='application/json')

    def test_stale_or_missing_version_preserves_public_article_until_reload(self):
        self.client.force_login(self.editor)
        detail = self.client.get(reverse('jornal_detail', args=[self.article.slug]))
        original_version = self.article.data_edicao.isoformat()
        self.assertContains(detail, f'data-editor-version="{original_version}"')

        first = self.post_json({
            'titulo': 'Primeira revisão', 'conteudo_markdown': 'Texto da primeira revisão',
            'expected_edit': original_version,
        })
        self.assertEqual(first.status_code, 200)
        self.article.refresh_from_db()
        self.assertNotEqual(self.article.data_edicao.isoformat(), original_version)

        for expected in (original_version, None):
            with self.subTest(expected=expected):
                stale = self.post_json({
                    'titulo': 'Revisão atrasada', 'conteudo_markdown': 'Texto perdido',
                    'expected_edit': expected,
                })
                self.assertEqual(stale.status_code, 409)
                self.article.refresh_from_db()
                self.assertEqual(self.article.titulo, 'Primeira revisão')
                self.assertEqual(self.article.conteudo_markdown, 'Texto da primeira revisão')

        self.assertContains(self.client.get(reverse('jornal_detail', args=[self.article.slug])),
                            'Texto da primeira revisão')
        fresh = self.post_json({
            'titulo': 'Segunda revisão', 'conteudo_markdown': 'Texto da segunda revisão',
            'expected_edit': self.article.data_edicao.isoformat(),
        })
        self.assertEqual(fresh.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.titulo, 'Segunda revisão')
