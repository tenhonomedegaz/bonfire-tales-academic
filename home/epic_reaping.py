"""Transactional runtime for damage-die maximization declared by a tag."""

from dataclasses import asdict, dataclass
import hashlib
import json
import re
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


REAPING_TAG = (
    "trigger=damage_roll(source:attack|spell|feature), choose:damage_type, "
    "maximize:all_dice_of_chosen_type, "
    "lockout{target, reset:target_death|short_rest|long_rest}"
)
REAPING_STATE_KEY = "epic:damage_dice_maximize:target_lock"

_REAPING_RE = re.compile(
    r"^trigger\s*=\s*damage_roll\(\s*source\s*:\s*"
    r"(?P<sources>[a-z_]+(?:\|[a-z_]+)*)\s*\)\s*,\s*"
    r"choose\s*:\s*(?P<choice>[a-z_]+)\s*,\s*"
    r"maximize\s*:\s*(?P<maximize>[a-z_]+)\s*,\s*"
    r"lockout\{\s*(?P<scope>[a-z_]+)\s*,\s*reset\s*:\s*"
    r"(?P<resets>[a-z_]+(?:\|[a-z_]+)*)\s*\}$"
)


@dataclass(frozen=True)
class DamageDie:
    """One die already rolled by the caller; this module never rolls dice."""

    sides: int
    rolled: int


@dataclass(frozen=True)
class DamageComponent:
    """Dice and fixed damage sharing one damage type."""

    damage_type: str
    dice: tuple[DamageDie, ...]
    fixed: int = 0


@dataclass(frozen=True)
class ResolvedDamageComponent:
    damage_type: str
    original_rolls: tuple[int, ...]
    applied_rolls: tuple[int, ...]
    fixed: int
    total: int
    maximized: bool


@dataclass(frozen=True)
class DamageResolution:
    chosen_type: str
    components: tuple[ResolvedDamageComponent, ...]
    total: int


def _integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} deve ser um número inteiro.")
    return value


def _damage_type(value, label="tipo de dano"):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Informe um {label} válido.")
    return value.strip().casefold()


def maximize_damage_type(components, chosen_type):
    """Maximize only dice of ``chosen_type`` and preserve every fixed value.

    The caller supplies each die's sides and actual roll. No notation is parsed
    and no die is rolled here, so the function does not add damage rules.
    """
    selected = _damage_type(chosen_type, "tipo de dano escolhido")
    if isinstance(components, (str, bytes)):
        raise ValueError("Informe os componentes de dano.")
    try:
        rows = tuple(components)
    except TypeError as exc:
        raise ValueError("Informe os componentes de dano.") from exc
    if not rows:
        raise ValueError("Informe ao menos um componente de dano.")

    resolved = []
    selected_dice = 0
    for component in rows:
        if not isinstance(component, DamageComponent):
            raise ValueError("Cada componente deve ser DamageComponent.")
        damage_type = _damage_type(component.damage_type)
        fixed = _integer(component.fixed, "O dano fixo")
        if isinstance(component.dice, (str, bytes)):
            raise ValueError("Os dados devem ser uma sequência de DamageDie.")
        original = []
        applied = []
        for die in component.dice:
            if not isinstance(die, DamageDie):
                raise ValueError("Cada dado deve ser DamageDie.")
            sides = _integer(die.sides, "O número de faces")
            rolled = _integer(die.rolled, "O resultado do dado")
            if sides < 1 or rolled < 1 or rolled > sides:
                raise ValueError("Cada resultado deve estar entre 1 e o número de faces.")
            original.append(rolled)
            applied.append(sides if damage_type == selected else rolled)
        maximized = damage_type == selected and bool(applied)
        if maximized:
            selected_dice += len(applied)
        resolved.append(ResolvedDamageComponent(
            damage_type=damage_type,
            original_rolls=tuple(original),
            applied_rolls=tuple(applied),
            fixed=fixed,
            total=sum(applied) + fixed,
            maximized=maximized,
        ))
    if not selected_dice:
        raise ValueError("O tipo escolhido deve possuir ao menos um dado de dano.")
    return DamageResolution(
        chosen_type=selected,
        components=tuple(resolved),
        total=sum(row.total for row in resolved),
    )


def _definition(person, ruleset=None):
    """Find the first active source declaring this mechanism."""
    talent_attrs = _talent_attr_map(person, ruleset=ruleset)
    for _kind, display_name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, talent_attrs)):
            continue
        for tag in tags:
            match = _REAPING_RE.fullmatch(tag)
            if not match:
                continue
            if (match.group("choice") != "damage_type"
                    or match.group("maximize") != "all_dice_of_chosen_type"
                    or match.group("scope") != "target"):
                continue
            resets = frozenset(match.group("resets").split("|"))
            if resets != {"target_death", "short_rest", "long_rest"}:
                continue
            sources = frozenset(match.group("sources").split("|"))
            if not sources:
                continue
            name = str(getattr(source, "nome", "") or display_name or "").strip()
            return {
                "name": name or "Maximização de dados de dano",
                "sources": sources,
                "origin": _feature_identity(source),
            }
    return None


