"""Resolve a target's saving throw against a tagged elemental spell."""

import hashlib
import json
import re
import secrets
import uuid

from django.db import transaction

from .character_engine import (
    _feature_talent_attr_sig, _features_do_personagem, _talent_attr_map,
)
from .models import TbOperacaoRecurso, TbPersonagem


STORM_SAVE_TAG = "dadv:spell_save{damage:raio|trovejante}"
_STORM_RE = re.compile(r"^dadv:spell_save\{damage:(?P<types>[a-z_]+(?:\|[a-z_]+)*)\}$")


def storm_save_types(person, ruleset=None):
    """Collect damage types from active selected sources, without source-name checks."""
    choices = _talent_attr_map(person, ruleset=ruleset)
    types = set()
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or ()))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        for tag in tags:
            match = _STORM_RE.fullmatch(tag)
            if match:
                types.update(match.group("types").split("|"))
    return sorted(types)


@transaction.atomic
def roll_storm_spell_save(person, *, operation_id, damage_type, target_modifier,
                          save_dc, target_has_advantage, confirmed, ruleset=None):
    """Roll the target's d20 on the server; disadvantage cancels advantage."""
    try:
        operation_id = uuid.UUID(str(operation_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identificador inválido.") from exc
    damage_type = str(damage_type or "").strip().casefold()
    if type(target_modifier) is not int:
        raise ValueError("Modificador de salvaguarda inválido.")
    if type(save_dc) is not int or save_dc < 1:
        raise ValueError("CD inválida.")
    if type(target_has_advantage) is not bool or confirmed is not True:
        raise ValueError("Confirme a situação da salvaguarda.")
    fingerprint = hashlib.sha256(json.dumps([
        "storm-save", damage_type, target_modifier, save_dc,
        target_has_advantage, confirmed], separators=(",", ":")).encode()).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt is not None:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return dict(receipt.resposta, replayed=True)
    if damage_type not in storm_save_types(locked, ruleset=ruleset):
        raise ValueError("A fonte ativa não impõe desvantagem para este tipo de dano.")
    count = 1 if target_has_advantage else 2
    rolls = [secrets.randbelow(20) + 1 for _ in range(count)]
    die = min(rolls)
    total = die + target_modifier
    result = {
        "operation_id": str(operation_id), "damage_type": damage_type,
        "rolls": rolls, "die": die, "total": total, "save_dc": save_dc,
        "succeeded": total >= save_dc, "advantage_cancelled": target_has_advantage,
        "replayed": False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=result, status_http=200)
    return result
