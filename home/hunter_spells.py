"""Resolve Hunter grants only from the profile's sealed spell catalog."""
from .content_versions import resolve_content
from .hunter_preparation import preparation
from .models import TbPersonagemCacador
from .versioned_classes import EVALUATOR, VOCABULARY
from .versioned_spells import spell_catalog


def grants_at(ruleset, *, level, order=''):
    spells = list(spell_catalog(ruleset).values())
    data = resolve_content(ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    result = []
    for grant in data.get('spell_grants', []):
        if grant['level'] > level or grant['order'] not in ('', order):
            continue
        identity = grant.get('catalog_identity')
        if identity:
            matches = [spell for spell in spells if spell.slug == identity['slug']
                       and spell.nivel == identity['level']]
        else:
            matches = [spell for spell in spells
                       if (spell.nome_ingles or '').strip().casefold() == grant['english'].strip().casefold()]
        if len(matches) != 1 or not matches[0].slug:
            raise ValueError('Hunter spell absent or ambiguous in pinned catalog: %s' % grant['english'])
        spell = matches[0]
        result.append({'slug': spell.slug, 'nivel': spell.nivel, 'fonte': grant['source']})
    return result


def granted_spells(person, ruleset):
    profiles = list(TbPersonagemCacador.objects.filter(
        personagem_classe__id_personagem=person).select_related('ruleset', 'personagem_classe'))
    if not profiles:
        return []
    if any(profile.ruleset_id != ruleset.pk for profile in profiles):
        raise ValueError('Hunter profile and spell ruleset differ.')
    result = []
    for profile in profiles:
        prepared = preparation(profile, selected=[], allow_pending_order=True)
        result.extend(grants_at(ruleset, level=prepared['level'], order=prepared['order']))
        from .hunter_traveler import final_grants
        result.extend(final_grants(profile))
    return result
