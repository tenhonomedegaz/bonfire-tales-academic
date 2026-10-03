"""Initial Chronicle review must decide on the draft actually shown in the queue."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from home.models import TbCronica


class ChronicleInitialSnapshotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.author = user.objects.create_user('snapshot-author', password='test')
        cls.reviewer = user.objects.create_user('snapshot-reviewer', password='test', is_staff=True)
        cls.reviewer.user_permissions.add(Permission.objects.get(
            codename='change_tbcronica', content_type__app_label='home',
        ))
        cls.story = TbCronica.objects.create(
            titulo='Primeira versão', slug='primeira-versao-snapshot',
            conteudo_markdown='Texto inicialmente lido', autor=cls.author, status='pendente',
        )

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def test_changed_initial_draft_cannot_be_approved_or_rejected_from_old_queue(self):
        self.client.force_login(self.reviewer)
        queue = self.client.get(reverse('cronicas_review'))
        snapshot = queue.context['pendentes'][0].review_snapshot
        self.assertContains(queue, f'data-snapshot="{snapshot}"')
        self.client.force_login(self.author)
        changed = self.post_json(reverse('cronica_edit', args=[self.story.slug]), {
            'titulo': 'Segunda versão', 'conteudo_markdown': 'Texto alterado depois da leitura',
        })
        self.assertEqual(changed.status_code, 200)

        self.client.force_login(self.reviewer)
        action_url = reverse('cronica_review_action', args=[self.story.pk])
        for action in ('aprovar', 'reprovar'):
            response = self.post_json(action_url, {
                'action': action, 'feedback': 'Rever conteúdo', 'expected_snapshot': snapshot,
            })
            self.assertEqual(response.status_code, 409)
            self.story.refresh_from_db()
            self.assertEqual(self.story.status, 'pendente')
            self.assertIsNone(self.story.revisado_por)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('cronica_detail', args=[self.story.slug])).status_code, 404)

        self.client.force_login(self.reviewer)
        current = self.client.get(reverse('cronicas_review')).context['pendentes'][0].review_snapshot
        self.assertNotEqual(current, snapshot)
        accepted = self.post_json(action_url, {'action': 'aprovar', 'expected_snapshot': current})
        self.assertEqual(accepted.status_code, 200)
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[self.story.slug])),
                            'Texto alterado depois da leitura')