def _operation_id(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identificador da operação inválido.") from exc


def _creature_ref(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Informe a identificação estável da criatura.")
    return value.strip()


def _target_digest(creature_ref):
    return hashlib.sha256(creature_ref.encode("utf-8")).hexdigest()


def _json_resolution(resolution):
    return json.loads(json.dumps(asdict(resolution), ensure_ascii=False))


def _fingerprint(action, payload):
    document = ["damage-dice-maximize", action, payload]
    raw = json.dumps(document, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _receipt(locked, operation_id, fingerprint):
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt is None:
        return None
    if receipt.fingerprint != fingerprint:
        raise ValueError("Esta operação já foi usada com outros dados.")
    return dict(receipt.resposta, replayed=True)


def reaping_state(person, *, ruleset=None):
    """Project whether the declared mechanism is currently locked."""
    definition = _definition(person, ruleset=ruleset)
    if definition is None:
        return None
    lock = TbPersonagemEstado.objects.filter(
        id_personagem=person, chave=REAPING_STATE_KEY, ativo=True).first()
    return {
        "name": definition["name"],
        "available": lock is None,
        "lock_key": REAPING_STATE_KEY if lock is not None else None,
        "sources": sorted(definition["sources"]),
    }


@transaction.atomic
def use_reaping(person, *, operation_id, creature_ref, source_kind,
                components, chosen_type, ruleset=None):
    """Resolve damage and atomically acquire this mechanism's target lock."""
    operation_id = _operation_id(operation_id)
    creature_ref = _creature_ref(creature_ref)
    source_kind = str(source_kind or "").strip().casefold()
    resolution = maximize_damage_type(components, chosen_type)
    payload = {
        "creature_ref": creature_ref,
        "source_kind": source_kind,
        "resolution": _json_resolution(resolution),
    }
    fingerprint = _fingerprint("use", payload)

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay

    definition = _definition(locked, ruleset=ruleset)
    if definition is None:
        raise ValueError("O personagem não possui uma fonte ativa para este mecanismo.")
    if source_kind not in definition["sources"]:
        raise ValueError("A origem do dano não é permitida pela fonte ativa.")
    if TbPersonagemEstado.objects.filter(
            id_personagem=locked, chave=REAPING_STATE_KEY, ativo=True).exists():
        raise ValueError("O mecanismo permanece bloqueado pela criatura anterior.")

    target_digest = _target_digest(creature_ref)
    activate_state(
        locked,
        REAPING_STATE_KEY,
        origin=definition["origin"],
        payload={"target_digest": target_digest},
        ends_on=["target_death", "short_rest", "long_rest"],
    )

    response = {
        "ok": True,
        "operation_id": str(operation_id),
        "name": definition["name"],
        "target_lock": REAPING_STATE_KEY,
        "damage": _json_resolution(resolution),
        "replayed": False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked,
        operation_id=operation_id,
        fingerprint=fingerprint,
        resposta=response,
        status_http=200,
    )
    return response


@transaction.atomic
def release_reaping_on_death(person, *, operation_id, creature_ref,
                             current_hp, dead):
    """Release the matching target lock after explicit 0 HP and death facts."""
    operation_id = _operation_id(operation_id)
    creature_ref = _creature_ref(creature_ref)
    current_hp = _integer(current_hp, "Os PV atuais")
    payload = {
        "creature_ref": creature_ref,
        "current_hp": current_hp,
        "dead": dead,
    }
    fingerprint = _fingerprint("target_death", payload)

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    if current_hp != 0 or dead is not True:
        raise ValueError("A liberação exige que a criatura esteja morta com 0 PV.")

    state = (TbPersonagemEstado.objects.select_for_update()
             .filter(id_personagem=locked, chave=REAPING_STATE_KEY,
                     ativo=True).first())
    released = bool(
        state is not None
        and (state.payload_json or {}).get("target_digest")
        == _target_digest(creature_ref)
    )
    if released:
        end_state(locked, REAPING_STATE_KEY)
    response = {
        "ok": True,
        "operation_id": str(operation_id),
        "released": released,
        "replayed": False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked,
        operation_id=operation_id,
        fingerprint=fingerprint,
        resposta=response,
        status_http=200,
    )
    return response
