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


def false_cast_slugs(feature):
    if not isinstance(feature, dict) or feature.get('spell_uses'):
        return frozenset()
    rule = FALSE_CAST_RULES.get(feature.get('name_en'))
    if not rule:
        return frozenset()
    entries = feature.get('entries_en')
    if not isinstance(entries, list) or any(not isinstance(entry, str) for entry in entries):
        return frozenset()
    text = ' '.join(entries)
    if not rule[0].search(text) or re.search(r'\bcast(?:s|ing)?\b', text, re.I):
        return frozenset()
    slugs = rule[1]
    if not all(f'cast{{spell:{slug}}}' in (feature.get('tags') or [])
               for slug in slugs):
        return frozenset()
    return slugs


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
