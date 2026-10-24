"""Runtime for the bonus-action healing dice declared by an epic tag."""

import hashlib
import json
import re
import secrets
import uuid

from django.db import transaction

from .character_engine import (
    _feature_identity,
    _feature_talent_attr_sig,
    _features_do_personagem,
    _talent_attr_map,
    derive,
)
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemRecurso
from .resource_engine import spend_resource
from .epic_healing_bonus import healing_bonus, mark_healing_bonuses


# This declaration deliberately contains only Recuperar Vitalidade.  The other
# benefit of Dádiva da Recuperação remains unpublished until its zero-HP runtime
# exists.
RECOVERY_POOL_TAG = (
    "define{recovery_pool: max:10, die:d10, reset:short_or_long}, "
    "action:bonus_action, uses{10, reset:short_or_long}, "
    "heal:sum(rolled_d10)@self"
)
RECOVERY_POOL_KEY = "epic:recovery_pool"
SURVIVAL_TAG = (
    "trigger=reduce_to_0(target:self), "
    "instant{set:hp=1, heal:half(max_hp)}, uses{1, reset:long_rest}"
)
SURVIVAL_KEY = "epic:survival"

_RECOVERY_POOL_RE = re.compile(
    r"^define\{\s*recovery_pool\s*:\s*max\s*:\s*(?P<maximum>\d+)\s*,\s*"
    r"die\s*:\s*d(?P<faces>\d+)\s*,\s*reset\s*:\s*(?P<reset>[a-z_]+)\s*\}\s*,\s*"
    r"action\s*:\s*bonus_action\s*,\s*uses\{\s*(?P<uses>\d+)\s*,\s*"
    r"reset\s*:\s*(?P=reset)\s*\}\s*,\s*"
    r"heal\s*:\s*sum\(\s*rolled_d(?P=faces)\s*\)@self$"
)
_SURVIVAL_RE = re.compile(
    r"^trigger=reduce_to_0\(target:self\), "
    r"instant\{set:hp=(?P<retain>\d+), heal:half\(max_hp\)\}, "
    r"uses\{(?P<uses>\d+), reset:(?P<reset>[a-z_]+)\}$"
)


def _definition(person, ruleset=None):
    """Find the selected active source that declares this exact pool."""
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, display_name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or ()))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        for tag in tags:
            match = _RECOVERY_POOL_RE.fullmatch(tag)
            if match is None:
                continue
            maximum = int(match.group("maximum"))
            if (maximum != int(match.group("uses")) or maximum != 10
                    or int(match.group("faces")) != 10
                    or match.group("reset") != "short_or_long"):
                continue
            return {
                "name": str(getattr(source, "nome", "") or display_name or "").strip(),
                "maximum": maximum,
                "faces": int(match.group("faces")),
                "reset": match.group("reset"),
                "origin": _feature_identity(source),
            }
    return None


def _contract(definition):
    return {
        "key": RECOVERY_POOL_KEY,
        "name": definition["name"] or "Recuperar Vitalidade",
        "maximum": definition["maximum"],
        "reset": definition["reset"],
        "origin": definition["origin"],
    }


def _operation_id(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identificador da operação inválido.") from exc


def _dice_count(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10:
        raise ValueError("Informe de 1 a 10 dados da reserva.")
    return value


def _boolean(value, label):
    if value is not True and value is not False:
        raise ValueError(f"{label} deve ser booleano.")
    return value


def _fingerprint(dice_count, bonus_action_available, confirmed):
    payload = ["recovery-pool", dice_count, bonus_action_available, confirmed]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def _receipt(person, operation_id, fingerprint):
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=person, operation_id=operation_id).first()
    if receipt is None:
        return None
    if receipt.fingerprint != fingerprint:
        raise ValueError("Esta operação já foi usada com outros dados.")
    return dict(receipt.resposta, replayed=True)


def recovery_pool_state(person, ruleset=None):
    """Return the selected source's projected pool without creating a ledger row."""
    definition = _definition(person, ruleset=ruleset)
    if definition is None:
        return None
    resource = TbPersonagemRecurso.objects.filter(
        id_personagem=person, chave=RECOVERY_POOL_KEY).first()
    current = definition["maximum"] if resource is None else max(
        0, min(definition["maximum"], int(resource.atual or 0)))
    return {"available": current, "max": definition["maximum"]}


def _survival_definition(person, ruleset=None):
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, display_name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or ()))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        for tag in tags:
            match = _SURVIVAL_RE.fullmatch(tag)
            if (match and int(match.group("retain")) == 1
                    and int(match.group("uses")) == 1
                    and match.group("reset") == "long_rest"):
                return {
                    "key": SURVIVAL_KEY,
                    "name": str(getattr(source, "nome", "") or display_name or "Sobrevivência"),
                    "maximum": 1,
                    "reset": "long_rest",
                    "origin": _feature_identity(source),
                }
    return None


