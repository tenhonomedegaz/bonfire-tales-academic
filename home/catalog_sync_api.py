"""Preview and apply the installed content fixture through the restricted API."""

from collections import Counter
import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.db import connection
from django.db.models import ForeignKey

from .content_maintenance import (
    GLOBAL_LOCK_KEY, _audit, _fresh_backup, _local_postgres, _protected_directory,
)
from .db_access import ApiProblem
from .deploy_sync import (
    CONTENT_MODELS, OFFICIAL_REPLACE_MODELS, SUBSTITUI, UPSERT_POR_SLUG,
    _m, estado_modelos, inspect_content_deletions, sincronizar_conteudo,
)


FIXTURE = Path(settings.BASE_DIR) / 'home' / 'fixtures' / 'conteudo.json'


def _package():
    raw = FIXTURE.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise ValueError('Fixture instalado nao e uma lista.')
    allowed = {'home.' + name.lower() for name in CONTENT_MODELS}
    if any(not isinstance(row, dict) or row.get('model') not in allowed
           or not isinstance(row.get('fields'), dict) for row in rows):
        raise ValueError('Fixture contem modelo fora do catalogo.')
    return raw.decode('utf-8'), digest, rows


def _state():
    models = estado_modelos(CONTENT_MODELS)
    digest = hashlib.sha256(json.dumps(models, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()
    return digest, models


def _diff(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row['model'], []).append(row)
    # Resolve incoming foreign keys to production PKs before comparing fields.
    # The merge itself performs this remap for slug-managed parent tables.
    pk_maps = {}
    for name in UPSERT_POR_SLUG:
        incoming = grouped.get('home.' + name.lower(), ())
        if not incoming:
            continue
        live = dict(_m(name).objects.values_list('slug', 'pk'))
        pk_maps[name] = {
            row['pk']: live[row['fields']['slug']]
            for row in incoming if row['fields'].get('slug') in live
        }
    result = {}
    unsafe = 0
    for name in CONTENT_MODELS:
        label = 'home.' + name.lower()
        incoming = grouped.get(label)
        if incoming is None:
            result[name] = {'status': 'preserved_missing_from_fixture'}
            continue
        model = _m(name)
        by_slug = name in UPSERT_POR_SLUG or name in OFFICIAL_REPLACE_MODELS
        if by_slug:
            keys = [row['fields'].get('slug') for row in incoming]
            if any(not isinstance(key, str) or not key for key in keys):
                raise ValueError('Slug ausente em ' + name)
            if name in OFFICIAL_REPLACE_MODELS:
                live = model.objects.filter(comunidade=False, autor__isnull=True)
            else:
                live = model.objects.all()
            current = set(live.values_list('slug', flat=True))
        else:
            keys = [row.get('pk') for row in incoming]
            if any(type(key) is not int for key in keys):
                raise ValueError('PK ausente em ' + name)
            current = set(model.objects.values_list(model._meta.pk.attname, flat=True))
            live = model.objects.all()
        if len(keys) != len(set(keys)):
            raise ValueError('Chave duplicada em ' + name)
        target = set(keys)
        existing = {
            (row['fields']['slug'] if by_slug else row['pk']): row['fields']
            for row in json.loads(serializers.serialize('json', live))
        }
        fields_changed = Counter()
        records_changed = 0
        foreign_keys = {
            field.name: pk_maps.get(field.related_model.__name__, {})
            for field in model._meta.fields if isinstance(field, ForeignKey)
        }
        for row, key in zip(incoming, keys):
            old = existing.get(key)
            if old is None:
                continue
            new = dict(row['fields'])
            for field_name, mapping in foreign_keys.items():
                if field_name in new:
                    new[field_name] = mapping.get(new[field_name], new[field_name])
            changed = [field for field in set(old) | set(new)
                       if old.get(field) != new.get(field)]
            if changed:
                records_changed += 1
                fields_changed.update(changed)
        removed = len(current - target) if name in SUBSTITUI else 0
        unsafe += removed
        result[name] = {
            'current': len(current), 'incoming': len(target),
            'matched': len(current & target), 'new': len(target - current),
            'would_remove': removed,
            'production_only_preserved': len(current - target) if name in UPSERT_POR_SLUG else 0,
            'changed_records': records_changed,
            'changed_fields': dict(sorted(fields_changed.items())),
        }
    tombstones = Counter(status for _name, _slug, status, _refs in inspect_content_deletions())
    unsafe += tombstones['would_delete']
    return result, dict(tombstones), unsafe


def _preview():
    if not _local_postgres():
        raise ApiProblem(503, 'local_postgres_required', 'PostgreSQL local obrigatorio.')
    text, package_hash, rows = _package()
    base_version, state = _state()
    diff, tombstones, unsafe = _diff(rows)
    return text, {
        'package_sha256': package_hash, 'base_version': base_version,
        'models': diff, 'tombstones': tombstones,
        'unsafe_deletions': unsafe,
        'backup_ready': _backup_ready(),
        'current_counts': {name: item['count'] for name, item in state.items()},
    }


def _backup_ready():
    from .content_maintenance import _backup_ready as ready
    return ready()


def catalog_sync_preview_operation(payload, _api_key):
    if (set(payload) not in (set(), {'package_sha256'}) or
            ('package_sha256' in payload and
             not isinstance(payload['package_sha256'], str))):
        raise ApiProblem(400, 'invalid_catalog_preview', 'Previa de catalogo invalida.')
    try:
        _text, result = _preview()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        raise ApiProblem(409, 'catalog_preflight_failed', 'Fixture ou catalogo invalido.') from None
    if payload.get('package_sha256', result['package_sha256']) != result['package_sha256']:
        raise ApiProblem(409, 'catalog_package_changed', 'O fixture instalado mudou.')
    return result


def catalog_sync_operation(payload, api_key):
    if (set(payload) != {'base_version', 'package_sha256'} or
            not all(isinstance(payload[k], str) and payload[k]
                    for k in ('base_version', 'package_sha256'))):
        raise ApiProblem(400, 'invalid_catalog_sync', 'Versao base e hash do pacote obrigatorios.')
    if not _local_postgres():
        raise ApiProblem(503, 'local_postgres_required', 'PostgreSQL local obrigatorio.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [GLOBAL_LOCK_KEY])
    try:
        text, preview = _preview()
        if payload['package_sha256'] != preview['package_sha256']:
            raise ApiProblem(409, 'catalog_package_changed', 'O fixture instalado mudou.')
        if payload['base_version'] != preview['base_version']:
            raise ApiProblem(409, 'catalog_state_changed', 'O catalogo mudou desde a previa.')
        if preview['unsafe_deletions']:
            raise ApiProblem(409, 'catalog_deletions_pending',
                             'A previa encontrou exclusoes que exigem decisao separada.')
        folder = _protected_directory()
        backup = _fresh_backup(folder, 'catalog-' + preview['package_sha256'][:12])
        _audit(folder, 'catalog_backup', preview['package_sha256'], str(api_key.pk),
               backup_file=backup.name)
        report = sincronizar_conteudo(text)
        _diff_after, _tombstones_after, unsafe_after = _diff(json.loads(text))
        if unsafe_after or any(item.get('new', 0) or item.get('changed_records', 0)
                               for item in _diff_after.values()):
            raise RuntimeError('Merge deixou registros esperados ausentes ou divergentes.')
        after, _state_models = _state()
        # The API's DbAccessAudit row is committed with the merge; a file log here
        # could falsely claim success if the surrounding transaction rolls back.
        return {
            'package_sha256': preview['package_sha256'],
            'before_version': preview['base_version'], 'after_version': after,
            'backup_file': backup.name,
            'updated': sum(item[1] for item in report['pass1']),
            'inserted': sum(item[2] for item in report['pass1']),
            'replaced': sum(item[1] for item in report['pass2']),
            'memory_preserved': report['mem_ok'],
            'production_content_preserved': report['prod_preservada_ok'],
            'community_preserved': report['comunidade_ok'],
        }
    except ApiProblem:
        raise
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        raise ApiProblem(409, 'catalog_sync_failed', 'Preflight, backup ou merge falhou.') from None
