"""Resolve a chance de preservar um espaço ao conjurar uma magia identificada."""

import secrets
import hashlib
import json
import uuid

from django.db import transaction

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


@transaction.atomic
def cast_sheet_spell(person, *, operation_id, owned_spell_id, slot_level, ruleset=None):
    """Record a tagged nonpersistent cast and mutate its slot at most once."""
    from .models import TbOperacaoRecurso, TbPersonagem
    from .resource_commands import _current_slot
    from .resource_engine import spend_resource
    from .character_engine import derive
    from .views import _magias_sheet_info

    try:
        operation_id = uuid.UUID(str(operation_id))
        owned_spell_id = int(owned_spell_id)
        slot_level = int(slot_level)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Conjuração inválida.") from exc
    if not 1 <= slot_level <= 9:
        raise ValueError("Espaço inválido.")
    fingerprint = hashlib.sha256(json.dumps([
        "sheet-spell-cast", owned_spell_id, slot_level],
        separators=(",", ":")).encode()).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Operação já usada com outros dados.")
        return dict(receipt.resposta, replayed=True)
    info = _magias_sheet_info(locked, derive(locked, ruleset=ruleset), [],
                              ruleset=ruleset)
    spell = next((row for row in info.get("lista", ())
                  if row.get("id") == owned_spell_id), None)
    if (spell is None or spell.get("catalog_only") or spell.get("log_castable")
            or spell.get("suspensa_na_revisao")
            or spell.get("innate_label")
            or not (spell.get("preparada") or spell.get("sempre_preparada"))
            or type(spell.get("nivel")) is not int
            or not free_cast_available(locked, spell["nivel"], ruleset=ruleset)):
        raise ValueError("Magia ou fonte indisponível.")
    if not any(caster.get("classe_id") == spell.get("classe_id")
               and caster.get("slots_kind") in {"full", "half", "third"}
               for caster in info.get("spellcasters", ())):
        raise ValueError("Esta magia não usa os espaços desta classe.")
    slot = next((row for row in info.get("slots", ())
                 if row["nivel"] == slot_level), None)
    if (slot is None or slot_level < spell["nivel"]
            or _current_slot(locked, slot_level, slot["total"])["atual"] <= 0):
        raise ValueError("Espaço indisponível.")
    result = roll_free_cast(locked, spell["nivel"], ruleset=ruleset)
    if not result:
        raise ValueError("Fonte indisponível.")
    key = "spell-slot:%d" % slot_level
    if not result["slot_preserved"]:
        ok, _snapshot = spend_resource(locked, {
            "key": key, "legacy_name": key, "name": key,
            "maximum": slot["total"], "reset": "long_rest",
            "origin": "spellcasting",
        }, 1)
        if not ok:
            raise ValueError("Espaço esgotado.")
    response = {
        "operation_id": str(operation_id), "spell_id": owned_spell_id,
        "spell_name": spell["nome"], "spell_level": spell["nivel"],
        "slot_level": slot_level, "die": result["die"],
        "slot_preserved": result["slot_preserved"], "replayed": False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
