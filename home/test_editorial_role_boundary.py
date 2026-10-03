"""Editorial roles can publish and review without gaining operational admin access."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from home.models import TbCronica, TbJornal


class EditorialRoleBoundaryTests(TestCase):
    def test_separate_staff_roles_publish_only_their_authorized_content(self):
        users = get_user_model()
        author = users.objects.create_user('role-author', password='test')
        journal_editor = users.objects.create_user('role-journal', password='test', is_staff=True)
        chronicle_reviewer = users.objects.create_user('role-reviewer', password='test', is_staff=True)
        generic_staff = users.objects.create_user('role-generic', password='test', is_staff=True)
        for user, codename in (
            (journal_editor, 'add_tbjornal'),
            (chronicle_reviewer, 'change_tbcronica'),
        ):
            user.user_permissions.add(Permission.objects.get(
                content_type__app_label='home', codename=codename,
            ))

        story = TbCronica.objects.create(
            titulo='Relato aguardando revisão', slug='relato-aguardando-revisao',
            conteudo_markdown='Texto da crônica', autor=author, status='pendente',
        )
        article_url = reverse('jornal_create')
        queue_url = reverse('cronicas_review')
        decision_url = reverse('cronica_review_action', args=[story.pk])
        admin_url = reverse('admin:index')

        self.client.force_login(generic_staff)
        self.assertEqual(self.client.get(article_url).status_code, 403)
        self.assertEqual(self.client.get(queue_url).status_code, 403)
        self.assertNotEqual(self.client.get(admin_url).status_code, 200)
        self.assertEqual(self.client.post(article_url, json.dumps({
            'titulo': 'Publicação indevida',
        }), content_type='application/json').status_code, 403)

        self.client.force_login(journal_editor)
        self.assertEqual(self.client.get(article_url).status_code, 200)
        self.assertEqual(self.client.get(queue_url).status_code, 403)
        self.assertNotEqual(self.client.get(admin_url).status_code, 200)
        created = self.client.post(article_url, json.dumps({
            'titulo': 'Notícia da comunidade',
            'conteudo_markdown': 'Conteúdo editorial publicado',
        }), content_type='application/json')
        self.assertEqual(created.status_code, 200)
        article = TbJornal.objects.get(slug=created.json()['slug'])
        self.assertEqual(article.autor_id, journal_editor.pk)
        self.assertEqual(self.client.get(decision_url).status_code, 403)

        self.client.force_login(chronicle_reviewer)
        self.assertEqual(self.client.get(article_url).status_code, 403)
        self.assertNotEqual(self.client.get(admin_url).status_code, 200)
        self.assertEqual(self.client.post(article_url, json.dumps({
            'titulo': 'Publicação indevida',
        }), content_type='application/json').status_code, 403)
        queue = self.client.get(queue_url)
        self.assertEqual(queue.status_code, 200)
        self.assertContains(queue, 'Relato aguardando revisão')
        snapshot = queue.context['pendentes'][0].review_snapshot
        self.client.force_login(journal_editor)
        denied = self.client.post(decision_url, json.dumps({
            'action': 'aprovar', 'expected_snapshot': snapshot,
        }), content_type='application/json')
        self.assertEqual(denied.status_code, 403)
        story.refresh_from_db()
        self.assertEqual(story.status, 'pendente')
        self.client.force_login(chronicle_reviewer)
        approved = self.client.post(decision_url, json.dumps({
            'action': 'aprovar', 'expected_snapshot': snapshot,
        }), content_type='application/json')
        self.assertEqual(approved.status_code, 200)
        story.refresh_from_db()
        self.assertEqual(story.status, 'aprovada')
        self.assertEqual(story.revisado_por_id, chronicle_reviewer.pk)
        self.assertFalse(TbJornal.objects.filter(titulo='Publicação indevida').exists())

        self.client.logout()
        self.assertContains(self.client.get(reverse('jornal_detail', args=[article.slug])),
                            'Conteúdo editorial publicado')
        self.assertContains(self.client.get(reverse('cronica_detail', args=[story.slug])),
                            'Texto da crônica')
