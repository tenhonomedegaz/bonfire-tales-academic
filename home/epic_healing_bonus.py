"""Apply healing tag operations with a persistent once-per-turn lock."""

import hashlib
import json
import uuid

from django.db import transaction

from .character_engine import (
    _feature_identity, _feature_talent_attr_sig, _features_do_personagem,
    _talent_attr_map, derive,
)
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemEstado
from .resource_engine import activate_state, end_state
from .tag_engine.evaluator import evaluate_tags


HEALING_TURN_PREFIX = "epic:healing_turn:"


def _turn_key(origin, tag):
    digest = hashlib.sha256(json.dumps(
        [str(origin), tag], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()[:32]
    return HEALING_TURN_PREFIX + digest


def healing_bonus(person, *, hp, maximum_hp, ruleset=None):
    """Return available bonus and state locks to activate on actual healing."""
    sheet = derive(person, ruleset=ruleset)
    context = {
        "resolve_runtime": True, "event": "healing", "self_hp": hp,
        "self_max_hp": maximum_hp,
        **{f"{prefix}_mod": sheet["atributos"][attribute]["mod"]
           for prefix, attribute in (("str", "FOR"), ("dex", "DES"),
                                     ("con", "CON"), ("int", "INT"),
                                     ("wis", "SAB"), ("cha", "CAR"))},
    }
    choices = _talent_attr_map(person, ruleset=ruleset)
    total = 0
    pending = []
    for _kind, _name, source, _level in _features_do_personagem(person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or ()))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        origin = _feature_identity(source)
        for tag in tags:
            if "trigger=healing" not in tag:
                continue
            turn_limited = "1/turn" in tag
            key = _turn_key(origin, tag) if turn_limited else None
            if key and TbPersonagemEstado.objects.filter(
                    id_personagem=person, chave=key, ativo=True).exists():
                continue
            amount = sum(
                max(0, int(operation.value))
                for operation in evaluate_tags([tag], context).operations
                if (operation.active and operation.op == "heal"
                    and operation.target == "pv"
                    and isinstance(operation.value, (int, float))
                    and not isinstance(operation.value, bool))
            )
            if amount:
                total += amount
                if key:
                    pending.append((key, str(origin)))
    return total, pending


def mark_healing_bonuses(person, pending):
    """Commit limited benefits only after healing changed the character's PV."""
    for key, origin in pending:
        activate_state(person, key, origin=origin,
                       payload={"kind": "healing"}, ends_on=["turn_start"])


def healing_turn_state(person):
    return TbPersonagemEstado.objects.filter(
        id_personagem=person, chave__startswith=HEALING_TURN_PREFIX,
        ativo=True).exists()


@transaction.atomic
def begin_healing_turn(person, *, operation_id, turn_ref, confirmed):
    """Release limited healing bonuses at a declared turn start."""
    try:
        operation_id = uuid.UUID(str(operation_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Identificador inválido.") from exc
    turn_ref = str(turn_ref or "").strip()
    if not turn_ref or len(turn_ref) > 180 or any(ord(char) < 32 for char in turn_ref):
        raise ValueError("Informe a referência do turno iniciado.")
    if confirmed is not True:
        raise ValueError("Confirme o início do turno na mesa.")
    fingerprint = hashlib.sha256(json.dumps(
        ["healing-turn", turn_ref, confirmed], separators=(",", ":")
    ).encode()).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt is not None:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return dict(receipt.resposta, replayed=True)
    if TbOperacaoRecurso.objects.filter(
            id_personagem=locked,
            resposta__healing_turn_ref=turn_ref).exists():
        raise ValueError("Este início de turno já foi registrado.")
    active = TbPersonagemEstado.objects.filter(
        id_personagem=locked, chave__startswith=HEALING_TURN_PREFIX,
        ativo=True)
    released = [state.chave for state in active]
    for key in released:
        end_state(locked, key)
    result = {"operation_id": str(operation_id), "healing_turn_ref": turn_ref,
              "released": len(released), "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=result, status_http=200)
    return result
