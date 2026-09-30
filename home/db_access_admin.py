"""Superuser-only JSON backend for managed API key lifecycle."""
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from .db_access import ApiProblem, VALID_SCOPES, parse_json_body
from .db_access_models import DbAccessAudit, ManagedApiKey


def _json(payload, status=200):
    response = JsonResponse(payload, status=status, json_dumps_params={'ensure_ascii': False})
    response['Cache-Control'] = 'no-store'
    return response


def _metadata(api_key):
    return {
        'id': str(api_key.pk),
        'name': api_key.name,
        'prefix': api_key.prefix,
        'scopes': api_key.scopes,
        'expires_at': api_key.expires_at.isoformat() if api_key.expires_at else None,
        'revoked_at': api_key.revoked_at.isoformat() if api_key.revoked_at else None,
        'created_at': api_key.created_at.isoformat(),
        'last_used_at': api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        'rotated_from': str(api_key.rotated_from_id) if api_key.rotated_from_id else None,
    }


def _require_superuser(request):
    if not request.user.is_authenticated:
        raise ApiProblem(401, 'unauthorized', 'Login necessario.')
    if not request.user.is_active or not request.user.is_superuser:
        raise ApiProblem(403, 'forbidden', 'Apenas superusers podem gerenciar chaves.')


def _problem(exc):
    body = {'error': {'code': exc.code, 'message': exc.message}}
    if exc.details is not None:
        body['error']['details'] = exc.details
    return _json(body, exc.status)


def _key_parameters(payload, *, defaults=None):
    defaults = defaults or {}
    name = str(payload.get('name', defaults.get('name', ''))).strip()
    if not name or len(name) > 100:
        raise ApiProblem(400, 'invalid_name', 'Nome e obrigatorio (maximo 100 caracteres).')
    scopes = payload.get('scopes', defaults.get('scopes', ['read']))
    if (not isinstance(scopes, list) or not scopes
            or any(not isinstance(scope, str) or scope not in VALID_SCOPES
                   for scope in scopes)):
        raise ApiProblem(400, 'invalid_scopes', 'Escopos permitidos: read e write.')
    scopes = sorted(set(scopes))
    raw_expiry = payload.get('expires_at', defaults.get('expires_at'))
    if raw_expiry in (None, ''):
        expires_at = None
    elif hasattr(raw_expiry, 'tzinfo'):
        expires_at = raw_expiry
    else:
        expires_at = parse_datetime(str(raw_expiry))
        if not expires_at or timezone.is_naive(expires_at):
            raise ApiProblem(400, 'invalid_expiry', 'expires_at deve ser ISO 8601 com fuso horario.')
    if expires_at and expires_at <= timezone.now():
        raise ApiProblem(400, 'invalid_expiry', 'A expiracao deve estar no futuro.')
    return name, scopes, expires_at


def _create_key(*, name, scopes, expires_at, user, rotated_from=None):
    for _attempt in range(5):
        secret = ManagedApiKey.new_secret()
        prefix = secret[:16]
        if not ManagedApiKey.objects.filter(prefix=prefix).exists():
            key = ManagedApiKey.objects.create(
                name=name,
                prefix=prefix,
                secret_hash=ManagedApiKey.digest(secret),
                scopes=scopes,
                expires_at=expires_at,
                created_by=user,
                rotated_from=rotated_from,
            )
            return key, secret
    raise ApiProblem(503, 'key_generation_failed', 'Nao foi possivel gerar uma chave unica.')


def _audit_management(action, key, field_names=(), *, status_code=200):
    # The authenticated actor is intentionally not copied into the audit row:
    # created_by remains available on the key, while audit contains no PII.
    DbAccessAudit.objects.create(
        action=action,
        model_label='managed_api_key',
        object_pk=str(key.pk),
        status_code=status_code,
        field_names=sorted(set(field_names)),
    )


@require_http_methods(['GET'])
def api_key_console(request):
    try:
        _require_superuser(request)
    except ApiProblem as exc:
        return _problem(exc)
    response = render(request, 'admin/db_access_keys.html')
    response['Cache-Control'] = 'no-store'
    return response


@require_http_methods(['GET', 'POST'])
def api_keys(request):
    try:
        _require_superuser(request)
        if request.method == 'GET':
            return _json({'items': [_metadata(key) for key in ManagedApiKey.objects.all()]})
        payload = parse_json_body(request)
        name, scopes, expires_at = _key_parameters(payload)
        with transaction.atomic():
            key, secret = _create_key(
                name=name, scopes=scopes, expires_at=expires_at, user=request.user,
            )
            _audit_management('key_create', key, payload.keys(), status_code=201)
        return _json({'item': _metadata(key), 'secret': secret,
                      'notice': 'Copie agora; o segredo nao sera exibido novamente.'}, 201)
    except ApiProblem as exc:
        return _problem(exc)


@require_http_methods(['POST'])
def api_key_revoke(request, key_id):
    try:
        _require_superuser(request)
        with transaction.atomic():
            try:
                key = ManagedApiKey.objects.select_for_update().get(pk=key_id)
            except (ManagedApiKey.DoesNotExist, ValueError):
                raise ApiProblem(404, 'not_found', 'Chave nao encontrada.') from None
            if not key.revoked_at:
                key.revoked_at = timezone.now()
                key.save(update_fields=('revoked_at',))
                _audit_management('key_revoke', key)
        return _json({'item': _metadata(key)})
    except ApiProblem as exc:
        return _problem(exc)


@require_http_methods(['POST'])
def api_key_rotate(request, key_id):
    try:
        _require_superuser(request)
        payload = parse_json_body(request)
        with transaction.atomic():
            try:
                old = ManagedApiKey.objects.select_for_update().get(pk=key_id)
            except (ManagedApiKey.DoesNotExist, ValueError):
                raise ApiProblem(404, 'not_found', 'Chave nao encontrada.') from None
            if old.revoked_at:
                raise ApiProblem(409, 'already_revoked', 'Chave ja revogada.')
            name, scopes, expires_at = _key_parameters(payload, defaults={
                'name': old.name,
                'scopes': old.scopes,
                'expires_at': old.expires_at,
            })
            new, secret = _create_key(
                name=name, scopes=scopes, expires_at=expires_at,
                user=request.user, rotated_from=old,
            )
            old.revoked_at = timezone.now()
            old.save(update_fields=('revoked_at',))
            _audit_management('key_rotate', old, payload.keys())
        return _json({'item': _metadata(new), 'secret': secret,
                      'notice': 'A chave anterior foi revogada. Copie o novo segredo agora.'}, 201)
    except ApiProblem as exc:
        return _problem(exc)
