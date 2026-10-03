import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from home.models import TbCronica, TbRegiao, TbTerritorio
from home.views import _cronica_pending_snapshot


class CronicaRevisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.autor = user.objects.create_user('autor-cronica', password='senha')
        cls.outro = user.objects.create_user('outro-cronica', password='senha')
        cls.staff = user.objects.create_user('staff-cronica', password='senha', is_staff=True)
        cls.staff.user_permissions.add(Permission.objects.get(
            codename='change_tbcronica', content_type__app_label='home',
        ))
        cls.staff_sem_publicacao = user.objects.create_user(
            'staff-sem-publicacao', password='senha', is_staff=True,
        )
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

    def test_staff_can_open_published_story(self):
        self.client.force_login(self.staff)
        detail = self.client.get(reverse('cronica_detail', args=[self.cronica.slug]))
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.context['can_edit_wiki'])

    def test_generic_staff_cannot_review_or_publish(self):
        self.edit(content='Edição privada pendente')
        self.client.force_login(self.staff_sem_publicacao)
        self.assertEqual(self.client.get(reverse('cronicas_review')).status_code, 403)
        self.assertEqual(self.post_json(reverse('cronica_review_action', args=[self.cronica.pk]), {
            'action': 'aprovar',
        }).status_code, 403)
        listing = self.client.get(reverse('mundo_cronicas'))
        self.assertNotContains(listing, 'href="%s"' % reverse('cronicas_review'))
        self.assertEqual(listing.context['pendente_count'], 0)
        public_detail = self.client.get(reverse('cronica_detail', args=[self.cronica.slug]))
        self.assertEqual(public_detail.context['revisao_edicao'], {})
        self.assertNotContains(public_detail, 'Edição privada pendente')
        pending = TbCronica.objects.create(
            titulo='Ainda privada', slug='ainda-privada',
            conteudo_markdown='Texto só para revisão', autor=self.autor, status='pendente',
        )
        self.assertEqual(self.client.get(reverse('cronica_detail', args=[pending.slug])).status_code, 404)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('cronica_detail', args=[pending.slug])),
                            'Texto só para revisão')
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.conteudo_markdown, 'Texto publicado')
        self.assertEqual(self.cronica.revisao_edicao['estado'], 'pendente')

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
        self.assertContains(self.client.get(reverse('mundo_cronicas')),
                            'href="%s"' % reverse('cronicas_review'))

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

    def test_rejection_requires_feedback_for_initial_and_revised_story(self):
        pending = TbCronica.objects.create(
            titulo='Primeira versão', slug='primeira-versao',
            conteudo_markdown='Rascunho inicial', autor=self.autor, status='pendente',
        )
        self.client.force_login(self.staff)
        url = reverse('cronica_review_action', args=[pending.pk])
        for feedback in ('', '   ', {'texto': 'invalido'}):
            response = self.post_json(url, {'action': 'reprovar', 'feedback': feedback})
            self.assertEqual(response.status_code, 400)
            pending.refresh_from_db()
            self.assertEqual(pending.status, 'pendente')
            self.assertFalse(pending.feedback_staff)
        self.assertEqual(self.post_json(url, {
            'action': 'reprovar', 'feedback': '  Ajuste o início.  ',
            'expected_snapshot': _cronica_pending_snapshot(pending),
        }).status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.feedback_staff, 'Ajuste o início.')

        self.edit(content='Nova versão pendente')
        self.assertEqual(self.review('reprovar', '   ').status_code, 400)
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.revisao_edicao['estado'], 'pendente')
        self.assertEqual(self.cronica.conteudo_markdown, 'Texto publicado')

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
            'action': 'aprovar', 'expected_snapshot': _cronica_pending_snapshot(new_story),
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

    def test_review_queue_shows_every_proposed_editorial_field(self):
        for name in ('Norte', 'Sul'):
            TbTerritorio.objects.create(nome=name, slug=name.lower())
        TbRegiao.objects.create(nome='Serra', slug='serra', territorio='Norte')
        TbRegiao.objects.create(nome='Costa', slug='costa', territorio='Sul')
        self.client.force_login(self.autor)
        response = self.post_json(reverse('cronica_edit', args=[self.cronica.slug]), {
            'titulo': 'Nova versão', 'conteudo_markdown': 'Novo texto',
            'resumo': 'Resumo proposto', 'imagem_url': 'https://example.com/capa.png',
            'personagem_nome': 'Narrador',
            'territorio': ['Norte', 'Sul'], 'regiao': ['Serra', 'Costa'],
        })
        self.assertEqual(response.status_code, 200)
        self.client.force_login(self.staff)
        queue = self.client.get(reverse('cronicas_review'))
        self.assertContains(queue, 'Resumo proposto')
        self.assertContains(queue, 'https://example.com/capa.png')
        self.assertContains(queue, 'Norte, Sul / Serra, Costa')
        self.assertNotContains(queue, 'Resumo publicado')
        self.assertNotContains(queue, '[&quot;Norte&quot;')

    def test_invalid_author_metadata_cannot_create_or_replace_story(self):
        self.client.force_login(self.autor)
        create_url = reverse('cronica_create')
        edit_url = reverse('cronica_edit', args=[self.cronica.slug])
        for name, length in (('titulo', 201), ('resumo', 301),
                             ('imagem_url', 501), ('personagem_nome', 151)):
            payload = {'titulo': 'Válida', 'conteudo_markdown': 'Texto', name: 'x' * length}
            self.assertEqual(self.post_json(create_url, payload).status_code, 400)
            self.assertEqual(self.post_json(edit_url, payload).status_code, 400)
        self.assertFalse(TbCronica.objects.filter(titulo='Válida').exists())
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.titulo, 'Título publicado')
        self.assertEqual(self.cronica.revisao_edicao, {})

    def test_legacy_invalid_revision_cannot_overwrite_public_story(self):
        self.edit()
        self.cronica.refresh_from_db()
        revision = self.cronica.revisao_edicao
        revision['resumo'] = 'x' * 301
        self.cronica.revisao_edicao = revision
        self.cronica.save(update_fields=['revisao_edicao'])
        response = self.review('aprovar')
        self.assertEqual(response.status_code, 409)
        self.cronica.refresh_from_db()
        self.assertEqual(self.cronica.resumo, 'Resumo publicado')
        self.assertEqual(self.cronica.revisao_edicao['estado'], 'pendente')
