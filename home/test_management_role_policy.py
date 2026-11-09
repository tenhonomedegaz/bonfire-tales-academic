from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from home.gestao.role_policy import apply_policy, preview_policy
from home.gestao.workflows import can_review
from home.gestao_models import ManagementRolePolicyReceipt


class RolePolicyTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_user('policy-admin', is_superuser=True, is_staff=False)
        self.member = users.objects.create_user('policy-member')
        self.group = Group.objects.create(name='Staff')
        self.member.groups.add(self.group)
        self.external = Permission.objects.get(codename='view_tbclasse')
        self.group.permissions.add(self.external)
        self.portal = Permission.objects.get(codename='review_portal_ticket')

    def preview(self):
        return preview_policy(actor=self.admin, role='Staff', permissions=[str(self.portal.pk)],
                              reason='Equipe autorizada para atendimento.')

    def test_apply_and_replay_preserve_other_permissions_and_flags(self):
        preview = self.preview()
        self.assertFalse(self.group.permissions.filter(pk=self.portal.pk).exists())
        receipt = apply_policy(actor=self.admin, ticket=preview['ticket'])
        self.assertEqual(apply_policy(actor=self.admin, ticket=preview['ticket']).pk, receipt.pk)
        self.assertEqual(ManagementRolePolicyReceipt.objects.count(), 1)
        self.assertTrue(self.group.permissions.filter(pk=self.external.pk).exists())
        self.assertTrue(can_review(get_user_model().objects.get(pk=self.member.pk), 'ticket'))
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_staff)
        self.assertFalse(self.member.is_superuser)

    def test_deny_nonadmin_arbitrary_permission_and_stale_policy(self):
        with self.assertRaises(PermissionDenied):
            preview_policy(actor=self.member, role='Staff', permissions=[], reason='Nao autorizado')
        with self.assertRaises(ValidationError):
            preview_policy(actor=self.admin, role='Staff', permissions=[str(self.external.pk)],
                           reason='Permissao fora do escopo')
        preview = self.preview()
        self.group.permissions.clear()
        with self.assertRaises(ValidationError):
            apply_policy(actor=self.admin, ticket=preview['ticket'])
        self.assertFalse(ManagementRolePolicyReceipt.objects.exists())

    def test_http_preview_confirm_and_nonadmin_denial(self):
        url = reverse('gestao:role_policy')
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'action': 'preview', 'role': 'Staff',
            'permissions': [str(self.portal.pk)], 'reason': 'Equipe autorizada para atender.'})
        ticket = response.context['preview']['ticket']
        self.assertFalse(self.group.permissions.filter(pk=self.portal.pk).exists())
        self.assertEqual(self.client.post(url, {'action': 'confirm', 'ticket': ticket}).status_code, 302)
        self.assertTrue(self.group.permissions.filter(pk=self.portal.pk).exists())
