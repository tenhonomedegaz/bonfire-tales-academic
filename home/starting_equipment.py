"""Resolve equipamento inicial declarado pela linguagem de tags.

O criador não conhece classes nem nomes de itens. Ele consome um bloco
``starting_equipment{...}``, resolve referências ao catálogo e devolve um plano
validado. Classes novas só precisam declarar outro bloco com a mesma gramática.
"""
from collections import OrderedDict
from copy import deepcopy

from .tag_engine import parse_tags


def _scalar(node, key, default=None):
    child = next((item for item in node.children if item.name == key), None)
    if child is None or child.value in (None, ''):
        return default
    return child.value


def _positive_int(value, default=1):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _label(value):
    return str(value or '').replace('_', ' ').strip().capitalize()


def _item_payload(item, qty=1):
    return {
        'id': item.pk,
        'slug': item.slug,
        'nome': item.nome,
        'qty': _positive_int(qty),
        'categoria': item.categoria,
        'subcategoria': item.subcategoria or '',
        'custo': str(item.preco) if item.preco is not None else None,
        'peso': str(item.peso) if item.peso is not None else None,
        'tags_json': deepcopy(item.tags_json or []),
    }


def _item_from_node(node, by_slug):
    slug = str(_scalar(node, 'slug', '') or '').strip()
    item = by_slug.get(slug)
    return _item_payload(item, _scalar(node, 'qty', 1)) if item else None


def _currency(node):
    block = next((child for child in node.children
                  if child.name == 'currency' and child.operator == 'block'), None)
    return _positive_int(_scalar(block, 'po', 0) if block else 0, default=0)


def _catalog_options(node, queryset):
    category = str(_scalar(node, 'category', '') or '').strip()
    subcategory = str(_scalar(node, 'subcategory', '') or '').strip()
    prefix = str(_scalar(node, 'subcategory_prefix', '') or '').strip()
    if not category:
        return []
    qs = [item for item in queryset if item.categoria == category
          and (not subcategory or item.subcategoria == subcategory)
          and (not prefix or (item.subcategoria or '').startswith(prefix))]
    qty = _positive_int(_scalar(node, 'qty', 1))
    return [{
        'value': item.slug,
        'label': item.nome,
        'items': [_item_payload(item, qty)],
    } for item in sorted(qs, key=lambda item: (item.nome, item.pk))]


def _option_from_node(node, by_slug, queryset):
    catalog = _catalog_options(node, queryset)
    if catalog:
        return catalog

    nested = [_item_from_node(child, by_slug)
              for child in node.children if child.name == 'item']
    if any(item is None for item in nested):
        return []
    direct_slug = str(_scalar(node, 'slug', '') or '').strip()
    if direct_slug:
        item = by_slug.get(direct_slug)
        if not item:
            return []
        nested.append(_item_payload(item, _scalar(node, 'qty', 1)))
    if not nested:
        return []

    key = str(_scalar(node, 'key', '') or '').strip()
    key = key or '+'.join(item['slug'] for item in nested)
    explicit_label = _scalar(node, 'label', '')
    label = _label(explicit_label) if explicit_label else ' + '.join(
        ('%dx %s' % (item['qty'], item['nome'])) if item['qty'] > 1 else item['nome']
        for item in nested)
    return [{'value': key, 'label': label, 'items': nested}]


def starting_equipment_for_class(classe, *, ruleset=None):
    """Retorna o kit estruturado de ``classe`` ou ``None`` se ele não foi declarado."""
    from .models import TbItemMundano

    if ruleset is not None:
        from .versioned_classes import VersionedClassCatalog
        classe = VersionedClassCatalog(ruleset, classe.pk).classe

    root = next((node for node in parse_tags(classe.tags_json or []).nodes
                 if node.name == 'starting_equipment' and node.operator == 'block'), None)
    if root is None:
        return None

    if ruleset is None:
        queryset = list(TbItemMundano.objects.all())
    else:
        from .versioned_items import item_catalog
        queryset = list(item_catalog(ruleset, 'mundane-item-catalog', TbItemMundano).values())
    by_slug = {item.slug: item for item in queryset}
    static_items = [_item_from_node(node, by_slug)
                    for node in root.children if node.name == 'item']
    static_items = [item for item in static_items if item]
    referenced = sum(1 for node in root.children if node.name == 'item')
    missing = max(0, referenced - len(static_items))

    choices = []
    for index, pick in enumerate(node for node in root.children if node.name == 'pick'):
        options = []
        for option_node in (node for node in pick.children if node.name == 'option'):
            options.extend(_option_from_node(option_node, by_slug, queryset))
        choices.append({
            'key': 'equipment_pick_%d' % (index + 1),
            'count': _positive_int(_scalar(pick, 'count', 1)),
            'label': 'Escolha de equipamento %d' % (index + 1),
            'options': options,
        })
        if not options:
            missing += 1

    alternative = next((node for node in root.children
                        if node.name == 'alternative' and node.operator == 'block'), None)
    return {
        'items': static_items,
        'choices': choices,
        'currency_po': _currency(root),
        'alternative_po': _currency(alternative) if alternative else 0,
        'valid': missing == 0 and all(group['options'] for group in choices),
        'missing_references': missing,
    }


def resolve_starting_equipment(classe, mode, selections=None, *, ruleset=None):
    """Valida escolhas e materializa itens do kit sem persistir nada."""
    schema = starting_equipment_for_class(classe, ruleset=ruleset)
    errors = []
    if schema is None or not schema['valid']:
        errors.append('O equipamento inicial desta classe ainda não foi configurado corretamente.')
        return {'schema': schema, 'items': [], 'currency_po': 0}, errors

    if mode == 'ouro':
        return {
            'schema': schema,
            'items': [],
            'currency_po': schema['alternative_po'],
        }, errors

    selections = selections if isinstance(selections, dict) else {}
    chosen_items = list(schema['items'])
    for group in schema['choices']:
        raw = selections.get(group['key'], [])
        values = [str(value) for value in (raw if isinstance(raw, list) else [raw]) if value]
        if len(values) != group['count'] or len(set(values)) != len(values):
            errors.append('%s: escolha %d opção(ões).' % (group['label'], group['count']))
            continue
        options = {option['value']: option for option in group['options']}
        if any(value not in options for value in values):
            errors.append('%s contém uma opção inválida.' % group['label'])
            continue
        for value in values:
            chosen_items.extend(options[value]['items'])

    aggregated = OrderedDict()
    for item in chosen_items:
        if item['slug'] not in aggregated:
            aggregated[item['slug']] = dict(item)
        else:
            aggregated[item['slug']]['qty'] += item['qty']
    return {
        'schema': schema,
        'items': list(aggregated.values()),
        'currency_po': schema['currency_po'],
    }, errors
