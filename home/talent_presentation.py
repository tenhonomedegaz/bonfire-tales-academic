"""Read attribute presentation from unconditional tags, with legacy fallback."""

import re

from .tag_engine.parser import ParseError, parse_tag


_GAIN = re.compile(r"([a-z_]+)\s*([+-]\d+)", re.I)
_CAP = re.compile(r"([a-z_]+)\s*=\s*(\d+)", re.I)
_ATTRIBUTES = ('Forca', 'Destreza', 'Constituicao', 'Inteligencia', 'Sabedoria', 'Carisma')
_ALIASES = dict(zip(('str', 'dex', 'con', 'int', 'wis', 'cha'), _ATTRIBUTES))
_ALIASES.update(dict(zip(('for', 'des', 'con', 'int', 'sab', 'car'), _ATTRIBUTES)))
_CHOICE_TARGETS = {'talent_attr_score', 'asi_attr_score'}
_LABELS = {'Forca': 'Força', 'Constituicao': 'Constituição', 'Inteligencia': 'Inteligência'}


def _unconditional(nodes):
    for node in nodes:
        if node.name in {'attr', 'attr_max'} and node.operator == ':' and not node.qualifiers:
            yield node
        elif node.name == 'always_active' and not node.qualifiers and not any(
                child.name in {'requires', 'if', 'trigger', 'while'} for child in node.children):
            yield from _unconditional(node.children)


def attribute_presentation(tags, legacy_attributes=()):
    nodes = []
    for tag in tags or ():
        try:
            nodes.extend(_unconditional(parse_tag(tag).nodes))
        except (ParseError, TypeError, ValueError):
            continue
    caps = {}
    gains = []
    for node in nodes:
        match = (_GAIN if node.name == 'attr' else _CAP).fullmatch(str(node.value or ''))
        if match is None:
            continue
        target, value = match.groups()
        if len(value) > 16:
            continue
        if node.name == 'attr_max':
            caps[target.lower()] = int(value)
        else:
            gains.append((target.lower(), int(value)))
    options, summaries = [], []
    for target, amount in gains:
        if target in _CHOICE_TARGETS:
            available = list(legacy_attributes) or list(_ATTRIBUTES)
            summary = f'{amount:+d} em um atributo de sua escolha'
        else:
            label = _ALIASES.get(target.removesuffix('_score'))
            if not label:
                continue
            available = [label]
            summary = f'{amount:+d} em {_LABELS.get(label, label)}'
        options.extend(available)
        if target in caps:
            summary += f', até {caps[target]}'
        summaries.append(summary)
    options = list(dict.fromkeys(options or legacy_attributes))
    return {
        'atributos_opcoes': options,
        'atributos_str': ', '.join(options) or 'Nenhum',
        'aumento_atributo': '; '.join(summaries) or ', '.join(options) or 'Nenhum',
    }
