"""Runtime for attack-accuracy epic tags.

The table remains responsible for deciding whether a numeric attack result missed.
This module only rolls d20s, records those rolls, and applies a confirmed
once-per-turn conversion declared by an active source tag.
"""

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
)
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemEstado
from .resource_engine import activate_state, end_state


NO_DISADVANTAGE_TAG = "attack_roll:immune(disadvantage)"
AUTO_HIT_TAG = "trigger=failed_attack, convert:hit, lockout{self, reset:turn_start}"
FORTUNE_TAG = (
    "while_active{trigger=drop_to_0, requires:can_see, "
    "adv:attack{scope:next_attack, until:next_turn_end}}"
)
AUTO_HIT_STATE_KEY = "epic:attack_accuracy:auto_hit:turn_lock"
FORTUNE_STATE_KEY = "epic:attack_accuracy:next_advantage"
_TURN_REF_RE = re.compile(r"^.{1,180}$", re.S)
_ATTACK_RECEIPT_KIND = "epic_tagged_attack"


def _definitions(person, ruleset=None):
    """Read active declarations, including the selected talent attribute source."""
    choices = _talent_attr_map(person, ruleset=ruleset)
    no_disadvantage = None
    auto_hit = None
    fortune = None
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        for tag in tags:
            if tag == NO_DISADVANTAGE_TAG and no_disadvantage is None:
                no_disadvantage = {"origin": _feature_identity(source)}
            elif tag == AUTO_HIT_TAG and auto_hit is None:
                auto_hit = {"origin": _feature_identity(source)}
            elif tag == FORTUNE_TAG and fortune is None:
                fortune = {"origin": _feature_identity(source)}
    return {"no_disadvantage": no_disadvantage, "auto_hit": auto_hit,
            "fortune": fortune}


