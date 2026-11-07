"""Class catalog snapshots and the first engine adapter for sealed content.

Character activation remains unavailable until the other content consumers migrate.
"""
import json
from functools import lru_cache
from pathlib import Path

from django.db import transaction

from .content_versions import create_revision, resolve_content, seal_ruleset
from .models import TbClasse, TbClassehabilidade, TbRecursoclasse, TbSubclasse


EVALUATOR = 'class-features-v1'
VOCABULARY = 'class-catalog-v1'
MODELS = (TbClasse, TbSubclasse, TbClassehabilidade, TbRecursoclasse)


def validate_class_contracts(value):
    if (not isinstance(value, dict) or set(value) - {'spell_grants'}
            or ('spell_grants' in value and value['spell_grants'] != 'tags-v1')):
        raise ValueError('Unsupported class consumer contract.')
    return dict(value)


@lru_cache(maxsize=1)
def _legacy_tag_supplements():
    path = Path(__file__).parent / 'rules' / 'legacy_choice_supplements.json'
    return json.loads(path.read_text(encoding='utf-8')).get('tag_supplements', [])


@lru_cache(maxsize=1)
def _legacy_description_supplements():
    path = Path(__file__).parent / 'rules' / 'legacy_choice_supplements.json'
    return json.loads(path.read_text(encoding='utf-8')).get('description_supplements', [])


def _fields(obj):
    return {field.attname: getattr(obj, field.attname) for field in obj._meta.concrete_fields}


def inventory_class(class_id):
    """Read complete class collections, including empty collections, without writing."""
    with transaction.atomic():
        # Publication must serialize catalog writers before using this draft
        # inventory as a production baseline.
        classe = TbClasse.objects.get(pk=class_id)
        rows = {TbClasse._meta.label_lower: [_fields(classe)]}
        for model in MODELS[1:]:
            rows[model._meta.label_lower] = [
                _fields(obj) for obj in model.objects.filter(id_classe_id=class_id).order_by('pk')]
        return {'schema': 1, 'class_id': class_id, 'collections': rows}


def seal_class_snapshot(class_id, *, author=None):
    """Preparation only: a snapshot does not bind or activate a character."""
    payload = inventory_class(class_id)
    revision = create_revision('class-catalog:%s' % class_id, payload, author=author)
    return seal_ruleset([revision], evaluator_version=EVALUATOR,
                        vocabulary_version=VOCABULARY, author=author)


