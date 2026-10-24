"""Resolve a tagged minimum for damage dice of an owned spell."""

import hashlib
import json
import re
import uuid

from django.db import transaction

from .character_engine import (
    _feature_talent_attr_sig, _features_do_personagem, _talent_attr_map,
)
from .magic_workshop import _spell_damage_types
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemMagia


SPELL_DIE_FLOOR_TAG = (
    "trigger=cast_spell(circle:1+), damage_die_floor:3(roll:1|2)"
)
_TAG_RE = re.compile(
    r"^trigger=cast_spell\(circle:1\+\), "
    r"damage_die_floor:3\(roll:1\|2\)$"
)


def _active(person, ruleset=None):
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or []))
        if (any("talent_attr_score" in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        if any(_TAG_RE.fullmatch(tag) for tag in tags):
            return True
    return False


def damage_spell_options(person, ruleset=None):
    if not _active(person, ruleset=ruleset):
        return []
    options = []
    for owned in TbPersonagemMagia.objects.filter(
            id_personagem=person).select_related("id_magia"):
        spell = owned.id_magia
        if (spell is None or spell.nivel < 1
                or not (owned.preparada or owned.sempre_preparada)):
            continue
        damage_types = _spell_damage_types(spell)
        if damage_types:
            options.append({"id": owned.pk, "name": spell.nome,
                            "circle": spell.nivel, "damage_types": damage_types})
    return sorted(options, key=lambda row: (row["name"], row["id"]))


def _dice(value):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 100:
        raise ValueError("Declare entre 1 e 100 dados de dano.")
    out = []
    for row in value:
        if (not isinstance(row, (list, tuple)) or len(row) != 2
                or type(row[0]) is not int or type(row[1]) is not int
                or not 3 <= row[0] <= 100 or not 1 <= row[1] <= row[0]):
            raise ValueError("Declare faces e resultado válidos para cada dado.")
        out.append((row[0], row[1]))
    return out


@transaction.atomic
def resolve_spell_damage(person, *, operation_id, owned_spell_id,
                         damage_type, dice, fixed=0, ruleset=None):
    try:
        operation_id = uuid.UUID(str(operation_id))
        owned_spell_id = int(owned_spell_id)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Identificação da operação ou magia inválida.") from exc
    if type(fixed) is not int or not -10000 <= fixed <= 10000:
        raise ValueError("Dano fixo inválido.")
    damage_type = str(damage_type or "").strip().casefold()
    declared = _dice(dice)
    payload = ["spell-die-floor", owned_spell_id, damage_type, declared, fixed]
    fingerprint = hashlib.sha256(json.dumps(
        payload, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt is not None:
        if receipt.fingerprint != fingerprint:
            raise ValueError("Esta operação já foi usada com outros dados.")
        return dict(receipt.resposta, replayed=True)
    if not _active(locked, ruleset=ruleset):
        raise ValueError("Fonte de dano mágico refinado indisponível.")
    owned = TbPersonagemMagia.objects.select_related("id_magia").filter(
        pk=owned_spell_id, id_personagem=locked).first()
    spell = owned.id_magia if owned else None
    if (spell is None or spell.nivel < 1
            or not (owned.preparada or owned.sempre_preparada)
            or damage_type not in _spell_damage_types(spell)):
        raise ValueError("Magia danosa preparada e tipo de dano são obrigatórios.")
    applied = [max(3, rolled) for _sides, rolled in declared]
    total = sum(applied) + fixed
    if total < 0:
        raise ValueError("O dano total não pode ser negativo.")
    response = {"ok": True, "operation_id": str(operation_id),
                "spell_id": owned.pk, "damage_type": damage_type,
                "original_dice": [rolled for _sides, rolled in declared],
                "applied_dice": applied, "fixed": fixed,
                "total": total, "replayed": False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response


def parse_damage_dice(text):
    """Read the sheet's comma-separated ``faces:roll`` declaration."""
    if not isinstance(text, str) or len(text) > 1000:
        raise ValueError("Dados de dano inválidos.")
    rows = []
    for token in text.split(","):
        parts = token.strip().split(":")
        if len(parts) != 2 or not all(part.strip().isdigit() for part in parts):
            raise ValueError("Use faces:resultado para cada dado.")
        rows.append((int(parts[0]), int(parts[1])))
    return _dice(rows)
