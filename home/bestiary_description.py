"""Display projection for imported bestiary descriptions.

The legacy importer stored a generated statblock summary in the description
field. Suppress it only when the current record still matches that summary;
editorial text and stale projections remain visible for review.
"""

import re
import unicodedata


_FEATURE_LINE = re.compile(r'^- \*\*(.+?)\*\*(?: \((.*)\))?$')
_LEGACY_PROSE_NAMES = {
    'sono': 'Sleep',
    'escuridao': 'Darkness',
    'visao-no-escuro': 'Darkvision',
}


def _feature_base(name):
    return re.sub(r'\s*\([^)]*\)$', '', str(name or '')).strip().casefold()


def _accent_fold(value):
    return ''.join(
        char for char in unicodedata.normalize('NFKD', str(value or '').strip().casefold())
        if not unicodedata.combining(char)
    )


def _same_feature_refs(raw_refs, block):
    """A legacy spell mention is safe to hide only when the structured refs agree."""
    from .management.commands.limpar_residuos_banco import _clean_creature_text

    refs = block.get('spell_refs') or []
    if not raw_refs:
        return not refs
    if not refs and (_legacy_prose_refs(raw_refs, block) or
                     _environmental_light_refs(raw_refs, block)):
        return True
    if not isinstance(refs, list):
        return False
    mentioned = [_accent_fold(part) for part in raw_refs.split(',')]
    if len(mentioned) != len(refs):
        return False
    return all(
        isinstance(ref, dict) and name in {
            _accent_fold(ref.get('name')),
            _accent_fold(ref.get('name_en')),
            # The old stored summary translated condition/damage words even
            # inside English spell titles. Resolve against that exact legacy
            # projection of the same structured spell, never by loose words.
            _accent_fold(_clean_creature_text(ref.get('name_en') or '')),
        }
        for name, ref in zip(mentioned, refs)
    )


def _legacy_prose_refs(raw_refs, block):
    """Recognize only source-backed false spell names from existing repair rules."""
    from .bestiary_false_casts import FALSE_CAST_RULES

    rule = FALSE_CAST_RULES.get(block.get('name_en'))
    entries = block.get('entries_en')
    if (not rule or block.get('spell_uses') or not isinstance(entries, list) or
            not entries or any(not isinstance(entry, str) for entry in entries)):
        return False
    text = ' '.join(entries)
    if not rule[0].search(text) or re.search(r'\bcast(?:s|ing)?\b', text, re.I):
        return False
    if any(f'cast{{spell:{slug}}}' in (block.get(key) or [])
           for key in ('tags', 'tags_json') for slug in rule[1]):
        return False
    if not all(slug in _LEGACY_PROSE_NAMES for slug in rule[1]):
        return False
    expected = {_accent_fold(_LEGACY_PROSE_NAMES[slug]) for slug in rule[1]}
    mentioned = [_accent_fold(name) for name in raw_refs.split(',') if name.strip()]
    return len(mentioned) == len(rule[1]) and set(mentioned) == expected


def _environmental_light_refs(raw_refs, block):
    """Old Light/Darkness labels are not spells in a dim-light condition."""
    if [_accent_fold(name) for name in raw_refs.split(',')] != ['light', 'darkness']:
        return False
    if block.get('spell_uses'):
        return False
    if any('cast{spell:' in str(tag) for key in ('tags', 'tags_json')
           for tag in (block.get(key) or [])):
        return False
    entries = block.get('entries_en')
    if not isinstance(entries, list) or not entries or any(not isinstance(entry, str) for entry in entries):
        return False
    text = ' '.join(entries)
    return (bool(re.search(r'\bdim light or darkness\b', text, re.I)) and
            not re.search(r'\bcast(?:s|ing)?\b', text, re.I))