class VersionedClassCatalog:
    def __init__(self, ruleset, class_id):
        payload = resolve_content(ruleset, 'class-catalog:%s' % class_id,
                                  evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        if payload.get('schema') != 1 or payload.get('class_id') != class_id:
            raise ValueError('Invalid class snapshot.')
        self.contracts = validate_class_contracts(payload.get('contracts', {}))
        self.presentation_source = payload.get('presentation_source')
        if self.presentation_source not in (None, 'catalog'):
            raise ValueError('Unsupported class presentation source.')
        self.collections = {}
        for model in MODELS:
            rows = payload['collections'][model._meta.label_lower]
            allowed = {f.attname for f in model._meta.concrete_fields}
            objects = []
            for row in rows:
                if set(row) != allowed:
                    raise ValueError('Incompatible class snapshot fields.')
                objects.append(model(**row))
            self.collections[model] = objects
        for supplement in _legacy_tag_supplements():
            for feature in self.collections[TbClassehabilidade]:
                if (feature.pk == supplement['feature_pk']
                        and feature.id_classe_id == class_id
                        and feature.id_subclasse_id == supplement['subclass_pk']
                        and supplement['old_tag'] in (feature.tags_json or [])):
                    index = feature.tags_json.index(supplement['old_tag'])
                    feature.tags_json = (feature.tags_json[:index]
                                         + supplement['new_tags']
                                         + feature.tags_json[index + 1:])
        for supplement in _legacy_description_supplements():
            for feature in self.collections[TbClassehabilidade]:
                if (feature.pk == supplement['feature_pk']
                        and feature.id_classe_id == class_id
                        and feature.id_subclasse_id == supplement['subclass_pk']):
                    description = feature.descricao or ''
                    for old, new in supplement['replacements']:
                        description = description.replace(old, new)
                    feature.descricao = description
        classes = self.collections[TbClasse]
        if len(classes) != 1 or classes[0].pk != class_id:
            raise ValueError('Invalid class identity.')
        self.classe = classes[0]
        self.subclasses = {s.pk: s for s in self.collections[TbSubclasse]}
        # Hydrate FK caches from the snapshot to prevent these objects from reading
        # mutable parent rows when consumers access their class/subclass names.
        for model in MODELS[1:]:
            for obj in self.collections[model]:
                if obj.id_classe_id != class_id:
                    raise ValueError('Foreign class in snapshot.')
                obj.id_classe = self.classe
                if hasattr(obj, 'id_subclasse_id'):
                    if obj.id_subclasse_id and obj.id_subclasse_id not in self.subclasses:
                        raise ValueError('Missing subclass in snapshot.')
                    obj.id_subclasse = self.subclasses.get(obj.id_subclasse_id)

    def features(self, level, subclass_id=None):
        from .character_engine import _tag_levels
        if subclass_id is not None and subclass_id not in self.subclasses:
            raise ValueError('Subclass is not part of this ruleset.')
        all_features = self.collections[TbClassehabilidade]
        levels = _tag_levels(self.classe.tags_json, 'subclass-choices')
        if not levels:
            levels = {h.niveladquirido for h in all_features if h.id_subclasse_id is not None}
        unlocked = bool(levels) and level >= min(levels)
        base, subclass = [], []
        for h in sorted(all_features, key=lambda h: (h.niveladquirido, h.nome)):
            if h.niveladquirido > level:
                continue
            if h.id_subclasse_id is None:
                base.append(('classe', self.classe.nome, h, level))
            elif unlocked and h.id_subclasse_id == subclass_id:
                subclass.append(('subclasse', h.id_subclasse.nome, h, level))
        return base + subclass

    def resources(self, level, subclass_id=None):
        # Use the same frozen unlock rule as class features, even when the
        # subclass has no feature at the requested level.
        from .character_engine import _tag_levels
        if subclass_id is not None and subclass_id not in self.subclasses:
            raise ValueError('Subclass is not part of this ruleset.')
        levels = _tag_levels(self.classe.tags_json, 'subclass-choices')
        if not levels:
            levels = {h.niveladquirido for h in self.collections[TbClassehabilidade]
                      if h.id_subclasse_id is not None}
        unlocked = bool(levels) and level >= min(levels)
        return [r for r in self.collections[TbRecursoclasse]
                if r.id_subclasse_id is None
                or (unlocked and r.id_subclasse_id == subclass_id)]


def resolved_classes(ruleset, classes):
    """Preserve character progression while hydrating pinned class identities."""
    from copy import copy
    out = []
    for original in classes:
        catalog = VersionedClassCatalog(ruleset, original.id_classe_id)
        if original.id_subclasse_id is not None and original.id_subclasse_id not in catalog.subclasses:
            raise ValueError('Subclass is not part of this ruleset.')
        row = copy(original)
        if hasattr(row, '_state'):
            row._state = copy(original._state)
            row._state.fields_cache = dict(original._state.fields_cache)
        row.id_classe = catalog.classe
        row.id_subclasse = catalog.subclasses.get(original.id_subclasse_id)
        # The character's permanent choice belongs to this row, never to the
        # shared class catalog. Keep it on the detached object only.
        from .models import TbPersonagemCacador
        profile = (TbPersonagemCacador.objects.filter(personagem_classe_id=original.pk).first()
                   if getattr(original, 'pk', None) else None)
        if profile is not None:
            if profile.ruleset_id != ruleset.pk:
                raise ValueError('Hunter profile and resolved ruleset differ.')
            data = resolve_content(ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                                   vocabulary_version=VOCABULARY)
            choices = data.get('spellcasting_ability_choices')
            if choices is not None:
                if catalog.classe.slug != 'cacador' or profile.ability not in choices:
                    raise ValueError('Invalid pinned Hunter spellcasting ability.')
                row.id_classe._character_spellcasting_ability = (ruleset.pk, profile.ability)
        out.append(row)
    return out
