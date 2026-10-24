"""Resolve a chance de preservar um espaço ao conjurar uma magia identificada."""

import secrets

from .character_engine import (
    _feature_talent_attr_sig, _features_do_personagem, _talent_attr_map,
)


FREE_CAST_TAG = "cast{spell_level:1|2|3|4, roll:d4, match_level:without_slot}"


def free_cast_available(person, spell_level, *, ruleset=None):
    """Only an active, selected source grants the level-specific roll."""
    if type(spell_level) is not int or spell_level not in range(1, 5):
        return False
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or ()))
        if FREE_CAST_TAG not in tags:
            continue
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        return True
    return False


def roll_free_cast(person, spell_level, *, ruleset=None):
    """Return a server-side d4 result, or None when the tag does not apply."""
    if not free_cast_available(person, spell_level, ruleset=ruleset):
        return None
    die = secrets.randbelow(4) + 1
    return {"die": die, "slot_preserved": die == spell_level}
