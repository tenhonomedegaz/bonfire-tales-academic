"""Display projection for imported bestiary descriptions.

The legacy importer stored a generated statblock summary in the description
field. Suppress it only when the current record still matches that summary;
editorial text and stale projections remain visible for review.
"""

import re


_FEATURE_LINE = re.compile(r'^- \*\*(.+?)\*\*(?: \(.*\))?$')


def _feature_base(name):
    return re.sub(r'\s*\([^)]*\)$', '', str(name or '')).strip().casefold()


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
        names = {str(block.get(key) or '').strip().casefold() for key in ('name', 'name_en')}
        actual_name = actual_match.group(1).strip().casefold()
        # A source label may omit a translated qualifier. A different qualifier
        # can change the rule, so keep that summary visible for review.
        bare_name = not re.search(r'\s*\([^)]*\)$', actual_name)
        if actual_name not in names and not (
            bare_name and actual_name in {_feature_base(name) for name in names}
        ):
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
