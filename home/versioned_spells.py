"""Pinned spell metadata; preparation and manual entries remain character state."""
from .models import TbMagia
from .content_versions import create_revision, resolve_content
from .versioned_classes import EVALUATOR, VOCABULARY, _fields
from copy import deepcopy


def snapshot_spells(*, author=None):
    from .models import TbClasse
    from .character_engine import _slug
    scopes = {}
    for classe in TbClasse.objects.order_by('pk'):
        for key in (classe.slug, classe.nome, _slug(classe.slug), _slug(classe.nome)):
            if key:
                scopes[str(key).strip().lower()] = classe.nome
    return create_revision('spell-catalog', {'schema': 1, 'class_scopes': scopes, 'spells': [
        _fields(m) for m in TbMagia.objects.order_by('pk')]}, author=author)


def spell_catalog(ruleset):
    data = resolve_content(ruleset, 'spell-catalog', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    fields = {f.attname for f in TbMagia._meta.concrete_fields}
    if data.get('schema') != 1 or any(set(row) != fields for row in data['spells']):
        raise ValueError('Invalid pinned spell catalog.')
    return {obj.pk: obj for obj in (TbMagia(**deepcopy(row)) for row in data['spells'])}


def spell_scopes(ruleset):
    data = resolve_content(ruleset, 'spell-catalog', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    scopes = data.get('class_scopes')
    if data.get('schema') != 1 or not isinstance(scopes, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in scopes.items()):
        raise ValueError('Pinned spell catalog lacks class scopes.')
    return scopes
