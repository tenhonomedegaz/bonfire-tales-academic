import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_ENVIRONMENT = (
    'POSTGRES_URL',
    'DB_ENGINE',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
    'DB_HOST',
    'DB_PORT',
)


class DatabaseSettingsTests(unittest.TestCase):
    def load_settings(self, **database_environment):
        environment = os.environ.copy()
        environment.update({name: '' for name in DATABASE_ENVIRONMENT})
        environment.update(
            {
                'DJANGO_SECRET_KEY': 'database-settings-test-key',
                'DJANGO_DEBUG': '0',
                'PYTHONIOENCODING': 'utf-8',
            }
        )
        environment.update(database_environment)
        script = textwrap.dedent(
            '''
            import json
            import bonfire.settings as settings

            database = settings.DATABASES['default']
            print(json.dumps({
                'ENGINE': database['ENGINE'],
                'NAME': database['NAME'],
                'USER': database['USER'],
                'HOST': database['HOST'],
                'PORT': database['PORT'],
            }))
            '''
        )
        return subprocess.run(
            [sys.executable, '-c', script],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding='utf-8',
        )

    def assert_configuration_error(self, result, message):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)

    def test_configuration_is_required(self):
        result = self.load_settings()

        self.assert_configuration_error(result, 'Configuração PostgreSQL obrigatória')

    def test_sqlite_engine_is_rejected(self):
        result = self.load_settings(DB_ENGINE='django.db.backends.sqlite3')

        self.assert_configuration_error(result, 'Configuração PostgreSQL obrigatória')

    def test_invalid_postgres_url_is_rejected(self):
        result = self.load_settings(POSTGRES_URL='mysql://localhost/bonfire')

        self.assert_configuration_error(result, 'POSTGRES_URL deve ser uma URL PostgreSQL válida')

    def test_postgres_url_with_invalid_port_is_rejected(self):
        result = self.load_settings(POSTGRES_URL='postgres://localhost:not-a-port/bonfire')

        self.assert_configuration_error(result, 'POSTGRES_URL contém dados inválidos')

    def test_invalid_url_does_not_expose_credentials(self):
        result = self.load_settings(
            POSTGRES_URL='postgres://user:secret-sentinel@invalid\u2100host/bonfire',
        )

        self.assert_configuration_error(result, 'POSTGRES_URL contém dados inválidos')
        self.assertNotIn('secret-sentinel', result.stderr)
        self.assertNotIn('secret-sentinel', result.stdout)

    def test_postgres_url_configures_postgresql(self):
        result = self.load_settings(
            POSTGRES_URL='postgres://db.example.test:5544/bonfire',
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'bonfire',
                'USER': 'postgres',
                'HOST': 'db.example.test',
                'PORT': '5544',
            },
        )

    def test_db_variables_configure_postgresql(self):
        result = self.load_settings(
            DB_ENGINE='postgresql',
            DB_NAME='bonfire',
            DB_USER='test-user',
            DB_PASSWORD='test-password',
            DB_HOST='db.example.test',
            DB_PORT='5544',
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'bonfire',
                'USER': 'test-user',
                'HOST': 'db.example.test',
                'PORT': '5544',
            },
        )

    def test_legacy_db_engine_uses_legacy_defaults(self):
        result = self.load_settings(DB_ENGINE='django.db.backends.postgresql')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'postgres',
                'USER': 'postgres',
                'HOST': 'localhost',
                'PORT': '5432',
            },
        )
