"""A Chronicle cover travels from author submission through review to public reading."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import TbCronica
from .views import _cronica_author_snapshot, _cronica_pending_snapshot


class ChronicleCoverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.author = users.objects.create_user('cover-author', password='test')
        cls.reviewer = users.objects.create_user('cover-reviewer', password='test', is_staff=True)
        cls.reviewer.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbcronica',
        ))

    def post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json')

    def test_author_cover_is_reviewed_then_visible_in_list_and_detail(self):
        self.client.force_login(self.author)
        create = self.client.get(reverse('cronica_create'))
        self.assertContains(create, 'id="edImagemUrl"')
        cover = 'https://example.org/capa.jpg'
        response = self.post_json(reverse('cronica_create'), {
            'titulo': 'Capa revisada', 'conteudo_markdown': 'Texto da crônica',
            'imagem_url': cover,
        })
        self.assertEqual(response.status_code, 200)
        story = TbCronica.objects.get(slug=response.json()['slug'])
        self.assertEqual(story.imagem_url, cover)
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('mundo_cronicas')), cover)
        self.assertEqual(self.client.get(reverse('cronica_detail', args=[story.slug])).status_code, 404)

        self.client.force_login(self.reviewer)
        self.assertContains(self.client.get(reverse('cronicas_review')), cover)
        approved = self.post_json(reverse('cronica_review_action', args=[story.pk]), {
            'action': 'aprovar', 'expected_snapshot': _cronica_pending_snapshot(story),
        })
        self.assertEqual(approved.status_code, 200)
        self.client.logout()
        self.assertContains(self.client.get(reverse('mundo_cronicas')), f'src="{cover}"')
        self.assertContains(self.client.get(reverse('cronica_detail', args=[story.slug])), f'src="{cover}"')

        self.client.force_login(self.author)
        edit = self.client.get(reverse('cronica_edit', args=[story.slug]))
        self.assertContains(edit, f'value="{cover}"')
        story.refresh_from_db()
        revised_cover = '/media/capas/nova.jpg'
        self.assertEqual(self.post_json(reverse('cronica_edit', args=[story.slug]), {
            'titulo': story.titulo, 'conteudo_markdown': story.conteudo_markdown,
            'imagem_url': revised_cover, 'expected_edit': _cronica_author_snapshot(story),
        }).status_code, 200)
        story.refresh_from_db()
        self.assertEqual(story.imagem_url, cover)
        self.assertEqual(story.revisao_edicao['imagem_url'], revised_cover)
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[story.slug])), f'src="{cover}"')
        self.assertNotContains(self.client.get(reverse('cronica_detail', args=[story.slug])), revised_cover)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post_json(reverse('cronica_review_action', args=[story.pk]), {
            'action': 'aprovar', 'expected_revision': story.revisao_edicao['submetida_em'],
        }).status_code, 200)
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[story.slug])), f'src="{revised_cover}"')

    def test_invalid_cover_cannot_enter_or_replace_publication(self):
        self.client.force_login(self.author)
        url = reverse('cronica_create')
        for invalid in ('javascript:alert(1)', '//example.org/capa.jpg', 'https://example.org/\nX'):
            response = self.post_json(url, {
                'titulo': 'Capa insegura', 'conteudo_markdown': 'Texto', 'imagem_url': invalid,
            })
            self.assertEqual(response.status_code, 400)
        self.assertFalse(TbCronica.objects.filter(titulo='Capa insegura').exists())

        story = TbCronica.objects.create(
            titulo='Publicada', slug='publicada-capa', conteudo_markdown='Original',
            imagem_url='/static/assets/logo.png', autor=self.author, status='aprovada',
        )
        response = self.post_json(reverse('cronica_edit', args=[story.slug]), {
            'titulo': 'Mudança indevida', 'conteudo_markdown': 'Novo texto',
            'imagem_url': 'data:image/svg+xml,<svg/>',
            'expected_edit': _cronica_author_snapshot(story),
        })
        self.assertEqual(response.status_code, 400)
        story.refresh_from_db()
        self.assertEqual(story.titulo, 'Publicada')
        self.assertEqual(story.imagem_url, '/static/assets/logo.png')
        self.assertEqual(story.revisao_edicao, {})
