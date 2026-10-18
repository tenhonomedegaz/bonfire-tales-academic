"""Database identity gate for G01 writes approved only in isolated DEV."""

from django.core.management.base import CommandError
from django.db import connection


ALLOWED_DATABASES = {
    'bonfire_redesign_6113ea68',
    'test_bonfire_redesign_6113ea68',
}
LOOPBACK_ADDRESSES = {'::1', '127.0.0.1'}


def require_redesign_dev_database():
    if connection.vendor != 'postgresql':
        raise CommandError('G01 write requires the isolated PostgreSQL DEV database.')
    with connection.cursor() as cursor:
        cursor.execute('select current_database(), inet_server_addr()')
        database, address = cursor.fetchone()
    if (database not in ALLOWED_DATABASES or
            str(address) not in LOOPBACK_ADDRESSES or
            connection.settings_dict['NAME'] != database):
        raise CommandError('G01 write requires the dedicated local redesign DEV database.')
    return database
