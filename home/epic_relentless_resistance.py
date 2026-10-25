"""Runtime for the choices and reaction declared by Relentless Resistance tags."""

import hashlib
import json
import re
import secrets
import uuid
from decimal import Decimal, InvalidOperation
from contextvars import ContextVar

from django.db import transaction

from .character_engine import (
    _feature_identity, _feature_talent_attr_sig, _features_do_personagem,
    _spell_mod, _talent_attr_map, bonus_proficiencia, derive,
)
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemEstado
from .resource_engine import activate_state, end_state
from .tag_engine.runtime_values import dice_spec, roll_dice


DAMAGE_TYPES = (
    "acido", "frio", "energia", "fogo", "raio", "necrotico", "veneno",
    "psiquico", "radiante", "trovejante",
)
RESISTANCE_TAG = (
    "pick:damage_resistance:2(from:acido|frio|energia|fogo|raio|necrotico|"
    "veneno|psiquico|radiante|trovejante, upgrade:resist_to_immune, swap:long_rest)"
)
ALTER_RUIN_TAG = (
    "trigger=take_damage(type:chosen_resistance), target{range:60ft, visible, "
    "unless:total_cover}, save:dex(dc:8+pb+declared(spell_mod|con_mod)), "
    "dmg:3d12+declared(spell_mod|con_mod), uses{1, reset:round, reaction:free}"
)
CHOICE_STATE_KEY = "epic:relentless_resistance:choices"
ROUND_LOCK_KEY = "epic:relentless_resistance:alter_ruin:round"

_CHOICE_RE = re.compile(
    r"^pick:damage_resistance:(?P<count>\d+)\(from:(?P<types>[a-z_]+(?:\|[a-z_]+)*), "
    r"upgrade:resist_to_immune, swap:long_rest\)$"
)
_RUIN_RE = re.compile(
    r"^trigger=take_damage\(type:chosen_resistance\), target\{range:(?P<range>\d+)ft, "
    r"visible, unless:total_cover\}, save:dex\(dc:8\+pb\+declared\(spell_mod\|con_mod\)\), "
    r"dmg:(?P<dice>\d+d\d+)\+declared\(spell_mod\|con_mod\), "
    r"uses\{1, reset:round, reaction:free\}$"
)
_PROJECTING = ContextVar("epic_relentless_resistance_projecting", default=False)


def _operation_id(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Identificador da operação inválido.") from exc


def _ref(value, label):
    value = str(value or "").strip()
    if not value or len(value) > 180 or any(ord(char) < 32 for char in value):
        raise ValueError(f"Informe uma referência estável de {label}.")
    return value


def _distance(value):
    try:
        value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Informe uma distância válida em pés.") from exc
    if not value.is_finite() or value < 0:
        raise ValueError("A distância deve ser um número não negativo em pés.")
    return value


def _receipt(person, operation_id, action, payload):
    fingerprint = hashlib.sha256(json.dumps(
        ["epic_relentless_resistance", action, payload], ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=person, operation_id=operation_id).first()
    if receipt is not None:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return fingerprint, dict(receipt.resposta, replayed=True)
    return fingerprint, None


def _definition(person, ruleset=None):
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or ()))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        choice_match = next((_CHOICE_RE.fullmatch(tag) for tag in tags
                             if _CHOICE_RE.fullmatch(tag)), None)
        ruin_match = next((_RUIN_RE.fullmatch(tag) for tag in tags
                           if _RUIN_RE.fullmatch(tag)), None)
        if choice_match is not None and ruin_match is not None:
            try:
                dice_spec(ruin_match.group("dice"))
            except ValueError:
                continue
            types = tuple(choice_match.group("types").split("|"))
            count = int(choice_match.group("count"))
            if (len(types) != len(set(types)) or not set(types) <= set(DAMAGE_TYPES)
                    or not 1 <= count <= len(types)):
                continue
            return {
                "origin": _feature_identity(source),
                "types": types,
                "count": count,
                "range_ft": int(ruin_match.group("range")),
                "dice": ruin_match.group("dice"),
            }
    return None


def _other_defenses(person, origin, ruleset=None):
    """Only inspect other active tag sources; this service never overwrites them."""
    defenses = {damage_type: "none" for damage_type in DAMAGE_TYPES}
    # The declaration tags above do not produce a native ``resist:`` operation,
    # so derive() here contains only the defenses supplied by the other sources.
    # This also covers the engine's conditional and nested tags, rather than only
    # the simple spelling of a resistance in tags_json.
    token = _PROJECTING.set(True)
    try:
        derived = derive(person, ruleset=ruleset)
    finally:
        _PROJECTING.reset(token)
    for damage_type in DAMAGE_TYPES:
        if damage_type in (derived.get("imunidades") or ()):
            defenses[damage_type] = "immune"
        elif damage_type in (derived.get("resistencias") or ()):
            defenses[damage_type] = "resist"
    return defenses


