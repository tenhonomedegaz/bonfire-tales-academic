"""Read-only comparison of proposed catalog rows against stable natural keys."""

from .db_access import (
    ApiProblem, MODEL_ALLOWLIST, clean_values, row_version,
    serialize_instance, validate_instance,
)


def catalog_upsert_preview(payload, api_key):
    """Return reviewed individual REST mutations; never save catalog content."""
    if set(payload) - {'model', 'items'}:
        raise ApiProblem(400, 'invalid_field', 'Use apenas model e items.')
    name, items = payload.get('model'), payload.get('items')
    if not isinstance(name, str) or name not in MODEL_ALLOWLIST:
        raise ApiProblem(404, 'model_not_found', 'Modelo nao permitido.')
    access = MODEL_ALLOWLIST[name]
    if not access.writable or 'slug' not in access.filterable or 'slug' not in access.writable:
        raise ApiProblem(400, 'unsupported_catalog', 'Catalogo sem contrato de escrita por slug.')
    if not isinstance(items, list) or not 1 <= len(items) <= 10:
        raise ApiProblem(400, 'invalid_items', 'Envie de 1 a 10 registros por previa.')
    seen, operations = set(), []
    counts = {'create': 0, 'update': 0, 'unchanged': 0}
    for index, values in enumerate(items):
        if not isinstance(values, dict):
            raise ApiProblem(400, 'invalid_item', 'Cada registro deve ser um objeto.')
        slug = values.get('slug')
        if not isinstance(slug, str) or not slug or slug in seen:
            raise ApiProblem(400, 'invalid_identity', 'Slugs devem ser preenchidos e distintos.')
        seen.add(slug)
        current = access.model._default_manager.filter(slug=slug).first()
        before = serialize_instance(current, access) if current is not None else {}
        version = row_version(current, access) if current is not None else None
        cleaned = clean_values(access, values, partial=current is not None)
        candidate = current or access.model()
        for field, value in cleaned.items():
            setattr(candidate, field, value)
        validate_instance(candidate, access, exclude_untouched=(
            set(access.writable) - set(values) if current is not None else ()))
        after = serialize_instance(candidate, access)
        changes = {field: {'before': before.get(field), 'after': after[field]}
                   for field in values if current is None or before.get(field) != after[field]}
        action = 'create' if current is None else 'update' if changes else 'unchanged'
        counts[action] += 1
        operations.append({
            'index': index, 'slug': slug, 'action': action,
            'pk': current.pk if current is not None else None,
            'version': version, 'changes': changes,
        })
    return {'model': name, 'counts': counts, 'operations': operations,
            'content_mutated': False, 'requires_review': True}
