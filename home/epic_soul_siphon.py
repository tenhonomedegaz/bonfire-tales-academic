"""Transactional runtime for a healing reaction declared by an active source."""

import hashlib
import json
import re
import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .character_engine import (
    _feature_identity,
    _feature_talent_attr_sig,
    _features_do_personagem,
    _talent_attr_map,
    bonus_proficiencia,
    derive,
)
from .models import (
    TbOperacaoRecurso,
    TbPersonagem,
    TbPersonagemRecurso,
)
from .resource_engine import ensure_resource
from .epic_healing_bonus import healing_bonus, mark_healing_bonuses


SIPHON_TAG = (
    "trigger=enemy_reduce_to_0(range:120ft, source:not{self}), "
    "action=reaction, instant{heal:50(target:self)}, "
    "uses{pb, reset:long_rest}"
)
SIPHON_KEY = "epic:soul_siphon"

_SIPHON_RE = re.compile(
    r"^trigger\s*=\s*enemy_reduce_to_0\(\s*"
    r"range\s*:\s*(?P<range>\d+)ft\s*,\s*source\s*:\s*not\{self\}\s*\)\s*,\s*"
    r"action\s*=\s*reaction\s*,\s*"
    r"instant\{\s*heal\s*:\s*(?P<heal>\d+)\(target\s*:\s*self\)\s*\}\s*,\s*"
    r"uses\{\s*(?P<uses>pb|\d+)\s*,\s*"
    r"reset\s*:\s*(?P<reset>[a-z_]+)\s*\}$"
)


def _definition(person, ruleset=None):
    """Return the first eligible active source and its declared mechanics."""
    talent_attrs = _talent_attr_map(person, ruleset=ruleset)
    for _kind, display_name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, talent_attrs)):
            continue
        for tag in tags:
            match = _SIPHON_RE.fullmatch(tag)
            if not match:
                continue
            name = str(getattr(source, "nome", "") or display_name or "").strip()
            if not name:
                continue
            level = (sum(int(row.nivel or 0) for row in person.classes.all())
                     or int(person.nivel or 1))
            uses = (bonus_proficiencia(level) if match.group("uses") == "pb"
                    else int(match.group("uses")))
            return {
                "name": name,
                "heal": int(match.group("heal")),
                "range_ft": int(match.group("range")),
                "maximum": max(0, int(uses)),
                "reset": match.group("reset"),
                "origin": _feature_identity(source),
            }
    return None


def _project_current(resource, maximum):
    if resource is None:
        return maximum
    spent = max(0, int(resource.maximo or 0) - int(resource.atual or 0))
    return max(0, min(maximum, maximum - spent))


def siphon_state(person, *, ruleset=None):
    """Project the active reaction counter without materializing it."""
    definition = _definition(person, ruleset=ruleset)
    if definition is None:
        return None
    resource = TbPersonagemRecurso.objects.filter(
        id_personagem=person, chave=SIPHON_KEY).first()
    return {
        "key": SIPHON_KEY,
        "name": definition["name"],
        "current": _project_current(resource, definition["maximum"]),
        "maximum": definition["maximum"],
        "heal": definition["heal"],
        "range_ft": definition["range_ft"],
    }


def _distance(value):
    try:
        distance = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Informe uma distância válida em pés.") from exc
    if not distance.is_finite() or distance < 0:
        raise ValueError("A distância deve ser um número não negativo em pés.")
    return distance


def _fingerprint(distance, enemy_at_zero, reaction_available, confirmed):
    payload = [
        "soul-siphon",
        format(distance, "f"),
        bool(enemy_at_zero),
        bool(reaction_available),
        bool(confirmed),
    ]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


@transaction.atomic
def use_siphon(person, *, operation_id, distance_ft, enemy_at_zero,
               reaction_available, confirmed, ruleset=None):
    """Validate, heal, spend one use, and persist one idempotent receipt."""
    try:
        operation_id = uuid.UUID(str(operation_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identificador da operação inválido.") from exc
    distance = _distance(distance_ft)
    fingerprint = _fingerprint(
        distance, enemy_at_zero, reaction_available, confirmed)

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt is not None:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return dict(receipt.resposta, replayed=True)

    definition = _definition(locked, ruleset=ruleset)
    if definition is None:
        raise ValueError("O personagem não possui uma fonte ativa para esta reação.")
    if enemy_at_zero is not True:
        raise ValueError("Confirme que o inimigo foi reduzido a 0 PV.")
    if reaction_available is not True:
        raise ValueError("A reação precisa estar disponível.")
    if confirmed is not True:
        raise ValueError("Confirme o evento declarado na mesa.")
    if distance > definition["range_ft"]:
        raise ValueError("O inimigo está fora do alcance declarado.")

    contract = {
        "key": SIPHON_KEY,
        "name": definition["name"],
        "maximum": definition["maximum"],
        "reset": definition["reset"],
        "origin": definition["origin"],
    }
    resource = ensure_resource(locked, contract)
    if int(resource.atual or 0) < 1:
        raise ValueError("Não há usos disponíveis para esta reação.")

    before_hp = max(0, int(locked.pv_atual or 0))
    derived_maximum = int(derive(locked, ruleset=ruleset)["pv"]["maximo_calculado"] or 0)
    maximum_hp = max(0, int(locked.pv_maximo or 0), derived_maximum)
    bonus, pending = (healing_bonus(
        locked, hp=before_hp, maximum_hp=maximum_hp, ruleset=ruleset)
        if before_hp < maximum_hp else (0, []))
    after_hp = max(before_hp, min(maximum_hp, before_hp + definition["heal"] + bonus))
    healed = max(0, after_hp - before_hp)
    locked.pv_atual = after_hp
    locked.save(update_fields=["pv_atual"])
    if healed:
        mark_healing_bonuses(locked, pending)

    resource.atual = int(resource.atual) - 1
    resource.versao += 1
    resource.save(update_fields=["atual", "versao"])
    response = {
        "ok": True,
        "operation_id": str(operation_id),
        "key": SIPHON_KEY,
        "name": definition["name"],
        "healed": healed,
        "hp_current": after_hp,
        "current": int(resource.atual),
        "maximum": int(resource.maximo),
        "heal": definition["heal"],
        "range_ft": definition["range_ft"],
        "replayed": False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked,
        operation_id=operation_id,
        fingerprint=fingerprint,
        resposta=response,
        status_http=200,
    )
    return response
