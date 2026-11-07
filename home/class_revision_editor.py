"""Create a new sealed class catalog from reviewed, structured row changes.

Changes affect only the new snapshot. Existing revisions, live rows and
characters remain untouched until a separate publication step selects it.
"""
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction

from .content_versions import create_revision, digest, resolve_content, seal_ruleset
from .models import TbClasse, TbClassehabilidade, TbRecursoclasse, TbRuleset, TbSubclasse
from .versioned_classes import (EVALUATOR, MODELS, VOCABULARY, VersionedClassCatalog,
                                _fields, validate_class_contracts)


MODEL_BY_LABEL = {model._meta.label_lower: model for model in MODELS}
PRESENTATION_SOURCE = 'catalog'


def _editable_fields(model):
    protected = {model._meta.pk.attname, 'id_classe_id', 'id_subclasse_id'}
    if model is TbClasse:
        protected.add('slug')
    if model is TbSubclasse:
        protected.add('slug')
    return {field.attname for field in model._meta.concrete_fields} - protected


def _validate_row(model, row, class_id):
    if model is TbClasse:
        if row[model._meta.pk.attname] != class_id:
            raise ValueError('Class identity cannot change.')
    elif row['id_classe_id'] != class_id:
        raise ValueError('Foreign class row.')
    for field in model._meta.concrete_fields:
        value = row[field.attname]
        if value is None:
            if not field.null:
                raise ValueError('Null value in required class field.')
            continue
        try:
            converted = field.to_python(value)
            if type(converted) is not type(value) or converted != value:
                raise ValueError('Noncanonical class field type.')
            field.run_validators(converted)
        except ValidationError as exc:
            raise ValueError('Invalid class field value.') from exc
    if 'tags_json' in row and not isinstance(row['tags_json'], list):
        raise ValueError('Class tags must be a list.')
    if 'valores_json' in row and not isinstance(row['valores_json'], dict):
        raise ValueError('Resource values must be a map.')
    if model is TbClassehabilidade and not 1 <= row['niveladquirido'] <= 20:
        raise ValueError('Feature level must be between 1 and 20.')


def _prepare_revision(base_checksum, class_id, changes, presentation_source, *, contracts=None, lock=False):
    if not isinstance(changes, list) or (not changes and contracts is None and presentation_source is None):
        raise ValueError('At least one reviewed change is required.')
    if presentation_source not in (None, PRESENTATION_SOURCE):
        raise ValueError('Unsupported presentation source.')
    query = TbRuleset.objects.select_for_update() if lock else TbRuleset.objects
    ruleset = query.get(checksum=base_checksum)
    identity = 'class-catalog:%s' % class_id
    payload = resolve_content(ruleset, identity, evaluator_version=EVALUATOR,
                              vocabulary_version=VOCABULARY)
    if payload.get('schema') != 1 or payload.get('class_id') != class_id:
        raise ValueError('Invalid base class catalog.')
    payload = deepcopy(payload)
    collections = payload['collections']
    seen = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) - {'model', 'action', 'pk', 'fields'}:
            raise ValueError('Invalid class change.')
        model = MODEL_BY_LABEL.get(change.get('model'))
        action = change.get('action')
        pk = change.get('pk')
        if model is None or action not in {'add', 'update', 'remove'} or type(pk) is not int or pk <= 0:
            raise ValueError('Unknown class row or operation.')
        key = (model, pk)
        if key in seen:
            raise ValueError('A class row may be changed only once.')
        seen.add(key)
        rows = collections[model._meta.label_lower]
        matches = [row for row in rows if row[model._meta.pk.attname] == pk]
        if len(matches) > 1:
            raise ValueError('Duplicate class row identity.')
        if action == 'add':
            if matches or 'fields' in change or model is TbClasse:
                raise ValueError('Cannot add this class row.')
            row = _fields(model.objects.get(pk=pk))
            _validate_row(model, row, class_id)
            rows.append(row)
        elif action == 'remove':
            if not matches or 'fields' in change or model is TbClasse:
                raise ValueError('Cannot remove this class row.')
            rows.remove(matches[0])
        else:
            fields = change.get('fields')
            if not matches or not isinstance(fields, dict) or not fields or not set(fields) <= _editable_fields(model):
                raise ValueError('Invalid class field update.')
            updated = {**matches[0], **deepcopy(fields)}
            _validate_row(model, updated, class_id)
            matches[0].update(updated)
    if presentation_source:
        payload['presentation_source'] = presentation_source
    if contracts is not None:
        payload['contracts'] = validate_class_contracts(contracts)
    _validate_snapshot(payload, class_id)
    return ruleset, identity, payload


