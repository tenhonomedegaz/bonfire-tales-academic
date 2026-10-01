"""Display projection for imported bestiary descriptions.

The legacy importer stored a generated statblock summary in the description
field. Suppress it only when the current record still matches that summary;
editorial text and stale projections remain visible for review.
"""

import re
import unicodedata


_FEATURE_LINE = re.compile(r'^- \*\*(.+?)\*\*(?: \((.*)\))?$')


def _feature_base(name):
    return re.sub(r'\s*\([^)]*\)$', '', str(name or '')).strip().casefold()


def _accent_fold(value):
    return ''.join(
        char for char in unicodedata.normalize('NFKD', str(value or '').strip().casefold())
        if not unicodedata.combining(char)
    )


def _same_feature_refs(raw_refs, block):
    """A legacy spell mention is safe to hide only when the structured refs agree."""
    refs = block.get('spell_refs') or []
    if not raw_refs:
        return not refs
    if not isinstance(refs, list):
        return False
    mentioned = [_accent_fold(part) for part in raw_refs.split(',')]
    if len(mentioned) != len(refs):
        return False
    return all(
        isinstance(ref, dict) and name in {
            _accent_fold(ref.get('name')),
            _accent_fold(ref.get('name_en')),
        }
        for name, ref in zip(mentioned, refs)
    )


def _same_imported_summary(description, generated, statblock):
    """Accept stale translated feature labels only; metadata and structure stay exact."""
    from .management.commands.importar_bestiario_csv import SECOES

    actual = [line.strip() for line in description.splitlines() if line.strip()]
    expected = [line.strip() for line in generated.splitlines() if line.strip()]
    if len(actual) != len(expected):
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
        names = {_accent_fold(block.get(key)) for key in ('name', 'name_en')}
        actual_name = _accent_fold(actual_match.group(1))
        # A source label may omit a translated qualifier. A different qualifier
        # can change the rule, so keep that summary visible for review.
        bare_name = not re.search(r'\s*\([^)]*\)$', actual_name)
        if actual_name not in names and not (
            bare_name and actual_name in {_feature_base(name) for name in names}
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
