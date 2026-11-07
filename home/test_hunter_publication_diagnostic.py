"""Protected publication status and fail-closed Hunter route."""
import time

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import TbClassPublication, TbClasse


class HunterPublicationDiagnosticTests(TestCase):
    def setUp(self):
        self.url = reverse('admin:hunter_publication_status')
        self.admin = User.objects.create_superuser('publication-admin', 'a@example.com', 'x')
        self.staff = User.objects.create_user('publication-staff', 's@example.com', 'x', is_staff=True)

    def unlock(self):
        session = self.client.session
        session['admin_console_authenticated_at'] = time.time()
        session.save()

    def test_requires_admin_login_superuser_and_console_unlock(self):
        self.assertNotEqual(self.client.get(self.url).status_code, 200)
        self.client.force_login(self.staff)
        self.unlock()
        self.assertNotEqual(self.client.get(self.url).status_code, 200)
        self.client.force_login(self.admin)
        session = self.client.session
        session.pop('admin_console_authenticated_at', None)
        session.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.unlock()
        self.assertEqual(self.client.get(self.url).status_code, 200)
        session = self.client.session
        session['admin_console_authenticated_at'] = time.time() - 901
        session.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_reports_missing_config_and_missing_ruleset_without_data(self):
        self.client.force_login(self.admin)
        self.unlock()
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=''):
            self.assertEqual(self.client.get(self.url).json()['code'], 'class_missing')
            self.assertEqual(self.client.get(reverse('classe_detail', args=['cacador'])).status_code, 404)
        # A class identity is needed to distinguish missing config from a
        # missing class; neither branch needs a sealed catalog.
        classe, _ = TbClasse.objects.get_or_create(
            slug='cacador', defaults={'nome': 'Caçador'})
        TbClassPublication.objects.filter(id_classe=classe).delete()
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=''):
            result = self.client.get(self.url).json()
            self.assertEqual(result, {'schema': 1, 'published': False,
                                      'code': 'config_missing', 'checksum_prefix': None})
            self.assertEqual(self.client.get(reverse('classe_detail', args=['cacador'])).status_code, 503)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='a' * 64):
            result = self.client.get(self.url).json()
            self.assertEqual(result['code'], 'ruleset_missing')
            self.assertNotIn('a' * 64, str(result))
