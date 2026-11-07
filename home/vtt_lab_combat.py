"""Pure CombatEncounter adapter; persist a pinned start and a bounded replay journal.

Request UUID/revision and idempotency belong to the caller. No database, live
library lookup, random rolls, official character writes or private engine saves.
Source changes invalidate existing journals; recovery is explicit and must retain
the original state rather than silently replaying it with a different engine.
"""

import hashlib
import json
import math
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from .tag_engine.combat_encounter import CombatEncounter
from .tag_engine.library import Library, library_scope
from .tag_engine.parser import parse_tag
from .vtt_lab_resources import action_costs, apply_costs, validate_pools
from .vtt_lab_movement import (flat_available, movement_budget, networkx_version, plan_walk,
                               validate_board, validate_movement, validate_positions)


MAX_COMBATANTS = 32
MAX_JOURNAL = 256
MAX_LIBRARY_BYTES = 512 * 1024
MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_AMOUNT = 1_000_000
_FIELDS = {
    'combat_start': {'teams'},
    'combat_start_turn': {'actor_id'},
    'combat_attack': {'target_id', 'action_id', 'hit', 'damage', 'damage_type'},
    'combat_heal': {'target_id', 'amount'},
    'combat_move': {'x', 'y', 'z'},
    'combat_end_turn': set(),
    'combat_end': set(),
}


def _engine_revision():
    root = Path(__file__).parent
    digest = hashlib.sha256(b'vtt-lab-combat-engine-v1\0')
    for name in ('vtt_lab_combat.py', 'tag_engine/combat_encounter.py', 'tag_engine/combat_conditions.py',
                 'tag_engine/attack_effects.py', 'tag_engine/evaluator.py', 'tag_engine/parser.py',
                 'tag_engine/lexer.py', 'tag_engine/nodes.py', 'tag_engine/library.py',
                 'tag_engine/runtime_values.py', 'vtt_lab_resources.py', 'resource_engine.py', 'vtt_lab_movement.py'):
        source = (root / name).read_bytes().replace(b'\r\n', b'\n')
        digest.update(name.encode('ascii') + b'\0' + str(len(source)).encode('ascii') + b'\0' + source)
    digest.update(b'networkx\0' + networkx_version().encode('ascii'))
    return digest.hexdigest()


ENGINE_REVISION = _engine_revision()


def _encoded(value):
    def check(item, depth=0):
        if depth > 32:
            raise ValueError('Combat JSON is too deeply nested')
        kind = type(item)
        if kind is dict:
            if not all(type(key) is str for key in item):
                raise ValueError('Combat JSON keys must be strings')
            for child in item.values():
                check(child, depth + 1)
        elif kind is list:
            for child in item:
                check(child, depth + 1)
        elif kind is float:
            if not math.isfinite(item):
                raise ValueError('Nonfinite combat JSON')
        elif kind not in (str, int, bool, type(None)):
            raise ValueError('Combat state must contain only JSON values')
    try:
        check(value)
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, OverflowError, RecursionError, UnicodeError) as error:
        raise ValueError('Invalid combat JSON') from error


def _copy(value, limit=MAX_STATE_BYTES):
    encoded = _encoded(value)
    if len(encoded) > limit:
        raise ValueError('Combat JSON exceeds its size limit')
    return json.loads(encoded)


def _integer(value, minimum=0, maximum=MAX_AMOUNT):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Combat numbers must be bounded integers, not bool or float')
    return value


