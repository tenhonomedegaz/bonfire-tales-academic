"""A failed saving throw can become a success when an active tag grants it."""

import hashlib
import json
import re
import uuid

from django.db import transaction

from .character_engine import (
    _feature_identity, _feature_talent_attr_sig, _features_do_personagem,
    _talent_attr_map,
)
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemEstado
from .resource_engine import activate_state


LEGENDARY_SAVE_TAG = (
    "trigger=failed_save(kind:any|death), result:success, "
    "lockout{self, reset:short_rest|long_rest}"
)
LEGENDARY_SAVE_STATE_KEY = "epic:legendary_save:rest_lock"
_TAG_RE = re.compile(
    r"^trigger=failed_save\(kind:any\|death\), result:success, "
    r"lockout\{self, reset:short_rest\|long_rest\}$"
)
_SAVE_KINDS = {"str", "dex", "con", "int", "wis", "cha", "death"}


def _definition(person, ruleset=None):
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        if any(_TAG_RE.fullmatch(tag) for tag in tags):
            return _feature_identity(source)
    return None


def legendary_save_state(person, ruleset=None):
    origin = _definition(person, ruleset=ruleset)
    if origin is None:
        return None
    spent = TbPersonagemEstado.objects.filter(
        id_personagem=person, chave=LEGENDARY_SAVE_STATE_KEY, ativo=True).exists()
    return {"active": True, "available": not spent}


@transaction.atomic
def use_legendary_save(person, *, operation_id, save_kind, failed, ruleset=None):
    try:
        operation_id = uuid.UUID(str(operation_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identificador de operação inválido.") from exc
    save_kind = str(save_kind or "").strip().casefold()
    if save_kind not in _SAVE_KINDS or failed is not True:
        raise ValueError("Declare uma salvaguarda que falhou.")
    fingerprint = hashlib.sha256(json.dumps(
        ["legendary-save", save_kind, failed], separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt is not None:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return dict(receipt.resposta, replayed=True)
    origin = _definition(locked, ruleset=ruleset)
    if origin is None:
        raise ValueError("Fonte de resistência lendária indisponível.")
    if TbPersonagemEstado.objects.filter(
            id_personagem=locked, chave=LEGENDARY_SAVE_STATE_KEY, ativo=True).exists():
        raise ValueError("Resistência lendária já utilizada neste descanso.")
    activate_state(locked, LEGENDARY_SAVE_STATE_KEY, origin=origin,
                   payload={"save_kind": save_kind},
                   ends_on=["short_rest", "long_rest"])
    response = {"ok": True, "operation_id": str(operation_id),
                "save_kind": save_kind, "result": "success", "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
