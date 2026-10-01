"""Apply a reviewed, source-checked batch of imported creature action tags."""

from copy import deepcopy
from hashlib import sha256
import json
import re

from .bestiary_audit import statblock_hash
from .management.commands.importar_bestiario_csv import _split_secao
from .tag_engine import Library, ERROR, validate_tags_json


class FeatureRetagConflict(ValueError):
    pass


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


def _metric(feet):
    value = int(feet) * 3
    return str(value // 10) if value % 10 == 0 else f'{value // 10},{value % 10}'


def _correct_dual_range(action, source_entries):
    if (not isinstance(source_entries, list) or len(source_entries) != 1 or
            not isinstance(source_entries[0], str) or
            not isinstance(action.get('entries'), list) or len(action['entries']) != 1 or
            not isinstance(action['entries'][0], str)):
        raise FeatureRetagConflict('Texto de alcance nao e simples.')
    matches = re.findall(r'\brange (\d+)/(\d+) ft\b', source_entries[0])
    if len(matches) != 1:
        raise FeatureRetagConflict('Alcance duplo nao comprovado no CSV.')
    short, long = matches[0]
    old = f'alcance {short}/{_metric(long)} m [{long} pés]'
    new = f'alcance {_metric(short)}/{_metric(long)} m [{short}/{long} pés]'
    text = action['entries'][0]
    if text.count(old) != 1:
        raise FeatureRetagConflict('Alcance traduzido divergente.')
    action['entries'] = [text.replace(old, new, 1)]


def _correct_prone_name(action, source_entries):
    if (not isinstance(source_entries, list) or len(source_entries) != 1 or
            not isinstance(source_entries[0], str) or
            not isinstance(action.get('entries'), list) or len(action['entries']) != 1 or
            not isinstance(action['entries'][0], str) or
            not re.search(r'If the target is a (?:Medium|Large) or smaller creature, '
                          r'it has the Prone condition\.', source_entries[0])):
        raise FeatureRetagConflict('Condicao Caido nao comprovada no CSV.')
    text = action['entries'][0]
    old = 'condição Propenso.'
    if text.count(old) != 1:
        raise FeatureRetagConflict('Condicao traduzida divergente.')
    action['entries'] = [text.replace(old, 'condição Caído.', 1)]


def reviewed_statblock(creature, source_row, proposal, *, library=None):
    """Return (copy, changed); refuse any changed source, identity or feature."""
    if (creature.pk != proposal.get('pk') or creature.slug != proposal.get('slug') or
            creature.comunidade or creature.autor_id or
            not isinstance(creature.statblock_json, dict) or
            not isinstance(proposal.get('features'), list) or
            not proposal['features'] or source_row.get('Name', '').strip() !=
            creature.statblock_json.get('name_en')):
        raise FeatureRetagConflict('Identidade da criatura divergente.')
    source = _split_secao(source_row.get('Actions'), {})
    sb = deepcopy(creature.statblock_json)
    actions = sb.get('actions')
    if not isinstance(actions, list) or len(actions) != len(source) or any(
            not isinstance(action, dict) or action.get('name_en') != original['name_en']
            or action.get('entries_en') != original['entries']
            for action, original in zip(actions, source)):
        raise FeatureRetagConflict('Acoes nao correspondem ao CSV.')
    current_hash = statblock_hash(creature.statblock_json)
    already_applied = current_hash == proposal.get('after_sha256')
    seen = set()
    for feature in proposal['features']:
        if not isinstance(feature, dict):
            raise FeatureRetagConflict('Proposta de habilidade invalida.')
        index = feature.get('index')
        tags = feature.get('tags')
        if (not isinstance(index, int) or isinstance(index, bool) or
                index < 0 or index >= len(actions) or index in seen or
                not isinstance(tags, list) or not tags or
                any(not isinstance(tag, str) or not tag.strip() for tag in tags)):
            raise FeatureRetagConflict('Indice ou tags invalidos.')
        seen.add(index)
        action = actions[index]
        if (action.get('name_en') != feature.get('name_en') or
                _digest(source[index]['entries']) != feature.get('source_entries_sha256') or
                'tags' in action):
            raise FeatureRetagConflict('Habilidade ou fonte divergente.')
        existing_tags = action.get('tags_json') or []
        if existing_tags and existing_tags != tags:
            raise FeatureRetagConflict('Habilidade ja possui tags diferentes.')
        correct_range = feature.get('correct_dual_range', False)
        correct_prone = feature.get('correct_prone_name', False)
        if not isinstance(correct_range, bool) or not isinstance(correct_prone, bool):
            raise FeatureRetagConflict('Aprovacao de correcao invalida.')
        diagnostics = validate_tags_json(tags, library or Library(), None, strict_names=True)
        if any(d.level == ERROR for d in diagnostics):
            raise FeatureRetagConflict('Tag mecanica invalida.')
        if already_applied:
            if existing_tags != tags:
                raise FeatureRetagConflict('Resultado existente diverge da revisao.')
        else:
            action['tags_json'] = tags
            if correct_range:
                _correct_dual_range(action, source[index]['entries'])
            if correct_prone:
                _correct_prone_name(action, source[index]['entries'])
    if already_applied:
        return creature.statblock_json, False
    before = proposal.get('before_sha256')
    after = proposal.get('after_sha256')
    if current_hash != before or statblock_hash(sb) != after:
        raise FeatureRetagConflict('Statblock mudou desde a revisao.')
    return sb, True


def source_entries_hash(entries):
    return _digest(entries)