def _duplicate_prose_heading(line, statblock):
    """An old parser sometimes promoted a sentence inside an entry to a heading."""
    from .management.commands.importar_bestiario_csv import SECOES
    from .management.commands.limpar_residuos_banco import _clean_creature_text

    match = _FEATURE_LINE.fullmatch(line)
    if not match or match.group(2):
        return False
    title = _accent_fold(_clean_creature_text(match.group(1)))
    names = set()
    entries = []
    for _, key, _ in SECOES:
        for block in statblock.get(key) or []:
            if not isinstance(block, dict):
                continue
            for name_key in ('name', 'name_en'):
                name = _accent_fold(_clean_creature_text(block.get(name_key) or ''))
                names.update((name, _feature_base(name)))
            for entry_key in ('entries_en', 'entries'):
                values = block.get(entry_key)
                if isinstance(values, list):
                    entries.extend(
                        _accent_fold(_clean_creature_text(entry))
                        for entry in values if isinstance(entry, str)
                    )
    return bool(title and title not in names and any(title in entry for entry in entries))


def _legacy_source_feature_name(block):
    """Rebuild the old base label from the same importer, without its qualifier."""
    from .management.commands.importar_bestiario_csv import _descricao_markdown, _traduz_feature
    from .management.commands.limpar_residuos_banco import _clean_creature_text

    source_name = block.get('name_en')
    if not isinstance(source_name, str) or not source_name.strip():
        return ''
    base = re.sub(r'\s*\([^)]*\)$', '', source_name).strip()
    projection = _clean_creature_text(_descricao_markdown({}, {
        'name': '', 'actions': [{'name': _traduz_feature(base)}],
    }))
    feature = next((line for line in projection.splitlines()
                    if _FEATURE_LINE.fullmatch(line)), '')
    match = _FEATURE_LINE.fullmatch(feature)
    return _accent_fold(match.group(1)) if match else ''


def _same_imported_summary(description, generated, statblock):
    """Accept stale translated feature labels only; metadata and structure stay exact."""
    from .management.commands.importar_bestiario_csv import SECOES
    from .management.commands.limpar_residuos_banco import _clean_creature_text

    actual = [line.strip() for line in description.splitlines() if line.strip()]
    expected = [line.strip() for line in generated.splitlines() if line.strip()]
    if len(actual) != len(expected):
        if len(actual) == len(expected) + 1:
            for index, line in enumerate(actual):
                if (_duplicate_prose_heading(line, statblock) and
                        _same_imported_summary('\n'.join(actual[:index] + actual[index + 1:]),
                                               generated, statblock)):
                    return True
        return False
    features = iter(
        block for _, key, _ in SECOES
        for block in (statblock.get(key) or []) if isinstance(block, dict)
    )
    in_features = False
    for found, target in zip(actual, expected):
        if target.startswith('#### '):
            in_features = target != '#### Magias referenciadas'
        match = _FEATURE_LINE.fullmatch(target) if in_features else None
        if not match:
            if found != target:
                return False
            continue
        block = next(features, None)
        if block is None:
            return False
        actual_match = _FEATURE_LINE.fullmatch(found)
        if not actual_match:
            return False
        names = {
            variant
            for key in ('name', 'name_en')
            for variant in (
                _accent_fold(block.get(key)),
                _accent_fold(_clean_creature_text(block.get(key) or '')),
            )
        }
        actual_name = _accent_fold(actual_match.group(1))
        # A source label may omit a translated qualifier. A different qualifier
        # can change the rule, so keep that summary visible for review.
        bare_name = not re.search(r'\s*\([^)]*\)$', actual_name)
        if actual_name not in names and not (
            bare_name and (
                actual_name in {_feature_base(name) for name in names} or
                actual_name == _legacy_source_feature_name(block)
            )
        ):
            return False
        if not _same_feature_refs(actual_match.group(2), block):
            return False
    return True


def display_description(creature):
    description = (creature.descricao_markdown or '').strip()
    statblock = creature.statblock_json
    if not description or creature.comunidade or not isinstance(statblock, dict) or not statblock.get('name'):
        return description

    from .management.commands.importar_bestiario_csv import _descricao_markdown
    from .management.commands.limpar_residuos_banco import _clean_creature_text

    generated = _descricao_markdown({}, statblock).strip()
    cleaned = _clean_creature_text(generated).strip()
    if description in (generated, cleaned) or _same_imported_summary(description, cleaned, statblock):
        return ''
    return description
