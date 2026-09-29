"""Apply only reviewed, identity-checked spell-slug corrections to a copy."""

from collections import defaultdict
from copy import deepcopy

from .bestiary_audit import normalized_slug, statblock_hash


class RepairConflict(ValueError):
    pass


def _path_value(value, path):
    for part in path:
        if not isinstance(part, (str, int)) or isinstance(part, bool):
            raise RepairConflict('Caminho de referência inválido.')
        try:
            value = value[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise RepairConflict('Caminho de referência ausente.') from exc
    return value


def reconcile_snapshot(rows, report):
    """Return (copy, counts). Any conflict aborts before returning a modified copy."""
    if not isinstance(rows, list) or not isinstance(report, dict):
        raise RepairConflict('Backup ou relatório inválido.')
    candidates = report.get('repair_candidates')
    if not isinstance(candidates, list):
        raise RepairConflict('Relatório sem candidatos de reparo.')
    copied = deepcopy(rows)
    creatures, spells = {}, {}
    for row in copied:
        if row.get('model') == 'home.tbbestiario':
            if row.get('pk') in creatures:
                raise RepairConflict('PK de criatura duplicada.')
            creatures[row.get('pk')] = row
        elif row.get('model') == 'home.tbmagia':
            if row.get('pk') in spells:
                raise RepairConflict('PK de magia duplicada.')
            spells[row.get('pk')] = row
    spell_normalized = defaultdict(set)
    for row in spells.values():
        slug = row['fields'].get('slug')
        if slug:
            spell_normalized[normalized_slug(slug)].add(slug)

    grouped = defaultdict(list)
    seen_paths = set()
    for candidate in candidates:
        pk = candidate.get('creature_pk')
        path = candidate.get('path')
        if (not isinstance(path, list) or len(path) < 3 or path[-1] != 'slug'
                or any(not isinstance(part, (str, int)) or isinstance(part, bool) for part in path)
                or not any(part in ('spell_refs', 'spells') for part in path)):
            raise RepairConflict('Caminho de referência inválido.')
        key = (pk, tuple(path))
        if key in seen_paths:
            raise RepairConflict('Candidato duplicado.')
        seen_paths.add(key)
        creature = creatures.get(pk)
        spell = spells.get(candidate.get('spell_pk'))
        if not creature or creature['fields'].get('slug') != candidate.get('creature_slug'):
            raise RepairConflict('Identidade da criatura divergente.')
        if not spell or spell['fields'].get('slug') != candidate.get('new_slug'):
            raise RepairConflict('Identidade da magia divergente.')
        if (normalized_slug(candidate.get('old_slug')) != normalized_slug(candidate.get('new_slug'))
                or spell_normalized[normalized_slug(candidate.get('new_slug'))] != {candidate.get('new_slug')}):
            raise RepairConflict('Correspondência de slug não é única e exata.')
        grouped[pk].append(candidate)

    applied = unchanged = 0
    for pk, group in grouped.items():
        sb = creatures[pk]['fields'].get('statblock_json')
        if not isinstance(sb, dict):
            raise RepairConflict('Statblock inválido.')
        before_hashes = {candidate.get('expected_statblock_sha256') for candidate in group}
        after_hashes = {candidate.get('expected_after_statblock_sha256') for candidate in group}
        if len(before_hashes) != 1 or len(after_hashes) != 1 or None in before_hashes | after_hashes:
            raise RepairConflict('Revisões esperadas inconsistentes.')
        current_hash = statblock_hash(sb)
        if current_hash == next(iter(after_hashes)):
            if any(_path_value(sb, candidate['path']) != candidate['new_slug'] for candidate in group):
                raise RepairConflict('Resultado existente não confere com o relatório.')
            unchanged += len(group)
            continue
        if current_hash != next(iter(before_hashes)):
            raise RepairConflict('Statblock mudou desde a auditoria.')
        for candidate in group:
            parent = _path_value(sb, candidate['path'][:-1])
            if not isinstance(parent, dict) or parent.get('slug') != candidate['old_slug']:
                raise RepairConflict('Referência de origem divergente.')
            parent['slug'] = candidate['new_slug']
        if statblock_hash(sb) != next(iter(after_hashes)):
            raise RepairConflict('Resultado diverge da revisão esperada.')
        applied += len(group)
    return copied, {'applied': applied, 'unchanged': unchanged}
