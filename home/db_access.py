"""Safe, structured access to a small allowlist of editorial models."""
import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from . import models as home_models
from .db_access_models import DbAccessAudit, ManagedApiKey


MAX_BODY_BYTES = 64 * 1024
MAX_FILTERS = 8
MAX_PAGE_SIZE = 100
RATE_LIMIT = 60
RATE_WINDOW_SECONDS = 60
VALID_SCOPES = frozenset({'read', 'write', 'publish'})


@dataclass(frozen=True)
class ModelAccess:
    model: type
    readable: tuple
    writable: tuple
    filterable: tuple
    sortable: tuple


@dataclass(frozen=True)
class OperationHandler:
    callback: object
    require_base_version: bool = True
    scope: str = 'write'


# Trusted application code may register a structured operation here during app
# startup. There is deliberately no dynamic import, database-configured callable,
# SQL hook, shell hook, or DDL hook.
OPERATION_HANDLERS = {}


def register_operation_handler(name, callback, *, require_base_version=True, scope='write'):
    """Register one trusted operation callback under a stable API name.

    The callback receives ``(payload, api_key)`` and must return a JSON-safe dict.
    Registration is code-only and refuses replacement, keeping the exposed
    operation surface explicit and reviewable.
    """
    if not name or not name.replace('-', '').replace('_', '').isalnum():
        raise ValueError('invalid operation handler name')
    if not callable(callback):
        raise TypeError('operation handler must be callable')
    if scope not in VALID_SCOPES:
        raise ValueError('invalid operation handler scope')
    if name in OPERATION_HANDLERS:
        raise ValueError('operation handler already registered: %s' % name)
    OPERATION_HANDLERS[name] = OperationHandler(callback, require_base_version, scope)


MODEL_ALLOWLIST = {
    'regra': ModelAccess(
        home_models.TbRegra,
        ('id_regra', 'slug', 'nome', 'nome_en', 'categoria', 'definicao'),
        ('slug', 'nome', 'nome_en', 'categoria', 'definicao'),
        ('id_regra', 'slug', 'nome', 'categoria'),
        ('id_regra', 'slug', 'nome', 'categoria'),
    ),
    'idioma': ModelAccess(
        home_models.TbIdioma,
        ('id_idioma', 'slug', 'nome', 'nome_mundo', 'categoria',
         'idioma_caracteristico', 'transcricao', 'ordem'),
        ('slug', 'nome', 'nome_mundo', 'categoria',
         'idioma_caracteristico', 'transcricao', 'ordem'),
        ('id_idioma', 'slug', 'nome', 'categoria'),
        ('id_idioma', 'slug', 'nome', 'categoria', 'ordem'),
    ),
    'condicao': ModelAccess(
        home_models.TbCondicao,
        ('id_condicao', 'slug', 'nome', 'nome_en', 'categoria', 'resumo',
         'definicao', 'efeitos_json', 'ordem'),
        ('slug', 'nome', 'nome_en', 'categoria', 'resumo', 'definicao',
         'efeitos_json', 'ordem'),
        ('id_condicao', 'slug', 'nome', 'categoria'),
        ('id_condicao', 'slug', 'nome', 'categoria', 'ordem'),
    ),
    'raca': ModelAccess(
        home_models.TbRaca,
        ('id_raca', 'nome', 'slug', 'tagline', 'lore_presentation',
         'lore_roleplay', 'lore_society', 'imagem_url', 'permite_essencia'),
        ('nome', 'slug', 'tagline', 'lore_presentation', 'lore_roleplay',
         'lore_society', 'imagem_url', 'permite_essencia'),
        ('id_raca', 'slug', 'nome', 'permite_essencia'),
        ('id_raca', 'slug', 'nome'),
    ),
    'linhagem': ModelAccess(
        home_models.TbLinhagem,
        ('id_linhagem', 'id_raca', 'nome', 'slug', 'lore_presentation',
         'lore_roleplay', 'lore_society', 'descricao', 'imagem_url'),
        ('id_raca', 'nome', 'slug', 'lore_presentation', 'lore_roleplay',
         'lore_society', 'descricao', 'imagem_url'),
        ('id_linhagem', 'id_raca', 'slug', 'nome'),
        ('id_linhagem', 'id_raca', 'slug', 'nome'),
    ),
}


