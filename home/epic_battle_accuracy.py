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
AUTO_HIT_STATE_KEY = "epic:attack_accuracy:auto_hit:turn_lock"
_TURN_REF_RE = re.compile(r"^.{1,180}$", re.S)
_ATTACK_RECEIPT_KIND = "epic_tagged_attack"


def _definitions(person, ruleset=None):
    """Read active declarations, including the selected talent attribute source."""
    choices = _talent_attr_map(person, ruleset=ruleset)
    no_disadvantage = None
    auto_hit = None
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
    return {"no_disadvantage": no_disadvantage, "auto_hit": auto_hit}


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


def attack_accuracy_state(person, ruleset=None):
    """Project the currently active declarations and auto-hit availability."""
    definitions = _definitions(person, ruleset=ruleset)
    active = bool(definitions["no_disadvantage"] or definitions["auto_hit"])
    if not active:
        return None
    locked = TbPersonagemEstado.objects.filter(
        id_personagem=person, chave=AUTO_HIT_STATE_KEY, ativo=True).exists()
    return {
        "active": True,
        "auto_hit_available": bool(definitions["auto_hit"]) and not locked,
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
    if not (definitions["no_disadvantage"] or definitions["auto_hit"]):
        raise ValueError("O personagem não possui uma fonte ativa para precisão de ataque.")

    effective_disadvantage = disadvantage and not bool(definitions["no_disadvantage"])
    if advantage and not effective_disadvantage:
        mode = "advantage"
    elif effective_disadvantage and not advantage:
        mode = "disadvantage"
    else:
        mode = "normal"
    rolls = [secrets.randbelow(20) + 1 for _ in range(2 if mode != "normal" else 1)]
    applied = max(rolls) if mode == "advantage" else min(rolls)
    response = {
        "operation_id": str(operation_id),
        "rolls": rolls,
        "applied_d20": applied,
        "mode": mode,
        "replayed": False,
        "kind": _ATTACK_RECEIPT_KIND,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
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
