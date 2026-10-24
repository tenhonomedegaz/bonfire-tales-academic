"""Spend class Hit Dice through the existing resource ledger and healing tags."""

import hashlib
import json
import secrets
import uuid

from django.db import transaction

from .character_engine import (
    _dado_de_vida_classe, _feature_talent_attr_sig,
    _features_do_personagem, _talent_attr_map, derive,
)
from .epic_healing_bonus import healing_bonus, mark_healing_bonuses
from .models import TbOperacaoRecurso, TbPersonagem
from .resource_engine import spend_resource
from .tag_engine.evaluator import evaluate_tags


HIT_DICE_MAX_TAG = 'always_active{modify:hit_die=maximum}'


def _maximum_available(person, *, ruleset=None):
    choices = _talent_attr_map(person, ruleset=ruleset)
    for _kind, _name, source, _level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or ()))
        if (any('talent_attr_score' in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        for operation in evaluate_tags(tags, {}).operations:
            if (operation.active and operation.verb == 'modify'
                    and operation.value == 'hit_die=maximum'):
                return True
    return False


def _contracts(person, *, ruleset=None):
    classes = list(person.classes.select_related('id_classe').all())
    if ruleset is not None:
        from .versioned_classes import resolved_classes
        classes = resolved_classes(ruleset, classes)
    totals = {}
    for row in classes:
        die = _dado_de_vida_classe(row.id_classe)
        if die is not None and int(row.nivel or 0) > 0:
            totals[die] = totals.get(die, 0) + int(row.nivel)
    return {die: {
        'key': f'hit_dice:d{die}', 'name': f'Dados de Vida (d{die})',
        'maximum': count, 'reset': 'long_rest', 'origin': 'classes:hit_dice',
    } for die, count in totals.items()}


def hit_dice_state(person, *, ruleset=None):
    """Expose the existing class dice counts only when the max-roll tag is active."""
    if not _maximum_available(person, ruleset=ruleset):
        return None
    contracts = _contracts(person, ruleset=ruleset)
    resources = {row.chave: row for row in person.recursos.filter(
        chave__startswith='hit_dice:')}
    dice = []
    for die, contract in sorted(contracts.items()):
        row = resources.get(contract['key'])
        maximum = contract['maximum']
        spent = max(0, int(row.maximo) - int(row.atual)) if row else 0
        dice.append({'die': die, 'maximum': maximum,
                     'available': max(0, maximum - spent)})
    return dice


@transaction.atomic
def spend_hit_dice(person, *, operation_id, die, count, maximize, confirmed,
                   ruleset=None):
    """Spend dice once and heal with server rolls or the tagged maximum."""
    try:
        operation_id = uuid.UUID(str(operation_id))
        die, count = int(die), int(count)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('Dados de Vida inválidos.') from exc
    if (type(maximize) is not bool or type(confirmed) is not bool
            or not confirmed or count < 1):
        raise ValueError('Confirme o gasto de Dados de Vida.')
    payload = ['hit-dice', die, count, maximize, confirmed]
    fingerprint = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Esta operação já foi usada com outros dados.')
        return dict(receipt.resposta, replayed=True)
    if not _maximum_available(locked, ruleset=ruleset):
        raise ValueError('A recuperação máxima por Dados de Vida está indisponível.')
    contract = _contracts(locked, ruleset=ruleset).get(die)
    if contract is None or count > contract['maximum']:
        raise ValueError('A classe não possui esses Dados de Vida.')
    sheet = derive(locked, ruleset=ruleset)
    maximum_hp = max(0, int(locked.pv_maximo or 0),
                     int(sheet['pv']['maximo_calculado'] or 0))
    before = max(0, int(locked.pv_atual or 0))
    if before >= maximum_hp:
        raise ValueError('Os PV atuais já estão no máximo.')
    spent, resource = spend_resource(locked, contract, count)
    if not spent:
        raise ValueError('Dados de Vida insuficientes.')
    con_mod = int(sheet['atributos']['CON']['mod'])
    dice_values = ([die] * count if maximize else
                   [secrets.randbelow(die) + 1 for _ in range(count)])
    base_healing = max(0, sum(dice_values) + count * con_mod)
    bonus, pending = healing_bonus(
        locked, hp=before, maximum_hp=maximum_hp, ruleset=ruleset)
    after = max(before, min(maximum_hp, before + base_healing + bonus))
    locked.pv_atual = after
    locked.save(update_fields=['pv_atual'])
    if after > before:
        mark_healing_bonuses(locked, pending)
    result = {'operation_id': str(operation_id), 'die': die, 'count': count,
              'dice_values': dice_values, 'base_healing': base_healing,
              'healed': after - before, 'hp_after': after,
              'remaining': resource['current'], 'replayed': False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=result, status_http=200)
    return result
