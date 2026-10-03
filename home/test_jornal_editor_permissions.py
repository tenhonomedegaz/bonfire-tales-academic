"""Jornal publication requires explicit editorial permissions."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import TbJornal


class JornalEditorPermissionTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            'jornal-staff', 'jornal-staff@example.invalid', 'test-pass', is_staff=True
        )
        self.client.force_login(self.staff)
        self.article = TbJornal.objects.create(
            titulo='Artigo existente', slug='artigo-existente', conteudo_markdown='Original'
        )
        self.create_url = reverse('jornal_create')
        self.update_url = reverse('jornal_update', args=[self.article.slug])

    def grant(self, codename):
        self.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename=codename
        ))

    def post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json')

    def test_staff_without_jornal_permissions_can_only_read(self):
        listing = self.client.get(reverse('mundo_jornal'))
        detail = self.client.get(reverse('jornal_detail', args=[self.article.slug]))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(listing, self.create_url)
        self.assertNotContains(detail, 'id="btnEditArticle"')
        self.assertEqual(self.client.get(self.create_url).status_code, 403)
        self.assertEqual(self.post_json(self.create_url, {'titulo': 'Indevido'}).status_code, 403)
        self.assertEqual(self.post_json(self.update_url, {'titulo': 'Indevido'}).status_code, 403)
        self.article.refresh_from_db()
        self.assertEqual(self.article.titulo, 'Artigo existente')
        self.assertFalse(TbJornal.objects.filter(titulo='Indevido').exists())

    def test_add_and_change_permissions_allow_only_their_respective_actions(self):
        self.grant('add_tbjornal')
        listing = self.client.get(reverse('mundo_jornal'))
        self.assertContains(listing, self.create_url)
        self.assertEqual(self.client.get(self.create_url).status_code, 200)
        created = self.post_json(self.create_url, {'titulo': 'Artigo autorizado'})
        self.assertEqual(created.status_code, 200)
        self.assertTrue(TbJornal.objects.filter(slug='artigo-autorizado').exists())
        self.assertEqual(self.post_json(self.update_url, {'titulo': 'Indevido'}).status_code, 403)

        self.staff.user_permissions.remove(Permission.objects.get(
            content_type__app_label='home', codename='add_tbjornal'
        ))
        self.grant('change_tbjornal')
        self.assertNotContains(self.client.get(reverse('mundo_jornal')), self.create_url)
        self.assertEqual(self.post_json(self.create_url, {'titulo': 'Indevido'}).status_code, 403)
        detail = self.client.get(reverse('jornal_detail', args=[self.article.slug]))
        self.assertContains(detail, 'id="btnEditArticle"')
        changed = self.post_json(self.update_url, {'titulo': 'Artigo revisado'})
        self.assertEqual(changed.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.titulo, 'Artigo revisado')