def survival_state(person, ruleset=None):
    """Project the once-per-long-rest benefit without creating a resource."""
    definition = _survival_definition(person, ruleset=ruleset)
    if definition is None:
        return None
    resource = TbPersonagemRecurso.objects.filter(
        id_personagem=person, chave=SURVIVAL_KEY).first()
    return {"available": 1 if resource is None else max(0, min(1, int(resource.atual or 0)))}


@transaction.atomic
def apply_incoming_damage(person, *, operation_id, damage, use_survival, confirmed,
                          ruleset=None):
    """Apply final damage and trigger the declared survival effect if chosen."""
    operation_id = _operation_id(operation_id)
    if type(damage) is not int or damage <= 0:
        raise ValueError("Informe um dano final positivo.")
    use_survival = _boolean(use_survival, "Uso da sobrevivência")
    confirmed = _boolean(confirmed, "Confirmação")
    fingerprint = hashlib.sha256(json.dumps(
        ["survival-damage", damage, use_survival, confirmed],
        separators=(",", ":")).encode()).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    definition = _survival_definition(locked, ruleset=ruleset)
    if definition is None:
        raise ValueError("O personagem não possui a fonte ativa de sobrevivência.")
    if not confirmed:
        raise ValueError("Confirme o dano final declarado na mesa.")
    before_hp = max(0, int(locked.pv_atual or 0))
    if before_hp == 0:
        raise ValueError("O personagem já está a 0 PV.")
    before_temp = max(0, int(locked.pv_temporario or 0))
    absorbed = min(before_temp, damage)
    remaining_damage = damage - absorbed
    after_hp = max(0, before_hp - remaining_damage)
    triggered = False
    if after_hp == 0 and use_survival:
        spent, _resource = spend_resource(locked, definition)
        if not spent:
            raise ValueError("O benefício de sobrevivência já foi usado neste descanso.")
        derived_max = int(derive(locked, ruleset=ruleset)["pv"]["maximo_calculado"] or 0)
        maximum = max(0, int(locked.pv_maximo or 0), derived_max)
        after_hp = min(maximum, 1 + maximum // 2)
        bonus, pending = healing_bonus(
            locked, hp=1, maximum_hp=maximum, ruleset=ruleset)
        after_hp = min(maximum, after_hp + bonus)
        if after_hp > 1:
            mark_healing_bonuses(locked, pending)
        triggered = True
    locked.pv_atual = after_hp
    locked.pv_temporario = before_temp - absorbed
    locked.save(update_fields=["pv_atual", "pv_temporario"])
    response = {
        "operation_id": str(operation_id), "damage": damage, "absorbed": absorbed,
        "hp_before": before_hp, "hp_after": after_hp,
        "temp_hp_after": locked.pv_temporario, "survival_triggered": triggered,
        "replayed": False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    return response


@transaction.atomic
def use_recovery_pool(person, *, operation_id, dice_count, bonus_action_available,
                      confirmed, ruleset=None):
    """Spend dice, roll them once, heal, and store an idempotent receipt."""
    operation_id = _operation_id(operation_id)
    dice_count = _dice_count(dice_count)
    bonus_action_available = _boolean(bonus_action_available, "Ação bônus disponível")
    confirmed = _boolean(confirmed, "Confirmação")
    fingerprint = _fingerprint(dice_count, bonus_action_available, confirmed)

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    definition = _definition(locked, ruleset=ruleset)
    if definition is None:
        raise ValueError("O personagem não possui uma fonte ativa para Recuperar Vitalidade.")
    if not bonus_action_available:
        raise ValueError("A ação bônus precisa estar disponível.")
    if not confirmed:
        raise ValueError("Confirme o uso declarado na mesa.")
    if dice_count > definition["maximum"]:
        raise ValueError("A quantidade de dados excede a reserva declarada.")

    spent, resource = spend_resource(locked, _contract(definition), dice_count)
    if not spent:
        raise ValueError("Não há dados suficientes na reserva de Recuperar Vitalidade.")

    rolls = [secrets.randbelow(10) + 1 for _ in range(dice_count)]
    rolled_total = sum(rolls)
    hp_before = max(0, int(locked.pv_atual or 0))
    derived_max = int(derive(locked, ruleset=ruleset)["pv"]["maximo_calculado"] or 0)
    maximum_hp = max(0, int(locked.pv_maximo or 0), derived_max)
    bonus, pending = (healing_bonus(
        locked, hp=hp_before, maximum_hp=maximum_hp, ruleset=ruleset)
        if hp_before < maximum_hp else (0, []))
    hp_after = max(hp_before, min(maximum_hp, hp_before + rolled_total + bonus))
    healed = hp_after - hp_before
    locked.pv_atual = hp_after
    locked.save(update_fields=["pv_atual"])
    if healed:
        mark_healing_bonuses(locked, pending)

    response = {
        "operation_id": str(operation_id),
        "rolls": rolls,
        "rolled_total": rolled_total,
        "healed": healed,
        "hp_before": hp_before,
        "hp_after": hp_after,
        "resource_remaining": resource["current"],
        "replayed": False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    return response
