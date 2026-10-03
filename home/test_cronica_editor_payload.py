"""Author resubmits do not invalidate a pending editorial review."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import TbCronica
from .views import _cronica_author_snapshot


class CronicaEditorPayloadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.author = users.objects.create_user('cronica-payload-author', password='test')
        cls.reviewer = users.objects.create_user('cronica-payload-reviewer', password='test', is_staff=True)
        cls.reviewer.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbcronica',
        ))
        cls.story = TbCronica.objects.create(
            titulo='Cronica publicada', slug='cronica-payload',
            conteudo_markdown='Texto publico', autor=cls.author, status='aprovada',
        )

    def post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json')

    def test_identical_author_save_keeps_publication_and_pending_review_version(self):
        self.client.force_login(self.author)
        edit_url = reverse('cronica_edit', args=[self.story.slug])
        self.assertEqual(self.post_json(edit_url, {
            'expected_edit': _cronica_author_snapshot(self.story),
        }).status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.revisao_edicao, {})

        response = self.post_json(edit_url, {
            'conteudo_markdown': 'Texto proposto',
            'expected_edit': _cronica_author_snapshot(self.story),
        })
        self.assertEqual(response.status_code, 200)
        self.story.refresh_from_db()
        revision_token = self.story.revisao_edicao['submetida_em']
        self.assertEqual(self.story.conteudo_markdown, 'Texto publico')
        self.assertEqual(self.post_json(edit_url, {
            'expected_edit': _cronica_author_snapshot(self.story),
        }).status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.revisao_edicao['submetida_em'], revision_token)
        self.assertEqual(self.story.conteudo_markdown, 'Texto publico')
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[self.story.slug])), 'Texto publico')

        self.client.force_login(self.reviewer)
        review = self.post_json(reverse('cronica_review_action', args=[self.story.pk]), {
            'action': 'aprovar', 'expected_revision': revision_token,
        })
        self.assertEqual(review.status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.conteudo_markdown, 'Texto proposto')
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[self.story.slug])), 'Texto proposto')

    def test_malformed_payloads_are_rejected_without_publication(self):
        self.client.force_login(self.author)
        for url in (reverse('cronica_create'), reverse('cronica_edit', args=[self.story.slug])):
            for body in ('{', '{}', '[]'):
                with self.subTest(url=url, body=body):
                    response = self.client.post(url, body, content_type='application/json')
                    self.assertEqual(response.status_code, 400)
                    self.assertIn('error', response.json())
        self.client.force_login(self.reviewer)
        for body in ('{', '{}', '[]'):
            with self.subTest(body=body):
                response = self.client.post(
                    reverse('cronica_review_action', args=[self.story.pk]),
                    body, content_type='application/json',
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json())
        self.story.refresh_from_db()
        self.assertEqual(self.story.conteudo_markdown, 'Texto publico')
        self.assertEqual(self.story.revisao_edicao, {})
        self.assertEqual(TbCronica.objects.count(), 1)
