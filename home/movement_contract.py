"""Pure numeric movement projections, not a second character rules engine.

Character walking uses the immutable legacy base plus the already aggregated
numeric velocidade_bonus. Never parse the final display or evaluate tags here.
"""
from decimal import Decimal, localcontext
import math
import re


_NUMBER = r'[0-9]+(?:[.,][0-9]+)?'
_ATOM = re.compile(rf'({_NUMBER}) *(ft|m)', re.IGNORECASE | re.ASCII)
_DUAL = re.compile(rf'({_NUMBER}) *(ft|m) */ *({_NUMBER}) *(ft|m)', re.IGNORECASE | re.ASCII)
_MODE_ATOM = re.compile(rf'({_NUMBER})ft', re.ASCII)
_MODES = frozenset({'walk', 'fly', 'swim', 'climb', 'burrow'})
_MAX_SPEED = 10000
_METRES_PER_FOOT = Decimal('0.3')


def _contract():
    return {'schema': 1, 'unit': 'ft', 'speeds': {}, 'warnings': []}


def _warn(result, message):
    if len(result['warnings']) < 32 and message not in result['warnings']:
        result['warnings'].append(message)


def _finite(value, *, low=0):
    if (type(value) not in (int, float) or not low <= value <= _MAX_SPEED
            or not math.isfinite(value)):
        return None
    return int(value) if int(value) == value else value


def _decimal(text):
    return Decimal(text.replace(',', '.'))


def _base_feet(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 80:
        return None
    if any(ord(char) < 32 for char in value):
        return None
    text = value.strip(' ')
    atom = _ATOM.fullmatch(text)
    if atom:
        amount = _decimal(atom[1])
        feet = amount if atom[2].lower() == 'ft' else amount / _METRES_PER_FOOT
    else:
        dual = _DUAL.fullmatch(text)
        if not dual or dual[2].lower() == dual[4].lower():
            return None
        values = {dual[2].lower(): _decimal(dual[1]), dual[4].lower(): _decimal(dual[3])}
        with localcontext() as context:
            context.prec = 160
            if values['m'] != values['ft'] * _METRES_PER_FOOT:
                return None
        feet = values['ft']
    return _finite(float(feet))


def _mode_speed(value, walk):
    if value == 'walk':
        return walk
    if not isinstance(value, str) or len(value) > 32:
        return None
    match = _MODE_ATOM.fullmatch(value)
    return _finite(float(_decimal(match[1]))) if match else None


def _metadata(result, properties=None, fall=None):
    if properties is not None:
        if not isinstance(properties, dict) or len(properties) > 8:
            _warn(result, 'Movement properties are not a bounded object.')
        else:
            valid = {}
            for mode, value in properties.items():
                if (mode not in _MODES or mode not in result['speeds']
                        or not isinstance(value, dict) or value.keys() != {'hover'}
                        or type(value['hover']) is not bool):
                    _warn(result, 'Unknown or conditional movement properties were excluded.')
                    continue
                valid[mode] = {'hover': value['hover']}
            if valid:
                result['properties'] = valid
    if fall is not None:
        if not isinstance(fall, dict) or fall.keys() != {'threshold_ft', 'max_per_turn_ft'}:
            _warn(result, 'Conditional or malformed falling rules were excluded.')
            return
        threshold = _finite(fall['threshold_ft'])
        maximum = _finite(fall['max_per_turn_ft'])
        if threshold is None or maximum is None or maximum == 0:
            _warn(result, 'Invalid numeric falling rules were excluded.')
        else:
            result['fall'] = {'threshold_ft': threshold, 'max_per_turn_ft': maximum}


def character_movement(base, state):
    """Return base+final delta, generated mode atoms and validated metadata.

    No walk mode is inferred from an invalid base, display text or mode override.
    Independent explicit speeds can remain available when walking is unknown.
    """
    result = _contract()
    if not isinstance(state, dict):
        _warn(result, 'Character movement state must be an object.')
        return result
    base_speed = _base_feet(base)
    delta = _finite(state.get('velocidade_bonus', 0), low=-_MAX_SPEED)
    if base_speed is None:
        _warn(result, 'Walking base is unknown, ambiguous or inconsistent with 0.3 m/ft.')
    if delta is None:
        _warn(result, 'Aggregated movement bonus is not a bounded finite number.')
    walk = None
    if base_speed is not None and delta is not None:
        walk = _finite(base_speed + delta)
        if walk is None:
            _warn(result, 'Walking total is outside the supported numeric range.')
        else:
            result['speeds']['walk'] = walk
    modes = state.get('movimento_modos', {})
    if not isinstance(modes, dict) or len(modes) > 8:
        _warn(result, 'Movement modes must be a bounded object.')
    else:
        for mode, value in modes.items():
            if mode not in _MODES:
                _warn(result, 'Unknown movement mode was excluded.')
                continue
            speed = _mode_speed(value, walk)
            if mode == 'walk':
                if speed is None or speed != walk:
                    _warn(result, 'A walk mode cannot replace the authoritative base-plus-bonus total.')
                continue
            if speed is None:
                _warn(result, 'Movement mode has an unknown reference or invalid numeric atom.')
            else:
                result['speeds'][mode] = speed
    _metadata(result, state.get('movimento_propriedades'), state.get('queda_controlada'))
    return result


def creature_movement(creature):
    """Read explicit 5etools speed data; never infer owner or conditional speeds."""
    result = _contract()
    if getattr(creature, 'escala_com_dono', False):
        _warn(result, 'Owner-scaled movement needs an explicit owner context.')
        return result
    block = getattr(creature, 'statblock_json', None)
    if not isinstance(block, dict):
        _warn(result, 'Creature statblock is not an object.')
        return result
    raw = block.get('speed')
    direct = _finite(raw)
    if direct is not None:
        result['speeds']['walk'] = direct
        return result
    if not isinstance(raw, dict) or len(raw) > 12:
        _warn(result, 'Creature speed is not a bounded numeric movement contract.')
        return result
    if set(raw) & {'condition', 'conditions', 'requires', 'when', 'special', 'choose', 'alternative'}:
        _warn(result, 'Conditional creature movement requires explicit resolved facts.')
        return result
    for mode, value in raw.items():
        if mode == 'canHover':
            continue
        if mode not in _MODES:
            _warn(result, 'Unknown creature movement mode was excluded.')
            continue
        if isinstance(value, dict):
            value = value['number'] if value.keys() == {'number'} else None
        speed = _finite(value)
        if speed is None:
            _warn(result, 'Conditional or nonnumeric creature speed was excluded.')
        else:
            result['speeds'][mode] = speed
    if 'canHover' in raw:
        _metadata(result, {'fly': {'hover': raw['canHover']}})
    if not result['speeds'] and not result['warnings']:
        _warn(result, 'No unconditional numeric creature speed was supplied.')
    return result