def _validate_snapshot(payload, class_id):
    collections = payload['collections']
    classes = collections[TbClasse._meta.label_lower]
    if len(classes) != 1 or classes[0]['id_classe'] != class_id:
        raise ValueError('Invalid class row.')
    subclasses = collections[TbSubclasse._meta.label_lower]
    subclass_ids = {row['id_subclasse'] for row in subclasses}
    for model in MODELS:
        rows = collections[model._meta.label_lower]
        pk = model._meta.pk.attname
        if len({row[pk] for row in rows}) != len(rows):
            raise ValueError('Duplicate catalog identity.')
        for row in rows:
            _validate_row(model, row, class_id)
            if row.get('id_subclasse_id') is not None and row['id_subclasse_id'] not in subclass_ids:
                raise ValueError('Dangling subclass reference.')


def preview_class_revision(base_checksum, class_id, changes, *, presentation_source=None, contracts=None):
    """Compute a target checksum after the same preflight, without writing content."""
    ruleset, identity, payload = _prepare_revision(
        base_checksum, class_id, changes, presentation_source, contracts=contracts)
    revision_checksum = digest({'identity': identity, 'payload': payload, 'dependencies': []})
    manifest = {**ruleset.manifest, identity: revision_checksum}
    target_checksum = digest({'manifest': manifest, 'evaluator': EVALUATOR,
                              'vocabulary': VOCABULARY})
    return {'class_id': class_id, 'base_version': base_checksum,
            'revision_checksum': revision_checksum, 'ruleset_checksum': target_checksum,
            'change_count': len(changes), 'activated': False}


@transaction.atomic
def create_class_revision(base_checksum, class_id, changes, *, author=None,
                          presentation_source=None, contracts=None):
    """Seal a copy of a class catalog, checking every change and binding.

    Each change has model, action and pk. ``update`` additionally has a
    limited fields map; ``add`` copies a reviewed live row with that PK;
    ``remove`` omits a row from the new snapshot only. There is no client SQL.
    """
    ruleset, identity, payload = _prepare_revision(
        base_checksum, class_id, changes, presentation_source, contracts=contracts, lock=True)
    revision = create_revision(identity, payload, author=author)
    revisions = [entry.revision for entry in ruleset.entries.select_related('revision')
                 if entry.identity != identity]
    new_ruleset = seal_ruleset(revisions + [revision], evaluator_version=EVALUATOR,
                               vocabulary_version=VOCABULARY, author=author)
    VersionedClassCatalog(new_ruleset, class_id)
    return new_ruleset


def class_revision_operation(payload, api_key):
    """Bounded API operation; publication remains an explicit later action."""
    from .db_access import ApiProblem
    allowed = {'base_version', 'class_id', 'changes', 'presentation_source', 'contracts'}
    if set(payload) - allowed or type(payload.get('class_id')) is not int:
        raise ApiProblem(400, 'invalid_class_revision', 'Operação de classe inválida.')
    try:
        ruleset = create_class_revision(
            payload['base_version'], payload['class_id'], payload.get('changes'),
            author=None, presentation_source=payload.get('presentation_source'), contracts=payload.get('contracts'))
    except TbRuleset.DoesNotExist:
        raise ApiProblem(404, 'base_not_found', 'Revisão de base não encontrada.') from None
    except (ValueError, KeyError, TypeError, TbClasse.DoesNotExist,
            TbSubclasse.DoesNotExist, TbClassehabilidade.DoesNotExist,
            TbRecursoclasse.DoesNotExist):
        raise ApiProblem(400, 'invalid_class_revision', 'Mudanças de classe inválidas.') from None
    return {'class_id': payload['class_id'], 'base_version': payload['base_version'],
            'ruleset_checksum': ruleset.checksum, 'activated': False}


def class_revision_preview_operation(payload, api_key):
    """Read-scoped preflight of the same structured revision operation."""
    from .db_access import ApiProblem
    allowed = {'base_version', 'class_id', 'changes', 'presentation_source', 'contracts'}
    if set(payload) - allowed or type(payload.get('class_id')) is not int:
        raise ApiProblem(400, 'invalid_class_revision', 'Operação de classe inválida.')
    try:
        return preview_class_revision(
            payload['base_version'], payload['class_id'], payload.get('changes'),
            presentation_source=payload.get('presentation_source'), contracts=payload.get('contracts'))
    except TbRuleset.DoesNotExist:
        raise ApiProblem(404, 'base_not_found', 'Revisão de base não encontrada.') from None
    except (ValueError, KeyError, TypeError, TbClasse.DoesNotExist,
            TbSubclasse.DoesNotExist, TbClassehabilidade.DoesNotExist,
            TbRecursoclasse.DoesNotExist):
        raise ApiProblem(400, 'invalid_class_revision', 'Mudanças de classe inválidas.') from None
