"""Restricted, single-purpose publication of the reviewed Hunter DB revision.

This endpoint cannot accept SQL or select database objects. The public renderer
continues to read only the configured, immutable ruleset.
"""
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess

from django.conf import settings
from django.db import connection, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


BASE_CHECKSUM = 'da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289'
TARGET_CHECKSUM = 'ed230c319a8959a78cce978a1e72d11281f9f03bbe49b4c3f0e0158eb2a6e0a2'
SQL_SHA256 = '9d5ab77ac02a4cb2f0310663223bf0898bec2c3f43a9eff0f3b863bfd5b341bf'
SQL_FILE = Path(settings.BASE_DIR) / 'ref' / 'backups' / 'hunter_markdown_publicacao_db_20260930.sql'


def _local_postgres():
    config = settings.DATABASES['default']
    if connection.vendor != 'postgresql':
        return False
    host = config.get('HOST') or ''
    try:
        host_is_local = host == 'localhost' or ipaddress.ip_address(host).is_loopback
    except ValueError:
        host_is_local = False
    if not host_is_local:
        return False
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(), inet_server_addr()::text, current_schema(), pg_is_in_recovery()')
        name, address, schema, replica = cursor.fetchone()
    try:
        address_is_local = ipaddress.ip_interface(address).ip.is_loopback
    except (ValueError, TypeError):
        address_is_local = False
    return name == config['NAME'] and address_is_local and schema == 'public' and not replica


def _artifact_statements():
    import sqlparse

    raw = SQL_FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SQL_SHA256:
        raise ValueError('Reviewed SQL artifact differs.')
    statements = sqlparse.split(raw.decode('utf-8'))
    if (len(statements) != 14 or not statements[0].rstrip().endswith('BEGIN;')
            or statements[-2].strip() != 'COMMIT;'
            or not statements[-1].startswith('SELECT checksum, evaluator_version, vocabulary_version')):
        raise ValueError('Reviewed SQL structure differs.')
    return statements[1:-2]


def _fresh_backup():
    """Write and inspect a full custom-format dump before any mutation."""
    configured = os.environ.get('HUNTER_MAINTENANCE_BACKUP_DIR', '')
    folder = Path(configured)
    if not configured or not folder.is_absolute() or not folder.is_dir():
        raise ValueError('A pre-existing absolute backup directory is required.')
    if not settings.DEBUG and folder.resolve().is_relative_to(Path(settings.BASE_DIR).resolve()):
        raise ValueError('Production backups must be outside the served project tree.')
    dump = os.environ.get('HUNTER_MAINTENANCE_PG_DUMP') or shutil.which('pg_dump')
    restore = os.environ.get('HUNTER_MAINTENANCE_PG_RESTORE') or shutil.which('pg_restore')
    if not dump or not restore:
        raise ValueError('pg_dump and pg_restore are required.')
    config = settings.DATABASES['default']
    backup = folder / ('hunter_prepublication_' + secrets.token_hex(12) + '.dump')
    env = os.environ.copy()
    env['PGPASSWORD'] = config.get('PASSWORD') or ''
    env['PGCONNECT_TIMEOUT'] = '5'
    args = [dump, '--format=custom', '--no-password', '--file', str(backup),
            '--host', config['HOST'], '--port', str(config['PORT']),
            '--username', config['USER'], '--dbname', config['NAME']]
    try:
        subprocess.run(args, env=env, check=True, capture_output=True, timeout=300)
        if not backup.is_file() or backup.stat().st_size < 1024:
            raise ValueError('Backup is empty.')
        subprocess.run([restore, '--list', str(backup)], env=env, check=True,
                       capture_output=True, timeout=60)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        # An incomplete dump is not a recovery artifact.
        backup.unlink(missing_ok=True)
        raise ValueError('Fresh PostgreSQL backup failed verification.') from None
    return backup


def _publication_state():
    from .models import TbContentRevision, TbRuleset, TbRulesetContent

    old = TbRuleset.objects.filter(checksum=BASE_CHECKSUM).exists()
    target = TbRuleset.objects.filter(checksum=TARGET_CHECKSUM).first()
    revision = TbContentRevision.objects.filter(
        identity='class-catalog:4',
        checksum='da1219599e6582fa95f95aa8583ca9dffd15d9c3ef7b0155038a1d9bf16fa464',
    ).exists()
    entries = TbRulesetContent.objects.filter(ruleset=target).count() if target else 0
    return {'base_present': old, 'target_present': bool(target),
            'revision_present': revision, 'target_entries': entries,
            'configured_target': settings.HUNTER_CREATOR_RULESET_CHECKSUM == TARGET_CHECKSUM}


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def hunter_publication_maintenance(request):
    """Token-authenticated status/apply; response contains no SQL or player data."""
    token = os.environ.get('HUNTER_MAINTENANCE_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    if (len(token) < 40 or not supplied.startswith('Bearer ') or
            not hmac.compare_digest(supplied[7:], token)):
        return JsonResponse({'code': 'forbidden'}, status=403)
    if not settings.DEBUG and not request.is_secure():
        return JsonResponse({'code': 'https_required'}, status=403)
    try:
        if not _local_postgres():
            return JsonResponse({'code': 'local_postgres_required'}, status=503)
    except Exception:
        return JsonResponse({'code': 'database_unavailable'}, status=503)
    if request.method == 'GET':
        try:
            return JsonResponse({'code': 'ok', **_publication_state()})
        except Exception:
            return JsonResponse({'code': 'database_unavailable'}, status=503)

    if len(request.body) > 512:
        return JsonResponse({'code': 'invalid_request'}, status=400)
    try:
        body = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'code': 'invalid_request'}, status=400)
    if body != {'action': 'apply', 'expected_current_checksum': BASE_CHECKSUM}:
        return JsonResponse({'code': 'invalid_request'}, status=400)
    if settings.HUNTER_CREATOR_RULESET_CHECKSUM != BASE_CHECKSUM:
        return JsonResponse({'code': 'unexpected_publication'}, status=409)
    try:
        statements = _artifact_statements()
        if not _publication_state()['base_present']:
            return JsonResponse({'code': 'base_missing'}, status=409)
        backup = _fresh_backup()
        with transaction.atomic():
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            state = _publication_state()
            if not state['target_present'] or not state['revision_present'] or state['target_entries'] != 21:
                raise ValueError('Publication verification failed.')
    except Exception:
        return JsonResponse({'code': 'apply_failed'}, status=409)
    return JsonResponse({'code': 'installed', 'target_checksum_prefix': TARGET_CHECKSUM[:12],
                         'target_entries': 21, 'backup_file': backup.name})
