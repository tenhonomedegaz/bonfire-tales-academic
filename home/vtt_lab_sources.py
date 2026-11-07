"""Read-only, source-backed projections for the isolated VTT laboratory.

No model saves, derived HP/AC modifiers, inferred attacks, or class-name rules.
The encounter adapter consumes combat operations only, not sheet derivation.
"""
import re

from .resource_engine import canonical_key
from .tag_engine.parser import ParseError, parse_tag


MAX_SOURCES = 128
MAX_TAGS = 128
MAX_ACTIONS = 64
MAX_TEXT = 4096
MAX_TAG_BYTES = 65536
_ATTRIBUTES = {'FOR': 'str', 'DES': 'dex', 'CON': 'con',
               'INT': 'int', 'SAB': 'wis', 'CAR': 'cha'}
_SECTIONS = ('actions', 'action', 'bonus', 'bonus_actions', 'bonusActions',
             'reaction', 'reactions', 'legendary', 'legendary_actions',
             'lair_actions', 'trait', 'traits', 'features', 'abilities',
             'sources', 'fontes')
_ACTION_NODES = {'instant', 'attack', 'save', 'on', 'on_fail', 'on_success',
                 'trigger', 'cast', 'aoe', 'aura', 'while_active', 'effects', 'resource_cost'}
_UNRESOLVED = {'pick', 'match', 'define', 'list', 'table', 'modify', 'set'}
_GATES = {'requires', 'restriction', 'if', 'else', 'while', 'unless'}
_CONTEXT_RE = re.compile(
    r'\b(?:classlvl|lvl|pb|(?:str|dex|con|int|wis|cha|talent_attr|asi_attr|spell)_(?:mod|score))\b')
_RESOURCE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_:-]{0,179}')


def _resource_text(value, field, limit):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(char) < 32 for char in value)):
        raise ValueError('Invalid bounded resource ' + field + '.')
    return value.strip()


def character_resources(exported):
    """Create neutral lab pools, never read or update official resource balances.

    Keys retain the explicit exported id_fonte; aliases use canonical_key.
    Cross-pool alias collisions remain intact for the adapter to reject.
    Missing resources means no pools; an absent reset means manual reset.
    Malformed rows, opaque IDs containing '?' and duplicate IDs raise ValueError
    for the whole projection instead of silently choosing or inventing a pool.
    """
    if not isinstance(exported, dict):
        raise ValueError('A character export object is required.')
    rows = exported.get('recursos', [])
    if not isinstance(rows, list) or len(rows) > MAX_SOURCES:
        raise ValueError('Invalid bounded exported resources.')
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid exported resource row.')
        resource_id = _resource_text(row.get('id_fonte'), 'id_fonte', 180)
        if not _RESOURCE_ID.fullmatch(resource_id):
            raise ValueError('Resource id_fonte must be explicit, non-opaque and bounded.')
        if resource_id in result:
            raise ValueError('Duplicate exported resource id_fonte: ' + resource_id)
        name = _resource_text(row.get('nome'), 'nome', 200)
        maximum = _integer(row.get('max'), 0, 1000000)
        if maximum is None:
            raise ValueError('Resource max must be an integer from 0 to 1000000.')
        reset = _resource_text(row.get('reset', 'manual'), 'reset', 80)
        alias_sources = [name, resource_id]
        if 'slug' in row and row['slug'] not in (None, ''):
            alias_sources.append(_resource_text(row['slug'], 'slug', 160))
        aliases = []
        for value in alias_sources:
            alias = canonical_key(value)
            if not alias or len(alias) > 200:
                raise ValueError('Resource alias cannot be empty or exceed 200 characters.')
            if alias not in aliases:
                aliases.append(alias)
        result[resource_id] = {'nome': name, 'max': maximum, 'current': maximum,
                               'aliases': aliases, 'reset': reset}
    return result


def _warn(warnings, message):
    if len(warnings) < 64 and message not in warnings:
        warnings.append(message)


