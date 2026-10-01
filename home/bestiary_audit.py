"""Read-only, per-creature audit of an exported bestiary snapshot.

Structural checks locate review work; they do not certify RPG semantics.
"""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import re
import unicodedata

from .bestiary_catalog import cr_classification, size_keys, type_keys, usage_keys
from .tag_engine import ERROR, WARN, Library, validate_tags_json


FEATURE_SECTIONS = (
    'trait', 'traits', 'action', 'actions', 'bonus', 'bonus_actions',
    'reaction', 'reactions', 'legendary', 'legendary_actions',
    'mythic', 'mythic_actions', 'lair', 'lair_actions',
    'regional', 'regional_effects',
)
SUMMON_REF = re.compile(r'\bbestiary\s*\{\s*([^}]+)\s*\}', re.I)
STATIC_REF = re.compile(r'^[a-z0-9_-]+$', re.I)
CAST_SPELL = re.compile(r'cast\{spell:([^,}]+)')


def normalized_slug(value):
    folded = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', folded).strip('-')


def statblock_hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def _path_value(value, path):
    for part in path:
        value = value[part]
    return value


def _spell_references(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'spell_refs' and isinstance(child, list):
                for index, ref in enumerate(child):
                    yield path + (key, index), ref
            elif key == 'spell_uses' and isinstance(child, list):
                for index, use in enumerate(child):
                    if not isinstance(use, dict):
                        continue
                    for spell_index, ref in enumerate(use.get('spells') or []):
                        yield path + (key, index, 'spells', spell_index), ref
            elif isinstance(child, (dict, list)):
                yield from _spell_references(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
                yield from _spell_references(child, path + (index,))


def _mechanical_tags(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ('tags', 'tags_json') and isinstance(child, list):
                for index, tag in enumerate(child):
                    if isinstance(tag, str):
                        yield path + (key, index), tag
            elif isinstance(child, (dict, list)):
                yield from _mechanical_tags(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _mechanical_tags(child, path + (index,))


def audit_snapshot(rows):
    library = Library()
    creatures = [row for row in rows if row.get('model') == 'home.tbbestiario']
    spells = [row for row in rows if row.get('model') == 'home.tbmagia']
    spell_by_slug = {row['fields'].get('slug'): row['pk'] for row in spells if row['fields'].get('slug')}
    spell_by_normalized = {}
    for slug in spell_by_slug:
        spell_by_normalized.setdefault(normalized_slug(slug), []).append(slug)
    creature_slugs = {row['fields'].get('slug') for row in creatures}
    creature_normalized = {normalized_slug(slug) for slug in creature_slugs if slug}
    creature_by_normalized = {}
    for row in creatures:
        creature_by_normalized.setdefault(normalized_slug(row['fields'].get('slug')), []).append(row['pk'])
    result, repairs, totals = [], [], Counter()

    for row in creatures:
        fields = row['fields']
        sb = fields.get('statblock_json')
        issues = []
        kinds = type_keys(fields.get('tipo'))
        classification = {
            'type': kinds[0] if len(kinds) == 1 else None,
            'types': list(kinds),
            'sizes': list(size_keys(fields.get('tamanho'))),
            'cr': cr_classification(fields.get('nd'))[0],
            'usage': list(usage_keys(fields.get('escala_com_dono'),
                                     fields.get('companheiro_classe'),
                                     fields.get('companheiro_subclasse'))),
        }
        if not kinds:
            issues.append('type_needs_classification')
        if not classification['sizes']:
            issues.append('size_needs_classification')
        if not (classification['cr'] or '').startswith('nd:'):
            issues.append('cr_needs_review')
        if not isinstance(sb, dict):
            issues.append('statblock_not_object')
            sb = {}

        feature_count = untagged = legacy_tagged = syntax_errors = syntax_warnings = 0
        for section in FEATURE_SECTIONS:
            blocks = sb.get(section) or []
            if not isinstance(blocks, list):
                issues.append(f'{section}:not_list')
                continue
            names = set()
            for index, block in enumerate(blocks):
                feature_count += 1
                place = f'{section}[{index}]'
                if not isinstance(block, dict):
                    issues.append(f'{place}:not_object')
                    continue
                name = str(block.get('name') or '').strip()
                if not name:
                    issues.append(f'{place}:missing_name')
                elif name.casefold() in names:
                    issues.append(f'{place}:duplicate_name')
                names.add(name.casefold())
                entries = block.get('entries')
                if not isinstance(entries, list) or not entries:
                    issues.append(f'{place}:missing_entries')
                elif any(not isinstance(entry, str) for entry in entries):
                    issues.append(f'{place}:structured_entries_need_review')
                tags = block.get('tags_json')
                legacy_tags = block.get('tags')
                if legacy_tags:
                    legacy_tagged += 1
                    issues.append(f'{place}:legacy_tags_need_review')
                if not tags:
                    untagged += 1
                elif not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
                    issues.append(f'{place}:invalid_tag_shape')
                if legacy_tags and tags:
                    issues.append(f'{place}:two_tag_sources')
                if isinstance(tags, list) and tags and all(isinstance(tag, str) for tag in tags):
                    for diagnostic in validate_tags_json(tags, library, None, strict_names=True):
                        if diagnostic.level == ERROR:
                            syntax_errors += 1
                            issues.append(f'{place}:tag_syntax_error:{diagnostic.code}')
                        elif diagnostic.level == WARN:
                            syntax_warnings += 1
                            issues.append(f'{place}:tag_syntax_warning:{diagnostic.code}')

        tags = fields.get('tags_json') or []
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            issues.append('creature_tags_invalid_shape')
            tags = []
        for diagnostic in validate_tags_json(tags, library, None, strict_names=True):
            if diagnostic.level == ERROR:
                syntax_errors += 1
                issues.append(f'creature_tags:tag_syntax_error:{diagnostic.code}')
            elif diagnostic.level == WARN:
                syntax_warnings += 1
                issues.append(f'creature_tags:tag_syntax_warning:{diagnostic.code}')
        for index, tag in enumerate(tags):
            for reference in SUMMON_REF.findall(tag):
                if not STATIC_REF.fullmatch(reference.strip()):
                    issues.append(f'tags_json[{index}]:dynamic_bestiary_ref_needs_review')
                elif normalized_slug(reference) not in creature_normalized:
                    issues.append(f'tags_json[{index}]:unresolved_bestiary_ref')

        reference_count = 0
        candidate_start = len(repairs)
        for path, ref in _spell_references(sb):
            reference_count += 1
            path_text = '.'.join(map(str, path))
            slug = ref.get('slug') if isinstance(ref, dict) else None
            if not isinstance(slug, str) or not slug:
                issues.append(f'{path_text}:missing_spell_slug')
                continue
            if slug in spell_by_slug:
                continue
            matches = spell_by_normalized.get(normalized_slug(slug), [])
            if len(matches) != 1:
                issues.append(f'{path_text}:unresolved_spell_ref')
                continue
            canonical = matches[0]
            issues.append(f'{path_text}:noncanonical_spell_slug')
            repairs.append({
                'creature_pk': row['pk'], 'creature_slug': fields.get('slug'),
                'expected_statblock_sha256': statblock_hash(sb),
                'path': list(path) + ['slug'], 'old_slug': slug,
                'new_slug': canonical, 'spell_pk': spell_by_slug[canonical],
                'reason': 'unique_normalized_slug_match; review_before_apply',
            })

        for path, tag in _mechanical_tags(sb):
            matches_in_tag = list(CAST_SPELL.finditer(tag))
            if len(matches_in_tag) != 1:
                continue
            slug = matches_in_tag[0].group(1).strip()
            if slug in spell_by_slug:
                continue
            matches = spell_by_normalized.get(normalized_slug(slug), [])
            if len(matches) != 1:
                issues.append(f'{".".join(map(str, path))}:unresolved_cast_spell')
                continue
            canonical = matches[0]
            issues.append(f'{".".join(map(str, path))}:noncanonical_cast_spell')
            new_tag = tag[:matches_in_tag[0].start(1)] + canonical + tag[matches_in_tag[0].end(1):]
            repairs.append({
                'kind': 'tag', 'creature_pk': row['pk'], 'creature_slug': fields.get('slug'),
                'expected_statblock_sha256': statblock_hash(sb),
                'path': list(path), 'old_slug': slug, 'new_slug': canonical,
                'old_tag': tag, 'new_tag': new_tag, 'spell_pk': spell_by_slug[canonical],
                'reason': 'unique_normalized_slug_match; review_before_apply',
            })

        if len(repairs) > candidate_start:
            proposed = deepcopy(sb)
            for candidate in repairs[candidate_start:]:
                parent = _path_value(proposed, candidate['path'][:-1])
                parent[candidate['path'][-1]] = (candidate['new_tag'] if candidate.get('kind') == 'tag'
                                                 else candidate['new_slug'])
            after_hash = statblock_hash(proposed)
            for candidate in repairs[candidate_start:]:
                candidate['expected_after_statblock_sha256'] = after_hash

        if untagged:
            issues.append('untagged_features_need_semantic_review')
        for issue in issues:
            totals[issue.split(':')[-1]] += 1
        result.append({
            'pk': row['pk'], 'slug': fields.get('slug'),
            'classification': classification,
            'mechanics': {'feature_count': feature_count, 'untagged_count': untagged,
                          'legacy_tagged_count': legacy_tagged,
                          'syntax_error_count': syntax_errors, 'syntax_warning_count': syntax_warnings,
                          'status': 'pending_semantic_review'},
            'references': {'spell_count': reference_count},
            'issues': issues,
            'review_destination': ('classification_and_mechanics' if any(
                issue.endswith('needs_classification') or issue == 'cr_needs_review' for issue in issues)
                else 'mechanics_and_references'),
        })
        totals['features'] += feature_count
        totals['untagged_features'] += untagged
        totals['legacy_tagged_features'] += legacy_tagged
        totals['tag_syntax_errors'] += syntax_errors
        totals['tag_syntax_warnings'] += syntax_warnings
        totals['spell_references'] += reference_count

    consumer_references = []
    inbound = Counter()
    for row in rows:
        tags = row.get('fields', {}).get('tags_json') or []
        if not isinstance(tags, list):
            continue
        for tag_index, tag in enumerate(tags):
            if not isinstance(tag, str):
                continue
            for reference in SUMMON_REF.findall(tag):
                value = reference.strip()
                matches = creature_by_normalized.get(normalized_slug(value), []) if STATIC_REF.fullmatch(value) else []
                status = ('dynamic_needs_review' if not STATIC_REF.fullmatch(value) else
                          'resolved' if len(matches) == 1 else
                          'ambiguous' if matches else 'unresolved')
                if status == 'resolved':
                    inbound[matches[0]] += 1
                consumer_references.append({'model': row.get('model'), 'pk': row.get('pk'),
                                            'tag_index': tag_index, 'reference': value,
                                            'status': status, 'creature_pk': matches[0] if len(matches) == 1 else None})
    for record in result:
        record['references']['inbound_bestiary_count'] = inbound[record['pk']]
    return {
        'summary': {'creatures': len(result), 'spells_indexed': len(spell_by_slug),
                    'review_status': 'all_pending_semantic_review',
                    'consumer_references': len(consumer_references),
                    'consumer_references_unresolved': sum(ref['status'] == 'unresolved' for ref in consumer_references),
                    'consumer_references_dynamic': sum(ref['status'] == 'dynamic_needs_review' for ref in consumer_references),
                    **dict(sorted(totals.items()))},
        'records': result,
        'repair_candidates': repairs,
        'consumer_references': consumer_references,
    }
