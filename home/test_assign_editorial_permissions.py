"""Account selection is explicit and cannot partially grant editorial access."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse


class AssignEditorialPermissionsTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.journalist = users.objects.create_user('journalist', password='test', is_staff=True)
        self.staff = users.objects.create_user('staff', password='test', is_staff=True)
        self.loremaster = users.objects.create_user('loremaster', password='test', is_staff=True)

    def test_preview_does_not_grant_and_apply_grants_only_selected_roles(self):
        out = StringIO()
        arguments = {'journalist': ['journalist'], 'staff': ['staff'],
                     'loremaster': ['loremaster']}
        call_command('assign_editorial_permissions', stdout=out, **arguments)
        self.assertIn('Preview only', out.getvalue())
        for user in (self.journalist, self.staff, self.loremaster):
            self.assertFalse(user.user_permissions.exists())

        call_command('assign_editorial_permissions', apply=True, stdout=StringIO(), **arguments)
        expected = {
            self.journalist: {'add_tbjornal', 'change_tbjornal'},
            self.staff: {'triage_tbcronica'},
            self.loremaster: {'change_tbcronica'},
        }
        for user, codenames in expected.items():
            self.assertEqual(set(user.user_permissions.values_list('codename', flat=True)), codenames)
            self.assertFalse(user.is_superuser)
        for user, allowed, denied in (
            (self.journalist, 'jornal_create', 'cronicas_review'),
            (self.staff, 'cronicas_review', 'jornal_create'),
            (self.loremaster, 'cronicas_review', 'jornal_create'),
        ):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse(allowed)).status_code, 200)
            self.assertEqual(self.client.get(reverse(denied)).status_code, 403)
            self.assertNotEqual(self.client.get(reverse('admin:index')).status_code, 200)
        call_command('assign_editorial_permissions', apply=True, stdout=StringIO(), **arguments)
        self.assertEqual(self.staff.user_permissions.count(), 1)

    def test_missing_account_rejects_entire_batch(self):
        with self.assertRaisesMessage(CommandError, 'Unknown account(s): missing'):
            call_command('assign_editorial_permissions', journalist=['journalist'],
                         staff=['missing'], apply=True, stdout=StringIO())
        self.assertFalse(self.journalist.user_permissions.exists())

    def test_inactive_account_rejects_entire_batch(self):
        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])
        with self.assertRaisesMessage(CommandError, 'Inactive account(s): staff'):
            call_command('assign_editorial_permissions', journalist=['journalist'],
                         staff=['staff'], apply=True, stdout=StringIO())
        self.assertFalse(self.journalist.user_permissions.exists())

    def test_nonstaff_account_rejects_entire_batch(self):
        self.staff.is_staff = False
        self.staff.save(update_fields=['is_staff'])
        with self.assertRaisesMessage(CommandError, 'Accounts without is_staff: staff'):
            call_command('assign_editorial_permissions', journalist=['journalist'],
                         staff=['staff'], apply=True, stdout=StringIO())
        self.assertFalse(self.journalist.user_permissions.exists())
