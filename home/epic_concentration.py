"""Resolve declared interruptions of persistent spell concentration."""

import hashlib
import json
import re
import uuid

from django.db import transaction
from django.utils import timezone

from .character_engine import (
    _feature_talent_attr_sig, _features_do_personagem, _talent_attr_map,
)
from .models import TbOperacaoRecurso, TbPersonagem


FOCUS_TAG = "always_active{suppress{concentration_break}}"
_FOCUS_RE = re.compile(r"^always_active\{suppress\{concentration_break\}\}$")
HARD_BREAKS = frozenset({"new_concentration", "petrified", "unconscious", "death"})


def _has_focus(person, ruleset=None):
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        if any(_FOCUS_RE.fullmatch(tag) for tag in tags):
            return True
    return False


def _concentrating(person):
    return [state for state in person.estados.filter(ativo=True)
            if state.chave.startswith("spell:")
            and (state.payload_json or {}).get("concentration") is True]


def begin_concentration(person, key):
    """A successful concentrating cast replaces earlier concentration only."""
    ended = []
    for state in _concentrating(person):
        if state.chave == key:
            continue
        state.ativo = False
        state.encerrado_em = timezone.now()
        state.save(update_fields=["ativo", "encerrado_em"])
        ended.append(state.chave)
    return ended


@transaction.atomic
def resolve_concentration_event(person, *, operation_id, event, ruleset=None):
    try:
        operation_id = uuid.UUID(str(operation_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Identificação da operação inválida.") from exc
    if event not in {"damage", "petrified", "unconscious", "death"}:
        raise ValueError("Evento de concentração inválido.")
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    fingerprint = hashlib.sha256(json.dumps(
        ["concentration-event", event], separators=(",", ":")
    ).encode()).hexdigest()
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return dict(receipt.resposta, replayed=True)
    states = _concentrating(locked)
    if not states:
        raise ValueError("Nenhuma concentração ativa foi registrada.")
    focused = _has_focus(locked, ruleset=ruleset)
    ended = []
    if event in HARD_BREAKS:
        for state in states:
            state.ativo = False
            state.encerrado_em = timezone.now()
            state.save(update_fields=["ativo", "encerrado_em"])
            ended.append(state.chave)
        outcome = "ended"
    else:
        # A standard concentration save needs a declared result; never invent it.
        outcome = "retained" if focused else "save_required"
    response = {"event": event, "outcome": outcome, "ended": ended,
                "focused": focused, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
