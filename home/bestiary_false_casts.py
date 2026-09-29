"""Source-backed repairs for prose mistaken for spellcasting in imported traits."""

from copy import deepcopy
import re


FEATURE_SECTIONS = (
    'traits', 'actions', 'bonus_actions', 'reactions', 'legendary_actions',
    'mythic_actions', 'lair_actions', 'regional_effects',
    'trait', 'action', 'bonus', 'reaction', 'legendary', 'mythic', 'lair', 'regional',
)
FALSE_CAST_RULES = {
    'Unusual Nature': (
        re.compile(r"(?:doesn.t require|requires no).*\bsleep\b", re.I | re.S),
        frozenset({'sono'}),
    ),
    'Fey Ancestry': (
        re.compile(r"magic can.t put .* to sleep", re.I | re.S),
        frozenset({'sono'}),
    ),
    "Devil's Sight": (
        re.compile(r"magical darkness doesn.t impede .*darkvision", re.I | re.S),
        frozenset({'escuridao', 'visao-no-escuro'}),
    ),
}
PROSE_COLLISION_SLUGS = frozenset({
    'escuridao', 'telepatia', 'regenerar', 'salto', 'voo',
})


def false_cast_slugs(feature):
    if not isinstance(feature, dict) or feature.get('spell_uses'):
        return frozenset()
    entries = feature.get('entries_en')
    if not isinstance(entries, list) or any(not isinstance(entry, str) for entry in entries):
        return frozenset()
    text = ' '.join(entries)
    tags = feature.get('tags') or []
    false_slugs = set()
    # The English rules use "Resistance" both for a cantrip and for damage
    # resistance. Only the latter is a false spell reference.
    if ('cast{spell:resistencia}' in tags and
            'spellcasting' not in (feature.get('name_en') or '').lower() and
            re.search(r'\bresistance\b', text, re.I) and
            not re.search(r'\b(?:casts?|casting)\s+(?:the\s+)?(?:spell\s+)?resistance\b|'
                          r'\bresistance\s+(?:cantrip|spell)\b|'
                          r'\b(?:cantrips?|spells?\s+(?:prepared|known)|at will)\b',
                          text, re.I)):
        false_slugs.add('resistencia')
    # Light in a statblock usually describes illumination or a lighting
    # condition. It is only the cantrip when the feature explicitly casts it
    # or lists it among spells.
    if ('cast{spell:luz}' in tags and
            'spellcasting' not in (feature.get('name_en') or '').lower() and
            re.search(r'\blight\b', text, re.I) and
            not re.search(r'\b(?:casts?|casting)\s+(?:the\s+)?(?:spell\s+)?light\b|'
                          r'\blight\s+(?:cantrip|spell)\b|'
                          r'\b(?:cantrips?|spells?\s+(?:prepared|known)|at will)\b',
                          text, re.I)):
        false_slugs.add('luz')
    # These names also occur as ordinary environmental or innate mechanics.
    # The importer's spell-context check provides a second, source-text guard
    # before any old reference is removed.
    collisions = {slug for slug in PROSE_COLLISION_SLUGS
                  if f'cast{{spell:{slug}}}' in tags and
                  any(isinstance(ref, dict) and ref.get('slug') == slug
                      for ref in feature.get('spell_refs') or [])}
    if collisions:
        from home.management.commands.importar_bestiario_csv import (
            _cast_refs_in_prose, _feature_spell_refs,
        )
        refs = [ref for ref in feature.get('spell_refs') or [] if isinstance(ref, dict)]
        title = feature.get('name_en') or ''
        cast_slugs = {ref.get('slug') for ref in _cast_refs_in_prose(text, refs, title)}
        linked_slugs = {ref.get('slug') for ref in _feature_spell_refs(text, refs, title)}
        false_slugs.update(collisions - cast_slugs - linked_slugs)
    rule = FALSE_CAST_RULES.get(feature.get('name_en'))
    if (rule and rule[0].search(text) and
            not re.search(r'\bcast(?:s|ing)?\b', text, re.I) and
            all(f'cast{{spell:{slug}}}' in tags for slug in rule[1])):
        false_slugs.update(rule[1])
    return frozenset(false_slugs)


