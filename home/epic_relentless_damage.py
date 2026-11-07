"""Resolve a declared weapon hit using the attack profile's active tags."""

import hashlib
import json
import uuid

from django.db import transaction

from .character_engine import derive
from .models import TbOperacaoRecurso, TbPersonagem


def relentless_profiles(person, *, ruleset=None):
    profiles = derive(person, ruleset=ruleset)['ataques']['perfis']
    return [dict(index=index, name=profile['nome'], damage_type=profile['tipo_dano'])
            for index, profile in enumerate(profiles)
            if profile.get('tipo_dano') and (
                profile.get('ignora_resistencia') or profile.get('dano_critico_extra'))]


@transaction.atomic
def resolve_weapon_hit(person, *, operation_id, profile_index, rolled_damage,
                       critical, target_defense, confirmed, ruleset=None):
    """Record damage for a table-confirmed hit; target defenses come from the table."""
    try:
        operation_id = uuid.UUID(str(operation_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Identificador de operação inválido.') from exc
    if type(profile_index) is not int or profile_index < 0:
        raise ValueError('Perfil de ataque inválido.')
    if type(rolled_damage) is not int or not 0 <= rolled_damage <= 100000:
        raise ValueError('Dano rolado inválido.')
    if type(critical) is not bool or confirmed is not True:
        raise ValueError('Confirme o acerto e o crítico na mesa.')
    if target_defense not in ('none', 'resist', 'immune'):
        raise ValueError('Defesa do alvo inválida.')

    payload = [profile_index, rolled_damage, critical, target_defense]
    fingerprint = hashlib.sha256(json.dumps(
        ['weapon-hit', payload], separators=(',', ':')).encode()).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Esta operação já foi usada com outros dados.')
        return dict(receipt.resposta, replayed=True)

    profiles = derive(locked, ruleset=ruleset)['ataques']['perfis']
    if profile_index >= len(profiles):
        raise ValueError('Perfil de ataque inválido.')
    profile = profiles[profile_index]
    damage_type = profile.get('tipo_dano')
    ignores_resistance = bool(profile.get('ignora_resistencia'))
    declared_bonus = profile.get('dano_critico_extra', 0)
    if (not damage_type or not (ignores_resistance or declared_bonus)
            or type(declared_bonus) is not int or declared_bonus < 0):
        raise ValueError('Fonte de dano épico indisponível.')
    critical_bonus = declared_bonus if critical else 0
    before_defense = rolled_damage + critical_bonus
    if target_defense == 'immune':
        final_damage = 0
    elif target_defense == 'resist' and not ignores_resistance:
        final_damage = before_defense // 2
    else:
        final_damage = before_defense
    response = {
        'operation_id': str(operation_id), 'profile': profile['nome'],
        'damage_type': damage_type, 'rolled_damage': rolled_damage,
        'critical_bonus': critical_bonus, 'ignored_resistance': (
            target_defense == 'resist' and ignores_resistance),
        'final_damage': final_damage, 'target_defense': target_defense,
        'replayed': False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