def _integer(value, low, high, *, text=False):
    if text and isinstance(value, str) and len(value) <= 12 and re.fullmatch(r'[0-9]+', value):
        value = int(value)
    return value if type(value) is int and low <= value <= high else None


def _label(value, fallback=''):
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= 200 else fallback


def _statblock(creature):
    if getattr(creature, 'escala_com_dono', False):
        raise ValueError('Owner-scaled creatures require an explicit owner context.')
    value = getattr(creature, 'statblock_json', {})
    if not isinstance(value, dict) or len(value) > 128:
        raise ValueError('Invalid bounded creature statblock.')
    return value


def creature_snapshot(creature):
    """Export a fixed HP snapshot; formulas and owner scaling are not guessed."""
    block = _statblock(creature)
    hp = block.get('hp')
    if isinstance(hp, dict) and 'average' in hp:
        maximum = _integer(hp['average'], 1, 2**31 - 1)
    else:
        maximum = _integer(getattr(creature, 'pv', None), 1, 2**31 - 1, text=True)
    if maximum is None:
        raise ValueError('A fixed positive integer HP value is required.')
    pk = _integer(getattr(creature, 'pk', None), 1, 2**53 - 1)
    name = _label(getattr(creature, 'nome', None))
    slug = _label(getattr(creature, 'slug', None))
    if pk is None or not name or not slug:
        raise ValueError('A bounded creature identity is required.')
    derived = {'pv_max': maximum}
    warnings = []
    ac = block.get('ac', getattr(creature, 'ca', None))
    if isinstance(ac, list):
        ac = ac[0] if len(ac) == 1 else None
    if isinstance(ac, dict):
        ac = ac.get('ac')
    ac = _integer(ac, 1, 100, text=True)
    if ac is not None:
        derived['ca'] = ac
    elif block.get('ac') is not None or getattr(creature, 'ca', None) not in (None, ''):
        _warn(warnings, 'partial: AC is conditional or not a fixed integer.')
    return {'versao_contrato': 1, 'versao_menor': 1,
            'criatura': {'pk': pk, 'nome': name, 'slug': slug},
            'derive': derived, 'estado_mesa': {'pv_atual': maximum}, 'avisos': warnings}


def _nodes(program):
    pending = [(node, 0) for node in program.nodes]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > 256 or depth > 16:
            raise ValueError('Tag AST exceeds the bounded projection.')
        yield node
        pending.extend((child, depth + 1) for child in node.children)


def _tags(raw, warnings, source):
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_TAGS:
        _warn(warnings, 'partial: invalid tags in ' + source)
        return None
    if any(not isinstance(tag, str) or not tag.strip() or len(tag) > MAX_TEXT for tag in raw):
        _warn(warnings, 'partial: invalid tag text in ' + source)
        return None
    if sum(len(tag.encode('utf-8')) for tag in raw) > MAX_TAG_BYTES:
        _warn(warnings, 'partial: tag payload too large in ' + source)
        return None
    return list(raw)


def _program(tags, context, warnings, source):
    names = set()
    if any(re.search(r'\bpick\s*:', tag) for tag in tags):
        _warn(warnings, 'partial: unresolved choice operand in ' + source)
        return None
    try:
        for tag in tags:
            nodes = list(_nodes(parse_tag(tag)))
            if any(node.name == 'uses' and 'action' in node.scope for node in nodes):
                _warn(warnings, 'partial: unsupported action.uses resource declaration in ' + source)
                return None
            names.update(node.name for node in nodes)
    except (ParseError, ValueError, RecursionError, TypeError):
        _warn(warnings, 'partial: malformed tag program in ' + source)
        return None
    if names & _UNRESOLVED:
        _warn(warnings, 'partial: unresolved choice or local binding in ' + source)
        return None
    # Source-wide gates must not be detached from their effects or leak to other
    # features when several sources share the actor's single passive context.
    if names & _GATES:
        _warn(warnings, 'partial: gated source needs explicit resolved facts: ' + source)
        return None
    if any(set(_CONTEXT_RE.findall(tag)) - context.keys() for tag in tags):
        _warn(warnings, 'partial: unresolved numeric context in ' + source)
        return None
    return names


