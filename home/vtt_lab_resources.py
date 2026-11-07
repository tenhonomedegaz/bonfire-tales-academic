"""Pure, conservative activation costs for laboratory resource snapshots.

Only canonical_key is reused from the persistent resource service. Unsupported
costs fail closed; this module never calls its database mutators or rolls dice.
"""

import json
from copy import deepcopy

from .resource_engine import canonical_key
from .tag_engine.evaluator import evaluate_tags
from .tag_engine.lexer import tokenize
from .tag_engine.library import Library
from .tag_engine.parser import parse_tags


MAX_POOLS = 128
MAX_AMOUNT = 1_000_000
MAX_POOL_BYTES = 64 * 1024
_ALLOWED_SCOPES = {'instant', 'action'}
_GATES = {'requires', 'restriction', 'if', 'else', 'trigger', 'on', 'on_fail', 'on_success',
          'while', 'while_active', 'pick', 'match', 'save', 'scaling'}
_UNSUPPORTED = {'resource_restore', 'uses', 'restores'}


def _text(value, maximum):
    if (type(value) is not str or not 0 < len(value) <= maximum or value != value.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError('Invalid resource identity or label')
    return value


def _amount(value, *, minimum=0):
    if type(value) is not int or not minimum <= value <= MAX_AMOUNT:
        raise ValueError('Resource quantities must be bounded integers, not bool or float')
    return value


def validate_pools(resources):
    """Return an independent, bounded pool map; aliases are not display-name matches."""
    if type(resources) is not dict or len(resources) > MAX_POOLS:
        raise ValueError('Invalid resource pools')
    result = {}
    required = {'nome', 'max', 'current', 'aliases'}
    for resource_id, pool in resources.items():
        _text(resource_id, 256)
        if not canonical_key(resource_id):
            raise ValueError('Invalid canonical resource identity')
        if type(pool) is not dict or not required <= set(pool) or set(pool) - required - {'reset'}:
            raise ValueError('Invalid resource pool fields')
        _text(pool['nome'], 200)
        maximum, current = _amount(pool['max']), _amount(pool['current'])
        if current > maximum:
            raise ValueError('Resource current exceeds its maximum')
        aliases = pool['aliases']
        if type(aliases) is not list or len(aliases) > 32:
            raise ValueError('Invalid resource aliases')
        normalized = []
        for alias in aliases:
            _text(alias, 200)
            key = canonical_key(alias)
            if not key:
                raise ValueError('Empty canonical resource alias')
            if key not in normalized:
                normalized.append(key)
        result[resource_id] = {'nome': pool['nome'], 'max': maximum, 'current': current, 'aliases': normalized}
        if 'reset' in pool:
            result[resource_id]['reset'] = _text(pool['reset'], 80)
    if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > MAX_POOL_BYTES:
        raise ValueError('Resource pools exceed the bounded snapshot')
    return result


def _mentions(text):
    """Use the existing lexer to spot resource verbs hidden in opaque operands."""
    count = 0
    for token in tokenize(text):
        if token.type == 'STRING':
            count += _mentions(token.value[1:-1])
        elif token.type == 'WORD':
            word = token.value.lower()
            if word in _UNSUPPORTED:
                raise ValueError('Unsupported resource restoration or uses contract; action refused')
            count += word == 'resource_cost'
    return count


def _cost_nodes(tags):
    if (type(tags) is not list or len(tags) > 256
            or any(type(tag) is not str or not tag.strip() or len(tag) > 8192 for tag in tags)):
        raise ValueError('Invalid action tags for resource costs')
    mentions = sum(_mentions(tag) for tag in tags)
    try:
        program = parse_tags(tags)
    except Exception as error:
        raise ValueError('Invalid resource action syntax') from error
    costs, count = [], 0

    def walk(nodes, blocked=False, depth=0):
        nonlocal count
        if depth > 16:
            raise ValueError('Resource action scope is too deep')
        blocked = blocked or any(node.name in _GATES for node in nodes)
        for node in nodes:
            count += 1
            if count > 1024:
                raise ValueError('Resource action AST is too large')
            if node.name in _UNSUPPORTED:
                raise ValueError('Unsupported resource restoration or uses contract; action refused')
            if node.name == 'resource_cost':
                if (blocked or node.operator != ':' or node.children or node.qualifiers
                        or any(scope not in _ALLOWED_SCOPES for scope in node.scope)):
                    raise ValueError('Unsupported conditional or scoped resource cost; action refused')
                costs.append(node)
            if node.children:
                walk(node.children, blocked or node.name not in _ALLOWED_SCOPES or bool(node.qualifiers), depth + 1)
    walk(program.nodes)
    if mentions != len(costs):
        raise ValueError('Opaque resource cost cannot be executed; action refused')
    return costs


def action_costs(action, rulescontext, pools, library_raw=None):
    """Return {original_resource_id: positive_integer_cost}, without mutating pools.

    Unconditional root/instant/action costs are evaluated statically after their
    AST scope is checked. The evaluator owns operand binding and formula parsing.
    """
    resources = validate_pools(pools)
    if type(action) is not dict or 'tags' not in action or type(rulescontext) is not dict:
        raise ValueError('Invalid resource action or context')
    context = action.get('context', {})
    if type(context) is not dict:
        raise ValueError('Invalid action resource context')
    nodes = _cost_nodes(action['tags'])
    if not nodes:
        return {}
    # Boolean facts and floats must not become arithmetic currency through Python coercion.
    numeric_context = {key: value for key, value in {**rulescontext, **context}.items()
                       if type(key) is str and type(value) is int and abs(value) <= MAX_AMOUNT}
    library = Library(raw=library_raw, prefer_db=False)
    aliases = {}
    for resource_id, pool in resources.items():
        for alias in {canonical_key(resource_id), *pool['aliases']}:
            aliases.setdefault(alias, set()).add(resource_id)
    costs = {}
    for node in nodes:
        result = evaluate_tags([node.raw], numeric_context, library=library)
        operations = [operation for operation in result.operations if operation.verb == 'resource_cost']
        if (result.blocked or len(operations) != 1 or not operations[0].active
                or operations[0].op != 'resource'):
            raise ValueError('Resource cost is not executable in the pinned vocabulary')
        params = operations[0].params
        name = params.get('name')
        if (type(name) is not str or not name or any(params.get(key) for key in ('args', 'kwargs', 'flags'))):
            raise ValueError('Unsupported resource reference or alternative; action refused')
        binding = params.get('binding')
        amount = 1
        if binding is not None:
            if type(binding) is not dict or binding.get('operator') != ':':
                raise ValueError('Unsupported resource cost binding; action refused')
            if any(token.type == 'WORD' and token.value.lower() in {'true', 'false'}
                   for token in tokenize(binding.get('raw', ''))):
                raise ValueError('Boolean resource cost formula')
            amount = _amount(binding.get('value'), minimum=1)
        matching = aliases.get(canonical_key(name), set())
        if len(matching) != 1:
            raise ValueError('Resource cost alias is missing or ambiguous; action refused')
        resource_id = next(iter(matching))
        costs[resource_id] = _amount(costs.get(resource_id, 0) + amount, minimum=1)
    return costs


def apply_costs(pools, costs):
    """Return a debited copy, or raise before modifying anything when insufficient."""
    result = validate_pools(pools)
    if type(costs) is not dict:
        raise ValueError('Invalid activation costs')
    for resource_id, amount in costs.items():
        _amount(amount, minimum=1)
        if resource_id not in result or result[resource_id]['current'] < amount:
            raise ValueError('Insufficient laboratory resources; action refused')
    for resource_id, amount in costs.items():
        result[resource_id]['current'] -= amount
    return deepcopy(result)