def strip_false_casts(feature):
    """Return a copy and the removed slugs, leaving every other mechanic intact."""
    slugs = false_cast_slugs(feature)
    if not slugs:
        return feature, frozenset()
    result = deepcopy(feature)
    false_tags = {f'cast{{spell:{slug}}}' for slug in slugs}
    for key in ('tags', 'tags_json'):
        if isinstance(result.get(key), list):
            result[key] = [tag for tag in result[key] if tag not in false_tags]
            if not result[key]:
                result.pop(key)
    if isinstance(result.get('spell_refs'), list):
        result['spell_refs'] = [ref for ref in result['spell_refs']
                                if not isinstance(ref, dict) or ref.get('slug') not in slugs]
        if not result['spell_refs']:
            result.pop('spell_refs')
    return result, slugs


def _remaining_feature_values(statblock):
    tags, refs = set(), set()
    for section in FEATURE_SECTIONS:
        for feature in statblock.get(section) or []:
            if not isinstance(feature, dict):
                continue
            for key in ('tags', 'tags_json'):
                tags.update(tag for tag in feature.get(key) or [] if isinstance(tag, str))
            refs.update(ref.get('slug') for ref in feature.get('spell_refs') or []
                        if isinstance(ref, dict) and ref.get('slug'))
            for use in feature.get('spell_uses') or []:
                if not isinstance(use, dict):
                    continue
                tags.update(tag for tag in use.get('tags') or [] if isinstance(tag, str))
                refs.update(ref.get('slug') for ref in use.get('spells') or []
                            if isinstance(ref, dict) and ref.get('slug'))
    return tags, refs


def _remove_description_refs(description, removed_slugs):
    if not isinstance(description, str) or not removed_slugs:
        return description
    lines = description.splitlines(keepends=True)
    pattern = re.compile(r'^- `spell:([^`]+)` - ')
    lines = [line for line in lines
             if not (match := pattern.match(line)) or match.group(1) not in removed_slugs]
    for index, line in enumerate(lines):
        if line.strip() != '#### Magias referenciadas':
            continue
        end = next((i for i in range(index + 1, len(lines)) if lines[i].startswith('#### ')), len(lines))
        if not any(pattern.match(entry) for entry in lines[index + 1:end]):
            del lines[index:end]
        break
    return ''.join(lines)


def repair_false_casts(statblock, tags_json, description):
    if not isinstance(statblock, dict):
        return statblock, tags_json, description, []
    revised = deepcopy(statblock)
    edits = []
    removed_slugs = set()
    for section in FEATURE_SECTIONS:
        features = revised.get(section)
        if not isinstance(features, list):
            continue
        for index, feature in enumerate(features):
            fixed, slugs = strip_false_casts(feature)
            if not slugs:
                continue
            features[index] = fixed
            removed_slugs.update(slugs)
            edits.append({'section': section, 'index': index, 'name_en': feature['name_en'],
                          'entries_en': feature['entries_en'], 'removed_spell_slugs': sorted(slugs)})
    if not edits:
        return statblock, tags_json, description, []
    remaining_tags, remaining_refs = _remaining_feature_values(revised)
    removed_tags = {f'cast{{spell:{slug}}}' for slug in removed_slugs} - remaining_tags
    removed_refs = removed_slugs - remaining_refs
    if isinstance(revised.get('tags'), list):
        revised['tags'] = [tag for tag in revised['tags'] if tag not in removed_tags]
    if isinstance(revised.get('spell_refs'), list):
        revised['spell_refs'] = [ref for ref in revised['spell_refs']
                                 if not isinstance(ref, dict) or ref.get('slug') not in removed_refs]
    revised_tags = ([tag for tag in tags_json if tag not in removed_tags]
                    if isinstance(tags_json, list) else tags_json)
    revised_description = _remove_description_refs(description, removed_refs)
    return revised, revised_tags, revised_description, edits
