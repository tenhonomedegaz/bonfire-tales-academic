"""HTTPS JSON endpoints for the restricted database access API."""
import hashlib
import json

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .db_access import (
    ApiProblem, MAX_BODY_BYTES, MAX_FILTERS, MAX_PAGE_SIZE, MODEL_ALLOWLIST,
    OPERATION_HANDLERS, audit,
    authenticate, clean_values, parse_json_body, row_version, schema_document,
    serialize_instance, validate_instance, save_instance, register_operation_handler,
)
from .db_access_models import DbAccessIdempotency, ManagedApiKey
from .catalog_api_preview import catalog_upsert_preview
from .class_revision_editor import class_revision_operation, class_revision_preview_operation
from .class_publication import class_publication_operation, class_publication_preview_operation
from .catalog_sync_api import (
    bestiary_patch_operation, bestiary_patch_preview_operation,
    catalog_sync_operation, catalog_sync_preview_operation,
)


register_operation_handler('class-revision', class_revision_operation)
register_operation_handler('class-revision-preview', class_revision_preview_operation,
                           scope='read')
register_operation_handler('class-publication-preview', class_publication_preview_operation,
                           scope='read')
register_operation_handler('class-publication', class_publication_operation,
                           scope='publish')
register_operation_handler('catalog-sync-preview', catalog_sync_preview_operation,
                           require_base_version=False, scope='read')
register_operation_handler('catalog-sync', catalog_sync_operation, scope='publish')
register_operation_handler('bestiary-patch-preview', bestiary_patch_preview_operation,
                           require_base_version=False, scope='read')
register_operation_handler('bestiary-patch', bestiary_patch_operation, scope='publish')
register_operation_handler('catalog-upsert-preview', catalog_upsert_preview,
                           require_base_version=False, scope='read')


def _response(payload, status=200, *, version=None):
    response = JsonResponse(payload, status=status, json_dumps_params={'ensure_ascii': False})
    if version:
        response['ETag'] = '"%s"' % version
    response['Cache-Control'] = 'no-store'
    return response


def _problem(exc):
    body = {'error': {'code': exc.code, 'message': exc.message}}
    if exc.details is not None:
        body['error']['details'] = exc.details
    response = _response(body, exc.status)
    if exc.status == 401:
        response['WWW-Authenticate'] = 'Bearer'
    if exc.status == 429:
        response['Retry-After'] = '60'
    return response


def _access(model_name):
    try:
        return MODEL_ALLOWLIST[model_name]
    except KeyError:
        raise ApiProblem(404, 'model_not_found', 'Modelo nao permitido.') from None


def _columns(request, access):
    raw = request.GET.get('fields', '')
    if not raw:
        return access.readable
    columns = tuple(dict.fromkeys(item.strip() for item in raw.split(',') if item.strip()))
    if not columns or len(columns) > 20 or not set(columns).issubset(access.readable):
        raise ApiProblem(400, 'invalid_fields', 'Selecao de campos invalida.')
    return columns


def _request_hash(request):
    digest = hashlib.sha256()
    digest.update(request.method.encode('ascii'))
    digest.update(b'\0')
    digest.update(request.path.encode('utf-8'))
    digest.update(b'\0')
    digest.update(request.body)
    return digest.hexdigest()


def _idempotency_header(request):
    value = request.headers.get('Idempotency-Key', '').strip()
    if not value or len(value) > 200:
        raise ApiProblem(400, 'idempotency_required', 'Idempotency-Key e obrigatoria (maximo 200 caracteres).')
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _stored_or_conflict(api_key, key_hash, request_hash):
    stored = DbAccessIdempotency.objects.filter(api_key=api_key, key_hash=key_hash).first()
    if not stored:
        return None
    if stored.request_hash != request_hash:
        raise ApiProblem(409, 'idempotency_conflict', 'Idempotency-Key ja usada por outra requisicao.')
    return _response(stored.response_json, stored.status_code)


@require_http_methods(['GET'])
def db_schema(request):
    api_key = None
    try:
        api_key = authenticate(request, 'read')
        payload = schema_document()
        audit(api_key, 'schema', 200)
        return _response(payload)
    except ApiProblem as exc:
        if api_key:
            audit(api_key, 'schema', exc.status)
        return _problem(exc)


