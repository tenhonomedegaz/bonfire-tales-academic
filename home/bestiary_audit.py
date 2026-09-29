"""Read-only, per-creature audit of an exported bestiary snapshot.

Structural checks locate review work; they do not certify RPG semantics.
"""

from collections import Counter
from hashlib import sha256
import json
import re
import unicodedata

from .bestiary_catalog import cr_classification, size_keys, type_key


FEATURE_SECTIONS = (
    'trait', 'traits', 'action', 'actions', 'bonus', 'bonus_actions',
    'reaction', 'reactions', 'legendary', 'legendary_actions',
    'mythic', 'mythic_actions', 'lair', 'lair_actions',
    'regional', 'regional_effects',
)
SUMMON_REF = re.compile(r'\bbestiary\s*\{\s*([^}]+)\s*\}', re.I)
STATIC_REF = re.compile(r'^[a-z0-9_-]+$', re.I)


def normalized_slug(value):
    folded = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', folded).strip('-')


def statblock_hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


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


def audit_snapshot(rows):
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
        classification = {
            'type': type_key(fields.get('tipo')),
            'sizes': list(size_keys(fields.get('tamanho'))),
            'cr': cr_classification(fields.get('nd'))[0],
        }
        if not classification['type']:
            issues.append('type_needs_classification')
        if not classification['sizes']:
            issues.append('size_needs_classification')
        if not (classification['cr'] or '').startswith('nd:'):
            issues.append('cr_needs_review')
        if not isinstance(sb, dict):
            issues.append('statblock_not_object')
            sb = {}

        feature_count = untagged = 0
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
                tags = block.get('tags_json', block.get('tags'))
                if not tags:
                    untagged += 1
                elif not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
                    issues.append(f'{place}:invalid_tag_shape')
                if block.get('tags') and block.get('tags_json'):
                    issues.append(f'{place}:two_tag_sources')

        tags = fields.get('tags_json') or []
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            issues.append('creature_tags_invalid_shape')
            tags = []
        for index, tag in enumerate(tags):
            for reference in SUMMON_REF.findall(tag):
                if not STATIC_REF.fullmatch(reference.strip()):
                    issues.append(f'tags_json[{index}]:dynamic_bestiary_ref_needs_review')
                elif normalized_slug(reference) not in creature_normalized:
                    issues.append(f'tags_json[{index}]:unresolved_bestiary_ref')

        reference_count = 0
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

        if untagged:
            issues.append('untagged_features_need_semantic_review')
        for issue in issues:
            totals[issue.split(':')[-1]] += 1
        result.append({
            'pk': row['pk'], 'slug': fields.get('slug'),
            'classification': classification,
            'mechanics': {'feature_count': feature_count, 'untagged_count': untagged,
                          'status': 'pending_semantic_review'},
            'references': {'spell_count': reference_count},
            'issues': issues,
            'review_destination': ('classification_and_mechanics' if any(
                issue.endswith('needs_classification') or issue == 'cr_needs_review' for issue in issues)
                else 'mechanics_and_references'),
        })
        totals['features'] += feature_count
        totals['untagged_features'] += untagged
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
