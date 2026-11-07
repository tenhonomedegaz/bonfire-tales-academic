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
    'construct': 'construto', 'fiend': 'corruptor', 'demonio': 'corruptor',
    'dragon': 'dragao', 'elemental': 'elemental', 'fey': 'feerico',
    'fada': 'feerico', 'giant': 'gigante',
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
USAGE_LABELS = {
    'owner_scaled': 'Escala com dono',
    'linked_companion': 'Classe/subclasse',
}
SWARM_TYPES = {
    'beasts': 'besta', 'monstrosities': 'monstruosidade',
    'aberrations': 'aberracao', 'fiends': 'corruptor',
    'mortos-vivos': 'morto-vivo',
}
MULTI_TYPES = {
    'planta ou besta': ('planta', 'besta'),
    'celestial, fey, or fiend': ('celestial', 'feerico', 'corruptor'),
    'celestial, feerico ou corruptor': ('celestial', 'feerico', 'corruptor'),
    'celestial ou corruptor (tita)': ('celestial', 'corruptor'),
    'celestial ou corruptor (tit\ufffd)': ('celestial', 'corruptor'),
}
CR_PATTERN = re.compile(r'^\s*(\d+(?:/\d+)?)(?:\s*\(.*\))?\s*$')
UNRATED_PATTERN = re.compile(r'^None(?:\s*\(.*\))?$', re.I)


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


def usage_keys(owner_scaled=False, companion_class_id=None, companion_subclass_id=None):
    """Project explicit owner scaling and class links independently of creature type."""
    keys = []
    if owner_scaled:
        keys.append('owner_scaled')
    if companion_class_id is not None or companion_subclass_id is not None:
        keys.append('linked_companion')
    return tuple(keys)


def is_statblock_placeholder(value):
    """A name/type shell is not a playable statblock, even for an owner-scaled summon."""
    if not isinstance(value, dict):
        return True
    if 'variant_refs' in value or 'selection_note' in value:
        refs = value.get('variant_refs')
        return not (
            isinstance(value.get('selection_note'), str)
            and value['selection_note'].strip()
            and isinstance(refs, list) and bool(refs)
            and all(isinstance(ref, dict)
                    and isinstance(ref.get('name'), str) and ref['name'].strip()
                    and isinstance(ref.get('slug'), str)
                    and re.fullmatch(r'[a-z0-9-]+', ref['slug'])
                    for ref in refs)
        )
    if 'forms' in value:
        forms = value['forms']
        if not isinstance(forms, list) or not forms or any(
                is_statblock_placeholder(form) for form in forms):
            return True
    return not any(item for key, item in value.items()
                   if key not in {'name', 'type', 'size', 'cr', 'alignment'})


def cr_classification(value):
    """Return (filter key, numeric sort key, label); unknown CR is not zero."""
    raw = '' if value is None else str(value).strip()
    if not raw:
        return 'pending', float('inf'), 'ND pendente'
    if UNRATED_PATTERN.fullmatch(raw):
        return 'unrated', float('inf'), 'Sem ND fixo'
    match = CR_PATTERN.fullmatch(raw)
    if not match:
        return 'raw:' + raw, float('inf'), raw
    try:
        number = Fraction(match.group(1))
    except (ValueError, ZeroDivisionError):
        return 'raw:' + raw, float('inf'), raw
    key = str(number.numerator) if number.denominator == 1 else str(number)
    return 'nd:' + key, float(number), key


def cr_display(value):
    """Display exceptional ND states without replacing the source field."""
    raw = '' if value is None else str(value).strip()
    key, _, label = cr_classification(raw)
    return 'pendente' if key == 'pending' else label if key == 'unrated' else raw