@require_http_methods(['GET'])
def db_session(request):
    api_key = None
    try:
        api_key = authenticate(request, 'read')
        audit(api_key, 'session', 200)
        return _response({'connected': True, 'scopes': sorted(api_key.scopes),
                          'expires_at': api_key.expires_at.isoformat() if api_key.expires_at else None})
    except ApiProblem as exc:
        if api_key:
            audit(api_key, 'session', exc.status)
        return _problem(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def db_collection(request, model_name):
    api_key = None
    action = 'list' if request.method == 'GET' else 'create'
    try:
        access = _access(model_name)
        api_key = authenticate(request, 'read' if request.method == 'GET' else 'write')
        if request.method == 'GET':
            columns = _columns(request, access)
            filters = {}
            for key, value in request.GET.items():
                if not (key.startswith('filter[') and key.endswith(']')):
                    continue
                field_name = key[7:-1]
                if field_name not in access.filterable:
                    raise ApiProblem(400, 'invalid_filter', 'Filtro nao permitido: %s.' % field_name)
                field = access.model._meta.get_field(field_name)
                try:
                    filters[field.attname] = field.target_field.to_python(value) if field.is_relation else field.to_python(value)
                except (TypeError, ValueError):
                    raise ApiProblem(400, 'invalid_filter', 'Valor de filtro invalido.') from None
            if len(filters) > MAX_FILTERS:
                raise ApiProblem(400, 'too_many_filters', 'Use no maximo %d filtros.' % MAX_FILTERS)
            try:
                page = int(request.GET.get('page', '1'))
                page_size = int(request.GET.get('page_size', '25'))
            except ValueError:
                raise ApiProblem(400, 'invalid_pagination', 'Paginacao invalida.') from None
            if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
                raise ApiProblem(400, 'invalid_pagination', 'Paginacao fora dos limites.')
            ordering = request.GET.get('ordering') or access.sortable[0]
            bare_ordering = ordering[1:] if ordering.startswith('-') else ordering
            if bare_ordering not in access.sortable:
                raise ApiProblem(400, 'invalid_ordering', 'Ordenacao nao permitida.')
            qs = access.model._default_manager.filter(**filters).order_by(ordering, access.model._meta.pk.name)
            total = qs.count()
            start = (page - 1) * page_size
            items = [serialize_instance(row, access, columns) for row in qs[start:start + page_size]]
            payload = {'items': items, 'page': page, 'page_size': page_size, 'total': total}
            audit(api_key, action, 200, model_name=model_name, field_names=columns)
            return _response(payload)

        payload = parse_json_body(request)
        key_hash = _idempotency_header(request)
        request_hash = _request_hash(request)
        with transaction.atomic():
            locked_key = ManagedApiKey.objects.select_for_update().get(pk=api_key.pk)
            replay = _stored_or_conflict(locked_key, key_hash, request_hash)
            if replay:
                audit(api_key, 'create_replay', replay.status_code, model_name=model_name)
                return replay
            cleaned = clean_values(access, payload, partial=False)
            instance = access.model(**cleaned)
            validate_instance(instance, access)
            save_instance(instance)
            version = row_version(instance, access)
            body = {'item': serialize_instance(instance, access), 'version': version}
            DbAccessIdempotency.objects.create(
                api_key=locked_key, key_hash=key_hash, request_hash=request_hash,
                status_code=201, response_json=body,
            )
            audit(api_key, action, 201, model_name=model_name, object_pk=instance.pk,
                  field_names=payload.keys())
        return _response(body, 201, version=version)
    except ApiProblem as exc:
        if api_key:
            audit(api_key, action, exc.status, model_name=model_name)
        return _problem(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH'])
def db_object(request, model_name, object_pk):
    api_key = None
    action = 'retrieve' if request.method == 'GET' else 'update'
    try:
        access = _access(model_name)
        api_key = authenticate(request, 'read' if request.method == 'GET' else 'write')
        if request.method == 'GET':
            columns = _columns(request, access)
            try:
                instance = access.model._default_manager.get(pk=object_pk)
            except (access.model.DoesNotExist, ValueError, TypeError):
                raise ApiProblem(404, 'not_found', 'Registro nao encontrado.') from None
            version = row_version(instance, access)
            audit(api_key, action, 200, model_name=model_name, object_pk=instance.pk,
                  field_names=columns)
            return _response({'item': serialize_instance(instance, access, columns),
                              'version': version}, version=version)

        supplied_version = request.headers.get('If-Match', '').strip().strip('"')
        if len(supplied_version) != 64:
            raise ApiProblem(428, 'version_required', 'If-Match com a versao atual e obrigatorio.')
        payload = parse_json_body(request)
        key_hash = _idempotency_header(request)
        request_hash = _request_hash(request)
        with transaction.atomic():
            locked_key = ManagedApiKey.objects.select_for_update().get(pk=api_key.pk)
            replay = _stored_or_conflict(locked_key, key_hash, request_hash)
            if replay:
                audit(api_key, 'update_replay', replay.status_code, model_name=model_name,
                      object_pk=object_pk)
                return replay
            try:
                instance = access.model._default_manager.select_for_update().get(pk=object_pk)
            except (access.model.DoesNotExist, ValueError, TypeError):
                raise ApiProblem(404, 'not_found', 'Registro nao encontrado.') from None
            if row_version(instance, access) != supplied_version:
                raise ApiProblem(412, 'version_conflict', 'O registro mudou; leia novamente antes de atualizar.')
            cleaned = clean_values(access, payload, partial=True)
            for attname, value in cleaned.items():
                setattr(instance, attname, value)
            untouched = set(access.writable) - set(payload)
            validate_instance(instance, access, exclude_untouched=untouched)
            save_instance(instance, update_fields=list(cleaned))
            version = row_version(instance, access)
            body = {'item': serialize_instance(instance, access), 'version': version}
            DbAccessIdempotency.objects.create(
                api_key=locked_key, key_hash=key_hash, request_hash=request_hash,
                status_code=200, response_json=body,
            )
            audit(api_key, action, 200, model_name=model_name, object_pk=instance.pk,
                  field_names=payload.keys())
        return _response(body, version=version)
    except ApiProblem as exc:
        if api_key:
            audit(api_key, action, exc.status, model_name=model_name, object_pk=object_pk)
        return _problem(exc)


@csrf_exempt
@require_http_methods(['POST'])
def db_operation(request, handler_name):
    """Run a code-registered structured operation with common safety controls."""
    api_key = None
    try:
        try:
            spec = OPERATION_HANDLERS[handler_name]
        except KeyError:
            raise ApiProblem(404, 'handler_not_found', 'Operacao nao permitida.') from None
        api_key = authenticate(request, spec.scope)
        payload = parse_json_body(request)
        if spec.require_base_version and not str(payload.get('base_version', '')).strip():
            raise ApiProblem(428, 'base_version_required',
                             'base_version e obrigatoria para esta operacao.')
        key_hash = _idempotency_header(request)
        request_hash = _request_hash(request)
        with transaction.atomic():
            locked_key = ManagedApiKey.objects.select_for_update().get(pk=api_key.pk)
            replay = _stored_or_conflict(locked_key, key_hash, request_hash)
            if replay:
                audit(api_key, 'operation_replay', replay.status_code,
                      model_name='operation:%s' % handler_name)
                return replay
            body = spec.callback(payload, locked_key)
            if not isinstance(body, dict):
                raise ApiProblem(500, 'invalid_handler_result',
                                 'Handler deve retornar um objeto JSON.')
            try:
                encoded = json.dumps(body, ensure_ascii=False, default=str).encode('utf-8')
            except (TypeError, ValueError):
                raise ApiProblem(500, 'invalid_handler_result',
                                 'Handler retornou dados nao serializaveis.') from None
            if len(encoded) > MAX_BODY_BYTES:
                raise ApiProblem(500, 'handler_result_too_large',
                                 'Resposta do handler excede 64 KiB.')
            DbAccessIdempotency.objects.create(
                api_key=locked_key, key_hash=key_hash, request_hash=request_hash,
                status_code=200, response_json=body,
            )
            audit(api_key, 'operation', 200, model_name='operation:%s' % handler_name,
                  field_names=payload.keys())
        return _response(body)
    except ApiProblem as exc:
        if api_key:
            audit(api_key, 'operation', exc.status,
                  model_name='operation:%s' % handler_name)
        return _problem(exc)
