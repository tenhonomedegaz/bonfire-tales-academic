from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from home.gestao.roles import access_summary, apply_roles, preview_roles
from home.gestao_models import ManagementRoleReceipt


class ManagementRoleTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_user('roles-admin', is_superuser=True, is_staff=False)
        self.target = users.objects.create_user('roles-target')
        self.other = users.objects.create_user('roles-other')
        self.staff = Group.objects.create(name='Staff')
        self.custom = Group.objects.create(name='Other membership')
        self.target.groups.add(self.custom)
        self.direct = Permission.objects.get(content_type__app_label='home',
                                              codename='view_tbclasse')
        self.target.user_permissions.add(self.direct)
        self.grant_permission = Permission.objects.get(content_type__app_label='home',
                                                       codename='view_management_people')
        self.staff.permissions.add(self.grant_permission)

    def preview(self):
        return preview_roles(actor=self.admin, user_id=self.target.pk,
                             roles=['Staff', 'Rulesmaster'], reason='Equipe aprovada pelo administrador.')

    def test_preview_confirm_and_replay_preserve_direct_permissions_and_flags(self):
        preview = self.preview()
        self.assertEqual(preview['added'], ['Rulesmaster', 'Staff'])
        self.assertFalse(Group.objects.filter(name='Rulesmaster').exists())
        self.assertFalse(ManagementRoleReceipt.objects.exists())
        receipt = apply_roles(actor=self.admin, user_id=self.target.pk, ticket=preview['ticket'])
        replay = apply_roles(actor=self.admin, user_id=self.target.pk, ticket=preview['ticket'])
        self.assertEqual(receipt.pk, replay.pk)
        self.assertEqual(ManagementRoleReceipt.objects.count(), 1)
        self.target.refresh_from_db()
        self.assertEqual(set(self.target.groups.values_list('name', flat=True)),
                         {'Staff', 'Rulesmaster', 'Other membership'})
        self.assertFalse(self.target.is_staff)
        self.assertFalse(self.target.is_superuser)
        self.assertEqual(list(self.target.user_permissions.all()), [self.direct])
        self.assertFalse(Group.objects.get(name='Rulesmaster').permissions.exists())
        summary = access_summary(self.target)
        self.assertTrue(any('Permissão individual' in row['sources'] for row in summary))
        self.assertTrue(any('Staff' in row['sources'] for row in summary))

    def test_stale_permissions_and_revoked_administrator_are_rechecked(self):
        preview = self.preview()
        self.staff.permissions.clear()
        with self.assertRaises(ValidationError):
            apply_roles(actor=self.admin, user_id=self.target.pk, ticket=preview['ticket'])
        self.assertFalse(ManagementRoleReceipt.objects.exists())
        preview = self.preview()
        get_user_model().objects.filter(pk=self.admin.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            apply_roles(actor=self.admin, user_id=self.target.pk, ticket=preview['ticket'])
        self.assertFalse(self.target.groups.filter(name='Staff').exists())

    def test_nonadmin_and_cross_person_ticket_are_denied(self):
        self.other.user_permissions.add(self.grant_permission)
        with self.assertRaises(PermissionDenied):
            preview_roles(actor=self.other, user_id=self.target.pk, roles=['Staff'], reason='Denied action')
        preview = self.preview()
        with self.assertRaises(PermissionDenied):
            apply_roles(actor=self.admin, user_id=self.other.pk, ticket=preview['ticket'])
        self.client.force_login(self.other)
        url = reverse('gestao:roles', args=[self.target.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'action': 'preview'}).status_code, 403)

    def test_http_flow_requires_preview_and_csrf_and_exposes_access_origin(self):
        self.client.force_login(self.admin)
        url = reverse('gestao:roles', args=[self.target.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rulesmaster')
        self.assertContains(response, 'Voltar ao site')
        self.assertNotContains(response, 'target="_blank" href="/gestao/')
        response = self.client.post(url, {'action': 'preview', 'roles': ['Staff'],
                                        'reason': 'Autorizado para a equipe.'})
        self.assertEqual(response.status_code, 200)
        ticket = response.context['preview']['ticket']
        self.assertFalse(self.target.groups.filter(name='Staff').exists())
        response = self.client.post(url, {'action': 'confirm', 'ticket': ticket})
        self.assertRedirects(response, reverse('gestao:person', args=[self.target.pk]) + '?people_page=1',
                             fetch_redirect_response=False)
        response = self.client.get(reverse('gestao:person', args=[self.target.pk]))
        self.assertContains(response, 'Permissão individual')
        self.assertContains(response, 'Autorizado para a equipe.')
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(url, {'action': 'confirm', 'ticket': ticket}).status_code, 403)