def cr_components(value, statblock=None):
    """Separate source-provided CR, XP and proficiency without inferring mechanics."""
    statblock = statblock if isinstance(statblock, dict) else {}
    structured = value if isinstance(value, dict) else {}
    value = structured.get('cr') if structured else value
    raw = '' if value is None else str(value).strip()
    key, _, label = cr_classification(raw)
    nd = 'pendente' if key == 'pending' else label if key.startswith('nd:') or key == 'unrated' else raw
    xp_match = re.search(r'\b(?:XP|PX)\s*:?\s*(\d[\d., ]*)', raw, re.I)
    if xp_match is None:
        xp_match = re.search(r'(\d[\d., ]*)\s*(?:XP|PX)\b', raw, re.I)
    pb_match = re.search(
        r'\b(?:PB|BP|b[oô]nus de profici[eê]ncia)\s*:?\s*(.*?)(?=[;)]|\b(?:XP|PX)\b|$)', raw, re.I)

    def explicit(keys):
        nested = statblock.get('cr') if isinstance(statblock.get('cr'), dict) else {}
        for source in (structured, nested, statblock):
            for field in keys:
                candidate = source.get(field)
                if isinstance(candidate, (str, int, float)) and not isinstance(candidate, bool):
                    return str(candidate).strip()
        return ''

    xp = xp_match.group(1).strip(' ,;') if xp_match else explicit(('xp', 'experience', 'experience_points'))
    pb = pb_match.group(1).strip(' ,;') if pb_match else explicit(('pb', 'proficiency_bonus', 'proficiencyBonus'))
    notes = raw
    for match in sorted((match for match in (xp_match, pb_match) if match),
                        key=lambda match: match.start(), reverse=True):
        notes = notes[:match.start()] + notes[match.end():]
    if key.startswith('nd:'):
        notes = re.sub(r'^\s*\d+(?:/\d+)?', '', notes)
    elif key == 'unrated':
        notes = re.sub(r'^None\b', '', notes, flags=re.I)
    else:
        notes = ''
    return {'nd': nd, 'xp': xp, 'pb': pb, 'notes': notes.strip(' ();,\t'), 'source': raw}


# Native SVG paths, keyed by canonical creature type rather than creature name.
TYPE_ICON_PATHS = {
    'aberracao': ('M3 12Q12 2 21 12Q12 22 3 12Z', 'M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6', 'M5 5L3 2M19 5L21 2M5 19L3 22M19 19L21 22'),
    'besta': ('M7 18Q5 14 9 13Q12 10 15 13Q19 14 17 18Q15 21 12 19Q9 21 7 18Z', 'M5 8a2 3 0 1 0 0 .1M10 5a2 3 0 1 0 0 .1M15 5a2 3 0 1 0 0 .1M20 8a2 3 0 1 0 0 .1'),
    'celestial': ('M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6', 'M8 10L2 5L3 12L8 15M16 10L22 5L21 12L16 15M12 2V5M12 19V22'),
    'construto': ('M6 5H18V20H6ZM9 2V5M15 2V5M2 9H6M18 9H22M2 16H6M18 16H22', 'M9 10H10M14 10H15M9 16H15'),
    'corruptor': ('M6 9L3 2L10 6M18 9L21 2L14 6', 'M5 9Q12 3 19 9V15L12 22L5 15ZM8 11L10 12M16 11L14 12M9 17H15'),
    'dragao': ('M3 18L6 10L4 3L11 7L19 6L22 11L17 16H12L9 21', 'M11 7L14 2L15 7M17 10H18M7 13L12 15'),
    'elemental': ('M12 2C15 8 22 9 20 16A8 8 0 0 1 4 16C2 11 9 9 8 5L12 9Z', 'M12 12C17 16 14 21 10 19C7 17 10 15 12 12Z'),
    'feerico': ('M12 7V21M10 3L12 7L14 3', 'M12 10C3 0 0 10 8 13C0 18 7 23 12 16C17 23 24 18 16 13C24 10 21 0 12 10Z'),
    'gigante': ('M2 21L8 7L12 15L16 4L22 21Z', 'M14 12L16 9L19 15M6 21V17H8V21'),
    'humanoide': ('M12 3a4 4 0 1 0 0 8a4 4 0 1 0 0-8', 'M4 22V19a8 8 0 0 1 16 0V22'),
    'limo': ('M3 18Q0 14 6 12Q7 0 14 5Q20 3 20 12Q26 18 20 21H5Z', 'M10 13H11M15 12H16M11 17Q14 19 17 16'),
    'monstruosidade': ('M3 21L7 3L11 16M10 21L14 2L17 16M17 21L21 5L22 19',),
    'morto-vivo': ('M5 15A9 9 0 1 1 19 15L17 17V21H7V17Z', 'M8 10H9M15 10H16M12 13L10 16H14ZM10 18V21M14 18V21'),
    'planta': ('M12 22V10M12 16C2 18 1 8 2 5C10 5 14 9 12 16ZM12 12C11 4 18 1 22 2C23 9 18 14 12 12Z',),
}


def creature_type_icons(value):
    keys = type_keys(value) or ('pending',)
    return [{'key': key, 'label': TYPE_LABELS.get(key, 'Tipo pendente'),
             'paths': TYPE_ICON_PATHS.get(key, ('M12 2L22 12L12 22L2 12Z', 'M12 7V13M12 17H12.01'))}
            for key in keys]
