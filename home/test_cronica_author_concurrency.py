"""An author cannot replace a Chronicle draft changed since opening the editor."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import TbCronica


class ChronicleAuthorConcurrencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.author = users.objects.create_user('concurrent-author', password='test')
        cls.reviewer = users.objects.create_user('concurrent-reviewer', password='test', is_staff=True)
        cls.reviewer.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbcronica',
        ))

    def post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json')

    def test_old_author_tab_cannot_replace_pending_draft(self):
        story = TbCronica.objects.create(
            titulo='Rascunho', slug='rascunho-concorrente',
            conteudo_markdown='Texto inicial', autor=self.author, status='pendente',
        )
        url = reverse('cronica_edit', args=[story.slug])
        self.client.force_login(self.author)
        old = self.client.get(url).context['edit_snapshot']
        self.assertEqual(self.post_json(url, {
            'titulo': 'Versão atual', 'conteudo_markdown': 'Texto atual',
            'expected_edit': old,
        }).status_code, 200)
        for token in (old, None):
            stale = self.post_json(url, {
                'titulo': 'Versão antiga', 'conteudo_markdown': 'Texto perdido',
                'expected_edit': token,
            })
            self.assertEqual(stale.status_code, 409)
            self.assertIn('Recarregue', stale.json()['error'])
        story.refresh_from_db()
        self.assertEqual(story.titulo, 'Versão atual')
        self.assertEqual(story.conteudo_markdown, 'Texto atual')

        current = self.client.get(url).context['edit_snapshot']
        self.assertNotEqual(current, old)
        self.assertEqual(self.post_json(url, {
            'titulo': 'Versão final', 'conteudo_markdown': 'Texto final',
            'expected_edit': current,
        }).status_code, 200)
        self.client.force_login(self.reviewer)
        queue = self.client.get(reverse('cronicas_review'))
        self.assertContains(queue, 'Texto final')
        self.assertNotContains(queue, 'Texto perdido')
        snapshot = queue.context['pendentes'][0].review_snapshot
        self.assertEqual(self.post_json(reverse('cronica_review_action', args=[story.pk]), {
            'action': 'aprovar', 'expected_snapshot': snapshot,
        }).status_code, 200)
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[story.slug])), 'Texto final')

    def test_published_story_and_pending_revision_survive_old_tab(self):
        story = TbCronica.objects.create(
            titulo='Publicada', slug='publicada-concorrente',
            conteudo_markdown='Texto público', autor=self.author, status='aprovada',
        )
        url = reverse('cronica_edit', args=[story.slug])
        self.client.force_login(self.author)
        old = self.client.get(url).context['edit_snapshot']
        self.assertEqual(self.post_json(url, {
            'titulo': 'Revisão atual', 'conteudo_markdown': 'Texto em revisão',
            'expected_edit': old,
        }).status_code, 200)
        self.assertEqual(self.post_json(url, {
            'titulo': 'Rascunho antigo', 'conteudo_markdown': 'Texto antigo',
            'expected_edit': old,
        }).status_code, 409)
        story.refresh_from_db()
        self.assertEqual(story.titulo, 'Publicada')
        self.assertEqual(story.revisao_edicao['titulo'], 'Revisão atual')
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[story.slug])), 'Texto público')
        self.assertNotContains(self.client.get(reverse('cronica_detail', args=[story.slug])), 'Texto antigo')

        self.client.force_login(self.reviewer)
        self.assertEqual(self.post_json(reverse('cronica_review_action', args=[story.pk]), {
            'action': 'reprovar', 'feedback': 'Ajuste o final.',
            'expected_revision': story.revisao_edicao['submetida_em'],
        }).status_code, 200)
        self.client.force_login(self.author)
        self.assertEqual(self.post_json(url, {
            'titulo': 'Rascunho antigo', 'conteudo_markdown': 'Texto antigo',
            'expected_edit': old,
        }).status_code, 409)
        fresh = self.client.get(url)
        self.assertContains(fresh, 'Ajuste o final.')
        self.assertEqual(self.post_json(url, {
            'titulo': 'Revisão corrigida', 'conteudo_markdown': 'Texto corrigido',
            'expected_edit': fresh.context['edit_snapshot'],
        }).status_code, 200)
        story.refresh_from_db()
        self.assertEqual(story.titulo, 'Publicada')
        self.assertEqual(story.revisao_edicao['titulo'], 'Revisão corrigida')
