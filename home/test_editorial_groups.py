"""Future account cargos grant only their editorial flow, without admin access."""

import json
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from home.models import TbCronica, TbJornal


class EditorialGroupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # A reusable test database can lose data-migration rows after a flush.
        migration = import_module('home.migrations.0133_editorial_groups')
        migration.create_editorial_groups(
            apps, SimpleNamespace(connection=connection),
        )
        users = get_user_model()
        cls.author = users.objects.create_user('group-author')
        cls.journalist = users.objects.create_user('group-journalist')
        cls.staff = users.objects.create_user('group-staff')
        cls.loremaster = users.objects.create_user('group-loremaster')
        cls.reader = users.objects.create_user('group-reader')
        cls.story = TbCronica.objects.create(
            titulo='Relato para triagem', slug='relato-para-triagem',
            conteudo_markdown='Texto original', autor=cls.author, status='pendente',
        )

    def test_groups_exist_with_narrow_permissions_and_no_automatic_members(self):
        expected = {
            'Jornalista': {'add_tbjornal', 'change_tbjornal'},
            'Staff': {'triage_tbcronica'},
            'Loremaster': {'change_tbcronica'},
        }
        for name, codenames in expected.items():
            group = Group.objects.get(name=name)
            self.assertEqual(set(group.permissions.values_list('codename', flat=True)), codenames)
            self.assertFalse(group.user_set.exists())
        self.assertFalse(self.reader.is_staff)
        self.assertFalse(self.reader.has_perm('home.add_tbjornal'))

    def test_po_can_see_groups_and_user_assignment_in_superuser_admin(self):
        admin = get_user_model().objects.create_superuser('group-admin', password='test')
        self.client.force_login(admin)
        groups = self.client.get(reverse('admin:auth_group_changelist'))
        self.assertEqual(groups.status_code, 200)
        for name in ('Jornalista', 'Staff', 'Loremaster'):
            self.assertContains(groups, name)
        user_form = self.client.get(reverse('admin:auth_user_change', args=[self.reader.pk]))
        self.assertContains(user_form, 'groups')
        self.assertFalse(self.reader.groups.exists())

    def test_future_group_members_publish_and_review_without_operational_admin(self):
        self.journalist.groups.add(Group.objects.get(name='Jornalista'))
        self.staff.groups.add(Group.objects.get(name='Staff'))
        self.loremaster.groups.add(Group.objects.get(name='Loremaster'))
        queue_url = reverse('cronicas_review')
        journal_url = reverse('jornal_create')
        decision_url = reverse('cronica_review_action', args=[self.story.pk])
        admin_url = reverse('admin:index')

        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(journal_url).status_code, 403)
        self.assertEqual(self.client.get(queue_url).status_code, 403)

        self.client.force_login(self.journalist)
        self.assertFalse(self.journalist.is_staff)
        self.assertContains(self.client.get(reverse('mundo_jornal')), journal_url)
        self.assertEqual(self.client.get(journal_url).status_code, 200)
        created = self.client.post(journal_url, json.dumps({
            'titulo': 'Jornal do cargo', 'conteudo_markdown': 'Noticia autorizada',
        }), content_type='application/json')
        self.assertEqual(created.status_code, 200)
        article = TbJornal.objects.get(slug=created.json()['slug'])
        self.assertEqual(article.autor_id, self.journalist.pk)
        detail = self.client.get(reverse('jornal_detail', args=[article.slug]))
        self.assertContains(detail, 'Editar Artigo')
        updated = self.client.post(reverse('jornal_update', args=[article.slug]), json.dumps({
            'conteudo_markdown': 'Noticia editada',
            'expected_edit': article.data_edicao.isoformat(),
        }), content_type='application/json')
        self.assertEqual(updated.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.conteudo_markdown, 'Noticia editada')
        self.assertEqual(self.client.get(queue_url).status_code, 403)
        self.assertEqual(self.client.post(decision_url, '{}', content_type='application/json').status_code, 403)
        self.assertNotEqual(self.client.get(admin_url).status_code, 200)

        self.client.force_login(self.staff)
        self.assertFalse(self.staff.is_staff)
        self.assertContains(self.client.get(reverse('mundo_cronicas')), queue_url)
        queue = self.client.get(queue_url)
        self.assertEqual(queue.status_code, 200)
        self.assertTrue(queue.context['can_triage'])
        self.assertFalse(queue.context['can_decide_forwarded'])
        self.assertEqual(self.client.get(journal_url).status_code, 403)
        self.assertEqual(self.client.post(reverse('cronica_destaque', args=[self.story.pk]), {
            'destaque': 'true',
        }).status_code, 403)
        self.assertNotEqual(self.client.get(admin_url).status_code, 200)
        snapshot = queue.context['pendentes'][0].review_snapshot
        referred = self.client.post(decision_url, json.dumps({
            'action': 'encaminhar', 'feedback': 'Verificar a origem do relato',
            'expected_snapshot': snapshot,
        }), content_type='application/json')
        self.assertEqual(referred.status_code, 200)
        self.assertEqual(self.client.post(decision_url, json.dumps({
            'action': 'aprovar', 'expected_snapshot': snapshot,
        }), content_type='application/json').status_code, 403)

        self.client.force_login(self.loremaster)
        self.assertFalse(self.loremaster.is_staff)
        queue = self.client.get(queue_url)
        self.assertEqual(queue.status_code, 200)
        self.assertFalse(queue.context['can_triage'])
        self.assertTrue(queue.context['can_decide_forwarded'])
        self.assertEqual(self.client.get(journal_url).status_code, 403)
        self.assertNotEqual(self.client.get(admin_url).status_code, 200)
        approved = self.client.post(decision_url, json.dumps({
            'action': 'aprovar', 'expected_snapshot': snapshot,
        }), content_type='application/json')
        self.assertEqual(approved.status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'aprovada')
        self.assertEqual(self.story.revisado_por_id, self.loremaster.pk)
        self.assertContains(self.client.get(reverse('cronica_detail', args=[self.story.slug])),
                            'Destacar editorialmente')
        self.assertEqual(self.client.post(reverse('cronica_destaque', args=[self.story.pk]), {
            'destaque': 'true',
        }).status_code, 302)
        self.story.refresh_from_db()
        self.assertTrue(self.story.destaque_editorial)
        self.assertEqual(self.client.get(reverse('jornal_detail', args=[article.slug])).status_code, 200)
