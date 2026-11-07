"""Publish allowlisted, reviewed content packages; never accept client SQL/files."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
import logging
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

from .content_versions import digest
from .models import TbContentRevision, TbRuleset, TbRulesetContent


PACKAGE_DIR = Path(__file__).parent / 'content_packages'
# Adding a reviewed package changes this registry and adds its pinned manifest/artifact.
# The HTTP controller and execution rules remain unchanged.
PACKAGES = {
    'hunter-markdown-20260930': (
        'hunter_markdown_20260930.json',
        '3aaa543821ed75331bcc3d6a944bc7d5f568be35e8bbe118105679bf5b9400fc',
    ),
}
GLOBAL_LOCK_KEY = 0x424F4E46495245
logger = logging.getLogger(__name__)


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


def _load_package(package_id):
    if package_id not in PACKAGES:
        raise LookupError('Unknown package.')
    filename, expected_hash = PACKAGES[package_id]
    manifest_path = (PACKAGE_DIR / filename).resolve()
    if manifest_path.parent != PACKAGE_DIR.resolve():
        raise ValueError('Manifest path differs from allowlist.')
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError('Reviewed manifest differs.')
    data = json.loads(raw)
    required = {'schema', 'id', 'artifact', 'artifact_sha256', 'statement_count',
                'base_ruleset_checksum', 'target_ruleset_checksum',
                'target_revision_identity', 'target_revision_checksum',
                'expected_entries', 'evaluator_version', 'vocabulary_version',
                'activation_setting'}
    if (set(data) != required or data['schema'] != 1 or data['id'] != package_id
            or data['statement_count'] < 4 or data['expected_entries'] < 1
            or any(len(data[key]) != 64 for key in (
                'artifact_sha256', 'base_ruleset_checksum',
                'target_ruleset_checksum', 'target_revision_checksum'))):
        raise ValueError('Invalid reviewed manifest.')
    artifact = (Path(settings.BASE_DIR) / data['artifact']).resolve()
    if not artifact.is_relative_to(Path(settings.BASE_DIR).resolve()) or artifact.suffix != '.sql':
        raise ValueError('Artifact must be installed inside the project.')
    data['artifact_path'] = artifact
    return data


def _artifact_statements(package):
    import sqlparse

    raw = package['artifact_path'].read_bytes()
    if hashlib.sha256(raw).hexdigest() != package['artifact_sha256']:
        raise ValueError('Reviewed artifact differs.')
    statements = sqlparse.split(raw.decode('utf-8'))
    if (len(statements) != package['statement_count']
            or not statements[0].rstrip().endswith('BEGIN;')
            or statements[-2].strip() != 'COMMIT;'
            or not statements[-1].lstrip().startswith('SELECT ')):
        raise ValueError('Reviewed transaction envelope differs.')
    return statements[1:-2]


def _package_state(package):
    base = TbRuleset.objects.filter(checksum=package['base_ruleset_checksum']).first()
    target = TbRuleset.objects.filter(checksum=package['target_ruleset_checksum']).first()
    revision = TbContentRevision.objects.filter(
        identity=package['target_revision_identity'],
        checksum=package['target_revision_checksum']).first()
    integrity = False
    entries = 0
    if target:
        links = list(TbRulesetContent.objects.filter(ruleset=target).select_related('revision'))
        entries = len(links)
        integrity = (
            target.evaluator_version == package['evaluator_version']
            and target.vocabulary_version == package['vocabulary_version']
            and target.checksum == digest({
                'manifest': target.manifest,
                'evaluator': target.evaluator_version,
                'vocabulary': target.vocabulary_version,
            })
            and len(target.manifest) == package['expected_entries']
            and entries == package['expected_entries']
            and target.manifest.get(package['target_revision_identity']) == package['target_revision_checksum']
            and all(link.identity == link.revision.identity
                    and target.manifest.get(link.identity) == link.revision.checksum
                    and link.revision.checksum == digest({
                        'identity': link.revision.identity, 'payload': link.revision.payload,
                        'dependencies': link.revision.dependencies,
                    }) for link in links)
        )
    configured = getattr(settings, package['activation_setting'], None)
    return {
        'base_present': bool(base), 'target_present': bool(target),
        'target_integrity': integrity, 'target_entries': entries,
        'revision_present': bool(revision),
        'base_active': configured == package['base_ruleset_checksum'],
        'activated': configured == package['target_ruleset_checksum'],
    }


def _protected_directory():
    configured = os.environ.get('CONTENT_MAINTENANCE_BACKUP_DIR', '')
    folder = Path(configured)
    if not configured or not folder.is_absolute() or not folder.is_dir():
        raise ValueError('A pre-existing absolute backup directory is required.')
    if not settings.DEBUG and folder.resolve().is_relative_to(Path(settings.BASE_DIR).resolve()):
        raise ValueError('Production backups must be outside the served project tree.')
    return folder


def _audit(folder, event, package_id, operation_id, *, backup_file=None):
    record = {'at': datetime.now(timezone.utc).isoformat(), 'event': event,
              'package': package_id, 'operation_id': operation_id}
    if backup_file:
        record['backup_file'] = backup_file
    line = (json.dumps(record, separators=(',', ':')) + '\n').encode('utf-8')
    path = folder / 'content_maintenance_audit.jsonl'
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        if os.write(fd, line) != len(line):
            raise OSError('Audit record was incomplete.')
        os.fsync(fd)
    finally:
        os.close(fd)


def _fresh_backup(folder, package_id):
    dump = os.environ.get('CONTENT_MAINTENANCE_PG_DUMP') or shutil.which('pg_dump')
    restore = os.environ.get('CONTENT_MAINTENANCE_PG_RESTORE') or shutil.which('pg_restore')
    if not dump or not restore:
        raise ValueError('pg_dump and pg_restore are required.')
    config = settings.DATABASES['default']
    backup = folder / (package_id + '_' + secrets.token_hex(12) + '.dump')
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
        backup.unlink(missing_ok=True)
        raise ValueError('Fresh PostgreSQL backup failed verification.') from None
    return backup


def _backup_ready():
    try:
        _protected_directory()
    except (ValueError, OSError):
        return False
    return bool((os.environ.get('CONTENT_MAINTENANCE_PG_DUMP') or shutil.which('pg_dump'))
                and (os.environ.get('CONTENT_MAINTENANCE_PG_RESTORE') or shutil.which('pg_restore')))


@contextmanager
def _exclusive_application():
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [GLOBAL_LOCK_KEY])
        acquired = cursor.fetchone()[0]
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [GLOBAL_LOCK_KEY])


def _authorized(request, action):
    key = ('CONTENT_MAINTENANCE_READ_TOKEN' if action == 'read'
           else 'CONTENT_MAINTENANCE_APPLY_TOKEN')
    token = os.environ.get(key, '')
    other = os.environ.get('CONTENT_MAINTENANCE_APPLY_TOKEN' if action == 'read'
                           else 'CONTENT_MAINTENANCE_READ_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    return (len(token) >= 40 and token != other and supplied.startswith('Bearer ')
            and hmac.compare_digest(supplied[7:], token))


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def content_maintenance(request, package_id):
    """Read-only preview or explicit application of an installed allowlisted package."""
    if not _authorized(request, 'read' if request.method == 'GET' else 'apply'):
        return JsonResponse({'code': 'forbidden'}, status=403)
    if not settings.DEBUG and not request.is_secure():
        return JsonResponse({'code': 'https_required'}, status=403)
    try:
        package = _load_package(package_id)
    except LookupError:
        return JsonResponse({'code': 'unknown_package'}, status=404)
    except (OSError, ValueError, TypeError, KeyError):
        return JsonResponse({'code': 'package_invalid'}, status=409)
    try:
        if not _local_postgres():
            return JsonResponse({'code': 'local_postgres_required'}, status=503)
        statements = _artifact_statements(package)
        state = _package_state(package)
    except Exception:
        return JsonResponse({'code': 'preflight_failed'}, status=409)
    if request.method == 'GET':
        backup_ready = _backup_ready()
        return JsonResponse({'code': 'ok', 'package': package_id,
                             'artifact_verified': bool(statements), 'backup_ready': backup_ready,
                             'can_apply': bool(state['base_present'] and state['base_active']
                                               and not state['target_present'] and backup_ready),
                             **state})
    if len(request.body) > 512:
        return JsonResponse({'code': 'invalid_request'}, status=400)
    try:
        body = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'code': 'invalid_request'}, status=400)
    if body != {'action': 'apply', 'expected_base_checksum': package['base_ruleset_checksum']}:
        return JsonResponse({'code': 'invalid_request'}, status=400)
    operation_id = secrets.token_hex(12)
    try:
        with _exclusive_application() as acquired:
            if not acquired:
                return JsonResponse({'code': 'busy'}, status=409)
            # Recheck after acquiring the global lock: no stale preview authorizes a write.
            state = _package_state(package)
            if state['target_present']:
                if not state['target_integrity']:
                    return JsonResponse({'code': 'target_invalid'}, status=409)
                return JsonResponse({'code': 'already_installed', 'package': package_id,
                                     'activated': state['activated']})
            if (not state['base_present'] or
                    getattr(settings, package['activation_setting'], None) != package['base_ruleset_checksum']):
                return JsonResponse({'code': 'base_not_active'}, status=409)
            folder = _protected_directory()
            _audit(folder, 'started', package_id, operation_id)
            backup = _fresh_backup(folder, package_id)
            _audit(folder, 'backup_verified', package_id, operation_id, backup_file=backup.name)
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        for statement in statements:
                            cursor.execute(statement)
                    verified = _package_state(package)
                    if not verified['target_integrity'] or not verified['revision_present']:
                        raise ValueError('Publication verification failed.')
            except Exception:
                _audit(folder, 'rolled_back', package_id, operation_id, backup_file=backup.name)
                raise
            try:
                _audit(folder, 'installed', package_id, operation_id, backup_file=backup.name)
            except OSError:
                # The transaction already committed. Report that fact, never a retryable failure.
                logger.error('Content maintenance %s committed but final audit append failed', package_id)
                return JsonResponse({'code': 'installed_audit_incomplete', 'package': package_id},
                                    status=202)
    except Exception as exc:
        logger.warning('Content maintenance %s failed: %s', package_id, type(exc).__name__)
        return JsonResponse({'code': 'apply_failed'}, status=409)
    return JsonResponse({'code': 'installed', 'package': package_id,
                         'target_checksum_prefix': package['target_ruleset_checksum'][:12],
                         'target_entries': package['expected_entries'], 'backup_file': backup.name})
