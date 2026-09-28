import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.conquistas import conceder_conquista, registrar_publicacao_cronica
from home.models import (
    TbConquista, TbCosmetico, TbCronica, TbEventoConquista,
    TbUsuarioConquista, TbUsuarioCosmetico,
)


RULE = {'schema_version': 1, 'metric': 'stories_published',
        'scope': 'account', 'operator': 'gte', 'target': 1}


class FirstPublishedStoryAchievementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.author = users.create_user('story-achievement-author', password='x')
        cls.staff = users.create_user('story-achievement-staff', password='x', is_staff=True)

    def rule(self):
        reward = TbCosmetico.objects.create(slug='story-reward-test', nome='Prêmio teste',
                                             tipo='badge', origem='conquista')
        rule = TbConquista(slug='first-story-test', nome='Primeira crônica teste',
                           criterio='automatico', criterio_json=RULE, recompensa=reward)
        rule.full_clean()
        rule.save()
        return rule

    def story(self, slug, status='pendente'):
        return TbCronica.objects.create(titulo=slug, slug=slug,
                                        conteudo_markdown='Uma crônica de teste.',
                                        autor=self.author, status=status)

    def review(self, story, action):
        self.client.force_login(self.staff)
        return self.client.post(reverse('cronica_review_action', args=[story.pk]),
                                data=json.dumps({'action': action}),
                                content_type='application/json')

    def test_only_initial_approval_awards_once_with_auditable_fact(self):
        rule = self.rule()
        manual = TbConquista.objects.create(slug='story-manual-test',
            nome='Manual', criterio='manual')
        self.assertTrue(conceder_conquista(self.author, manual))
        story = self.story('first-story')
        self.assertEqual(self.review(story, 'reprovar').status_code, 200)
        self.assertFalse(TbEventoConquista.objects.exists())
        story.status = 'pendente'
        story.save(update_fields=['status'])
        self.assertEqual(self.review(story, 'aprovar').status_code, 200)
        story.refresh_from_db()
        event = TbEventoConquista.objects.get(tipo='story_published')
        grant = TbUsuarioConquista.objects.get(user=self.author, conquista=rule)
        self.assertEqual(event.chave_origem, f'cronica:{story.pk}:publicada')
        self.assertEqual(event.ocorrido_em, story.data_publicacao)
        self.assertEqual(grant.evidencia_json['evento_id'], str(event.pk))
        self.assertEqual(grant.definicao_json, RULE)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=self.author, cosmetico=rule.recompensa).exists())
        self.assertEqual(registrar_publicacao_cronica(story).pk, event.pk)
        self.assertEqual(self.review(story, 'aprovar').status_code, 409)
        self.client.force_login(self.author)
        edited = self.client.post(reverse('cronica_edit', args=[story.slug]),
            data=json.dumps({'titulo': 'Primeira crônica revisada',
                             'conteudo_markdown': 'Texto revisado', 'resumo': 'Resumo',
                             'territorio': [], 'regiao': []}),
            content_type='application/json')
        self.assertEqual(edited.status_code, 200)
        story.refresh_from_db()
        self.client.force_login(self.staff)
        approved_revision = self.client.post(reverse('cronica_review_action', args=[story.pk]),
            data=json.dumps({'action': 'aprovar',
                             'expected_revision': story.revisao_edicao['submetida_em']}),
            content_type='application/json')
        self.assertEqual(approved_revision.status_code, 200)
        self.assertEqual(TbEventoConquista.objects.filter(tipo='story_published').count(), 1)
        second = self.story('second-story')
        self.assertEqual(self.review(second, 'aprovar').status_code, 200)
        self.assertEqual(TbEventoConquista.objects.filter(tipo='story_published').count(), 2)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=self.author, conquista=rule).count(), 1)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(
            user=self.author, cosmetico=rule.recompensa).count(), 1)
        self.assertTrue(TbUsuarioConquista.objects.filter(user=self.author, conquista=manual).exists())
        self.client.logout()
        self.assertContains(self.client.get(reverse('public_profile', args=[self.author.username])),
                            rule.nome)

    def test_existing_published_story_prevents_false_first_award(self):
        rule = self.rule()
        self.story('old-story', status='aprovada')
        newer = self.story('new-story')
        self.assertEqual(self.review(newer, 'aprovar').status_code, 200)
        self.assertEqual(TbEventoConquista.objects.filter(tipo='story_published').count(), 1)
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.author, conquista=rule).exists())

    def test_award_failure_rolls_back_publication_and_event(self):
        self.rule()
        story = self.story('rollback-story')
        self.client.raise_request_exception = False
        try:
            with patch('home.conquistas.conceder_conquista', side_effect=RuntimeError('falha de teste')):
                response = self.review(story, 'aprovar')
        finally:
            self.client.raise_request_exception = True
        self.assertEqual(response.status_code, 500)
        story.refresh_from_db()
        self.assertEqual(story.status, 'pendente')
        self.assertFalse(TbEventoConquista.objects.exists())
        self.assertFalse(TbUsuarioConquista.objects.exists())

    def test_inactive_rule_keeps_fact_without_award(self):
        rule = self.rule()
        rule.ativo = False
        rule.save(update_fields=['ativo'])
        self.assertEqual(self.review(self.story('inactive-story'), 'aprovar').status_code, 200)
        self.assertEqual(TbEventoConquista.objects.filter(tipo='story_published').count(), 1)
        self.assertFalse(TbUsuarioConquista.objects.exists())
