"""Display projection for imported bestiary descriptions.

The legacy importer stored a generated statblock summary in the description
field. Suppress it only when the current record still matches that summary;
editorial text and stale projections remain visible for review.
"""


def display_description(creature):
    description = (creature.descricao_markdown or '').strip()
    statblock = creature.statblock_json
    if not description or creature.comunidade or not isinstance(statblock, dict) or not statblock.get('name'):
        return description

    from .management.commands.importar_bestiario_csv import _descricao_markdown
    from .management.commands.limpar_residuos_banco import _clean_creature_text

    generated = _descricao_markdown({}, statblock).strip()
    if description in (generated, _clean_creature_text(generated).strip()):
        return ''
    return description