def _rules(context=None):
    return {'defensive_tags': [], 'offensive_tags': [], 'tag_context': dict(context or {}),
            'actions': [], 'warnings': []}


def _source(result, tags, source, name, context, *, force_action=False):
    if not tags:
        return
    names = _program(tags, context, result['warnings'], source)
    if names is None:
        return
    if force_action or names & _ACTION_NODES:
        if names & _ACTION_NODES and any(
                node.name in {'resist', 'immune', 'ignore', 'crit_dmg', 'hp', 'ca'}
                and not set(node.scope) & _ACTION_NODES
                for tag in tags for node in _nodes(parse_tag(tag))):
            _warn(result['warnings'], 'partial: mixed source kept whole in its action, not flattened into global passives: ' + source)
        if len(result['actions']) >= MAX_ACTIONS:
            _warn(result['warnings'], 'partial: action limit reached.')
            return
        result['actions'].append({'id': source, 'nome': name, 'tags': list(tags),
                                  'context': dict(context)})
        return
    if any('classlvl' in _CONTEXT_RE.findall(tag) for tag in tags) and (
            context.get('classlvl') != result['tag_context'].get('classlvl')):
        _warn(result['warnings'], 'partial: source classlvl cannot enter actor passive context: ' + source)
        return
    result['defensive_tags'].extend(tags)
    result['offensive_tags'].extend(tags)


def _finish(result):
    if not result['actions']:
        result['actions'].append({'id': 'manual', 'nome': 'Ataque declarado', 'tags': []})
        _warn(result['warnings'], 'partial: manual action only; no supported source-backed action tags.')
    return result


def creature_rules(creature):
    """Expose real root/feature tags, never mechanics inferred from prose or CR."""
    block = _statblock(creature)
    result = _rules()
    root = _tags(getattr(creature, 'tags_json', []), result['warnings'], 'creature root')
    extra = _tags(block.get('tags_json', block.get('tags', [])), result['warnings'], 'statblock root')
    if root is not None and extra is not None:
        _source(result, list(dict.fromkeys(root + extra)), 'root',
                _label(getattr(creature, 'nome', None), 'Creature'), {})
    seen = 0
    for section in _SECTIONS:
        if section not in block:
            continue
        rows = block[section]
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list) or len(rows) > MAX_SOURCES:
            _warn(result['warnings'], 'partial: invalid statblock section: ' + section)
            continue
        for index, row in enumerate(rows):
            seen += 1
            if seen > MAX_SOURCES:
                _warn(result['warnings'], 'partial: creature source limit reached.')
                return _finish(result)
            source = 'statblock.' + section + '.' + str(index)
            if not isinstance(row, dict):
                _warn(result['warnings'], 'partial: malformed source: ' + source)
                continue
            tags = _tags(row.get('tags_json', row.get('tags', [])), result['warnings'], source)
            name = _label(row.get('nome') or row.get('name'))
            if not tags or not name:
                _warn(result['warnings'], 'partial: source without usable name/tags: ' + source)
                continue
            passive = section in {'trait', 'traits'}
            _source(result, tags, source, name, {}, force_action=not passive)
    return _finish(result)


def _character_features(character):
    from .character_engine import _features_do_personagem
    return _features_do_personagem(character)


def _character_choices(character, features):
    from .character_engine import _collect_escolhas
    return _collect_escolhas(character, features)


def _choice_subs(tag, choices):
    from .character_engine import _apply_choice_subs
    return _apply_choice_subs(tag, choices)


