"""Persistent, source-gated d20 intervention declared by epic tags."""

import hashlib
import json
import secrets
import uuid

from django.db import transaction

from .character_engine import (
    _feature_identity, _feature_talent_attr_sig, _features_do_personagem,
    _talent_attr_map,
)
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemEstado
from .resource_engine import activate_state, end_state
from .tag_engine.runtime_values import d20_adjustment, roll_dice


ALTER_FATE_TAG = "trigger=d20_result, range:60ft, roll:2d4, buff:d20(plus_or_minus:2d4), uses{1, reset:initiative_or_short_or_long}"
REVERBERANT_FATE_TAG = "trigger=self_natural_critical, reset:alter_fate(direction:critical_opposite)"
FATE_LOCK_KEY = "epic:fate:alter_fate:used"
FATE_RECOVERY_KEY = "epic:fate:alter_fate:recovered"


def _definition(person, ruleset=None):
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in source.tags_json or [])
        if any("talent_attr_score" in tag for tag in tags) and not _feature_talent_attr_sig(source, choices):
            continue
        for tag in tags:
            definition = d20_adjustment(tag)
            if definition:
                return dict(definition, origin=_feature_identity(source),
                            recover_on_critical=REVERBERANT_FATE_TAG in tags)
    return None


def _source(person, ruleset=None, *, recovery=False):
    definition = _definition(person, ruleset=ruleset)
    if recovery and definition and not definition["recover_on_critical"]:
        return None
    return definition["origin"] if definition else None


def fate_state(person, ruleset=None):
    definition = _definition(person, ruleset=ruleset)
    if definition is None:
        return None
    locked = TbPersonagemEstado.objects.filter(
        id_personagem=person, chave=FATE_LOCK_KEY, ativo=True).exists()
    recovery = TbPersonagemEstado.objects.filter(
        id_personagem=person, chave=FATE_RECOVERY_KEY, ativo=True).first()
    return {"available": not locked, "direction": (
        (recovery.payload_json or {}).get("direction") if recovery and not locked else None),
        "dice": definition["dice"], "range_ft": definition["range_ft"],
        "recover_on_critical": definition["recover_on_critical"]}


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Identificador da operação inválido.") from exc


def _ref(value):
    value = str(value or "").strip()
    if not value or len(value) > 180 or any(ord(char) < 32 for char in value):
        raise ValueError("Informe uma referência estável da rolagem ou evento.")
    return value


