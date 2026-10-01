"""Apply a reviewed, source-checked batch of imported creature action tags."""

from copy import deepcopy
from hashlib import sha256
import json

from .bestiary_audit import statblock_hash
from .management.commands.importar_bestiario_csv import _split_secao
from .tag_engine import Library, ERROR, validate_tags_json


class FeatureRetagConflict(ValueError):
    pass


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


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
        diagnostics = validate_tags_json(tags, library or Library(), None, strict_names=True)
        if any(d.level == ERROR for d in diagnostics):
            raise FeatureRetagConflict('Tag mecanica invalida.')
        action['tags_json'] = tags
    before = proposal.get('before_sha256')
    after = proposal.get('after_sha256')
    current = statblock_hash(creature.statblock_json)
    if current == after:
        return creature.statblock_json, False
    if current != before or statblock_hash(sb) != after:
        raise FeatureRetagConflict('Statblock mudou desde a revisao.')
    for feature in proposal['features']:
        old = creature.statblock_json['actions'][feature['index']]
        if old.get('tags_json'):
            raise FeatureRetagConflict('Habilidade ja possui tags diferentes.')
    return sb, True


def source_entries_hash(entries):
    return _digest(entries)
