"""Bounded, read-only view of one class's published catalog (or unpublished source).

POST class-catalog-read: class_id (positive int), section (see READABLE_FIELDS),
offset (default 0), limit (default 25, 1..100), fields (optional nonempty list).
Read scope and the common Idempotency-Key are required, not base_version.
Selection priority: publication pointer, server-configured immutable checksum,
then live source. A broken selected snapshot never permits source fallback.

Field names match GET /api/db/v1/...: id_classe and id_subclasse are scalar FK IDs
(nullable for subclasses of abilities/resources), NOT related objects. Django
stores these in attnames id_classe_id/id_subclasse_id; those internal aliases are
not accepted API fields. Primary keys retain their source IDs in both modes.
READABLE_FIELDS documents each section's exact allowlist. Defaults exclude
descricao; explicit descriptions are returned intact or the page is rejected.
JSON fields allow at most MAX_JSON_ITEMS entries/nodes and MAX_JSON_DEPTH levels.
The complete response, including its envelope, must fit MAX_BODY_BYTES in UTF-8.
No snapshots, publication pointers, source rows or character data are written.
"""
import json

from .class_publication import (
    CATALOG_ERRORS as SNAPSHOT_ERRORS, published_catalog, resolve_class_catalog,
)
from .db_access import ApiProblem, MAX_BODY_BYTES, MAX_PAGE_SIZE
from .models import TbClasse, TbClassehabilidade, TbRecursoclasse, TbSubclasse


SECTION_MODELS = {
    'classe': TbClasse,
    'subclasse': TbSubclasse,
    'habilidade': TbClassehabilidade,
    'recurso': TbRecursoclasse,
}
READABLE_FIELDS = {
    'classe': ('id_classe', 'slug', 'nome', 'tagline', 'tags_json'),
    'subclasse': ('id_subclasse', 'id_classe', 'slug', 'nome', 'tagline'),
    'habilidade': ('id_habilidade', 'id_classe', 'id_subclasse', 'niveladquirido',
                   'nome', 'nome_ingles', 'table_only', 'tags_json', 'descricao'),
    'recurso': ('id_recurso', 'id_classe', 'id_subclasse', 'slug', 'nome', 'nivel',
                'valor', 'valores_json', 'tipo', 'reset'),
}
DEFAULT_FIELDS = {
    section: tuple(name for name in fields if name != 'descricao')
    for section, fields in READABLE_FIELDS.items()
}
MAX_JSON_ITEMS = 1000
MAX_JSON_DEPTH = 8


def _selection(payload):
    if (not isinstance(payload, dict)
            or set(payload) - {'class_id', 'section', 'offset', 'limit', 'fields'}
            or type(payload.get('class_id')) is not int or payload['class_id'] < 1
            or not isinstance(payload.get('section'), str)
            or payload['section'] not in SECTION_MODELS):
        raise ApiProblem(400, 'invalid_class_catalog',
                         'Informe class_id inteiro positivo e section classe/subclasse/habilidade/recurso.')
    offset, limit = payload.get('offset', 0), payload.get('limit', 25)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= MAX_PAGE_SIZE:
        raise ApiProblem(400, 'invalid_pagination', 'offset >= 0 e limit entre 1 e 100 devem ser inteiros.')
    section = payload['section']
    fields = payload.get('fields', DEFAULT_FIELDS[section])
    if ('fields' in payload and not isinstance(fields, list)
            or not fields or len(fields) > len(READABLE_FIELDS[section])
            or any(not isinstance(name, str) or name not in READABLE_FIELDS[section] for name in fields)
            or len(set(fields)) != len(fields)):
        raise ApiProblem(400, 'invalid_fields', 'Selecione campos distintos permitidos para esta section.',
                         details={'allowed_fields': list(READABLE_FIELDS[section])})
    return section, offset, limit, fields


def _bounded_json(value, field):
    # Count before encoding so tiny JSON entries cannot evade the byte bound.
    stack, count = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        count += 1
        children = item.values() if isinstance(item, dict) else item if isinstance(item, list) else ()
        if (depth > MAX_JSON_DEPTH or count + len(children) > MAX_JSON_ITEMS):
            raise ApiProblem(413, 'class_catalog_json_too_large',
                             'Campo JSON excede os limites; selecione outros campos.',
                             details={'field': field, 'max_items': MAX_JSON_ITEMS,
                                      'max_depth': MAX_JSON_DEPTH})
        stack.extend((child, depth + 1) for child in children)


def _project(row, fields):
    result = {}
    for name in fields:
        # value_from_object uses FK attnames, never a descriptor/live parent fetch.
        value = row._meta.get_field(name).value_from_object(row)
        if name in ('tags_json', 'valores_json'):
            _bounded_json(value, name)
        result[name] = value
    return result


def class_catalog_read_operation(payload, api_key):
    section, offset, limit, fields = _selection(payload)
    class_id = payload['class_id']
    try:
        classe = TbClasse.objects.only('id_classe', 'slug').get(pk=class_id)
    except TbClasse.DoesNotExist:
        raise ApiProblem(404, 'class_not_found', 'Classe nao encontrada.') from None
    try:
        selection = resolve_class_catalog(classe, publication=published_catalog(classe))
        mode = selection.mode
    except SNAPSHOT_ERRORS:
        raise ApiProblem(409, 'invalid_published_catalog',
                         'Catalogo publicado invalido; leitura da fonte atual recusada.') from None

    model = SECTION_MODELS[section]
    checksum = None
    try:
        if mode == 'source':
            filters = {'pk': class_id} if model is TbClasse else {'id_classe_id': class_id}
            rows = model.objects.filter(**filters).order_by('pk')
            total = rows.count()
            # Excluded descriptions/fields are not fetched even for source mode.
            attnames = [model._meta.get_field(name).attname for name in fields]
            page = rows.only(*attnames)[offset:offset + limit]
        else:
            ruleset, catalog = selection.ruleset, selection.catalog
            checksum = ruleset.checksum
            rows = catalog.collections[model]
            ids = [row.pk for row in rows]
            if any(type(pk) is not int or pk < 1 for pk in ids) or len(set(ids)) != len(ids):
                raise ValueError('Invalid source identities in published catalog.')
            total = len(rows)
            page = sorted(rows, key=lambda row: row.pk)[offset:offset + limit]
        result = {'mode': mode, 'ruleset_checksum': checksum, 'class_id': class_id,
                  'section': section, 'total': total, 'offset': offset, 'limit': limit,
                  'rows': [_project(row, fields) for row in page]}
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except SNAPSHOT_ERRORS:
        raise ApiProblem(409 if mode != 'source' else 500,
                         'invalid_published_catalog' if mode != 'source' else 'invalid_class_catalog',
                         'Catalogo invalido; leitura recusada sem fallback.') from None
    if len(encoded) > MAX_BODY_BYTES:
        raise ApiProblem(413, 'class_catalog_result_too_large',
                         'Resposta excede o limite; reduza limit ou fields (omita descricao).',
                         details={'max_bytes': MAX_BODY_BYTES, 'response_bytes': len(encoded)})
    return result