def _choice_state(person, definition):
    state = TbPersonagemEstado.objects.filter(
        id_personagem=person, chave=CHOICE_STATE_KEY, ativo=True).first()
    if state is None or state.origem != definition["origin"]:
        return None
    selected = tuple((state.payload_json or {}).get("types") or ())
    if (len(selected) != definition["count"] or len(set(selected)) != definition["count"]
            or not set(selected) <= set(definition["types"])):
        return None
    return state, selected


def resistance_state(person, *, ruleset=None):
    """Project the two selected defenses while retaining defenses from other sources."""
    definition = _definition(person, ruleset=ruleset)
    if definition is None:
        return None
    selected_state = _choice_state(person, definition)
    if selected_state is None:
        return {"available_types": list(definition["types"]), "types": [], "defenses": [],
                "configured": False, "state_key": CHOICE_STATE_KEY,
                "range_ft": definition["range_ft"], "dice": definition["dice"],
                "choice_slots": list(range(1, definition["count"] + 1))}
    _state, selected = selected_state
    other = _other_defenses(person, definition["origin"], ruleset=ruleset)
    defenses = []
    for damage_type in selected:
        prior = other[damage_type]
        level = "immune" if prior in ("resist", "immune") else "resist"
        defenses.append({"damage_type": damage_type, "defense": level,
                         "upgraded": level == "immune", "other_defense": prior})
    return {"available_types": list(definition["types"]), "types": list(selected),
            "defenses": defenses, "configured": True, "state_key": CHOICE_STATE_KEY,
            "range_ft": definition["range_ft"], "dice": definition["dice"],
            "choice_slots": list(range(1, definition["count"] + 1))}


def apply_resistance_state(state, person, *, ruleset=None):
    """Project chosen defenses into the shared sheet/VTT-derived state."""
    # ``resistance_state`` derives external defenses.  During that derivation the
    # character engine returns here, so suppress only the recursive projection.
    if _PROJECTING.get():
        return state
    token = _PROJECTING.set(True)
    try:
        configured = resistance_state(person, ruleset=ruleset)
    finally:
        _PROJECTING.reset(token)
    if not configured or not configured["configured"]:
        return state
    resistances = list(state.get("resistencias") or [])
    immunities = list(state.get("imunidades") or [])
    for defense in configured["defenses"]:
        damage_type = defense["damage_type"]
        if defense["defense"] == "immune":
            if damage_type in resistances:
                resistances.remove(damage_type)
            if damage_type not in immunities:
                immunities.append(damage_type)
        elif damage_type not in immunities and damage_type not in resistances:
            resistances.append(damage_type)
    state["resistencias"] = resistances
    state["imunidades"] = immunities
    return state


@transaction.atomic
def choose_resistances(person, *, operation_id, damage_types, long_rest_ref=None,
                       long_rest_confirmed=False, ruleset=None):
    """Set the initial two choices, or replace them after a confirmed long rest."""
    operation_id = _operation_id(operation_id)
    if not isinstance(damage_types, (list, tuple)):
        raise ValueError("Informe os tipos de dano escolhidos.")
    selected = tuple(str(value or "").strip().casefold() for value in damage_types)
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("Escolha tipos de dano distintos.")
    long_rest_ref = (None if long_rest_ref is None else _ref(long_rest_ref, "descanso longo"))
    payload = {"types": selected, "long_rest_ref": long_rest_ref,
               "long_rest_confirmed": long_rest_confirmed}
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    fingerprint, replay = _receipt(locked, operation_id, "choose", payload)
    if replay is not None:
        return replay
    definition = _definition(locked, ruleset=ruleset)
    if (definition is None or len(selected) != definition["count"]
            or not set(selected) <= set(definition["types"])):
        raise ValueError("A fonte ativa não permite esses tipos de dano.")
    current = _choice_state(locked, definition)
    changing = current is not None and current[1] != selected
    if changing and (long_rest_ref is None or long_rest_confirmed is not True):
        raise ValueError("A troca das resistências exige um descanso longo confirmado.")
    if current is not None and current[1] == selected and long_rest_ref is not None:
        if long_rest_confirmed is not True:
            raise ValueError("Confirme o descanso longo declarado na mesa.")
    activate_state(locked, CHOICE_STATE_KEY, origin=definition["origin"],
                   payload={"types": list(selected), "long_rest_ref": long_rest_ref},
                   ends_on=[])
    response = dict(resistance_state(locked, ruleset=ruleset), operation_id=str(operation_id),
                    changed=changing, replayed=False)
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    return response


