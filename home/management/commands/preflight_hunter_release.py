"""Read-only inventory of the connected PostgreSQL before the Hunter release."""

import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from home.deploy_sync import CONTENT_MODELS, MEMORY_MODELS


class Command(BaseCommand):
    help = 'Report database identity, migration state and release-critical row counts without writes.'

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('O preflight do Caçador exige PostgreSQL.')

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    cursor.execute('SELECT current_database(), inet_server_addr()::text, '
                                   'inet_server_port(), current_user')
                    database, host, port, user = cursor.fetchone()
                    cursor.execute("SELECT tablename FROM pg_catalog.pg_tables "
                                   "WHERE schemaname = current_schema()")
                    tables = {row[0] for row in cursor.fetchall()}
                    cursor.execute("SELECT conrelid::regclass::text, conname FROM pg_constraint "
                                   "WHERE contype = 'f' AND NOT convalidated ORDER BY 1, 2")
                    invalid_fks = [list(row) for row in cursor.fetchall()]

                models = apps.get_app_config('home')
                counts = {}
                missing = []
                for name in dict.fromkeys(MEMORY_MODELS + CONTENT_MODELS):
                    table = models.get_model(name)._meta.db_table
                    if table not in tables:
                        missing.append(table)
                        continue
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT COUNT(*) FROM %s' % connection.ops.quote_name(table))
                        counts[table] = cursor.fetchone()[0]

                migrations = []
                if 'django_migrations' in tables:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT app, name FROM django_migrations ORDER BY app, name')
                        migrations = [list(row) for row in cursor.fetchall()]
                else:
                    missing.append('django_migrations')

                executor = MigrationExecutor(connection)
                pending = ['%s.%s' % (migration.app_label, migration.name) for migration, backwards in
                           executor.migration_plan(executor.loader.graph.leaf_nodes())
                           if not backwards]
        except Exception as exc:
            raise CommandError('Preflight falhou sem alterar o banco: %s' % exc) from exc

        result = {'database': {'name': database, 'host': host, 'port': port,
                               'user': user, 'vendor': connection.vendor},
                  'counts': counts, 'missing_tables': sorted(set(missing)),
                  'applied_migrations': migrations, 'pending_migrations': pending,
                  'unvalidated_foreign_keys': invalid_fks}
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        if missing or invalid_fks:
            raise CommandError('Preflight encontrou tabelas ausentes ou FKs não validadas.')
