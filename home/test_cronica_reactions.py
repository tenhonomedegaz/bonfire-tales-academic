import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.deploy_sync import MEMORY_MODELS
from home.models import TbCronica, TbCronicaCurtida


class CronicaReactionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.autor = user.objects.create_user('autor-reacao', password='senha')
        cls.leitor = user.objects.create_user('leitor-reacao', password='senha')
        cls.outro = user.objects.create_user('outro-reacao', password='senha')
        cls.publicada = TbCronica.objects.create(
            titulo='História publicada', slug='historia-publicada',
            conteudo_markdown='Texto público', autor=cls.autor, status='aprovada',
        )
        cls.pendente = TbCronica.objects.create(
            titulo='História pendente', slug='historia-pendente',
            conteudo_markdown='Texto em revisão', autor=cls.autor, status='pendente',
        )

    def react(self, cronica, value):
        return self.client.post(
            reverse('cronica_curtir', args=[cronica.pk]),
            data=json.dumps({'curtido': value}), content_type='application/json',
        )

    def test_desired_state_is_idempotent_and_returns_official_count(self):
        self.client.force_login(self.leitor)
        for _ in range(2):
            response = self.react(self.publicada, True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['curtidas'], 1)
            self.assertTrue(response.json()['curtido'])
        self.assertEqual(TbCronicaCurtida.objects.count(), 1)
        for _ in range(2):
            response = self.react(self.publicada, False)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['curtidas'], 0)
            self.assertFalse(response.json()['curtido'])
        self.assertFalse(TbCronicaCurtida.objects.exists())

    def test_each_reader_has_one_reaction_and_public_count_is_visible(self):
        self.client.force_login(self.leitor)
        self.react(self.publicada, True)
        detail = self.client.get(reverse('cronica_detail', args=[self.publicada.slug]))
        self.assertContains(detail, 'aria-pressed="true"')
        self.assertContains(detail, '1 curtida')
        self.client.force_login(self.outro)
        self.assertEqual(self.react(self.publicada, True).json()['curtidas'], 2)
        self.client.logout()
        detail = self.client.get(reverse('cronica_detail', args=[self.publicada.slug]))
        self.assertContains(detail, '2 curtidas')
        self.assertNotContains(detail, 'id="cronica-like-form"')
        self.assertEqual(TbCronicaCurtida.objects.count(), 2)

    def test_author_and_unapproved_story_cannot_receive_new_reactions(self):
        self.client.force_login(self.autor)
        self.assertEqual(self.react(self.publicada, True).status_code, 400)
        self.client.force_login(self.leitor)
        self.assertEqual(self.react(self.pendente, True).status_code, 404)
        self.assertFalse(TbCronicaCurtida.objects.exists())

    def test_anonymous_and_invalid_payload_do_not_change_state(self):
        self.assertEqual(self.react(self.publicada, True).status_code, 302)
        self.client.force_login(self.leitor)
        for value in ('true', 1, None):
            self.assertEqual(self.react(self.publicada, value).status_code, 400)
        self.assertFalse(TbCronicaCurtida.objects.exists())

    def test_story_reactions_are_production_memory(self):
        self.assertIn('TbCronicaCurtida', MEMORY_MODELS)

    def test_html_form_works_without_javascript(self):
        self.client.force_login(self.leitor)
        url = reverse('cronica_curtir', args=[self.publicada.pk])
        response = self.client.post(url, {'curtido': 'true'})
        self.assertRedirects(response, reverse('cronica_detail', args=[self.publicada.slug]))
        self.assertTrue(TbCronicaCurtida.objects.filter(cronica=self.publicada, leitor=self.leitor).exists())
        response = self.client.post(url, {'curtido': 'false'})
        self.assertRedirects(response, reverse('cronica_detail', args=[self.publicada.slug]))
        self.assertFalse(TbCronicaCurtida.objects.filter(cronica=self.publicada, leitor=self.leitor).exists())
