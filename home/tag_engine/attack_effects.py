"""Read attack interactions from evaluated tags without identifying their source."""

import re
import unicodedata


def _damage_key(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = value.encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', value).strip('_')


def ignored_resistance_types(operations):
    """Return damage types whose resistance an attack ignores; '*' means any."""
    ignored = set()
    for operation in operations:
        active = operation.get('active') if isinstance(operation, dict) else operation.active
        verb = operation.get('verb') if isinstance(operation, dict) else operation.verb
        params = operation.get('params') if isinstance(operation, dict) else operation.params
        if not active or verb != 'ignore' or not isinstance(params, dict):
            continue
        if params.get('name') != 'resist':
            continue
        args = params.get('args') or ()
        if not args:
            ignored.add('*')
        else:
            ignored.update(_damage_key(value) for value in args if isinstance(value, str))
    return ignored


def ignores_resistance(ignored, damage_type):
    return '*' in ignored or _damage_key(damage_type) in ignored


def critical_damage_bonus(operations):
    """Add evaluated critical damage operations from the attacker's sources."""
    total = 0
    for operation in operations:
        active = operation.get('active') if isinstance(operation, dict) else operation.active
        verb = operation.get('verb') if isinstance(operation, dict) else operation.verb
        value = operation.get('value') if isinstance(operation, dict) else operation.value
        if active and verb == 'crit_dmg' and type(value) is int and value > 0:
            total += value
    return total
