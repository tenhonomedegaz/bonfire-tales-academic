"""Spell progression opted into by a sealed Hunter revision."""
from .content_versions import resolve_content
from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog


def progression_at(classe, level, ruleset):
    if ruleset is None or 'hunter-rework' not in ruleset.manifest:
        return None
    frozen = VersionedClassCatalog(ruleset, classe.pk).classe
    if frozen.slug != 'cacador':
        return None
    data = resolve_content(ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    marker = data.get('spellcasting_progression')
    if marker is None:
        return None
    if marker != {'version': 1}:
        raise ValueError('Unsupported Hunter spell progression.')
    rows = data.get('progression')
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError('Incomplete Hunter spell progression.')
    for number, row in enumerate(rows, 1):
        if (not isinstance(row, dict) or row.get('level') != number
                or type(row.get('prepared_spells')) is not int or row['prepared_spells'] < 0
                or not isinstance(row.get('slots'), list) or len(row['slots']) != 5
                or any(type(value) is not int or value < 0 for value in row['slots'])):
            raise ValueError('Invalid Hunter spell progression.')
    level = 20 if level is None else int(level)
    if not 1 <= level <= 20:
        raise ValueError('Hunter spell progression requires level 1 through 20.')
    return rows[level - 1]
