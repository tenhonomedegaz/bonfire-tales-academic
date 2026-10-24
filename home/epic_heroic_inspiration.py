"""Consume an already granted Heroic Inspiration from the character ledger."""

import hashlib
import json
import re
import uuid

from django.db import transaction

from .character_engine import (
    _feature_talent_attr_sig, _features_do_personagem, _talent_attr_map,
)
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemRecurso


HEROIC_INSPIRATION_KEY = "heroic_inspiration"
RETAIN_INSPIRATION_TAG = (
    "trigger=heroic_inspiration_roll(result:failure), retain:heroic_inspiration"
)
_RETAIN_RE = re.compile(
    r"^trigger=heroic_inspiration_roll\(result:failure\), "
    r"retain:heroic_inspiration$"
)


def _can_retain(person, ruleset=None):
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        if any(_RETAIN_RE.fullmatch(tag) for tag in tags):
            return True
    return False


def inspiration_state(person, ruleset=None):
    """Existing grants only; an epic feature never creates Inspiration."""
    row = TbPersonagemRecurso.objects.filter(
        id_personagem=person, chave=HEROIC_INSPIRATION_KEY).first()
    return {"available": bool(row and row.origem and row.atual == 1
                              and row.maximo == 1),
            "can_retain": _can_retain(person, ruleset=ruleset),
            "origin": row.origem if row else ""}


@transaction.atomic
def use_inspiration(person, *, operation_id, roll_kind, failed, ruleset=None):
    """Apply the table's resolved outcome once; keep a failed use if tagged."""
    try:
        operation_id = uuid.UUID(str(operation_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Identificador de operação inválido.") from exc
    roll_kind = str(roll_kind or "").strip().casefold()
    if roll_kind not in {"attack", "ability_check", "save"} or type(failed) is not bool:
        raise ValueError("Declare uma rolagem e seu resultado.")
    fingerprint = hashlib.sha256(json.dumps(
        ["heroic-inspiration", roll_kind, failed], separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt is not None:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return dict(receipt.resposta, replayed=True)
    resource = TbPersonagemRecurso.objects.select_for_update().filter(
        id_personagem=locked, chave=HEROIC_INSPIRATION_KEY).first()
    if resource is None or not resource.origem or resource.atual != 1 or resource.maximo != 1:
        raise ValueError("Nenhuma Inspiração Heróica concedida está disponível.")
    retained = bool(failed and _can_retain(locked, ruleset=ruleset))
    if not retained:
        resource.atual = 0
        resource.versao += 1
        resource.save(update_fields=["atual", "versao"])
    response = {"ok": True, "operation_id": str(operation_id),
                "roll_kind": roll_kind, "failed": failed,
                "retained": retained, "remaining": resource.atual,
                "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
