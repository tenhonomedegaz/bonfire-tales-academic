"""Frozen magical equipment effects; inventory state remains live."""
from copy import deepcopy
from decimal import Decimal
from .content_versions import create_revision, resolve_content
from .models import TbItemMagico
from .versioned_classes import EVALUATOR, VOCABULARY, _fields


def snapshot_magic_items(*, author=None):
    rows = []
    for obj in TbItemMagico.objects.order_by('pk'):
        row = _fields(obj)
        row = {key: str(value) if isinstance(value, Decimal) else value for key, value in row.items()}
        rows.append(row)
    return create_revision('magic-item-catalog', {'schema': 1, 'items': rows}, author=author)


def item_features(ruleset, inventory):
    from .character_engine import _item_magico_equipavel
    data = resolve_content(ruleset, 'magic-item-catalog', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    if data.get('schema') != 1:
        raise ValueError('Unsupported item snapshot.')
    fields = {f.attname for f in TbItemMagico._meta.concrete_fields}
    objects = {}
    for row in data['items']:
        if set(row) != fields:
            raise ValueError('Incompatible item snapshot fields.')
        obj = TbItemMagico(**deepcopy(row))
        objects[obj.pk] = obj
    out = []
    for item in inventory:
        if not item.id_item_magico_id:
            continue
        if item.id_item_magico_id not in objects:
            raise ValueError('Magic item absent from pinned ruleset.')
        obj = objects[item.id_item_magico_id]
        if not item.equipado or not _item_magico_equipavel(obj):
            continue
        if obj.requer_sintonizacao and not item.sintonizado:
            continue
        if obj.tags_json:
            out.append(('item', item.nome, obj, None))
    return out


def snapshot_mundane_items(*, author=None):
    from .models import TbItemMundano
    rows = [{key: str(value) if isinstance(value, Decimal) else value
             for key, value in _fields(obj).items()}
            for obj in TbItemMundano.objects.order_by('pk')]
    return create_revision('mundane-item-catalog', {'schema': 1, 'items': rows}, author=author)


def item_catalog(ruleset, identity, model):
    """Hydrate a validated pinned catalog without reading mutable content."""
    data = resolve_content(ruleset, identity, evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    if data.get('schema') != 1:
        raise ValueError('Unsupported equipment snapshot.')
    fields = {f.attname for f in model._meta.concrete_fields}
    objects = {}
    for row in data['items']:
        if set(row) != fields:
            raise ValueError('Incompatible equipment snapshot fields.')
        obj = model(**deepcopy(row))
        objects[obj.pk] = obj
    return objects


def resolved_inventory(ruleset, inventory):
    """Copy possession state and replace catalog FKs without modifying live rows."""
    from copy import copy
    from .models import TbItemMundano
    catalogs = {}
    for identity, model in (('magic-item-catalog', TbItemMagico),
                            ('mundane-item-catalog', TbItemMundano)):
        catalogs[model] = item_catalog(ruleset, identity, model)
    out = []
    for original in inventory:
        item = copy(original)
        if hasattr(item, '_state'):
            item._state = copy(original._state)
            item._state.fields_cache = dict(original._state.fields_cache)
        item.tags_json = deepcopy(original.tags_json)
        for field, model in (('id_item_magico', TbItemMagico), ('id_item_mundano', TbItemMundano)):
            pk = getattr(original, field + '_id')
            if pk is not None and pk not in catalogs[model]:
                raise ValueError('Equipment identity absent from pinned ruleset.')
            setattr(item, field, catalogs[model].get(pk))
        item._versioned_weapon_catalog = list(catalogs[TbItemMundano].values())
        out.append(item)
    return out
