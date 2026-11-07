"""Persist a death restriction declared by an active character source.

The table confirms a creature's death. This module records the resulting rule
without equating zero hit points with death or identifying a talent by name.
"""

import hashlib
import json
import re
import uuid

from django.db import transaction

from .character_engine import (
    _feature_talent_attr_sig, _features_do_personagem, _talent_attr_map,
)
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemEstado


DEATH_SEAL_TAG = (
    "trigger=death_by_damage(source:self), "
    "restricts{resurrection, undead_transformation, "
    "except:desejo|ressurreicao_verdadeira}"
)
_SEAL_RE = re.compile(
    r"^trigger\s*=\s*death_by_damage\(source:self\)\s*,\s*"
    r"restricts\{resurrection\s*,\s*undead_transformation\s*,\s*"
    r"except:(?P<exceptions>[a-z_]+(?:\|[a-z_]+)*)\}$"
)


def _exceptions(person, ruleset=None):
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        for tag in tags:
            matched = _SEAL_RE.fullmatch(tag)
            if matched:
                return matched.group("exceptions").split("|")
    return None


def _target(value):
    value = str(value or "").strip()
    if not value or len(value) > 100 or any(ord(char) < 32 for char in value):
        raise ValueError("Identifique a criatura que morreu.")
    return value


def _state_key(target):
    digest = hashlib.sha256(target.encode("utf-8")).hexdigest()[:32]
    return f"epic:death_seal:{digest}"


def death_seal_state(person, *, ruleset=None):
    """Present the declaration action and recorded targets to the sheet owner."""
    exceptions = _exceptions(person, ruleset=ruleset)
    targets = [state.payload_json.get("target") for state in
               TbPersonagemEstado.objects.filter(
                   id_personagem=person, chave__startswith="epic:death_seal:",
                   ativo=True).order_by("id")]
    targets = [target for target in targets if target]
    if exceptions is None and not targets:
        return None
    return {"active": exceptions is not None, "targets": targets,
            "exceptions": exceptions or []}


@transaction.atomic
def record_death_seal(person, *, target, operation_id, caused_by_own_damage,
                      death_confirmed, ruleset=None):
    """Record a confirmed death once; a repeat with the same input is harmless."""
    try:
        operation_id = uuid.UUID(str(operation_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Operação inválida.") from exc
    target = _target(target)
    fingerprint = hashlib.sha256(json.dumps(
        ["death-seal", target, caused_by_own_damage, death_confirmed],
        ensure_ascii=False).encode("utf-8")).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt is not None:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return dict(receipt.resposta, replayed=True)
    exceptions = _exceptions(locked, ruleset=ruleset)
    if exceptions is None:
        raise ValueError("Nenhuma fonte ativa sela a morte.")
    if caused_by_own_damage is not True or death_confirmed is not True:
        raise ValueError("Confirme a morte causada por seu dano.")
    key = _state_key(target)
    state, _ = TbPersonagemEstado.objects.update_or_create(
        id_personagem=locked, chave=key,
        defaults={"origem": "tag:death_by_damage", "ativo": True,
                  "payload_json": {"target": target, "exceptions": exceptions,
                                   "block_undead": True}, "ends_on_json": [],
                  "encerrado_em": None},
    )
    response = {"ok": True, "target": target, "state_key": state.chave,
                "exceptions": exceptions, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response


def restoration_allowed(person, target, *, method):
    """Check a recorded seal when a resurrection/undead consumer asks."""
    target = _target(target)
    state = TbPersonagemEstado.objects.filter(
        id_personagem=person, chave=_state_key(target), ativo=True).first()
    if state is None:
        return True
    if method == "undead_transformation":
        return not bool(state.payload_json.get("block_undead"))
    return method in state.payload_json.get("exceptions", ())