def _text(value, maximum=256):
    if (type(value) is not str or not 0 < len(value) <= maximum or value != value.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError('Invalid combat identifier or label')
    return value


def _actor(value):
    if type(value) is not str:
        raise ValueError('Combat actor IDs must be UUID strings')
    try:
        return str(UUID(value))
    except ValueError as error:
        raise ValueError('Invalid combat actor UUID') from error


def _tags(value):
    if type(value) is not list or len(value) > 256:
        raise ValueError('Invalid combat tags')
    for tag in value:
        if type(tag) is not str or not tag.strip() or len(tag) > 8192:
            raise ValueError('Invalid combat tag text')
        try:
            parse_tag(tag)
        except Exception as error:
            raise ValueError('Invalid combat tag syntax') from error
    return value


def _context(value):
    if type(value) is not dict or len(value) > 128 or len(_encoded(value)) > 16 * 1024:
        raise ValueError('Invalid combat tag context')
    for key, item in value.items():
        if key in {'pb', 'lvl', 'classlvl'} or key.endswith('_mod'):
            _integer(item, minimum=-MAX_AMOUNT)
        if key == 'in_dim_light' and type(item) is not bool:
            raise ValueError('Lighting context must be boolean')
    return value


def _rules(value):
    required = {'defensive_tags', 'offensive_tags', 'tag_context', 'actions'}
    if type(value) is not dict or not required <= set(value):
        raise ValueError('Every combatant requires server-provided rules')
    _tags(value['defensive_tags'])
    _tags(value['offensive_tags'])
    _context(value['tag_context'])
    actions = value['actions']
    if type(actions) is not list or len(actions) > 128:
        raise ValueError('Invalid action list')
    seen = set()
    for action in actions:
        if type(action) is not dict or not {'id', 'nome', 'tags'} <= set(action):
            raise ValueError('Invalid server-provided action')
        action_id = _text(action['id'])
        _text(action['nome'], 300)
        if action_id in seen:
            raise ValueError('Duplicate action ID')
        seen.add(action_id)
        _tags(action['tags'])
        if 'context' in action:
            _context(action['context'])
    return value


def _library(raw):
    if type(raw) is not dict:
        raise ValueError('combat_start requires a server-provided library snapshot')
    raw = _copy(raw, MAX_LIBRARY_BYTES)
    try:
        Library(raw=raw, prefer_db=False)
        types = raw['catalogs']['damage_type']['valores']
        if type(types) is not list or not types or len(types) > 256:
            raise ValueError('Invalid damage vocabulary')
        for item in types:
            _text(item, 80)
        if len(set(types)) != len(types):
            raise ValueError('Duplicate damage vocabulary')
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Invalid pinned combat library') from error
    return raw, hashlib.sha256(_encoded(raw)).hexdigest(), types


def _command(value, *, journal=False):
    if type(value) is not dict or type(value.get('type')) is not str or value['type'] not in _FIELDS:
        raise ValueError('Unknown combat command')
    kind = value['type']
    required = {'type'} | _FIELDS[kind]
    if journal and kind == 'combat_start_turn':
        required |= {'turn_id'}
    metadata = set() if journal else {'command_id', 'expected_revision'}
    if not required <= set(value) or set(value) - required - metadata:
        raise ValueError('Invalid combat command fields')
    if 'command_id' in value:
        _actor(value['command_id'])
    if 'expected_revision' in value:
        _integer(value['expected_revision'], maximum=2 ** 53 - 1)
    out = {key: value[key] for key in required}
    if kind == 'combat_start':
        if type(out['teams']) is not dict or not 2 <= len(out['teams']) <= MAX_COMBATANTS:
            raise ValueError('Select between 2 and 32 combatants')
        teams = {_actor(actor): _text(team, 80) for actor, team in out['teams'].items()}
        if len(teams) != len(out['teams']) or len(set(teams.values())) < 2:
            raise ValueError('An encounter requires distinct actors and at least two teams')
        out['teams'] = teams
    for key in ('actor_id', 'target_id'):
        if key in out:
            out[key] = _actor(out[key])
    if kind == 'combat_attack':
        _text(out['action_id'])
        _text(out['damage_type'], 80)
        _integer(out['damage'])
        if type(out['hit']) is not bool:
            raise ValueError('Hit must be declared as a boolean')
    if kind == 'combat_heal':
        _integer(out['amount'])
    if kind == 'combat_move':
        _integer(out['x'], maximum=63)
        _integer(out['y'], maximum=63)
        _integer(out['z'], maximum=0)
    if 'turn_id' in out:
        _integer(out['turn_id'], minimum=1, maximum=MAX_JOURNAL)
    return out


def _tokens(state):
    if type(state) is not dict or type(state.get('tokens')) is not list:
        raise ValueError('Invalid laboratory token state')
    indexed = {}
    for token in state['tokens']:
        if type(token) is not dict:
            raise ValueError('Invalid laboratory token')
        actor = _actor(token.get('id'))
        if actor in indexed:
            raise ValueError('Duplicate token UUID')
        indexed[actor] = token
    return indexed


def _initial(entries, tokens, board, occupants):
    fields = {'id', 'nome', 'team', 'hp', 'max_hp', 'temp_hp', 'rules', 'resources', 'position', 'movement'}
    if type(entries) is not list or not 2 <= len(entries) <= MAX_COMBATANTS:
        raise ValueError('Invalid initial combat snapshot')
    seen, teams = set(), set()
    for entry in entries:
        if type(entry) is not dict or set(entry) != fields:
            raise ValueError('Invalid initial combatant fields')
        actor = _actor(entry['id'])
        if actor in seen or actor not in tokens or entry['id'] != actor:
            raise ValueError('Initial combatant is missing or duplicated')
        seen.add(actor)
        teams.add(_text(entry['team'], 80))
        _text(entry['nome'], 300)
        _integer(entry['max_hp'], minimum=1)
        _integer(entry['hp'], minimum=1, maximum=entry['max_hp'])
        _integer(entry['temp_hp'])
        if type(tokens[actor].get('max_hp')) is not int or tokens[actor]['max_hp'] != entry['max_hp']:
            raise ValueError('A combatant maximum changed outside the encounter')
        _rules(entry['rules'])
        entry['resources'] = validate_pools(entry['resources'])
        entry['movement'] = validate_movement(entry['movement'])
        position = validate_positions(board, {actor: entry['position']})[actor]
        if actor not in occupants or position != occupants[actor]:
            raise ValueError('Initial position disagrees with the occupancy snapshot')
        entry['position'] = position
    if len(teams) < 2:
        raise ValueError('An encounter requires at least two teams')
    return entries


class _ConditionContext:
    """Forward the existing public condition API with action-local evaluation facts."""
    def __init__(self, conditions, context):
        self.conditions, self.context = conditions, context

    def __getattr__(self, name):
        return getattr(self.conditions, name)

    def resolve(self, tags, *, context=None, **kwargs):
        return self.conditions.resolve(tags, context={**self.context, **(context or {})}, **kwargs)


@contextmanager
def _action_context(encounter, actor, context):
    # This ephemeral instance slot has no public setter. Never serialize it or modify shared engine code.
    entry = encounter._combatants[actor]
    original_context, original_conditions = entry['tag_context'], encounter.conditions
    try:
        entry['tag_context'] = {**original_context, **context}
        encounter.conditions = _ConditionContext(original_conditions, entry['tag_context'])
        yield
    finally:
        entry['tag_context'] = original_context
        encounter.conditions = original_conditions


def _conditions(encounter):
    return {actor: sorted({name for source in encounter.combatants
                           for name in encounter.conditions.facts(actor, source)})
            for actor in encounter.combatants}


def _movement_view(encounter, walking, *, manual=False):
    conditions = _conditions(encounter)
    result = {}
    for actor, budget in walking['budgets'].items():
        spent = walking['spent'][actor]
        remaining = None if budget is None else budget - spent
        reason = None
        if budget is None:
            reason = 'unknown_walk_speed'
        elif not flat_available(walking['positions']):
            reason = 'unsupported_flat_positions'
        elif manual or encounter.finished:
            reason = 'combat_finished'
        elif encounter.current_actor != actor:
            reason = 'not_current_actor'
        elif encounter.combatants[actor]['hp'] <= 0:
            reason = 'actor_not_living'
        elif conditions[actor]:
            reason = 'active_condition'
        elif remaining <= 0:
            reason = 'movement_exhausted'
        elif networkx_version() == 'unavailable':
            reason = 'networkx_unavailable'
        result[actor] = {'budget_units': budget, 'spent_units': spent, 'remaining_units': remaining,
                         'available': reason is None}
        if reason:
            result[actor]['reason'] = reason
    return result


def _move_plan(encounter, walking, destination):
    actor = encounter.current_actor
    if actor is None:
        raise ValueError('Walking requires an active turn')
    status = _movement_view(encounter, walking).get(actor)
    if status is None or not status['available']:
        raise ValueError('Automatic walking is unavailable: ' + (status or {}).get('reason', 'unknown_actor'))
    return plan_walk(walking['board'], walking['positions'], walking['teams'], actor,
                     destination, status['remaining_units'])


def _execute(encounter, initial, command, damage_types, resources, library_raw, walking):
    kind = command['type']
    if kind == 'combat_start_turn':
        if command['actor_id'] not in initial:
            raise ValueError('Unknown combatant')
        if not encounter.start_turn(command['actor_id'], command['turn_id']):
            raise ValueError('Repeated turn identity')
        walking['spent'][command['actor_id']] = 0
        walking['last_path'] = None
        return command['actor_id']
    if kind == 'combat_move':
        plan = _move_plan(encounter, walking, {key: command[key] for key in ('x', 'y', 'z')})
        actor = plan['actor_id']
        walking['positions'][actor].update(plan['path'][-1])
        walking['spent'][actor] += plan['cost_units']
        walking['last_path'] = plan['path']
        return actor
    if kind in {'combat_attack', 'combat_heal'}:
        target = command['target_id']
        if target not in initial or encounter.current_actor not in initial:
            raise ValueError('Actor and target must be encounter participants')
        if kind == 'combat_attack':
            if command['damage_type'] not in damage_types:
                raise ValueError('Damage type is not in the pinned vocabulary')
            rules = initial[encounter.current_actor]['rules']
            action = next((action for action in rules['actions'] if action['id'] == command['action_id']), None)
            if action is None:
                raise ValueError('Action does not belong to the active actor')
            actor = encounter.current_actor
            costs = action_costs(action, rules['tag_context'], resources[actor], library_raw)
            debited = apply_costs(resources[actor], costs)
            with _action_context(encounter, encounter.current_actor, action.get('context', {})):
                encounter.attack(target, action['tags'], hit=command['hit'], damage=command['damage'],
                                 damage_type=command['damage_type'])
            resources[actor] = debited
        else:
            encounter.heal(target, command['amount'])
        return target
    if kind == 'combat_end_turn':
        encounter.end_turn()
        return None
    if kind == 'combat_end':
        return None
    raise ValueError('A start command cannot be replayed inside an encounter')


def _view(encounter, damage_types, resources, walking, *, manual=False):
    combatants = encounter.combatants
    conditions = _conditions(encounter)
    return {'current_actor': None if manual else encounter.current_actor,
            'action_used': encounter.action_used, 'finished': manual or encounter.finished,
            'combatants': combatants, 'conditions': conditions,
            'resources': resources,
            'positions': {actor: {key: pos[key] for key in ('x', 'y', 'z')}
                          for actor, pos in walking['positions'].items()},
            'movement': _movement_view(encounter, walking, manual=manual), 'last_path': walking['last_path'],
            'damage_types': list(damage_types), 'events': [list(event) for event in encounter.events[-10:]]}


def _restore(combat, tokens, damage_types):
    fields = {'schema', 'active', 'initial', 'library_raw', 'library_hash', 'engine_revision', 'journal', 'view',
              'end_reason', 'last_result', 'board', 'occupants'}
    if (type(combat) is not dict or set(combat) != fields or type(combat['schema']) is not int
            or combat['schema'] != 1 or type(combat['active']) is not bool
            or type(combat['journal']) is not list or len(combat['journal']) > MAX_JOURNAL):
        raise ValueError('Invalid combat journal schema')
    board = validate_board(combat['board'])
    occupants = validate_positions(board, combat['occupants'])
    if combat['active'] and set(occupants) != set(tokens):
        raise ValueError('Encounter occupancy changed outside the pinned snapshot')
    entries = _initial(combat['initial'], tokens, board, occupants)
    initial = {entry['id']: entry for entry in entries}
    resources = {entry['id']: validate_pools(entry['resources']) for entry in entries}
    walking = {'board': board, 'positions': occupants,
               'teams': {entry['id']: entry['team'] for entry in entries},
               'budgets': {entry['id']: movement_budget(board, entry['movement']) for entry in entries},
               'spent': {entry['id']: 0 for entry in entries}, 'last_path': None}
    encounter = CombatEncounter([
        {'id': entry['id'], 'team': entry['team'], 'hp': entry['hp'], 'max_hp': entry['max_hp'],
         'temp_hp': entry['temp_hp'], 'defensive_tags': entry['rules']['defensive_tags'],
         'offensive_tags': entry['rules']['offensive_tags'], 'tag_context': entry['rules']['tag_context']}
        for entry in entries])
    turns, manual = 0, False
    for entry in combat['journal']:
        command = _command(entry, journal=True)
        if encounter.finished or manual:
            raise ValueError('A finished encounter has further journal commands')
        if command['type'] == 'combat_start_turn':
            turns += 1
            if command['turn_id'] != turns:
                raise ValueError('Turn identities must increase monotonically')
        _execute(encounter, initial, command, damage_types, resources, combat['library_raw'], walking)
        manual = command['type'] == 'combat_end'
    reason = 'manual' if manual else 'engine' if encounter.finished else None
    if combat['active'] != (reason is None) or combat['end_reason'] != reason:
        raise ValueError('Stored combat lifecycle disagrees with its replay')
    return encounter, initial, turns, reason, resources, walking


def _load(combat, tokens):
    if type(combat) is not dict:
        raise ValueError('No combat snapshot')
    if combat.get('engine_revision') != ENGINE_REVISION:
        raise ValueError('Combat engine revision changed; preserve the original state and start a new laboratory session')
    raw, digest, types = _library(combat.get('library_raw'))
    if combat.get('library_hash') != digest:
        raise ValueError('Pinned library hash mismatch')
    with library_scope(raw):
        encounter, initial, turns, reason, resources, walking = _restore(combat, tokens, types)
        view = _view(encounter, types, resources, walking, manual=reason == 'manual')
    return raw, digest, types, encounter, initial, turns, reason, view, resources, walking


def preview_movement(state, destination):
    """Replay the pinned encounter and return a walking plan without mutating state."""
    working = _copy(state)
    if type(destination) is not dict or set(destination) != {'x', 'y', 'z'}:
        raise ValueError('Invalid walking destination')
    command = _command({'type': 'combat_move', **_copy(destination)})
    raw, _, _, encounter, _, _, reason, _, _, walking = _load(working.get('combat'), _tokens(working))
    if reason is not None:
        raise ValueError('Encounter is finished')
    with library_scope(raw):
        return _move_plan(encounter, walking, {key: command[key] for key in ('x', 'y', 'z')})


def apply_combat(state, command, library_raw=None):
    """Apply one domain command atomically; return its actor/target UUID or None.

    The journal has at most 256 entries, reserving the final slot for manual end.
    combatants is a UUID map; conditions maps each participant to condition names.
    """
    working = _copy(state)
    normalized = _command(_copy(command))
    tokens = _tokens(working)
    kind = normalized['type']
    previous = working.get('combat')
    if kind == 'combat_start':
        last_result = None
        if previous is not None:
            _, _, _, _, _, _, reason, view, _, _ = _load(previous, tokens)
            if reason is None:
                raise ValueError('End the current encounter before starting another')
            last_result = {'view': view, 'end_reason': reason, 'library_hash': previous['library_hash']}
        raw, digest, types = _library(library_raw)
        board = validate_board(working.get('board', {}))
        occupants = validate_positions(board, {actor: {**{key: token.get(key) for key in ('x', 'y', 'z')},
                                                      'footprint': token.get('footprint', 1)}
                                               for actor, token in tokens.items()})
        initial = []
        for actor, team in sorted(normalized['teams'].items()):
            if actor not in tokens:
                raise ValueError('Unknown combatant token')
            token = tokens[actor]
            initial.append({'id': actor, 'nome': token.get('nome'), 'team': team,
                            'hp': token.get('hp'), 'max_hp': token.get('max_hp'),
                            'temp_hp': token.get('temp_hp', 0), 'rules': token.get('rules'),
                            'resources': validate_pools(token.get('resources', {})),
                            'position': occupants[actor], 'movement': validate_movement(token.get('movement'))})
        combat = {'schema': 1, 'active': True, 'initial': initial, 'library_raw': raw, 'engine_revision': ENGINE_REVISION,
                  'library_hash': digest, 'journal': [], 'view': {}, 'end_reason': None,
                  'last_result': last_result, 'board': board, 'occupants': occupants}
        working['combat'] = combat
        with library_scope(raw):
            encounter, _, _, _, resources, walking = _restore(combat, tokens, types)
            combat['view'] = _view(encounter, types, resources, walking)
        result = None
    else:
        raw, digest, types, encounter, initial, turns, reason, _, resources, walking = _load(previous, tokens)
        if reason is not None:
            raise ValueError('Encounter is finished')
        if library_raw is not None and _library(library_raw)[1] != digest:
            raise ValueError('Do not replace a running encounter library')
        combat = previous
        if (len(combat['journal']) >= MAX_JOURNAL or
                (kind != 'combat_end' and len(combat['journal']) >= MAX_JOURNAL - 1)):
            raise ValueError('Combat journal limit reached; end this encounter')
        if kind == 'combat_start_turn':
            normalized['turn_id'] = turns + 1
        with library_scope(raw):
            result = _execute(encounter, initial, normalized, types, resources, raw, walking)
            manual = kind == 'combat_end'
            combat['journal'].append(normalized)
            combat['end_reason'] = 'manual' if manual else 'engine' if encounter.finished else None
            combat['active'] = combat['end_reason'] is None
            combat['view'] = _view(encounter, types, resources, walking, manual=manual)
    for actor, values in combat['view']['combatants'].items():
        tokens[actor]['hp'], tokens[actor]['temp_hp'] = values['hp'], values['temp_hp']
        tokens[actor]['resources'] = combat['view']['resources'][actor]
    for actor, position in combat['view']['positions'].items():
        if actor in tokens:
            tokens[actor].update(position)
    _copy(working)  # Check the complete candidate before touching the caller's object.
    originals = _tokens(state)
    state['combat'] = working['combat']
    for actor, values in combat['view']['combatants'].items():
        originals[actor]['hp'], originals[actor]['temp_hp'] = values['hp'], values['temp_hp']
        originals[actor]['resources'] = combat['view']['resources'][actor]
    for actor, position in combat['view']['positions'].items():
        if actor in originals:
            originals[actor].update(position)
    return result
