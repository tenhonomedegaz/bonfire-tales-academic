"""Resolve a chosen, once-per-turn attack damage bonus from active tags."""

import hashlib
import json
import re
import uuid

from django.db import transaction

from .character_engine import (
    _feature_identity, _feature_talent_attr_sig, _features_do_personagem,
    _talent_attr_map, derive,
)
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemEstado
from .resource_engine import activate_state, end_state
from .tag_engine.evaluator import evaluate_tags


_STATE_PREFIX = 'epic:bloodied_attack:'


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('Identificador da operação inválido.') from exc


def _fingerprint(action, payload):
    raw = json.dumps([action, payload], sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def _receipt(person, operation_id, fingerprint):
    row = TbOperacaoRecurso.objects.filter(
        id_personagem=person, operation_id=operation_id).first()
    if row is None:
        return None
    if row.fingerprint != fingerprint:
        raise ValueError('Esta operação já foi usada com outros dados.')
    return dict(row.resposta, replayed=True)


def _available_bonuses(person, sheet, *, ruleset=None, include_used=False):
    maximum = int(sheet['pv']['maximo_calculado'] or person.pv_maximo or 0)
    hp = int(person.pv_atual or 0)
    level = int(sheet['nivel_total'] or person.nivel or 0)
    if maximum <= 0 or hp <= 0 or hp * 2 > maximum or level <= 0:
        return []
    context = {
        'resolve_runtime': True, 'event': 'hit',
        'self_hp': hp, 'self_max_hp': maximum, 'lvl': level,
    }
    choices = _talent_attr_map(person, ruleset=ruleset)
    out = []
    for _kind, _name, source, _class_level in _features_do_personagem(
            person, ruleset=ruleset):
        tags = tuple(str(tag).strip() for tag in (source.tags_json or ()))
        if (any('talent_attr_score' in tag for tag in tags)
                and not _feature_talent_attr_sig(source, choices)):
            continue
        origin = str(_feature_identity(source))
        for tag in dict.fromkeys(tags):
            if not (re.search(r'\b1\s*/\s*turn\b', tag)
                    and re.search(r'requires\s*:\s*self\s*\{\s*sangrando\s*\}', tag)
                    and re.search(r'trigger\s*=\s*hit\b', tag)):
                continue
            amount = sum(
                int(operation.value)
                for operation in evaluate_tags([tag], context).operations
                if operation.active and operation.op == 'add_damage'
                and operation.verb == 'dmg'
                and type(operation.value) is int and operation.value > 0
            )
            if amount:
                key = _STATE_PREFIX + hashlib.sha256(
                    json.dumps([origin, tag], ensure_ascii=False).encode()
                ).hexdigest()[:32]
                if (include_used or not TbPersonagemEstado.objects.filter(
                        id_personagem=person, chave=key, ativo=True).exists()):
                    out.append((key, origin, amount))
    return out


def bloodied_attack_state(person, *, ruleset=None):
    sheet = derive(person, ruleset=ruleset)
    bonuses = _available_bonuses(person, sheet, ruleset=ruleset,
                                 include_used=True)
    if not bonuses:
        return None
    profiles = [dict(index=index, name=profile['nome'], damage_type=profile['tipo_dano'])
                for index, profile in enumerate(sheet['ataques']['perfis'])
                if profile.get('tipo_dano')]
    if not profiles:
        return None
    available = _available_bonuses(person, sheet, ruleset=ruleset)
    return {'bonus': sum(amount for _key, _origin, amount in available),
            'available': bool(available),
            'profiles': profiles}


@transaction.atomic
def use_bloodied_attack_bonus(person, *, operation_id, profile_index,
                              hit_confirmed, ruleset=None):
    operation_id = _uuid(operation_id)
    if type(profile_index) is not int or profile_index < 0 or hit_confirmed is not True:
        raise ValueError('Confirme um acerto e perfil de ataque válido.')
    fingerprint = _fingerprint('bloodied-attack', profile_index)
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    sheet = derive(locked, ruleset=ruleset)
    bonuses = _available_bonuses(locked, sheet, ruleset=ruleset)
    profiles = sheet['ataques']['perfis']
    if not bonuses or profile_index >= len(profiles):
        raise ValueError('Bônus de ataque indisponível.')
    profile = profiles[profile_index]
    damage_type = profile.get('tipo_dano')
    if not damage_type:
        raise ValueError('O ataque precisa declarar seu tipo de dano.')
    for key, origin, _amount in bonuses:
        activate_state(locked, key, origin=origin,
                       payload={'kind': 'bloodied_attack'}, ends_on=['turn_start'])
    response = {
        'operation_id': str(operation_id), 'profile': profile['nome'],
        'damage_type': damage_type,
        'bonus_damage': sum(amount for _key, _origin, amount in bonuses),
        'replayed': False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response


@transaction.atomic
def begin_bloodied_attack_turn(person, *, operation_id, turn_ref, confirmed):
    operation_id = _uuid(operation_id)
    turn_ref = str(turn_ref or '').strip()
    if (not turn_ref or len(turn_ref) > 180 or
            any(ord(char) < 32 for char in turn_ref) or confirmed is not True):
        raise ValueError('Confirme a referência do novo turno.')
    fingerprint = _fingerprint('bloodied-turn', turn_ref)
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    replay = _receipt(locked, operation_id, fingerprint)
    if replay is not None:
        return replay
    if TbOperacaoRecurso.objects.filter(
            id_personagem=locked, resposta__bloodied_turn_ref=turn_ref).exists():
        raise ValueError('Este início de turno já foi registrado.')
    states = list(TbPersonagemEstado.objects.select_for_update().filter(
        id_personagem=locked, chave__startswith=_STATE_PREFIX, ativo=True))
    for state in states:
        end_state(locked, state.chave)
    response = {'operation_id': str(operation_id),
                'bloodied_turn_ref': turn_ref,
                'released': len(states), 'replayed': False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
