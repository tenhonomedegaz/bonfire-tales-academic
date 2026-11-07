"""Translate readable damage rows from the sheet into declared dice outcomes."""

import re

from .epic_reaping import DamageComponent, DamageDie


_DICE = re.compile(r"([1-9]\d?)d([1-9]\d{0,2})", re.I)


def parse_reaping_form(post):
    """Read one rolled damage event; never roll or guess missing dice."""
    types = post.getlist("damage_type")
    expressions = post.getlist("dice_expression")
    rolls = post.getlist("rolled_values")
    fixed_values = post.getlist("fixed_damage")
    if not types or len(types) > 10 or not (
            len(types) == len(expressions) == len(rolls) == len(fixed_values)):
        raise ValueError("Informe até dez parcelas de dano completas.")
    components = []
    for damage_type, expression, results, fixed in zip(
            types, expressions, rolls, fixed_values):
        damage_type = damage_type.strip()
        expression = expression.strip()
        results = results.strip()
        if not damage_type and not expression and not results and not fixed.strip():
            continue
        if not damage_type or len(damage_type) > 50:
            raise ValueError("Informe o tipo de cada parcela de dano.")
        if expression:
            match = _DICE.fullmatch(expression)
            if match is None:
                raise ValueError("Use uma expressão de dados como 3d8.")
            count, sides = (int(part) for part in match.groups())
            values = [part.strip() for part in results.split(",")]
            if len(values) != count or any(not value.isdecimal() for value in values):
                raise ValueError("Informe o resultado de cada dado na ordem da rolagem.")
            dice = tuple(DamageDie(sides=sides, rolled=int(value)) for value in values)
        else:
            if results:
                raise ValueError("Resultados exigem uma expressão de dados.")
            dice = ()
        try:
            fixed_damage = int(fixed or 0)
        except ValueError as exc:
            raise ValueError("O dano fixo deve ser inteiro.") from exc
        if abs(fixed_damage) > 1000:
            raise ValueError("O dano fixo informado é inválido.")
        components.append(DamageComponent(
            damage_type=damage_type, dice=dice, fixed=fixed_damage))
    if not components:
        raise ValueError("Informe ao menos uma parcela de dano.")
    return {
        "creature_ref": post.get("creature_ref"),
        "source_kind": post.get("source_kind"),
        "chosen_type": post.get("chosen_type"),
        "components": tuple(components),
    }
