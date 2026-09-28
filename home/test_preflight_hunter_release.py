import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase
from django.db.migrations import Migration

from .models import TbPersonagem


class HunterReleasePreflightTests(TransactionTestCase):
    def test_pending_migration_is_reported_without_applying_it(self):
        output = StringIO()
        with patch('home.management.commands.preflight_hunter_release.MigrationExecutor.migration_plan',
                   return_value=[(Migration('0113_hunter_regularization', 'home'), False)]):
            call_command('preflight_hunter_release', stdout=output)
        self.assertEqual(json.loads(output.getvalue())['pending_migrations'],
                         ['home.0113_hunter_regularization'])

    def test_connected_postgres_inventory_is_read_only_and_identifies_pending_migrations(self):
        owner = get_user_model().objects.create_user(username='hunter-preflight')
        person = TbPersonagem.objects.create(dono=owner, nome='Preservar no preflight')
        before = list(TbPersonagem.objects.values_list('pk', 'nome'))
        output = StringIO()
        call_command('preflight_hunter_release', stdout=output)
        report = json.loads(output.getvalue())

        self.assertEqual(report['database']['vendor'], 'postgresql')
        self.assertTrue(report['database']['name'])
        self.assertNotIn('password', report['database'])
        self.assertEqual(report['counts'][TbPersonagem._meta.db_table], 1)
        self.assertEqual(report['missing_tables'], [])
        self.assertEqual(report['unvalidated_foreign_keys'], [])
        self.assertEqual(report['pending_migrations'], [])
        self.assertIn(['home', '0113_hunter_regularization'], report['applied_migrations'])
        self.assertEqual(list(TbPersonagem.objects.values_list('pk', 'nome')), before)
        self.assertTrue(TbPersonagem.objects.filter(pk=person.pk).exists())
