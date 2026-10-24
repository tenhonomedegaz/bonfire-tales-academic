"""Runtime for a once-per-turn failed saving-throw reroll declared by a tag."""

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


REROLL_TAG = (
    "trigger=failed_save(kind:any|death), reroll:d20(keep:new), "
    "lockout{self, reset:turn_start}"
)
REROLL_STATE_KEY = "epic:save_reroll:turn_lock"

_REROLL_RE = re.compile(
    r"^trigger\s*=\s*failed_save\(\s*kind\s*:\s*"
    r"(?P<kinds>any\|death)\s*\)\s*,\s*"
    r"reroll\s*:\s*d20\(\s*keep\s*:\s*(?P<keep>new)\s*\)\s*,\s*"
    r"lockout\{\s*(?P<scope>self)\s*,\s*reset\s*:\s*"
    r"(?P<reset>turn_start)\s*\}$"
)
_SAVE_KIND_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$", re.I)


def _definition(person, ruleset=None):
    """Return an active declaration without relying on a source display name."""
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        for tag in tags:
            match = _REROLL_RE.fullmatch(tag)
            if match is not None:
                return {"origin": _feature_identity(source), "tag": tag}
    return None


def _operation_id(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identificador da operação inválido.") from exc


def _d20(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 20:
        raise ValueError(f"{label} deve ser um resultado inteiro de d20 entre 1 e 20.")
    return value


def _save_kind(value):
    value = str(value or "").strip().casefold()
    if not _SAVE_KIND_RE.fullmatch(value):
        raise ValueError("Informe a espécie de salvaguarda declarada na mesa.")
    return value


def _turn_ref(value):
    value = str(value or "").strip()
    if not value or len(value) > 180 or any(ord(char) < 32 for char in value):
        raise ValueError("Informe a referência estável do início de turno.")
    return value


def _fingerprint(action, payload):
    encoded = json.dumps(["save-reroll", action, payload], ensure_ascii=False,
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _receipt(person, operation_id, fingerprint):
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=person, operation_id=operation_id).first()
    if receipt is None:
        return None
    if receipt.fingerprint != fingerprint:
        raise ValueError("Esta operação já foi usada com outros dados.")
    return dict(receipt.resposta, replayed=True)


def reroll_state(person, ruleset=None):
    """Project availability from the pinned source and the persistent lock."""
    definition = _definition(person, ruleset=ruleset)
    if definition is None:
        return None
    locked = TbPersonagemEstado.objects.filter(
        id_personagem=person, chave=REROLL_STATE_KEY, ativo=True).exists()
    return {"active": True, "available": not locked,
            "state_key": REROLL_STATE_KEY if locked else None}


@transaction.atomic
def use_save_reroll(person, *, operation_id, save_kind, failed, original_roll,
                    ruleset=None):
    """Spend the tag mechanism and roll the replacement d20 once."""
    operation_id = _operation_id(operation_id)
    save_kind = _save_kind(save_kind)
    original_roll = _d20(original_roll, "O resultado original")
    payload = {"save_kind": save_kind, "failed": failed,
               "original_roll": original_roll}
    fingerprint = _fingerprint("use", payload)

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    definition = _definition(locked, ruleset=ruleset)
    if definition is None:
        raise ValueError("O personagem não possui uma fonte ativa para esta rerrolagem.")
    if failed is not True:
        raise ValueError("A rerrolagem exige uma salvaguarda que falhou.")
    if TbPersonagemEstado.objects.filter(
            id_personagem=locked, chave=REROLL_STATE_KEY, ativo=True).exists():
        raise ValueError("A rerrolagem já foi usada até o início do próximo turno.")

    new_roll = secrets.randbelow(20) + 1
    activate_state(
        locked, REROLL_STATE_KEY, origin=definition["origin"],
        payload={"save_kind": save_kind}, ends_on=["turn_start"],
    )
    response = {"ok": True, "operation_id": str(operation_id),
                "save_kind": save_kind, "original_d20": original_roll,
                "applied_d20": new_roll, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    return response


@transaction.atomic
def release_reroll_on_turn_start(person, *, operation_id, turn_ref, confirmed):
    """Release the lock after the table confirms the declared turn start."""
    operation_id = _operation_id(operation_id)
    turn_ref = _turn_ref(turn_ref)
    payload = {"turn_ref": turn_ref, "confirmed": confirmed}
    fingerprint = _fingerprint("turn_start", payload)

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    if confirmed is not True:
        raise ValueError("A liberação exige confirmação do início de turno na mesa.")
    state = TbPersonagemEstado.objects.select_for_update().filter(
        id_personagem=locked, chave=REROLL_STATE_KEY, ativo=True).first()
    released = state is not None
    if released:
        end_state(locked, REROLL_STATE_KEY)
    response = {"ok": True, "operation_id": str(operation_id), "turn_ref": turn_ref,
                "released": released, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    return response