def _character_context(exported, warnings):
    derived = exported.get('derive') or {}
    person = exported.get('personagem') or {}
    if not isinstance(derived, dict) or not isinstance(person, dict):
        raise ValueError('Invalid character export.')
    context = {}
    for key, value, low, high in [('lvl', person.get('nivel_total'), 1, 1000),
                                   ('pb', derived.get('pb'), 0, 100)]:
        value = _integer(value, low, high)
        if value is not None:
            context[key] = value
        else:
            _warn(warnings, 'partial: missing exported context: ' + key)
    attributes = derived.get('atributos') or {}
    if not isinstance(attributes, dict):
        raise ValueError('Invalid exported attributes.')
    for label, key in _ATTRIBUTES.items():
        entry = attributes.get(label, {})
        if not isinstance(entry, dict):
            continue
        score = _integer(entry.get('valor'), 1, 100)
        modifier = _integer(entry.get('mod'), -50, 50)
        if score is not None:
            context[key + '_score'] = score
        if modifier is not None:
            context[key + '_mod'] = modifier
    classes = person.get('classes', [])
    if not isinstance(classes, list) or len(classes) > MAX_SOURCES:
        raise ValueError('Invalid exported classes.')
    if len(classes) == 1 and isinstance(classes[0], dict):
        level = _integer(classes[0].get('nivel'), 1, 1000)
        if level is not None:
            context['classlvl'] = level
    return context


def character_rules(character, exported):
    """Only features named by the export's Type:PK identities may contribute."""
    if (not isinstance(exported, dict) or type(exported.get('versao_contrato')) is not int
            or exported['versao_contrato'] != 1):
        raise ValueError('A version-1 character export is required.')
    result = _rules()
    result['tag_context'] = _character_context(exported, result['warnings'])
    rows = exported.get('habilidades', [])
    if not isinstance(rows, list) or len(rows) > MAX_SOURCES:
        raise ValueError('Invalid bounded exported abilities.')
    allowed = set()
    for row in rows:
        source = row.get('fonte') if isinstance(row, dict) else None
        if isinstance(source, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}:[0-9]{1,16}', source):
            allowed.add(source)
        else:
            _warn(result['warnings'], 'partial: malformed exported source identity.')
    features = _character_features(character)
    if not isinstance(features, (list, tuple)) or len(features) > MAX_SOURCES:
        raise ValueError('Invalid bounded character features.')
    eligible = []
    found = set()
    for feature in features:
        if not isinstance(feature, (list, tuple)) or len(feature) != 4:
            _warn(result['warnings'], 'partial: malformed character feature.')
            continue
        obj = feature[2]
        source = type(obj).__name__ + ':' + str(getattr(obj, 'pk', ''))
        if source in allowed and source not in found and not getattr(obj, 'table_only', False):
            eligible.append((source, feature)); found.add(source)
    if allowed - found:
        _warn(result['warnings'], 'partial: exported sources were not found in current character features.')
    try:
        choices, lists = _character_choices(character, [feature for _, feature in eligible])
        if (not isinstance(choices, dict) or not isinstance(lists, dict) or
                len(choices) > MAX_SOURCES or len(lists) > MAX_SOURCES or
                any(not isinstance(key, str) or not isinstance(value, str) or len(value) > 256
                    for key, value in choices.items())):
            raise ValueError('Invalid choices')
    except (ValueError, TypeError, AttributeError):
        choices, lists = {}, {}
        _warn(result['warnings'], 'partial: character choices could not be resolved.')
    for source, feature in eligible:
        _, _, obj, level = feature
        tags = _tags(getattr(obj, 'tags_json', []), result['warnings'], source)
        if not tags:
            continue
        context = dict(result['tag_context'])
        if level is not None:
            level = _integer(level, 1, 1000)
            if level is None:
                _warn(result['warnings'], 'partial: invalid source classlvl: ' + source)
                continue
            context['classlvl'] = level
        refs = {match for tag in tags for match in re.findall(r'\bpick:([a-z0-9_]+)', tag)}
        if any(not isinstance(lists.get(key, []), list) or len(lists.get(key, [])) > 1 for key in refs):
            _warn(result['warnings'], 'partial: ambiguous choice list in ' + source)
            continue
        if refs:
            try:
                tags = [_choice_subs(tag, choices) for tag in tags]
            except (ValueError, TypeError):
                _warn(result['warnings'], 'partial: choice substitution failed in ' + source)
                continue
            tags = _tags(tags, result['warnings'], source)
            if not tags:
                continue
        _source(result, tags, source, _label(getattr(obj, 'nome', None), source), context)
    return _finish(result)
