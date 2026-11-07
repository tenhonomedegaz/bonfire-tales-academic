"""Reproducible source/baseline inventory; no inferred migration equivalences."""
import hashlib
import json
from pathlib import Path

from .ranger_reference import checksum, compare_fixture, extract_reference


def build_inventory(source, baseline, documents=()):
    reference = extract_reference(source)
    comparison = compare_fixture(reference, baseline)
    rows = json.loads(Path(baseline).read_text(encoding='utf-8'))
    classe = next(r for r in rows if r['model'] == 'home.tbclasse'
                  and r['fields'].get('slug') == 'cacador')
    class_id = classe['pk']
    direct = [r for r in rows if r['fields'].get('id_classe') == class_id
              or (r['model'] == 'home.tbbestiario' and r['fields'].get('companheiro_classe') == class_id)]
    option_ids = {r['fields']['id_opcao'] for r in direct if r['model'] == 'home.tbacessoopcao'}
    options = [r for r in rows if r['model'] == 'home.tbopcaojogo' and
               (r['pk'] in option_ids or 'caçador' in str(r['fields']).casefold()
                or 'cacador' in str(r['fields']).casefold())]
    article = reference['article_text'].casefold()
    spells = [r for r in rows if r['model'] == 'home.tbmagia' and (
        'cacador' in (r['fields'].get('classes_slugs') or [])
        or 'caçador' in (r['fields'].get('classes') or '').casefold()
        or any(str(r['fields'].get(key) or '').casefold() in article
               for key in ('nome', 'nome_ingles') if r['fields'].get(key)))]
    selected = {(r['model'], r['pk']): r for r in [classe] + direct + options + spells}
    entries = reference['entries']
    source_matrix = []
    for entry in entries:
        candidates = [f['legacy_id'] for f in comparison['features'] if entry['id'] in f['candidate_ids']]
        source_matrix.append({'source_id': entry['id'], 'owner': entry['owner'],
            'level': entry['level'], 'name': entry['name'], 'legacy_candidates': candidates,
            'effect_source': entry['checksum'], 'action': 'author-new-revision',
            'automatic_equivalence': False})
    for feature in comparison['features']:
        # A same-name/level row is evidence for review, never permission to migrate choices.
        feature['migration_action'] = 'retain-legacy; replace-in-new-catalog; explicitly-reselect-choices'
        feature['new_effects'] = [dict(source_id=e['id'], text=e['section_text'])
                                  for e in entries if e['id'] in feature['candidate_ids']]
        feature['automatic_equivalence'] = False
    docs = []
    for path in documents:
        raw = Path(path).read_bytes()
        lines = raw.decode('utf-8').splitlines()
        docs.append({'path': str(path).replace('\\', '/'), 'sha256': hashlib.sha256(raw).hexdigest(),
                     'findings': [{'line': n, 'text': line} for n, line in enumerate(lines, 1)
                                  if 'caçador' in line.casefold() or 'cacador' in line.casefold()]})
    payload = {'schema': 1, 'scope': 'repository baseline; production preflight still required',
        'reference': reference, 'baseline': comparison,
        'baseline_records': [dict(row, checksum=checksum(row)) for _, row in sorted(selected.items())],
        'association_policy': 'Direct class FKs, option ACLs/text mentions, spell class lists/name mentions. Associations are not migration equivalences.',
        'source_matrix': source_matrix, 'rule_documents': docs,
        'coverage': {'source_entries': len(entries), 'levels': len(reference['progression']),
                     'orders': len(reference['orders']), 'legacy_features': len(comparison['features']),
                     'baseline_records': len(selected)},
        'activation_ready': False}
    payload['checksum'] = checksum(payload)
    return payload


def content_catalog(inventory):
    """Complete level/Order text for consumers; mechanics remain explicit separately."""
    source = inventory['reference']
    return {'schema': 1, 'source_sha256': source['source_sha256'],
            'progression': source['progression'], 'orders': source['orders'],
            'features': [dict(id=e['id'], name=e['name'], level=e['level'],
                              order=e['owner'], text=e['section_text'])
                         for e in source['entries'] if e['level'] is not None]}
