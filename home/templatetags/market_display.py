"""Market presentation filters; the existing catalog remains authoritative."""

import re

from django import template

from home.moeda import preco_em_pc


register = template.Library()
_ICONS = frozenset({
    'arma', 'armadura', 'ferramenta', 'municao', 'foco', 'pacote',
    'montaria', 'veiculo', 'mercadoria', 'veneno', 'explosivo',
    'comida', 'equipamento_aventura', 'guide',
})


@register.filter
def market_symbol(category):
    return category if category in _ICONS else 'equipamento_aventura'


@register.filter
def copper_price(value):
    """Use the same parser as checkout; an unpriced entry stays unpriced."""
    amount = preco_em_pc(value)
    return amount if amount is not None else ''


@register.filter
def mastery_labels(value):
    """Expand authored mastery labels for display without changing their keys."""
    return re.sub(
        r'\b([a-zà-öø-ÿ]+)_([a-z]+)\b',
        lambda match: f'{match[1].capitalize()} ({match[2].capitalize()})',
        str(value or ''), flags=re.I,
    )


@register.filter
def market_lookup(mapping, identity):
    return (mapping or {}).get(str(identity), [])
