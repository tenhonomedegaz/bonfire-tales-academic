import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.models import TbCronica


class CronicaRevisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.autor = user.objects.create_user('autor-cronica', password='senha')
        cls.outro = user.objects.create_user('outro-cronica', password='senha')
        cls.staff = user.objects.create_user('staff-cronica', password='senha', is_staff=True)
        cls.cronica = TbCronica.objects.create(
            titulo='Título publicado', slug='titulo-publicado',
            conteudo_markdown='Texto publicado', resumo='Resumo publicado',
            autor=cls.autor, status='aprovada',
        )

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def edit(self, title='Título novo', content='Texto novo'):
        self.client.force_login(self.autor)
        return self.post_json(reverse('cronica_edit', args=[self.cronica.slug]), {
            'titulo': title, 'conteudo_markdown': content, 'resumo': 'Resumo novo',
            'territorio': [], 'regiao': [],
        })

    def review(self, action, feedback='', expected_revision=None):
        self.client.force_login(self.staff)
        self.cronica.refresh_from_db()
        if expected_revision is None:
            expected_revision = self.cronica.revisao_edicao.get('submetida_em', '')
        return self.post_json(reverse('cronica_review_action', args=[self.cronica.pk]), {
            'action': action, 'feedback': feedback, 'expected_revision': expected_revision,
        })

    def test_published_story_remains_visible_while_edit_is_reviewed(self):
        self.assertEqual(self.edit().status_code, 200)
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.status, 'aprovada')
        self.assertEqual(self.cronica.titulo, 'Título publicado')
        self.assertEqual(self.cronica.conteudo_markdown, 'Texto publicado')
        self.assertEqual(self.cronica.revisao_edicao['estado'], 'pendente')

        self.client.logout()
        detail = self.client.get(reverse('cronica_detail', args=[self.cronica.slug]))
        listing = self.client.get(reverse('mundo_cronicas'))
        self.assertContains(detail, 'Texto publicado')
        self.assertNotContains(detail, 'Texto novo')
        self.assertContains(listing, 'Título publicado')
        self.assertNotContains(listing, 'Título novo')

        self.client.force_login(self.staff)
        queue = self.client.get(reverse('cronicas_review'))
        self.assertContains(queue, 'Texto novo')
        self.assertNotContains(queue, 'Texto publicado')

    def test_staff_approval_publishes_all_fields_once(self):
        self.edit()
        self.assertEqual(self.review('aprovar').status_code, 200)
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.titulo, 'Título novo')
        self.assertEqual(self.cronica.conteudo_markdown, 'Texto novo')
        self.assertEqual(self.cronica.resumo, 'Resumo novo')
        self.assertEqual(self.cronica.revisao_edicao, {})
        self.assertEqual(self.review('aprovar').status_code, 409)

    def test_rejection_keeps_public_version_and_allows_resubmission(self):
        self.edit()
        self.assertEqual(self.review('reprovar', 'Revise o final').status_code, 200)
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.status, 'aprovada')
        self.assertEqual(self.cronica.conteudo_markdown, 'Texto publicado')
        self.assertEqual(self.cronica.revisao_edicao['estado'], 'reprovada')
        self.assertEqual(self.review('aprovar').status_code, 409)

        self.client.force_login(self.autor)
        editor = self.client.get(reverse('cronica_edit', args=[self.cronica.slug]))
        self.assertContains(editor, 'Texto novo')
        self.assertContains(editor, 'Revise o final')
        self.assertEqual(self.edit(content='Texto corrigido').status_code, 200)
        self.assertEqual(self.review('aprovar').status_code, 200)
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.conteudo_markdown, 'Texto corrigido')

    def test_non_owner_cannot_edit_or_review(self):
        self.client.force_login(self.outro)
        url = reverse('cronica_edit', args=[self.cronica.slug])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.post_json(url, {'titulo': 'Ataque'}).status_code, 404)
        self.assertEqual(self.post_json(reverse('cronica_review_action', args=[self.cronica.pk]), {
            'action': 'aprovar',
        }).status_code, 302)
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.revisao_edicao, {})

    def test_initial_publication_still_requires_staff_approval(self):
        self.client.force_login(self.autor)
        response = self.post_json(reverse('cronica_create'), {
            'titulo': 'Nova história', 'conteudo_markdown': 'Texto inicial',
        })
        self.assertEqual(response.status_code, 200)
        slug = response.json()['slug']
        self.client.logout()
        self.assertEqual(self.client.get(reverse('cronica_detail', args=[slug])).status_code, 404)
        new_story = TbCronica.objects.get(slug=slug)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('cronicas_review')), 'Texto inicial')
        self.assertEqual(self.post_json(reverse('cronica_review_action', args=[new_story.pk]), {
            'action': 'aprovar',
        }).status_code, 200)
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[slug])), 'Texto inicial')

    def test_staff_cannot_approve_an_outdated_editorial_snapshot(self):
        self.edit(content='Primeiro rascunho')
        self.cronica.refresh_from_db()
        old_revision = self.cronica.revisao_edicao['submetida_em']
        self.edit(content='Segundo rascunho')
        self.assertEqual(self.review('aprovar', expected_revision=old_revision).status_code, 409)
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.conteudo_markdown, 'Texto publicado')
        self.assertEqual(self.cronica.revisao_edicao['conteudo_markdown'], 'Segundo rascunho')
