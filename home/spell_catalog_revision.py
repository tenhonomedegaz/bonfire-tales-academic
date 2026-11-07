"""Add reviewed source spells to a new sealed catalog; never rewrite a revision."""
from copy import deepcopy
import json
import re

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from .content_versions import create_revision, digest, resolve_content, seal_ruleset
from .db_access import ApiProblem, MAX_BODY_BYTES, MODEL_ALLOWLIST, row_version
from .models import TbMagia, TbRuleset
from .versioned_classes import EVALUATOR, VOCABULARY, _fields
from .tag_engine.library import Library
from .tag_engine.validator import ERROR, validate_tags_json


def _prepare(payload, *, lock=False):
    if (not isinstance(payload, dict) or set(payload) != {'base_version', 'spells'}
            or not isinstance(payload['base_version'], str)
            or not re.fullmatch(r'[a-f0-9]{64}', payload['base_version'])
            or not isinstance(payload['spells'], list) or not 1 <= len(payload['spells']) <= 10):
        raise ApiProblem(400, 'invalid_spell_revision', 'Informe base_version e de uma a dez magias revisadas.')
    seen = set()
    for entry in payload['spells']:
        if (not isinstance(entry, dict) or set(entry) != {'id', 'version'}
                or type(entry['id']) is not int or entry['id'] <= 0
                or entry['id'] in seen or not isinstance(entry['version'], str)
                or not re.fullmatch(r'[a-f0-9]{64}', entry['version'])):
            raise ApiProblem(400, 'invalid_spell_revision', 'Identidades distintas e versoes de detalhe sao obrigatorias.')
        seen.add(entry['id'])
    query = TbRuleset.objects.select_for_update() if lock else TbRuleset.objects
    base = query.get(checksum=payload['base_version'])
    data = resolve_content(base, 'spell-catalog', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    allowed = {field.attname for field in TbMagia._meta.concrete_fields}
    if (data.get('schema') != 1 or not isinstance(data.get('spells'), list)
            or not isinstance(data.get('class_scopes'), dict)
            or any(not isinstance(key, str) or not isinstance(value, str)
                   for key, value in data['class_scopes'].items())):
        raise ValueError('Invalid spell catalog.')
    vocabulary = resolve_content(base, 'tag-library', evaluator_version=EVALUATOR,
                                 vocabulary_version=VOCABULARY)
    if vocabulary.get('schema') != 1 or not isinstance(vocabulary.get('library'), dict):
        raise ValueError('Invalid pinned vocabulary.')
    library = Library(raw=vocabulary['library'], prefer_db=False)
    data = deepcopy(data)
    ids, slugs = {}, set()
    for row in data['spells']:
        if (not isinstance(row, dict) or set(row) != allowed
                or type(row['id_magia']) is not int or row['id_magia'] <= 0
                or not isinstance(row['slug'], str) or not row['slug']
                or row['id_magia'] in ids or row['slug'] in slugs):
            raise ValueError('Invalid spell identity in base catalog.')
        ids[row['id_magia']] = row
        slugs.add(row['slug'])
    items = []
    for entry in sorted(payload['spells'], key=lambda item: item['id']):
        source = (TbMagia.objects.select_for_update() if lock else TbMagia.objects).get(pk=entry['id'])
        source.full_clean(validate_unique=False)
        version = row_version(source, MODEL_ALLOWLIST['magia'])
        if version != entry['version']:
            raise ApiProblem(412, 'spell_source_changed', 'A magia mudou apos a revisao; releia o detalhe.')
        row = _fields(source)
        if source.pk in ids:
            if ids[source.pk] != row:
                raise ApiProblem(409, 'spell_identity_conflict', 'A PK ja existe com outro conteudo; sobrescrita recusada.')
            action = 'unchanged'
        else:
            if source.slug in slugs:
                raise ApiProblem(409, 'spell_identity_conflict', 'O slug ja existe com outra PK; sobrescrita recusada.')
            if (not isinstance(source.tags_json, list) or not all(isinstance(tag, str) for tag in source.tags_json)
                    or not isinstance(source.classes_slugs, list)
                    or not all(isinstance(slug, str) for slug in source.classes_slugs)):
                raise ApiProblem(400, 'invalid_source_spell', 'Listas mecanicas da magia devem conter textos.')
            if len(json.dumps(row, ensure_ascii=False, allow_nan=False).encode('utf-8')) > MAX_BODY_BYTES:
                raise ApiProblem(413, 'spell_source_too_large', 'Magia excede o limite individual de 64 KiB.')
            if any(issue.level == ERROR for issue in validate_tags_json(source.tags_json, library)):
                raise ApiProblem(400, 'invalid_pinned_spell_tags', 'Tags invalidas no vocabulario da revisao de base.')
            data['spells'].append(row)
            ids[source.pk] = row
            slugs.add(source.slug)
            action = 'add'
        items.append({'id': source.pk, 'slug': source.slug, 'version': version, 'action': action})
    entry = base.entries.select_related('revision').get(identity='spell-catalog')
    dependencies = entry.revision.dependencies
    revision_checksum = digest({'identity': 'spell-catalog', 'payload': data, 'dependencies': dependencies})
    manifest = {**base.manifest, 'spell-catalog': revision_checksum}
    checksum = digest({'manifest': manifest, 'evaluator': EVALUATOR, 'vocabulary': VOCABULARY})
    result = {'base_version': base.checksum, 'ruleset_checksum': checksum,
              'revision_checksum': revision_checksum, 'items': items,
              'added': sum(item['action'] == 'add' for item in items), 'activated': False}
    return base, data, dependencies, result


def _run(payload, *, apply=False):
    try:
        base, data, dependencies, result = _prepare(payload, lock=apply)
        if apply and result['added']:
            revision = create_revision('spell-catalog', data, dependencies=dependencies)
            unchanged = [entry.revision for entry in base.entries.select_related('revision')
                         if entry.identity != 'spell-catalog']
            target = seal_ruleset(unchanged + [revision], evaluator_version=EVALUATOR,
                                  vocabulary_version=VOCABULARY)
            if target.checksum != result['ruleset_checksum']:
                raise ValueError('Preview and sealed result differ.')
        return result
    except TbRuleset.DoesNotExist:
        raise ApiProblem(404, 'base_not_found', 'Revisao de base nao encontrada.') from None
    except TbMagia.DoesNotExist:
        raise ApiProblem(404, 'spell_not_found', 'Magia de origem nao encontrada.') from None
    except ValidationError:
        raise ApiProblem(400, 'invalid_source_spell', 'Magia de origem invalida; revise o cadastro.') from None
    except (ValueError, KeyError, TypeError, AttributeError, ObjectDoesNotExist):
        raise ApiProblem(409, 'invalid_spell_catalog', 'Catalogo imutavel invalido; revisao recusada.') from None


def spell_catalog_revision_preview_operation(payload, api_key):
    return _run(payload)


@transaction.atomic
def spell_catalog_revision_operation(payload, api_key):
    return _run(payload, apply=True)
