"""Jornal saves only actual editorial changes and rejects malformed requests."""

import json
from unittest.mock import patch

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import TbJornal


class JornalChangeAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_user(
            'jornal-audit-editor', password='test', is_staff=True,
        )
        cls.editor.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbjornal',
        ))
        cls.article = TbJornal.objects.create(
            titulo='Publicado', slug='publicado-auditado',
            conteudo_markdown='Texto original', resumo='Resumo original',
        )

    def setUp(self):
        self.client.force_login(self.editor)
        self.url = reverse('jornal_update', args=[self.article.slug])

    def post(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type='application/json')

    def test_identical_save_keeps_version_and_history_then_real_change_is_public(self):
        original_version = self.article.data_edicao
        payload = {'expected_edit': original_version.isoformat()}
        self.assertEqual(self.post(payload).status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.data_edicao, original_version)
        self.assertFalse(LogEntry.objects.filter(object_id=str(self.article.pk), action_flag=CHANGE).exists())

        changed = self.post({**payload, 'conteudo_markdown': 'Texto revisado'})
        self.assertEqual(changed.status_code, 200)
        self.article.refresh_from_db()
        self.assertNotEqual(self.article.data_edicao, original_version)
        self.assertEqual(LogEntry.objects.filter(
            object_id=str(self.article.pk), action_flag=CHANGE, user=self.editor,
        ).count(), 1)
        self.client.logout()
        self.assertContains(self.client.get(reverse('jornal_detail', args=[self.article.slug])), 'Texto revisado')

    def test_malformed_json_does_not_change_publication_or_history(self):
        original_version = self.article.data_edicao
        for body in ('{', '{}', '[]'):
            with self.subTest(body=body):
                response = self.client.post(self.url, body, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json())
        self.article.refresh_from_db()
        self.assertEqual(self.article.data_edicao, original_version)
        self.assertEqual(self.article.conteudo_markdown, 'Texto original')
        self.assertFalse(LogEntry.objects.filter(object_id=str(self.article.pk), action_flag=CHANGE).exists())

    def test_malformed_create_does_not_publish_article(self):
        self.editor.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='add_tbjornal',
        ))
        self.client.logout()
        self.client.force_login(self.editor)
        url = reverse('jornal_create')
        for body in ('{', '{}', '[]'):
            with self.subTest(body=body):
                response = self.client.post(url, body, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json())
        self.assertEqual(TbJornal.objects.count(), 1)

    def test_create_records_editor_and_rolls_back_if_audit_fails(self):
        self.editor.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='add_tbjornal',
        ))
        url = reverse('jornal_create')
        payload = json.dumps({'titulo': 'Publicação auditada', 'conteudo_markdown': 'Texto público'})
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        article = TbJornal.objects.get(slug=response.json()['slug'])
        self.assertEqual(LogEntry.objects.filter(
            object_id=str(article.pk), action_flag=ADDITION, user=self.editor,
        ).count(), 1)
        self.client.logout()
        self.assertContains(self.client.get(reverse('jornal_detail', args=[article.slug])), 'Texto público')

        self.client.force_login(self.editor)
        with patch.object(LogEntry.objects, 'create', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'audit unavailable'):
                self.client.post(url, json.dumps({'titulo': 'Falha editorial'}),
                                 content_type='application/json')
        self.assertFalse(TbJornal.objects.filter(titulo='Falha editorial').exists())
