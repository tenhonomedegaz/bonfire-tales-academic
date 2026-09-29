"""Conservative catalog classification for the existing bestiary fields.

These projections do not rewrite imported statblocks. Unrecognized values stay
unclassified so an editor can resolve them against their source.
"""

import re
import unicodedata
from fractions import Fraction


TYPE_LABELS = {
    'aberracao': 'Aberração', 'besta': 'Besta', 'celestial': 'Celestial',
    'construto': 'Construto', 'corruptor': 'Corruptor', 'dragao': 'Dragão',
    'elemental': 'Elemental', 'feerico': 'Feérico', 'gigante': 'Gigante',
    'humanoide': 'Humanoide', 'limo': 'Limo', 'monstruosidade': 'Monstruosidade',
    'morto-vivo': 'Morto-vivo', 'planta': 'Planta',
}
TYPE_ALIASES = {
    'aberration': 'aberracao', 'beast': 'besta', 'celestial': 'celestial',
    'construct': 'construto', 'fiend': 'corruptor', 'dragon': 'dragao',
    'elemental': 'elemental', 'fey': 'feerico', 'giant': 'gigante',
    'humanoid': 'humanoide', 'ooze': 'limo', 'monstrosity': 'monstruosidade',
    'undead': 'morto-vivo', 'plant': 'planta',
}
SIZE_LABELS = {
    'T': 'Mínimo', 'S': 'Pequeno', 'M': 'Médio', 'L': 'Grande',
    'H': 'Enorme', 'G': 'Colossal',
}
SIZE_ALIASES = {
    't': 'T', 'tiny': 'T', 'minimo': 'T', 'minusculo': 'T',
    's': 'S', 'small': 'S', 'pequeno': 'S',
    'm': 'M', 'medium': 'M', 'medio': 'M',
    'l': 'L', 'large': 'L', 'grande': 'L',
    'h': 'H', 'huge': 'H', 'enorme': 'H',
    'g': 'G', 'gargantuan': 'G', 'colossal': 'G', 'descomunal': 'G',
}
SIZE_COMBINATIONS = {
    'small or medium': ('S', 'M'),
    'huge or gargantuan': ('H', 'G'),
    'tiny, small, medium, large, or huge': ('T', 'S', 'M', 'L', 'H'),
}
SWARM_TYPES = {
    'beasts': 'besta', 'monstrosities': 'monstruosidade',
    'aberrations': 'aberracao', 'fiends': 'corruptor',
    'mortos-vivos': 'morto-vivo',
}
MULTI_TYPES = {
    'celestial, fey, or fiend': ('celestial', 'feerico', 'corruptor'),
    'celestial ou corruptor (tita)': ('celestial', 'corruptor'),
    'celestial ou corruptor (tit\ufffd)': ('celestial', 'corruptor'),
}
CR_PATTERN = re.compile(r'^\s*(\d+(?:/\d+)?)(?:\s*\(.*\))?\s*$')


def _fold(value):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(ch)).strip().casefold()


def type_key(value):
    raw = _fold(value)
    if not raw:
        return None
    base = raw.split(' (', 1)[0]
    if base in TYPE_LABELS:
        return base
    if base in TYPE_ALIASES:
        return TYPE_ALIASES[base]
    if re.fullmatch(r'enxame de mortos-vivos mi.dos', base):
        return 'morto-vivo'
    swarm = re.fullmatch(r'swarm of (?:tiny|small|medium) ([a-z]+)', base)
    return SWARM_TYPES.get(swarm.group(1)) if swarm else None


def type_keys(value):
    """Return all explicitly listed types; ambiguous or unknown types stay pending."""
    single = type_key(value)
    if single:
        return (single,)
    return MULTI_TYPES.get(_fold(value), ())


def size_keys(value):
    raw = _fold(value)
    if raw in SIZE_ALIASES:
        return (SIZE_ALIASES[raw],)
    return SIZE_COMBINATIONS.get(raw, ())


def cr_classification(value):
    """Return (filter key, numeric sort key, label); unknown CR is not zero."""
    raw = str(value or '').strip()
    if not raw:
        return None, float('inf'), ''
    match = CR_PATTERN.fullmatch(raw)
    if not match:
        return 'raw:' + raw, float('inf'), raw
    try:
        number = Fraction(match.group(1))
    except (ValueError, ZeroDivisionError):
        return 'raw:' + raw, float('inf'), raw
    key = str(number.numerator) if number.denominator == 1 else str(number)
    return 'nd:' + key, float(number), key
