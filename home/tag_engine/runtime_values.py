"""Bounded operands for runtime consumers of the existing tag language."""

import re

from .parser import ParseError, parse_tag


_DICE = re.compile(r"(?:(\d+)\s*)?d(\d+)", re.I)
_FEET = re.compile(r"(\d+)ft", re.I)


def dice_spec(expression):
    match = _DICE.fullmatch(str(expression or "").strip())
    if match is None:
        raise ValueError("Invalid dice expression.")
    count = int(match.group(1) or 1)
    faces = int(match.group(2))
    if not 1 <= count <= 100 or not 2 <= faces <= 1000:
        raise ValueError("Dice expression exceeds runtime limits.")
    return count, faces


def roll_dice(expression, randbelow):
    count, faces = dice_spec(expression)
    return [randbelow(faces) + 1 for _ in range(count)]


def _fields(nodes):
    fields = {node.name: node for node in nodes}
    if len(fields) != len(nodes):
        raise ValueError("Duplicate runtime operand.")
    return fields


def d20_adjustment(tag):
    """Read an intervention operation, independent of its source or title."""
    try:
        fields = _fields(parse_tag(tag).nodes)
        if set(fields) != {"trigger", "range", "roll", "buff", "uses"}:
            return None
        if any(fields[key].qualifiers for key in ("range", "uses")):
            return None
        if fields["trigger"].value != "d20_result" or fields["trigger"].qualifiers:
            return None
        distance = _FEET.fullmatch(str(fields["range"].value))
        dice = str(fields["roll"].value)
        dice_spec(dice)
        if (distance is None or fields["roll"].qualifiers
                or fields["buff"].value != "d20"
                or len(fields["buff"].qualifiers) != 1):
            return None
        modifier = _fields(parse_tag(fields["buff"].qualifiers[0]).nodes)
        if (set(modifier) != {"plus_or_minus"}
                or modifier["plus_or_minus"].qualifiers
                or dice_spec(modifier["plus_or_minus"].value) != dice_spec(dice)):
            return None
        usage = _fields(fields["uses"].children)
        # This operation consumes one lock; a multi-use pool is a different contract.
        if (set(usage) != {"_literal", "reset"}
                or usage["_literal"].value != "1"
                or usage["reset"].value != "initiative_or_short_or_long"):
            return None
        return {"range_ft": int(distance.group(1)), "dice": dice}
    except (ParseError, ValueError, TypeError):
        return None


def slot_preservation(tag):
    """Read spell levels and matching die from a cast operation."""
    try:
        program = parse_tag(tag)
        if (len(program.nodes) != 1 or program.nodes[0].name != "cast"
                or program.nodes[0].qualifiers):
            return None
        fields = _fields(program.nodes[0].children)
        if set(fields) != {"spell_level", "roll", "match_level"}:
            return None
        if any(node.qualifiers for node in fields.values()):
            return None
        if fields["match_level"].value != "without_slot":
            return None
        levels = tuple(int(value) for value in fields["spell_level"].value.split("|"))
        count, faces = dice_spec(fields["roll"].value)
        if (count != 1 or not levels or len(set(levels)) != len(levels)
                or not all(1 <= level <= 9 and level <= faces for level in levels)):
            return None
        return {"levels": levels, "faces": faces}
    except (ParseError, ValueError, TypeError, AttributeError):
        return None