def _declared_modifier(person, kind, ruleset=None):
    kind = str(kind or "").strip().casefold()
    if kind not in ("spell", "constitution"):
        raise ValueError("Declare modificador de conjuração ou Constituição.")
    derived = derive(person, ruleset=ruleset)
    if kind == "spell":
        classes = list(person.classes.all().order_by("-principal", "id"))
        if ruleset is not None:
            from .versioned_classes import resolved_classes
            classes = resolved_classes(ruleset, classes)
        return kind, int(_spell_mod(classes, derived["atributos"], ruleset=ruleset))
    return kind, int((derived.get("atributos") or {}).get("CON", {}).get("mod", 0))


@transaction.atomic
def alter_ruin(person, *, operation_id, round_ref, damage_type, damage_received,
               target_distance_ft, target_visible, target_has_total_cover,
               target_save_modifier, declared_modifier, ruleset=None):
    """Resolve Alter Ruin from the declared tag, without consuming a reaction."""
    operation_id = _operation_id(operation_id)
    round_ref = _ref(round_ref, "rodada")
    damage_type = str(damage_type or "").strip().casefold()
    distance = _distance(target_distance_ft)
    if type(target_save_modifier) is not int:
        raise ValueError("Modificador de salvaguarda do alvo inválido.")
    if any(value is not True and value is not False for value in (
            damage_received, target_visible, target_has_total_cover)):
        raise ValueError("Confirme as condições declaradas na mesa.")
    payload = {"round_ref": round_ref, "damage_type": damage_type,
               "damage_received": damage_received, "target_distance_ft": format(distance, "f"),
               "target_visible": target_visible, "target_has_total_cover": target_has_total_cover,
               "target_save_modifier": target_save_modifier,
               "declared_modifier": declared_modifier}
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    fingerprint, replay = _receipt(locked, operation_id, "alter_ruin", payload)
    if replay is not None:
        return replay
    definition = _definition(locked, ruleset=ruleset)
    selected_state = _choice_state(locked, definition) if definition else None
    if selected_state is None:
        raise ValueError("Escolha as resistências antes de usar Alterar Ruína.")
    if damage_received is not True or damage_type not in selected_state[1]:
        raise ValueError("Alterar Ruína exige dano de um tipo escolhido.")
    if distance > definition["range_ft"] or target_visible is not True or target_has_total_cover is not False:
        raise ValueError("O alvo não atende alcance, visão ou cobertura declarados.")
    if TbPersonagemEstado.objects.filter(
            id_personagem=locked, chave=ROUND_LOCK_KEY, ativo=True).exists():
        raise ValueError("Alterar Ruína já foi usado nesta rodada.")
    modifier_kind, modifier = _declared_modifier(locked, declared_modifier, ruleset=ruleset)
    level = sum(int(row.nivel or 0) for row in locked.classes.all()) or int(locked.nivel or 1)
    save_dc = 8 + bonus_proficiencia(level) + modifier
    save_die = secrets.randbelow(20) + 1
    save_total = save_die + target_save_modifier
    succeeded = save_total >= save_dc
    dice = roll_dice(definition["dice"], secrets.randbelow) if not succeeded else []
    damage = sum(dice) + modifier if dice else 0
    activate_state(locked, ROUND_LOCK_KEY, origin=definition["origin"],
                   payload={"round_ref": round_ref}, ends_on=["round"])
    response = {"ok": True, "operation_id": str(operation_id), "round_ref": round_ref,
                "damage_type": damage_type, "range_ft": definition["range_ft"],
                "declared_modifier": modifier_kind, "modifier": modifier, "save_dc": save_dc,
                "save_die": save_die, "save_total": save_total, "succeeded": succeeded,
                "dice": dice, "damage": damage, "reaction_spent": False, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    return response


@transaction.atomic
def reset_alter_ruin_on_round(person, *, operation_id, round_ref, confirmed):
    """Release the once-per-round lock after the table confirms a new round."""
    operation_id = _operation_id(operation_id)
    round_ref = _ref(round_ref, "rodada")
    payload = {"round_ref": round_ref, "confirmed": confirmed}
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    fingerprint, replay = _receipt(locked, operation_id, "round", payload)
    if replay is not None:
        return replay
    if confirmed is not True:
        raise ValueError("Confirme a nova rodada declarada na mesa.")
    released = bool(end_state(locked, ROUND_LOCK_KEY))
    response = {"ok": True, "operation_id": str(operation_id), "round_ref": round_ref,
                "released": released, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id, fingerprint=fingerprint,
        resposta=response, status_http=200)
    return response