def _receipt(person, operation_id, action, payload):
    fingerprint = hashlib.sha256(json.dumps(
        ["epic_fate", action, payload], sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    existing = TbOperacaoRecurso.objects.filter(
        id_personagem=person, operation_id=operation_id).first()
    if existing:
        if existing.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return fingerprint, dict(existing.resposta, replayed=True)
    return fingerprint, None


def _save_receipt(person, operation_id, fingerprint, response):
    TbOperacaoRecurso.objects.create(
        id_personagem=person, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response


@transaction.atomic
def alter_fate(person, *, operation_id, roll_ref, distance_ft, direction,
               d20_result_confirmed, ruleset=None):
    """Roll the tagged adjustment after a declared d20 success or failure."""
    operation_id = _uuid(operation_id)
    roll_ref = _ref(roll_ref)
    try:
        distance_ft = int(distance_ft)
    except (TypeError, ValueError) as exc:
        raise ValueError("Distância inválida.") from exc
    if distance_ft < 0 or direction not in ("increase", "decrease"):
        raise ValueError("Alvo fora do alcance ou direção inválida.")
    if d20_result_confirmed is not True:
        raise ValueError("Confirme o resultado da rolagem d20 na mesa.")
    payload = [roll_ref, distance_ft, direction]
    locked_person = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    fingerprint, replay = _receipt(locked_person, operation_id, "use", payload)
    if replay is not None:
        return replay
    definition = _definition(locked_person, ruleset=ruleset)
    if definition is None:
        raise ValueError("Fonte ativa de Alterar Destino indisponível.")
    origin = definition["origin"]
    if distance_ft > definition["range_ft"]:
        raise ValueError("Alvo fora do alcance declarado.")
    if TbOperacaoRecurso.objects.filter(
            id_personagem=locked_person, resposta__fate_roll_ref=roll_ref).exists():
        raise ValueError("Esta rolagem já foi alterada.")
    state = fate_state(locked_person, ruleset=ruleset)
    if not state["available"] or state["direction"] not in (None, direction):
        raise ValueError("Uso indisponível para esta direção.")
    dice = roll_dice(definition["dice"], secrets.randbelow)
    activate_state(locked_person, FATE_LOCK_KEY, origin=origin,
                   payload={"roll_ref": roll_ref}, ends_on=["short_rest", "long_rest"])
    end_state(locked_person, FATE_RECOVERY_KEY)
    response = {"operation_id": str(operation_id), "fate_roll_ref": roll_ref,
                "dice": dice, "modifier": sum(dice) * (1 if direction == "increase" else -1),
                "direction": direction, "replayed": False}
    return _save_receipt(locked_person, operation_id, fingerprint, response)


@transaction.atomic
def recover_fate(person, *, operation_id, event_ref, natural_d20,
                 own_roll_confirmed, critical_confirmed, ruleset=None):
    """Restore spent use after the character's own natural 1 or 20."""
    operation_id = _uuid(operation_id)
    event_ref = _ref(event_ref)
    if type(natural_d20) is not int or natural_d20 not in (1, 20):
        raise ValueError("A rolagem deve ser um crítico natural 1 ou 20.")
    if own_roll_confirmed is not True or critical_confirmed is not True:
        raise ValueError("Confirme o próprio resultado crítico na mesa.")
    locked_person = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    fingerprint, replay = _receipt(locked_person, operation_id, "critical",
                                   [event_ref, natural_d20])
    if replay is not None:
        return replay
    definition = _definition(locked_person, ruleset=ruleset)
    if definition is None or not definition["recover_on_critical"]:
        raise ValueError("Fonte ativa de Causalidade Reverberante indisponível.")
    origin = definition["origin"]
    if TbOperacaoRecurso.objects.filter(
            id_personagem=locked_person, resposta__fate_critical_ref=event_ref).exists():
        raise ValueError("Este crítico já foi registrado.")
    spent = TbPersonagemEstado.objects.filter(
        id_personagem=locked_person, chave=FATE_LOCK_KEY, ativo=True).exists()
    if spent:
        end_state(locked_person, FATE_LOCK_KEY)
        activate_state(locked_person, FATE_RECOVERY_KEY, origin=origin,
                       payload={"direction": "decrease" if natural_d20 == 20 else "increase"},
                       ends_on=["short_rest", "long_rest"])
    response = {"operation_id": str(operation_id), "fate_critical_ref": event_ref,
                "recovered": spent, "direction": (
                    "decrease" if natural_d20 == 20 else "increase") if spent else None,
                "replayed": False}
    return _save_receipt(locked_person, operation_id, fingerprint, response)


@transaction.atomic
def reset_fate_on_initiative(person, *, operation_id, initiative_ref,
                             confirmed, ruleset=None):
    operation_id = _uuid(operation_id)
    initiative_ref = _ref(initiative_ref)
    if confirmed is not True:
        raise ValueError("Confirme a rolagem de iniciativa.")
    locked_person = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    fingerprint, replay = _receipt(locked_person, operation_id, "initiative", initiative_ref)
    if replay is not None:
        return replay
    if _source(locked_person, ruleset=ruleset) is None:
        raise ValueError("Fonte ativa de Alterar Destino indisponível.")
    if TbOperacaoRecurso.objects.filter(
            id_personagem=locked_person, resposta__fate_initiative_ref=initiative_ref).exists():
        raise ValueError("Esta iniciativa já foi registrada.")
    end_state(locked_person, FATE_LOCK_KEY)
    end_state(locked_person, FATE_RECOVERY_KEY)
    response = {"operation_id": str(operation_id), "fate_initiative_ref": initiative_ref,
                "replayed": False}
    return _save_receipt(locked_person, operation_id, fingerprint, response)
