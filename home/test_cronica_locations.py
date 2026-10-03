"""Location integrity from Chronicle authorship through editorial approval."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from home.models import TbCronica, TbRegiao, TbTerritorio
from home.views import _cronica_pending_snapshot


class ChronicleLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.author = user.objects.create_user('author-location', password='test')
        cls.reviewer = user.objects.create_user('reviewer-location', password='test', is_staff=True)
        cls.reviewer.user_permissions.add(Permission.objects.get(
            codename='change_tbcronica', content_type__app_label='home',
        ))
        for name in ('Norte', 'Sul'):
            TbTerritorio.objects.create(nome=name, slug=name.lower())
        TbRegiao.objects.create(nome='Serra', slug='serra', territorio='Norte')
        TbRegiao.objects.create(nome='Costa', slug='costa', territorio='Sul')
        cls.published = TbCronica.objects.create(
            titulo='História publicada', slug='historia-localizada',
            conteudo_markdown='Texto público', autor=cls.author, status='aprovada',
            territorio='Norte', regiao='Serra',
        )

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def test_create_rejects_unknown_or_mismatched_location_and_publishes_valid_one(self):
        self.client.force_login(self.author)
        url = reverse('cronica_create')
        base = {'titulo': 'Viagem', 'conteudo_markdown': 'Relato'}
        for location in (
            {'territorio': ['Desconhecido'], 'regiao': []},
            {'territorio': ['Norte'], 'regiao': ['Costa']},
            {'territorio': ['Norte'], 'regiao': ['Inexistente']},
            {'territorio': {'nome': 'Norte'}, 'regiao': []},
        ):
            with self.subTest(location=location):
                self.assertEqual(self.post_json(url, {**base, **location}).status_code, 400)
                self.assertFalse(TbCronica.objects.filter(titulo='Viagem').exists())

        response = self.post_json(url, {
            **base, 'territorio': ['Norte', 'Sul'], 'regiao': ['Serra', 'Costa'],
        })
        self.assertEqual(response.status_code, 200)
        story = TbCronica.objects.get(slug=response.json()['slug'])
        self.assertEqual(story.territorios_lista, ['Norte', 'Sul'])
        self.assertEqual(story.regioes_lista, ['Serra', 'Costa'])
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post_json(reverse('cronica_review_action', args=[story.pk]), {
            'action': 'aprovar', 'expected_snapshot': _cronica_pending_snapshot(story),
        }).status_code, 200)
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[story.slug])), 'Norte, Sul')
        self.assertContains(self.client.get(reverse('mundo_cronicas') + '?territorio=Norte'), 'Viagem')

    def test_invalid_edit_and_stale_revision_keep_published_location(self):
        self.client.force_login(self.author)
        edit_url = reverse('cronica_edit', args=[self.published.slug])
        payload = {'titulo': 'Novo título', 'conteudo_markdown': 'Novo texto',
                   'territorio': ['Norte'], 'regiao': ['Costa']}
        self.assertEqual(self.post_json(edit_url, payload).status_code, 400)
        self.published.refresh_from_db()
        self.assertEqual(self.published.regiao, 'Serra')
        self.assertEqual(self.published.revisao_edicao, {})

        payload['regiao'] = ['Serra']
        self.assertEqual(self.post_json(edit_url, payload).status_code, 200)
        self.published.refresh_from_db()
        revision = self.published.revisao_edicao
        revision['regiao'] = 'Costa'  # legacy or externally corrupted draft
        self.published.revisao_edicao = revision
        self.published.save(update_fields=['revisao_edicao'])
        self.client.force_login(self.reviewer)
        response = self.post_json(reverse('cronica_review_action', args=[self.published.pk]), {
            'action': 'aprovar', 'expected_revision': revision['submetida_em'],
        })
        self.assertEqual(response.status_code, 409)
        self.published.refresh_from_db()
        self.assertEqual(self.published.regiao, 'Serra')
        self.assertEqual(self.published.revisao_edicao['estado'], 'pendente')

    def test_initial_legacy_story_with_unknown_location_cannot_be_approved(self):
        pending = TbCronica.objects.create(
            titulo='Rascunho antigo', slug='rascunho-antigo-local',
            conteudo_markdown='Texto', autor=self.author, status='pendente',
            territorio='Desconhecido', regiao='Serra',
        )
        self.client.force_login(self.reviewer)
        response = self.post_json(reverse('cronica_review_action', args=[pending.pk]), {
            'action': 'aprovar', 'expected_snapshot': _cronica_pending_snapshot(pending),
        })
        self.assertEqual(response.status_code, 409)
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'pendente')