def _operation_id(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identificador da operação inválido.") from exc


def _boolean(value, label):
    if value is not True and value is not False:
        raise ValueError(f"{label} deve ser booleano.")
    return value


def _turn_ref(value):
    value = str(value or "").strip()
    if not _TURN_REF_RE.fullmatch(value) or any(ord(char) < 32 for char in value):
        raise ValueError("Informe a referência estável do início de turno.")
    return value


def _fingerprint(action, payload):
    raw = json.dumps(["attack-accuracy", action, payload], ensure_ascii=False,
                     sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _receipt(person, operation_id, fingerprint):
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=person, operation_id=operation_id).first()
    if receipt is None:
        return None
    if receipt.fingerprint != fingerprint:
        raise ValueError("Esta operação já foi usada com outros dados.")
    return dict(receipt.resposta, replayed=True)


def _critical_margin(person, ruleset=None):
    """Sum active critical-range tags without binding combat rules to a talent name."""
    from .character_engine import derive
    from .tag_engine.evaluator import evaluate_tags

    choices = _talent_attr_map(person, ruleset=ruleset)
    critical_tags = []
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        for tag in dict.fromkeys(tags):
            # A marked target needs a target-specific attack context. The sheet
            # roll has none, so only general/self-gated margins belong here.
            if "crit_range" in tag and not re.search(r"\btarget\s*:", tag):
                critical_tags.append(tag)
    if not critical_tags:
        return 0
    sheet = derive(person, ruleset=ruleset)
    context = {
        "resolve_runtime": True, "event": "attack_roll",
        "self_hp": int(person.pv_atual or 0),
        "self_max_hp": int(sheet["pv"]["maximo_calculado"] or person.pv_maximo or 0),
    }
    return sum(
        operation.value for tag in critical_tags
        for operation in evaluate_tags([tag], context).operations
        if operation.active and operation.verb == "crit_range"
        and operation.op == "add_modifier"
        and type(operation.value) is int and operation.value > 0
    )


def attack_accuracy_state(person, ruleset=None):
    """Project the currently active declarations and auto-hit availability."""
    definitions = _definitions(person, ruleset=ruleset)
    critical_margin = _critical_margin(person, ruleset=ruleset)
    active = bool(definitions["no_disadvantage"] or definitions["auto_hit"]
                  or definitions["fortune"] or critical_margin)
    if not active:
        return None
    locked = TbPersonagemEstado.objects.filter(
        id_personagem=person, chave=AUTO_HIT_STATE_KEY, ativo=True).exists()
    return {
        "active": True,
        "auto_hit_available": bool(definitions["auto_hit"]) and not locked,
        "auto_hit_active": bool(definitions["auto_hit"]),
        "no_disadvantage": bool(definitions["no_disadvantage"]),
        "critical_threshold": max(2, 20 - critical_margin),
        "fortune_active": bool(definitions["fortune"]),
        "fortune_pending": bool(definitions["fortune"]) and TbPersonagemEstado.objects.filter(
            id_personagem=person, chave=FORTUNE_STATE_KEY, ativo=True).exists(),
    }


@transaction.atomic
def roll_tagged_attack(person, *, operation_id, advantage=False, disadvantage=False,
                       ruleset=None):
    """Roll an attack d20 on the server and preserve an idempotent receipt."""
    operation_id = _operation_id(operation_id)
    advantage = _boolean(advantage, "Vantagem")
    disadvantage = _boolean(disadvantage, "Desvantagem")
    payload = {"advantage": advantage, "disadvantage": disadvantage}
    fingerprint = _fingerprint("attack", payload)

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    definitions = _definitions(locked, ruleset=ruleset)
    from .epic_fate import _source as fate_source
    has_fate = fate_source(locked, ruleset=ruleset) is not None
    critical_margin = _critical_margin(locked, ruleset=ruleset)
    if not (definitions["no_disadvantage"] or definitions["auto_hit"]
            or definitions["fortune"]
            or critical_margin or has_fate):
        raise ValueError("O personagem não possui uma fonte ativa para precisão de ataque.")

    fortune_pending = bool(definitions["fortune"]) and TbPersonagemEstado.objects.filter(
        id_personagem=locked, chave=FORTUNE_STATE_KEY, ativo=True).exists()
    effective_disadvantage = disadvantage and not bool(definitions["no_disadvantage"])
    if (advantage or fortune_pending) and not effective_disadvantage:
        mode = "advantage"
    elif effective_disadvantage and not (advantage or fortune_pending):
        mode = "disadvantage"
    else:
        mode = "normal"
    rolls = [secrets.randbelow(20) + 1 for _ in range(2 if mode != "normal" else 1)]
    applied = max(rolls) if mode == "advantage" else min(rolls)
    if fortune_pending:
        end_state(locked, FORTUNE_STATE_KEY)
    response = {
        "operation_id": str(operation_id),
        "rolls": rolls,
        "applied_d20": applied,
        "mode": mode,
        "critical_threshold": max(2, 20 - critical_margin),
        "critical_on_hit": applied >= max(2, 20 - critical_margin),
        "fortune_consumed": fortune_pending,
        "replayed": False,
        "kind": _ATTACK_RECEIPT_KIND,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    if has_fate and applied in (1, 20) and fate_source(locked, ruleset=ruleset, recovery=True):
        from .epic_fate import recover_fate
        fate = recover_fate(
            locked, operation_id=uuid.uuid5(uuid.NAMESPACE_URL,
                                             "epic-fate-attack:%s" % operation_id),
            event_ref="attack:%s" % operation_id, natural_d20=applied,
            own_roll_confirmed=True, critical_confirmed=True, ruleset=ruleset)
        response["fate_recovered"] = fate["recovered"]
        TbOperacaoRecurso.objects.filter(
            id_personagem=locked, operation_id=operation_id).update(resposta=response)
    return response


@transaction.atomic
def record_visible_zero(person, *, operation_id, event_ref, creature_ref,
                        visible_confirmed, zero_confirmed, during_own_turn,
                        ruleset=None):
    """Record one table-confirmed visible creature reaching zero HP."""
    operation_id = _operation_id(operation_id)
    event_ref = _turn_ref(event_ref)
    creature_ref = _turn_ref(creature_ref)
    for flag in (visible_confirmed, zero_confirmed, during_own_turn):
        _boolean(flag, "Confirmação")
    if not visible_confirmed or not zero_confirmed:
        raise ValueError("Confirme a criatura visível e sua queda a 0 PV.")
    fingerprint = _fingerprint("visible_zero", [event_ref, creature_ref,
                                                during_own_turn])
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    definition = _definitions(locked, ruleset=ruleset)["fortune"]
    if definition is None:
        raise ValueError("Fonte de vantagem indisponível.")
    if TbOperacaoRecurso.objects.filter(
            id_personagem=locked, resposta__fortune_event_ref=event_ref).exists():
        raise ValueError("Este evento já foi registrado.")
    activate_state(locked, FORTUNE_STATE_KEY, origin=definition["origin"],
                   payload={"creature_ref": creature_ref,
                            "remaining_turn_ends": 2 if during_own_turn else 1},
                   ends_on=[])
    response = {"operation_id": str(operation_id), "fortune_event_ref": event_ref,
                "creature_ref": creature_ref, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response


@transaction.atomic
def end_fortune_turn(person, *, operation_id, turn_ref, confirmed,
                     ruleset=None):
    """Expire unused advantage after the end of the following own turn."""
    operation_id = _operation_id(operation_id)
    turn_ref = _turn_ref(turn_ref)
    confirmed = _boolean(confirmed, "Fim do turno")
    if not confirmed:
        raise ValueError("Confirme o fim do turno na mesa.")
    fingerprint = _fingerprint("fortune_turn_end", turn_ref)
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    if _definitions(locked, ruleset=ruleset)["fortune"] is None:
        raise ValueError("Fonte de vantagem indisponível.")
    if TbOperacaoRecurso.objects.filter(
            id_personagem=locked, resposta__fortune_turn_ref=turn_ref).exists():
        raise ValueError("Este fim de turno já foi registrado.")
    state = TbPersonagemEstado.objects.select_for_update().filter(
        id_personagem=locked, chave=FORTUNE_STATE_KEY, ativo=True).first()
    if state is None:
        raise ValueError("Não há vantagem pendente.")
    remaining = max(0, int(state.payload_json.get("remaining_turn_ends", 0)) - 1)
    if remaining:
        state.payload_json = dict(state.payload_json, remaining_turn_ends=remaining)
        state.save(update_fields=["payload_json"])
    else:
        end_state(locked, FORTUNE_STATE_KEY)
    response = {"operation_id": str(operation_id), "fortune_turn_ref": turn_ref,
                "remaining_turn_ends": remaining, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response


@transaction.atomic
def convert_tagged_miss(person, *, operation_id, attack_operation_id, miss_confirmed,
                        ruleset=None):
    """Convert a table-confirmed miss from a recorded attack to a hit once per turn."""
    operation_id = _operation_id(operation_id)
    attack_operation_id = _operation_id(attack_operation_id)
    miss_confirmed = _boolean(miss_confirmed, "A falha confirmada")
    payload = {"attack_operation_id": str(attack_operation_id),
               "miss_confirmed": miss_confirmed}
    fingerprint = _fingerprint("convert", payload)

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    definition = _definitions(locked, ruleset=ruleset)["auto_hit"]
    if definition is None:
        raise ValueError("O personagem não possui uma fonte ativa para converter falhas de ataque.")
    attack = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=attack_operation_id).first()
    if (attack is None or (attack.resposta or {}).get("kind") != _ATTACK_RECEIPT_KIND):
        raise ValueError("A conversão exige um ataque anterior registrado para este personagem.")
    if miss_confirmed is not True:
        raise ValueError("A conversão exige a confirmação da falha na mesa.")
    if TbOperacaoRecurso.objects.filter(
            id_personagem=locked, resposta__hit=True,
            resposta__attack_operation_id=str(attack_operation_id)).exists():
        raise ValueError("Esta rolagem de ataque já foi convertida em acerto.")
    if TbPersonagemEstado.objects.filter(
            id_personagem=locked, chave=AUTO_HIT_STATE_KEY, ativo=True).exists():
        raise ValueError("A conversão já foi usada até o início do próximo turno.")

    activate_state(locked, AUTO_HIT_STATE_KEY, origin=definition["origin"],
                   payload={"attack_operation_id": str(attack_operation_id)},
                   ends_on=["turn_start"])
    response = {"operation_id": str(operation_id), "attack_operation_id": str(attack_operation_id),
                "hit": True, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    return response


@transaction.atomic
def release_auto_hit_on_turn_start(person, *, operation_id, turn_ref, confirmed):
    """Release the once-per-turn lock after the table confirms a turn start."""
    operation_id = _operation_id(operation_id)
    turn_ref = _turn_ref(turn_ref)
    confirmed = _boolean(confirmed, "A confirmação")
    payload = {"turn_ref": turn_ref, "confirmed": confirmed}
    fingerprint = _fingerprint("turn_start", payload)

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    if confirmed is not True:
        raise ValueError("A liberação exige confirmação do início de turno na mesa.")
    state = TbPersonagemEstado.objects.select_for_update().filter(
        id_personagem=locked, chave=AUTO_HIT_STATE_KEY, ativo=True).first()
    released = state is not None
    if released:
        end_state(locked, AUTO_HIT_STATE_KEY)
    response = {"operation_id": str(operation_id), "turn_ref": turn_ref,
                "released": released, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    return response