class ApiProblem(Exception):
    def __init__(self, status, code, message, *, details=None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def parse_json_body(request):
    if len(request.body) > MAX_BODY_BYTES:
        raise ApiProblem(413, 'body_too_large', 'Corpo excede 64 KiB.')
    try:
        value = json.loads(request.body or b'{}')
    except (TypeError, ValueError, UnicodeDecodeError):
        raise ApiProblem(400, 'invalid_json', 'JSON invalido.') from None
    if not isinstance(value, dict):
        raise ApiProblem(400, 'invalid_json', 'O corpo deve ser um objeto JSON.')
    return value


def _field(access, name):
    try:
        return access.model._meta.get_field(name)
    except Exception:
        raise ApiProblem(400, 'invalid_field', 'Campo nao permitido: %s.' % name) from None


def serialize_value(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if hasattr(value, 'hex') and value.__class__.__module__ == 'uuid':
        return str(value)
    return value


def serialize_instance(instance, access, columns=None):
    columns = columns or access.readable
    result = {}
    for name in columns:
        field = _field(access, name)
        value = field.value_from_object(instance)
        result[name] = serialize_value(value)
    return result


def row_version(instance, access):
    canonical = json.dumps(
        serialize_instance(instance, access),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def clean_values(access, payload, *, partial):
    unknown = sorted(set(payload) - set(access.writable))
    if unknown:
        raise ApiProblem(400, 'invalid_field', 'Campos nao permitidos.', details=unknown)
    if not payload:
        raise ApiProblem(400, 'empty_mutation', 'Informe ao menos um campo.')
    cleaned = {}
    errors = {}
    for name, value in payload.items():
        field = _field(access, name)
        try:
            if value is None:
                if not field.null:
                    raise ValidationError('null nao permitido')
                cleaned[field.attname] = None
            elif isinstance(field, models.ForeignKey):
                pk = field.target_field.to_python(value)
                if not field.remote_field.model._default_manager.filter(pk=pk).exists():
                    raise ValidationError('referencia inexistente')
                cleaned[field.attname] = pk
            else:
                converted = field.to_python(value)
                field.run_validators(converted)
                cleaned[field.attname] = converted
        except (ValidationError, TypeError, ValueError) as exc:
            errors[name] = getattr(exc, 'messages', [str(exc)])
    if errors:
        raise ApiProblem(400, 'invalid_value', 'Valores invalidos.', details=errors)
    return cleaned


def validate_instance(instance, access, *, exclude_untouched=()):
    try:
        instance.full_clean(exclude=list(exclude_untouched), validate_unique=True)
    except ValidationError as exc:
        details = getattr(exc, 'message_dict', {'__all__': exc.messages})
        raise ApiProblem(400, 'validation_error', 'Registro invalido.', details=details) from None


def authenticate(request, scope):
    if not request.is_secure():
        raise ApiProblem(400, 'https_required', 'A API aceita somente HTTPS.')
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        raise ApiProblem(401, 'unauthorized', 'Bearer token ausente.')
    secret = header[7:].strip()
    if len(secret) < 20:
        raise ApiProblem(401, 'unauthorized', 'Chave invalida.')
    prefix = secret[:16]
    try:
        api_key = ManagedApiKey.objects.get(prefix=prefix)
    except ManagedApiKey.DoesNotExist:
        raise ApiProblem(401, 'unauthorized', 'Chave invalida.') from None
    if not api_key.matches(secret) or not api_key.is_usable():
        raise ApiProblem(401, 'unauthorized', 'Chave invalida, expirada ou revogada.')
    if not api_key.has_scope(scope):
        raise ApiProblem(403, 'insufficient_scope', 'Escopo %s necessario.' % scope)
    apply_rate_limit(api_key)
    return api_key


def apply_rate_limit(api_key):
    now = timezone.now()
    window = timedelta(seconds=RATE_WINDOW_SECONDS)
    with transaction.atomic():
        locked = ManagedApiKey.objects.select_for_update().get(pk=api_key.pk)
        if not locked.rate_window_started or locked.rate_window_started <= now - window:
            locked.rate_window_started = now
            locked.rate_count = 1
        elif locked.rate_count >= RATE_LIMIT:
            raise ApiProblem(429, 'rate_limited', 'Limite de 60 requisicoes por minuto excedido.')
        else:
            locked.rate_count += 1
        locked.last_used_at = now
        locked.save(update_fields=('rate_window_started', 'rate_count', 'last_used_at'))


def audit(api_key, action, status, *, model_name='', object_pk='', field_names=()):
    DbAccessAudit.objects.create(
        api_key=api_key,
        action=action[:24],
        model_label=model_name[:64],
        object_pk=str(object_pk)[:100],
        status_code=status,
        field_names=sorted(set(field_names)),
    )


def schema_document():
    output = {}
    for name, access in MODEL_ALLOWLIST.items():
        fields = {}
        for field_name in access.readable:
            field = _field(access, field_name)
            fields[field_name] = {
                'type': field.get_internal_type(),
                'nullable': field.null,
                'primary_key': field.primary_key,
                'relation': (
                    field.remote_field.model._meta.label_lower
                    if isinstance(field, models.ForeignKey) else None
                ),
                'writable': field_name in access.writable,
                'filterable': field_name in access.filterable,
                'sortable': field_name in access.sortable,
            }
        output[name] = {'fields': fields}
    return {'models': output, 'operations': {
        name: {'scope': spec.scope, 'base_version_required': spec.require_base_version}
        for name, spec in sorted(OPERATION_HANDLERS.items())
    }, 'limits': {
        'page_size': MAX_PAGE_SIZE,
        'filters': MAX_FILTERS,
        'body_bytes': MAX_BODY_BYTES,
        'rate': '%d/%ds' % (RATE_LIMIT, RATE_WINDOW_SECONDS),
    }}
